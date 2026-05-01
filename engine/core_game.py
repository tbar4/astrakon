# engine/core_game.py
from __future__ import annotations
import copy
import json
from engine.state import (
    Phase, FactionState, FactionAssets, CombatEvent,
    InvestmentAllocation, OperationalAction, ResponseDecision,
)
from engine.action_space import ActionSpace
from engine.simulation import (
    InvestmentResolver, SDAFilter, ConflictResolver, SimulationEngine,
    DebrisEngine, ManeuverBudgetEngine,
)
from scenarios.loader import Scenario


class CoreGame:
    """Synchronous, deep-copyable game state for IS-MCTS and AlphaZero training."""

    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self._action_space = ActionSpace(scenario)
        self._sim = SimulationEngine()
        self._debris_engine = DebrisEngine()
        self._maneuver_engine = ManeuverBudgetEngine()

        self.faction_order: list[str] = [f.faction_id for f in scenario.factions]

        # Build faction states from scenario starting assets
        self.faction_states: dict[str, FactionState] = {}
        for f in scenario.factions:
            self.faction_states[f.faction_id] = FactionState(
                faction_id=f.faction_id,
                name=f.name,
                budget_per_turn=f.budget_per_turn,
                current_budget=f.budget_per_turn,
                assets=f.starting_assets.model_copy(deep=True),
                coalition_id=f.coalition_id,
                coalition_loyalty=f.coalition_loyalty,
                archetype=f.archetype,
            )

        # Coalition structure: dict[coalition_id, list[member faction_ids]]
        self._coalitions: dict[str, list[str]] = {
            cid: coalition.member_ids
            for cid, coalition in scenario.coalitions.items()
        }

        self._victory_threshold: float = scenario.victory.coalition_orbital_dominance

        self.coalition_dominance: dict[str, float] = {}
        self._recompute_dominance()

        self.escalation_rung: int = 0
        self.debris_fields: dict[str, float] = {
            "leo": 0.0, "meo": 0.0, "geo": 0.0, "cislunar": 0.0,
        }
        self.combat_events: list[CombatEvent] = []
        self.pending_kinetics: list[dict] = []
        self.pending_deniables: list[dict] = []

        self._turn: int = 1
        self._phase: Phase = Phase.INVEST
        self._acting_faction_idx: int = 0
        self._total_turns: int = scenario.turns

        self._invest_decisions: dict[int, int] = {}
        self._ops_decisions: dict[int, int] = {}
        self._response_decisions: dict[int, int] = {}

        self._winner_coalition: str | None = None
        self._draw: bool = False

    def _recompute_dominance(self) -> None:
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        self.coalition_dominance = {
            cid: self._sim.compute_coalition_dominance(members, all_assets)
            for cid, members in self._coalitions.items()
        }

    def current_turn(self) -> int:
        return self._turn

    def current_phase(self) -> Phase:
        return self._phase

    def acting_faction_idx(self) -> int:
        return self._acting_faction_idx

    def is_terminal(self) -> bool:
        return self._winner_coalition is not None or self._draw

    def returns(self) -> list[float]:
        if not self.is_terminal():
            return [0.0] * len(self.faction_order)
        if self._draw:
            return [0.0] * len(self.faction_order)
        result = []
        for fid in self.faction_order:
            fs = self.faction_states[fid]
            result.append(1.0 if fs.coalition_id == self._winner_coalition else -1.0)
        return result

    def legal_actions(self, faction_idx: int) -> list[int]:
        """Return all globally-indexed action indices legal at this state for faction_idx."""
        if self.is_terminal():
            return []
        asp = self._action_space
        fid = self.faction_order[faction_idx]
        fs = self.faction_states[fid]

        if self._phase == Phase.INVEST:
            return list(range(asp.INVEST_COUNT))

        if self._phase == Phase.OPERATIONS:
            legal = []
            for local_idx, entry in enumerate(asp.ops_actions):
                global_idx = asp.OPS_OFFSET + local_idx
                action_type = entry["action_type"]
                mission = entry.get("mission", "")
                # intercept requires kinetic ASAT
                if mission == "intercept" and fs.assets.asat_kinetic == 0:
                    continue
                # gray_zone requires deniable ASAT or EW jammers
                if action_type == "gray_zone" and fs.assets.asat_deniable == 0 and fs.assets.ew_jammers == 0:
                    continue
                legal.append(global_idx)
            return legal

        if self._phase == Phase.RESPONSE:
            legal = []
            for local_idx, entry in enumerate(asp.response_actions):
                global_idx = asp.RESPONSE_OFFSET + local_idx
                # retaliate requires deniable ASAT
                if entry["retaliate"] and fs.assets.asat_deniable == 0:
                    continue
                legal.append(global_idx)
            return legal

        return []

    def apply_action(self, faction_idx: int, action_idx: int) -> None:
        """Apply one action for the current acting faction."""
        if faction_idx != self._acting_faction_idx:
            raise ValueError(
                f"Expected faction_idx={self._acting_faction_idx}, got {faction_idx}"
            )

        if self._phase == Phase.INVEST:
            self._invest_decisions[faction_idx] = action_idx
        elif self._phase == Phase.OPERATIONS:
            self._ops_decisions[faction_idx] = action_idx
        elif self._phase == Phase.RESPONSE:
            self._response_decisions[faction_idx] = action_idx

        if faction_idx + 1 < len(self.faction_order):
            self._acting_faction_idx += 1
        else:
            self._acting_faction_idx = 0
            if self._phase == Phase.INVEST:
                self._phase = Phase.OPERATIONS
            elif self._phase == Phase.OPERATIONS:
                self._phase = Phase.RESPONSE
            elif self._phase == Phase.RESPONSE:
                self._resolve_turn()

    def _resolve_turn(self) -> None:
        """Resolve a complete turn: kinetics, investment, ops, response, maintenance."""

        asp = self._action_space
        inv_res = self._sim.investment_resolver
        conflict_res = self._sim.conflict_resolver
        debris_eng = self._debris_engine
        maneuver_eng = self._maneuver_engine

        # ── Step 1: clear combat log ──────────────────────────────────────────
        self.combat_events = []

        # ── Step 2: resolve pending kinetics from prior turn ──────────────────
        # pending_kinetics entries: {attacker_id, target_faction_id, shell, power}
        resolved_kinetics: list[dict] = self.pending_kinetics
        self.pending_kinetics = []

        for k in resolved_kinetics:
            attacker_id = k["attacker_id"]
            target_id = k["target_faction_id"]
            if attacker_id not in self.faction_states or target_id not in self.faction_states:
                continue
            attacker_fs = self.faction_states[attacker_id]
            target_fs = self.faction_states[target_id]
            result = conflict_res.resolve_kinetic_asat(
                attacker_assets=attacker_fs.assets,
                target_assets=target_fs.assets,
                attacker_sda_level=attacker_fs.sda_level(),
            )
            nodes_destroyed = result["nodes_destroyed"]
            regime = result.get("regime", k.get("shell", "leo"))

            if nodes_destroyed > 0:
                # Deduct nodes from the targeted regime
                attr_map = {
                    "leo": "leo_nodes", "meo": "meo_nodes",
                    "geo": "geo_nodes", "cislunar": "cislunar_nodes",
                }
                attr = attr_map.get(regime, "leo_nodes")
                current = getattr(target_fs.assets, attr)
                setattr(target_fs.assets, attr, max(0, current - nodes_destroyed))

                # Add debris proportional to nodes destroyed
                debris_amount = nodes_destroyed * debris_eng.DEBRIS_PER_NODE_KINETIC
                self.debris_fields = debris_eng.add_debris(self.debris_fields, regime, debris_amount)

            self.combat_events.append(CombatEvent(
                turn=self._turn,
                attacker_id=attacker_id,
                target_faction_id=target_id,
                shell=regime,
                event_type="kinetic",
                nodes_destroyed=nodes_destroyed,
                detail=f"Kinetic ASAT: {nodes_destroyed} nodes destroyed in {regime}",
                detected=result.get("detected", False),
                attributed=result.get("attributed", False),
            ))

        # ── Step 3: apply INVEST decisions ────────────────────────────────────
        for faction_idx, action_idx in self._invest_decisions.items():
            fid = self.faction_order[faction_idx]
            fs = self.faction_states[fid]
            alloc, _name = asp.invest_portfolios[action_idx]
            result = inv_res.resolve(
                faction_id=fid,
                budget=fs.budget_per_turn,
                allocation=alloc,
                turn=self._turn,
                unlocked_techs=fs.unlocked_techs,
                partial_invest=fs.partial_invest,
            )
            # Apply immediate asset gains
            ia = result.immediate_assets
            fs.assets.leo_nodes += ia.leo_nodes
            fs.assets.meo_nodes += ia.meo_nodes
            fs.assets.geo_nodes += ia.geo_nodes
            fs.assets.cislunar_nodes += ia.cislunar_nodes
            fs.assets.launch_capacity += ia.launch_capacity
            fs.assets.asat_kinetic += ia.asat_kinetic
            fs.assets.asat_deniable += ia.asat_deniable
            fs.assets.ew_jammers += ia.ew_jammers

            # Bank partial remainder for next turn
            fs.partial_invest = result.partial_invest_out

            # Queue deferred returns on faction state
            fs.deferred_returns.extend(result.deferred_returns)

        # Process deferred returns that mature this turn
        for fid, fs in self.faction_states.items():
            matured = [d for d in fs.deferred_returns if d.get("turn_due") == self._turn]
            remaining = [d for d in fs.deferred_returns if d.get("turn_due") != self._turn]
            fs.deferred_returns = remaining
            for d in matured:
                category = d.get("category", "")
                amount = d.get("amount", 0)
                if category == "commercial_income":
                    # Convert income to budget (credited next turn via budget_per_turn proxy)
                    # For now add LEO nodes proportional to income as a simple proxy
                    fs.assets.leo_nodes += amount // 5
                elif category == "r_and_d":
                    # R&D yields SDA sensor improvements
                    fs.assets.sda_sensors += amount // 20
                elif category == "education":
                    # Education yields launch capacity
                    fs.assets.launch_capacity += amount // 30

        # ── Step 4: apply OPS decisions ───────────────────────────────────────
        for faction_idx, action_idx in self._ops_decisions.items():
            fid = self.faction_order[faction_idx]
            fs = self.faction_states[fid]
            ops = asp.ops_action_from_index(action_idx)
            action_type = ops.get("action_type", "")
            target_id = ops.get("target_faction_id")
            mission = ops.get("mission", "")

            if action_type == "task_assets" and mission == "intercept" and target_id:
                # Queue kinetic ASAT intercept for resolution next turn
                if fs.assets.asat_kinetic > 0 and target_id in self.faction_states:
                    self.pending_kinetics.append({
                        "attacker_id": fid,
                        "target_faction_id": target_id,
                        "shell": "leo",
                        "power": fs.assets.asat_kinetic,
                    })

            elif action_type == "gray_zone" and target_id:
                # Deniable effect: immediate small node disruption
                if target_id in self.faction_states and (
                    fs.assets.asat_deniable > 0 or fs.assets.ew_jammers > 0
                ):
                    target_fs = self.faction_states[target_id]
                    result = conflict_res.resolve_deniable_asat(
                        attacker_assets=fs.assets,
                        defender_sda_level=target_fs.sda_level(),
                    )
                    nodes_destroyed = result["nodes_destroyed"]
                    if nodes_destroyed > 0 and target_fs.assets.leo_nodes > 0:
                        target_fs.assets.leo_nodes = max(
                            0, target_fs.assets.leo_nodes - nodes_destroyed
                        )
                        debris_amount = nodes_destroyed * debris_eng.DEBRIS_PER_NODE_DENIABLE
                        self.debris_fields = debris_eng.add_debris(
                            self.debris_fields, "leo", debris_amount
                        )
                    self.combat_events.append(CombatEvent(
                        turn=self._turn,
                        attacker_id=fid,
                        target_faction_id=target_id,
                        shell="leo",
                        event_type="gray_zone",
                        nodes_destroyed=nodes_destroyed,
                        detail=f"Gray-zone deniable: {nodes_destroyed} nodes disrupted",
                        detected=result.get("detected", False),
                        attributed=result.get("attributed", False),
                    ))

        # ── Step 5: apply RESPONSE decisions ──────────────────────────────────
        for faction_idx, action_idx in self._response_decisions.items():
            resp = asp.response_action_from_index(action_idx)
            if resp.get("escalate"):
                self.escalation_rung = min(self.escalation_rung + 1, 5)

        # ── Step 6: replenish maneuver budgets ────────────────────────────────
        for fs in self.faction_states.values():
            maneuver_eng.replenish(fs)

        # ── Step 7: decay debris ──────────────────────────────────────────────
        self.debris_fields = debris_eng.decay(self.debris_fields)

        # ── Step 8: recompute dominance ───────────────────────────────────────
        self._recompute_dominance()

        # ── Step 9: check victory condition ───────────────────────────────────
        for cid, dominance in self.coalition_dominance.items():
            if dominance >= self._victory_threshold:
                self._winner_coalition = cid
                break

        # ── Step 10: clear decisions, advance turn, reset phase ───────────────
        self._invest_decisions = {}
        self._ops_decisions = {}
        self._response_decisions = {}
        self._turn += 1
        self._phase = Phase.INVEST

        # ── Step 11: check draw condition ─────────────────────────────────────
        if self._turn > self._total_turns and self._winner_coalition is None:
            self._draw = True

    def _estimate_adversary_assets(self, observer_id: str, target_id: str) -> FactionAssets:
        """Deterministic SDA-filtered estimate. No random — same state always gives same result."""
        observer_fs = self.faction_states[observer_id]
        target_fs = self.faction_states[target_id]
        sda = observer_fs.sda_level()
        a = target_fs.assets
        return FactionAssets(
            leo_nodes=int(a.leo_nodes * min(sda + 0.3, 1.0)),
            meo_nodes=int(a.meo_nodes * min(sda + 0.2, 1.0)),
            geo_nodes=int(a.geo_nodes * min(sda + 0.4, 1.0)),
            cislunar_nodes=int(a.cislunar_nodes * sda),
            asat_kinetic=int(a.asat_kinetic * sda) if sda >= 0.3 else 0,
            asat_deniable=round(a.asat_deniable * (sda - 0.5)) if sda >= 0.6 else 0,
            ew_jammers=int(a.ew_jammers * sda),
        )

    def clone(self) -> "CoreGame":
        return copy.deepcopy(self)

    def information_state_string(self, player_idx: int) -> str:
        """Deterministic encoding of what player_idx knows.

        Excludes same-phase prior actions of other factions (IS-MCTS invariant).
        """
        fid = self.faction_order[player_idx]
        fs = self.faction_states[fid]
        a = fs.assets

        lines = [
            f"IS:{fid}|T{self._turn}/{self._total_turns}|P{self._phase.value}|"
            f"ACT{self._acting_faction_idx}|ESC{self.escalation_rung}",
            f"DEB:{self.debris_fields['leo']:.3f}/{self.debris_fields['meo']:.3f}/"
            f"{self.debris_fields['geo']:.3f}/{self.debris_fields['cislunar']:.3f}",
            f"OWN:{a.leo_nodes}/{a.meo_nodes}/{a.geo_nodes}/{a.cislunar_nodes}/"
            f"{a.asat_kinetic}/{a.asat_deniable}/{a.ew_jammers}/{a.sda_sensors}/"
            f"{a.relay_nodes}/{a.launch_capacity}/{fs.current_budget}",
            "COAL:" + ",".join(f"{cid}={dom:.4f}" for cid, dom in sorted(self.coalition_dominance.items())),
        ]

        # Adversary estimates (SDA-filtered, deterministic)
        adv_lines = []
        for other_fid, other_fs in self.faction_states.items():
            if other_fs.coalition_id != fs.coalition_id:
                est = self._estimate_adversary_assets(fid, other_fid)
                adv_lines.append(
                    f"  {other_fid}:{est.leo_nodes}/{est.meo_nodes}/{est.geo_nodes}/"
                    f"{est.cislunar_nodes}/{est.asat_kinetic}"
                )
        if adv_lines:
            lines.append("ADV:")
            lines.extend(adv_lines)

        # Ally full state (shared intel)
        ally_lines = []
        for other_fid, other_fs in self.faction_states.items():
            if other_fid != fid and other_fs.coalition_id == fs.coalition_id:
                oa = other_fs.assets
                ally_lines.append(
                    f"  {other_fid}:{oa.leo_nodes}/{oa.meo_nodes}/{oa.geo_nodes}/"
                    f"{oa.cislunar_nodes}/{oa.asat_kinetic}/{oa.asat_deniable}/"
                    f"{oa.ew_jammers}/{oa.sda_sensors}/{oa.relay_nodes}/{oa.launch_capacity}"
                )
        if ally_lines:
            lines.append("ALLY:")
            lines.extend(ally_lines)

        detectable = sum(
            1 for k in self.pending_kinetics
            if k.get("target_faction_id") in [fid] + [
                f for f, s in self.faction_states.items() if s.coalition_id == fs.coalition_id
            ] and fs.sda_level() >= 0.3
        )
        lines.append(f"THREATS:{detectable}")

        return "\n".join(lines)
