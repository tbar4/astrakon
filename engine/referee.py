import asyncio
import random
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
from engine.state import (
    Phase, Decision, GameStateSnapshot, FactionState, FactionAssets,
    CoalitionState, CrisisEvent
)
from engine.simulation import SimulationEngine
from engine.events import CrisisEventLibrary
from output.audit import AuditTrail
from agents.base import AgentInterface

if TYPE_CHECKING:
    from scenarios.loader import Scenario


@dataclass
class GameResult:
    turns_completed: int
    winner_coalition: Optional[str]
    faction_outcomes: dict[str, str]  # faction_id -> "won" | "lost" | "draw"
    final_dominance: dict[str, float]


class GameReferee:
    def __init__(
        self,
        scenario: "Scenario",
        agents: dict[str, AgentInterface],
        audit: AuditTrail,
        header=None,
    ):
        self.scenario = scenario
        self.agents = agents
        self.audit = audit
        self.sim = SimulationEngine()
        self.event_library = CrisisEventLibrary(scenario.crisis_events_library)
        from tui.header import NullGameHeader
        self.header = header if header is not None else NullGameHeader()
        self._coalition_colors: dict[str, str] = {
            cid: ("green" if i == 0 else "red")
            for i, cid in enumerate(scenario.coalitions)
        }

        self.faction_states: dict[str, FactionState] = {
            f.faction_id: FactionState(
                faction_id=f.faction_id,
                name=f.name,
                budget_per_turn=f.budget_per_turn,
                current_budget=f.budget_per_turn,
                assets=f.starting_assets.model_copy(deep=True),
                coalition_id=f.coalition_id,
                coalition_loyalty=f.coalition_loyalty,
                archetype=f.archetype,
            )
            for f in scenario.factions
        }
        self.coalition_states: dict[str, CoalitionState] = {
            cid: CoalitionState(coalition_id=cid, member_ids=c.member_ids)
            for cid, c in scenario.coalitions.items()
        }
        self.tension_level: float = 0.2
        self.debris_level: float = 0.0
        self._turn_log: list[str] = []
        self._turn_log_summary: str = ""
        self._coordination_bonuses: dict[str, float] = {}
        self._event_sda_malus: dict[str, float] = {}
        self._prev_turn_ops: list[str] = []
        self._pending_kinetic_approaches: list[dict] = []
        self._debris_fields: dict[str, float] = {}
        self._escalation_rung: int = 0
        self._pending_deniable_approaches: list[dict] = []
        self._current_turn: int = 0
        self._initial_dominance: dict[str, float] = {}
        self._initial_assets: dict[str, FactionAssets] = {}

    def load_mutable_state(
        self,
        faction_states: dict,
        coalition_states: dict,
        tension_level: float,
        debris_level: float,
        turn_log: list,
        turn_log_summary: str,
        coordination_bonuses: dict,
        event_sda_malus: dict,
        prev_turn_ops: list,
        pending_kinetic_approaches: list,
        current_turn: int,
        initial_assets: dict | None = None,
        debris_fields: dict | None = None,
        escalation_rung: int = 0,
        pending_deniable_approaches: list | None = None,
    ) -> None:
        """Populate internal state from serialized game state (used by web runner)."""
        from engine.state import FactionState, CoalitionState, FactionAssets
        self.faction_states = {
            fid: FactionState.model_validate(fs) if isinstance(fs, dict) else fs
            for fid, fs in faction_states.items()
        }
        self.coalition_states = {
            cid: CoalitionState.model_validate(cs) if isinstance(cs, dict) else cs
            for cid, cs in coalition_states.items()
        }
        self.tension_level = tension_level
        self.debris_level = debris_level
        self._turn_log = list(turn_log)
        self._turn_log_summary = turn_log_summary
        self._coordination_bonuses = dict(coordination_bonuses)
        self._event_sda_malus = dict(event_sda_malus)
        self._prev_turn_ops = list(prev_turn_ops)
        self._pending_kinetic_approaches = list(pending_kinetic_approaches)
        self._debris_fields = dict(debris_fields) if debris_fields else {}
        self._escalation_rung = escalation_rung
        self._pending_deniable_approaches = list(pending_deniable_approaches) if pending_deniable_approaches else []
        self._current_turn = current_turn
        if initial_assets:
            self._initial_assets = {
                fid: FactionAssets.model_validate(a) if isinstance(a, dict) else a
                for fid, a in initial_assets.items()
            }

    def dump_mutable_state(self) -> dict:
        """Return serializable dict of all mutable game state."""
        return {
            "faction_states": {
                fid: fs.model_dump() for fid, fs in self.faction_states.items()
            },
            "coalition_states": {
                cid: cs.model_dump() for cid, cs in self.coalition_states.items()
            },
            "tension_level": self.tension_level,
            "debris_level": self.debris_level,
            "turn_log": list(self._turn_log),
            "turn_log_summary": self._turn_log_summary,
            "coordination_bonuses": dict(self._coordination_bonuses),
            "event_sda_malus": dict(self._event_sda_malus),
            "prev_turn_ops": list(self._prev_turn_ops),
            "pending_kinetic_approaches": list(self._pending_kinetic_approaches),
            "debris_fields": dict(self._debris_fields),
            "escalation_rung": self._escalation_rung,
            "pending_deniable_approaches": list(self._pending_deniable_approaches),
            "current_turn": self._current_turn,
        }

    async def run(self) -> GameResult:
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        self._initial_dominance = {
            cid: self.sim.compute_coalition_dominance(coalition.member_ids, all_assets)
            for cid, coalition in self.coalition_states.items()
        }
        self._initial_assets = {
            fid: fs.assets.model_copy(deep=True)
            for fid, fs in self.faction_states.items()
        }
        for turn in range(1, self.scenario.turns + 1):
            await self.run_turn(turn)
            winner = self._check_victory()
            if winner:
                return self._compute_result(turns_completed=turn, winner=winner)
        return self._compute_result(turns_completed=self.scenario.turns, winner=None)

    async def run_turn(self, turn: int):
        self._current_turn = turn
        self._turn_log = []
        self._replenish_budgets(turn)
        await self._run_investment_phase(turn)
        await self._run_operations_phase(turn)
        await self._run_response_phase(turn)
        self._update_faction_metrics()
        await self._display_turn_summary(turn)

    def _print_phase_banner(self, phase: Phase) -> None:
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        dominance = {
            cid: self.sim.compute_coalition_dominance(coalition.member_ids, all_assets)
            for cid, coalition in self.coalition_states.items()
        }
        self.header.print_phase_banner(
            turn=self._current_turn,
            tension=self.tension_level,
            debris=self.debris_level,
            coalition_dominance=dominance,
            coalition_colors=self._coalition_colors,
            phase=phase.value,
        )

    async def _display_turn_summary(self, turn: int):
        if not any(agent.is_human for agent in self.agents.values()):
            return
        from tui.summary import TurnSummary
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        dominance = {
            cid: self.sim.compute_coalition_dominance(coalition.member_ids, all_assets)
            for cid, coalition in self.coalition_states.items()
        }
        decisions = await self.audit.get_decisions(turn=turn)
        events = await self.audit.get_events(turn=turn)
        TurnSummary(
            turn=turn,
            total_turns=self.scenario.turns,
            events=events,
            turn_log=list(self._turn_log),
            decisions=decisions,
            faction_states=self.faction_states,
            coalition_states=self.coalition_states,
            coalition_colors=self._coalition_colors,
            dominance=dominance,
            victory_threshold=self.scenario.victory.coalition_orbital_dominance,
        ).display()

    def _replenish_budgets(self, turn: int):
        from engine.tech_tree import apply_passive_effects
        for fs in self.faction_states.values():
            fs.current_budget = fs.budget_per_turn
            cid = fs.coalition_id
            if cid and cid in self.scenario.coalitions:
                if self.scenario.coalitions[cid].hegemony_pool:
                    fs.current_budget = int(fs.current_budget * 1.1)
            due = [r for r in fs.deferred_returns if r["turn_due"] <= turn]
            for r in due:
                if r["category"] == "r_and_d":
                    tech_level = fs.tech_tree.get("r_and_d", 0)
                    fs.tech_tree["r_and_d"] = tech_level + r["amount"] // 10  # doubled from //20
                elif r["category"] == "education":
                    edu_level = fs.tech_tree.get("education", 0)
                    fs.tech_tree["education"] = edu_level + r["amount"] // 30
                elif r["category"] == "commercial_income":
                    fs.current_budget += r["amount"]
                else:
                    raise ValueError(f"Unknown deferred return category: {r['category']}")
            fs.deferred_returns = [r for r in fs.deferred_returns if r["turn_due"] > turn]
            # Education permanent bonus: +1 budget/turn per education point
            fs.current_budget += fs.tech_tree.get("education", 0)
            # Passive tech budget bonuses
            mods = apply_passive_effects(fs, "budget_replenish")
            fs.current_budget += mods["budget_bonus"]
        for fs in self.faction_states.values():
            self.sim.maneuver_budget_engine.replenish(fs)
        self._debris_fields = self.sim.debris_engine.decay(self._debris_fields)

    def _build_snapshot(
        self, faction_id: str, phase: Phase, available_actions: list[str]
    ) -> GameStateSnapshot:
        fs = self.faction_states[faction_id]
        coalition_id = fs.coalition_id

        # Compute effective SDA: coalition shared intel pools the best SDA among allies
        base_sda = fs.sda_level()
        if coalition_id and coalition_id in self.scenario.coalitions:
            if self.scenario.coalitions[coalition_id].shared_intel:
                coalition_key = None
                for cid, c in self.coalition_states.items():
                    if faction_id in c.member_ids:
                        coalition_key = cid
                        break
                if coalition_key:
                    base_sda = max(
                        self.faction_states[mid].sda_level()
                        for mid in self.coalition_states[coalition_key].member_ids
                        if mid in self.faction_states
                    )

        effective_sda = max(min(
            base_sda
            + self._coordination_bonuses.get(faction_id, 0.0)
            - self._event_sda_malus.get(faction_id, 0.0),
            1.0
        ), 0.0)

        ally_states = {}
        adversary_estimates = {}
        for fid, other_fs in self.faction_states.items():
            if fid == faction_id:
                continue
            if other_fs.coalition_id == coalition_id:
                ally_states[fid] = other_fs.model_copy(deep=True)
            else:
                adversary_estimates[fid] = self.sim.sda_filter.filter(
                    adversary_assets=other_fs.assets,
                    observer_sda_level=effective_sda,
                ).model_dump()

        # Detect incoming kinetic approaches if SDA sufficient
        incoming_threats = []
        for approach in self._pending_kinetic_approaches:
            if approach["target_fid"] == faction_id and effective_sda >= 0.3:
                attacker_name = self.faction_states.get(
                    approach["attacker_fid"],
                    type("_", (), {"name": approach["attacker_fid"]})()
                ).name
                incoming_threats.append({
                    "type": "kinetic_approach",
                    "attacker": attacker_name,
                    "declared_turn": approach["declared_turn"],
                })

        all_assets_for_dom = {fid: fs.assets for fid, fs in self.faction_states.items()}
        coalition_dominance = {
            cid: self.sim.compute_coalition_dominance(coalition.member_ids, all_assets_for_dom)
            for cid, coalition in self.coalition_states.items()
        }

        return GameStateSnapshot(
            turn=self._current_turn,
            phase=phase,
            faction_id=faction_id,
            faction_state=fs.model_copy(deep=True),
            ally_states=ally_states,
            adversary_estimates=adversary_estimates,
            coalition_states={cid: c.model_copy(deep=True) for cid, c in self.coalition_states.items()},
            available_actions=available_actions,
            tension_level=self.tension_level,
            debris_level=self.debris_level,
            turn_log_summary=self._turn_log_summary,
            joint_force_effectiveness=fs.joint_force_effectiveness,
            incoming_threats=incoming_threats,
            faction_names={fid: s.name for fid, s in self.faction_states.items()},
            debris_fields=dict(self._debris_fields),
            escalation_rung=self._escalation_rung,
            access_windows=self.sim.access_window_engine.compute(self._current_turn),
            total_turns=self.scenario.turns,
            coalition_dominance=coalition_dominance,
            victory_threshold=self.scenario.victory.coalition_orbital_dominance,
        )

    async def _fallback_decision(
        self, fid: str, phase: Phase, available_actions: list[str]
    ) -> Decision | None:
        from agents.rule_based import MahanianAgent
        try:
            fallback = MahanianAgent()
            fallback.initialize(next(f for f in self.scenario.factions if f.faction_id == fid))
            fallback.receive_state(self._build_snapshot(fid, phase, available_actions))
            return await fallback.submit_decision(phase)
        except Exception:
            return None

    async def _collect_decisions(
        self, phase: Phase, available_actions: list[str]
    ) -> dict[str, Decision]:
        self._print_phase_banner(phase)
        from rich.console import Console
        _console = Console()

        for faction_id, agent in self.agents.items():
            agent.receive_state(self._build_snapshot(faction_id, phase, available_actions))

        decisions = {}

        # Human agents first — interactive, no spinner
        for fid, agent in self.agents.items():
            if agent.is_human:
                try:
                    decisions[fid] = await agent.submit_decision(phase)
                except Exception:
                    result = await self._fallback_decision(fid, phase, available_actions)
                    if result is not None:
                        decisions[fid] = result

        # AI agents concurrently — show spinner while waiting
        ai_agents = {fid: agent for fid, agent in self.agents.items() if not agent.is_human}
        if ai_agents:
            ai_tasks = {fid: agent.submit_decision(phase) for fid, agent in ai_agents.items()}
            with _console.status(f"[dim]AI commanders deliberating ({phase.value} phase)...[/dim]"):
                results = await asyncio.gather(*ai_tasks.values(), return_exceptions=True)
            for fid, result in zip(ai_tasks.keys(), results):
                if isinstance(result, Exception):
                    decision = await self._fallback_decision(fid, phase, available_actions)
                    if decision is not None:
                        decisions[fid] = decision
                else:
                    decisions[fid] = result

        return decisions

    async def resolve_investment(self, turn: int, decisions: dict) -> None:
        """Resolve investment decisions (dict values may be Decision objects or JSON strings)."""
        from engine.tech_tree import NODE_BY_ID, prereqs_met
        # Apply debris disruption at start of invest phase
        self.faction_states, debris_log = self.sim.debris_engine.apply_debris_effects(
            self.faction_states, self._debris_fields
        )
        self._turn_log.extend(debris_log)
        from engine.state import Decision
        for fid, raw_decision in decisions.items():
            decision = Decision.model_validate_json(raw_decision) if isinstance(raw_decision, str) else raw_decision
            if decision.investment:
                fs = self.faction_states[fid]
                result = self.sim.investment_resolver.resolve(
                    faction_id=fid,
                    budget=fs.current_budget,
                    allocation=decision.investment,
                    turn=turn,
                )
                fs.assets.leo_nodes += result.immediate_assets.leo_nodes
                fs.assets.meo_nodes += result.immediate_assets.meo_nodes
                fs.assets.geo_nodes += result.immediate_assets.geo_nodes
                fs.assets.cislunar_nodes += result.immediate_assets.cislunar_nodes
                fs.assets.asat_deniable += result.immediate_assets.asat_deniable
                fs.assets.ew_jammers += result.immediate_assets.ew_jammers
                if result.immediate_assets.launch_capacity:
                    fs.assets.launch_capacity += result.immediate_assets.launch_capacity
                fs.deferred_returns.extend(result.deferred_returns)
                fs.current_budget = max(0, fs.current_budget - result.budget_spent)
            # Process tech unlocks
            for node_id in decision.tech_unlocks:
                fs = self.faction_states[fid]
                node = NODE_BY_ID.get(node_id)
                if node is None:
                    continue
                if node_id in fs.unlocked_techs:
                    continue
                if node.archetype is not None and node.archetype != fs.archetype:
                    self._turn_log.append(
                        f"[TECH] {fs.name} rejected unlock {node_id} — archetype mismatch"
                    )
                    continue
                rd_available = fs.tech_tree.get("r_and_d", 0)
                if rd_available < node.cost:
                    self._turn_log.append(
                        f"[TECH] {fs.name} rejected unlock {node_id} — insufficient R&D "
                        f"({rd_available}/{node.cost} pts)"
                    )
                    continue
                if not prereqs_met(node, fs.unlocked_techs):
                    self._turn_log.append(
                        f"[TECH] {fs.name} rejected unlock {node_id} — prereqs not met"
                    )
                    continue
                fs.tech_tree["r_and_d"] = rd_available - node.cost
                fs.unlocked_techs.append(node_id)
                # Apply one-time launch_capacity bonus for trunk_capacity
                if node_id == "trunk_capacity":
                    fs.assets.launch_capacity += 1
                self._turn_log.append(
                    f"[TECH] {fs.name} unlocked {node.name} (−{node.cost} R&D pts)"
                )
            await self.audit.write_decision(turn=turn, decision=decision)

    async def _run_investment_phase(self, turn: int):
        decisions = await self._collect_decisions(Phase.INVEST, ["allocate_budget"])
        await self.resolve_investment(turn, decisions)

    def _resolve_kinetic_approach(self, approach: dict):
        from engine.tech_tree import apply_passive_effects
        attacker_fid = approach["attacker_fid"]
        target_fid = approach["target_fid"]
        attacker_fs = self.faction_states.get(attacker_fid)
        target_fs = self.faction_states.get(target_fid)
        if not attacker_fs or not target_fs or attacker_fs.assets.asat_kinetic == 0:
            self._turn_log.append(
                f"Kinetic approach toward {target_fid} aborted — no ASATs remaining"
            )
            return

        attacker_mods = apply_passive_effects(attacker_fs, "asat_kinetic")
        result = self.sim.conflict_resolver.resolve_kinetic_asat(
            attacker_assets=attacker_fs.assets,
            target_assets=target_fs.assets,
            attacker_sda_level=attacker_fs.sda_level(),
            attacker_tech_mods=attacker_mods,
        )
        regime = result.get("regime", "leo")
        nodes_hit = 0
        if regime == "leo":
            nodes_hit = min(result["nodes_destroyed"], target_fs.assets.leo_nodes)
            target_fs.assets.leo_nodes -= nodes_hit
        elif regime == "meo":
            nodes_hit = min(result["nodes_destroyed"], target_fs.assets.meo_nodes)
            target_fs.assets.meo_nodes -= nodes_hit
        elif regime == "geo":
            nodes_hit = min(result["nodes_destroyed"], target_fs.assets.geo_nodes)
            target_fs.assets.geo_nodes -= nodes_hit
        elif regime == "cislunar":
            nodes_hit = min(result["nodes_destroyed"], target_fs.assets.cislunar_nodes)
            target_fs.assets.cislunar_nodes -= nodes_hit

        # rog_shock: free strike (don't consume ASAT)
        if attacker_mods["free_strike"]:
            attacker_fs.rog_shock_used = True
            self._turn_log.append(
                f"[TECH] {attacker_fs.name} activated Shock Strike (free kinetic, weapon not consumed)"
            )
        else:
            attacker_fs.assets.asat_kinetic -= 1

        # Debris (rog_debris doubles multiplier)
        if regime in ("leo", "meo", "geo", "cislunar"):
            debris_amount = self.sim.debris_engine.DEBRIS_PER_NODE_KINETIC * nodes_hit
            debris_amount *= attacker_mods["debris_multiplier"]
            self._debris_fields = self.sim.debris_engine.add_debris(
                self._debris_fields, regime, debris_amount
            )
        self.debris_level = max(self._debris_fields.values()) if self._debris_fields else 0.0
        self._escalation_rung = max(self._escalation_rung, 4)
        self._prev_turn_ops.append("kinetic_strike")
        attacker_fs.disruption_score += nodes_hit * 5

        # mah_escalation: target gains +1 ASAT kinetic (emergency procurement)
        if "mah_escalation" in target_fs.unlocked_techs:
            target_fs.assets.asat_kinetic += 1
            self._turn_log.append(
                f"[TECH] {target_fs.name} emergency procurement: +1 ASAT kinetic "
                f"(Escalation Response)"
            )

        detected = result["detected"]
        attributed = result["attributed"]
        suffix = (
            f" ({'attributed to ' + attacker_fs.name if attributed else 'detected, origin unclear'})"
            if detected else " (undetected)"
        )
        self._turn_log.append(
            f"[KINETIC] {attacker_fs.name} struck {target_fs.name} ({regime.upper()}): "
            f"{nodes_hit} nodes destroyed{suffix}"
        )

    def _resolve_retaliation(self, attacker_fid: str, target_fid: str):
        attacker_fs = self.faction_states.get(attacker_fid)
        target_fs = self.faction_states.get(target_fid)
        if not attacker_fs or not target_fs:
            return
        if attacker_fs.assets.asat_deniable > 0:
            result = self.sim.conflict_resolver.resolve_deniable_asat(
                attacker_assets=attacker_fs.assets,
                defender_sda_level=target_fs.sda_level(),
            )
            nodes_hit = min(result["nodes_destroyed"], target_fs.assets.leo_nodes)
            target_fs.assets.leo_nodes -= nodes_hit
            attacker_fs.assets.asat_deniable -= 1
            self._debris_fields = self.sim.debris_engine.add_debris(
                self._debris_fields, "leo",
                self.sim.debris_engine.DEBRIS_PER_NODE_DENIABLE * nodes_hit
            )
            self.debris_level = max(self._debris_fields.values()) if self._debris_fields else 0.0
            self._escalation_rung = max(self._escalation_rung, 5)  # cross-domain retaliation
            suffix = (
                f" ({'attributed' if result['attributed'] else 'detected, source unclear'})"
                if result["detected"] else " (undetected)"
            )
            self._turn_log.append(
                f"[RETALIATION] {attacker_fs.name} struck {target_fs.name}: "
                f"{nodes_hit} nodes disrupted{suffix}"
            )
            attacker_fs.disruption_score += nodes_hit * 5
            self._prev_turn_ops.append("deniable_strike")
        elif attacker_fs.assets.asat_kinetic > 0:
            result = self.sim.conflict_resolver.resolve_kinetic_asat(
                attacker_assets=attacker_fs.assets,
                target_assets=target_fs.assets,
                attacker_sda_level=attacker_fs.sda_level(),
            )
            regime = result.get("regime", "leo")
            nodes_hit = min(result["nodes_destroyed"], target_fs.assets.leo_nodes)
            target_fs.assets.leo_nodes -= nodes_hit
            attacker_fs.assets.asat_kinetic -= 1
            self._debris_fields = self.sim.debris_engine.add_debris(
                self._debris_fields, "leo",
                self.sim.debris_engine.DEBRIS_PER_NODE_KINETIC * nodes_hit
            )
            self.debris_level = max(self._debris_fields.values()) if self._debris_fields else 0.0
            self._escalation_rung = max(self._escalation_rung, 4)
            self._turn_log.append(
                f"[RETALIATION-KINETIC] {attacker_fs.name} kinetic strike on "
                f"{target_fs.name} ({regime.upper()}): {nodes_hit} nodes destroyed"
            )
            attacker_fs.disruption_score += nodes_hit * 5
            self._prev_turn_ops.append("kinetic_strike")

    def _apply_event_effect(self, event: CrisisEvent):
        if event.event_type == "asat_test":
            self._debris_fields = self.sim.debris_engine.add_debris(
                self._debris_fields, "leo", 0.08
            )
            self.debris_level = max(self._debris_fields.values()) if self._debris_fields else 0.0
            self._turn_log.append("ASAT test generated debris field (+8%)")
        elif event.event_type == "jamming_incident":
            if event.affected_factions:
                victim = random.choice(event.affected_factions)
                self._event_sda_malus[victim] = self._event_sda_malus.get(victim, 0.0) + 0.15
                victim_name = self.faction_states.get(
                    victim, type("_", (), {"name": victim})()
                ).name
                self._turn_log.append(
                    f"GPS jamming degrades {victim_name} SDA this turn (−15%)"
                )

    async def resolve_operations(self, turn: int, decisions: dict) -> None:
        """Resolve operations decisions. Call after pending kinetics are handled."""
        from engine.state import Decision
        kinetic_entries = [e for e in self._prev_turn_ops if 'kinetic' in e]
        self._prev_turn_ops = kinetic_entries
        self._coordination_bonuses = {}

        for fid, raw_decision in decisions.items():
            decision = Decision.model_validate_json(raw_decision) if isinstance(raw_decision, str) else raw_decision
            if not decision.operations:
                await self.audit.write_decision(turn=turn, decision=decision)
                continue

            fs = self.faction_states[fid]
            for op in decision.operations:
                target_fid = op.target_faction
                target_fs = self.faction_states.get(target_fid) if target_fid else None
                is_adversary = target_fs and target_fs.coalition_id != fs.coalition_id
                is_ally = target_fs and target_fs.coalition_id == fs.coalition_id

                if op.action_type == "task_assets":
                    mission = op.parameters.get("mission", "")
                    if mission == "intercept" and is_adversary:
                        if fs.assets.asat_kinetic == 0:
                            self._turn_log.append(
                                f"{fs.name} intercept ordered but no kinetic ASAT assets available — defaulting to surveillance"
                            )
                            self._prev_turn_ops.append("task_assets")
                        else:
                            ok, dv_msg = self.sim.maneuver_budget_engine.spend(fs, "kinetic_intercept")
                            if ok:
                                self._pending_kinetic_approaches.append({
                                    "attacker_fid": fid,
                                    "target_fid": target_fid,
                                    "declared_turn": turn,
                                    "approach_type": "kinetic",
                                    "rog_ascent": "rog_ascent" in fs.unlocked_techs,
                                })
                                self._escalation_rung = max(self._escalation_rung, 3)
                                self._turn_log.append(
                                    f"{fs.name} dispatched kinetic interceptor toward "
                                    f"{target_fs.name} (arrives turn {turn + 2})"
                                )
                                target_primary_shell = (
                                    "leo" if target_fs.assets.leo_nodes > 0 else
                                    "meo" if target_fs.assets.meo_nodes > 0 else
                                    "geo" if target_fs.assets.geo_nodes > 0 else "cislunar"
                                )
                                windows = self.sim.access_window_engine.compute(turn)
                                if not windows.get(target_primary_shell, True):
                                    self._turn_log.append(
                                        f"{fs.name} kinetic toward {target_fs.name} "
                                        f"({target_primary_shell.upper()}) — access window closed this turn, "
                                        f"2-turn transit may coincide with open window"
                                    )
                            else:
                                self._turn_log.append(f"{fs.name} kinetic intercept aborted — {dv_msg}")
                    else:
                        self._prev_turn_ops.append("task_assets")
                        if target_fid and is_adversary:
                            self._turn_log.append(
                                f"{fs.name} tasked assets against {target_fs.name} (surveillance)"
                            )

                elif op.action_type == "gray_zone" and is_adversary:
                    from engine.tech_tree import apply_passive_effects
                    # Apply coalition loyalty reduction (base 0.05, gz_influence → 0.15)
                    loyalty_mods = apply_passive_effects(fs, "gray_zone_loyalty")
                    if target_fs:
                        target_fs.coalition_loyalty = max(
                            0.0, target_fs.coalition_loyalty - loyalty_mods["loyalty_reduction"]
                        )
                    if fs.assets.asat_deniable > 0:
                        # Queue as delayed approach (1-turn transit)
                        ok, dv_msg = self.sim.maneuver_budget_engine.spend(fs, "deniable_approach")
                        if ok:
                            self._pending_deniable_approaches.append({
                                "attacker_fid": fid,
                                "target_fid": target_fid,
                                "declared_turn": turn,
                            })
                            self._escalation_rung = max(self._escalation_rung, 2)
                            self._turn_log.append(
                                f"{fs.name} co-orbital approach toward {target_fs.name} "
                                f"(arrives turn {turn + 1}, ambiguous signature)"
                            )
                        else:
                            self._turn_log.append(f"{fs.name} gray-zone op aborted — {dv_msg}")
                    elif fs.assets.ew_jammers > 0:
                        self._prev_turn_ops.append("gray_zone")
                        jamming_mods = apply_passive_effects(fs, "jamming_radius")
                        sda_malus = 0.30 if jamming_mods["extend_to_adjacent"] else 0.15
                        if target_fid:
                            self._event_sda_malus[target_fid] = (
                                self._event_sda_malus.get(target_fid, 0.0) + sda_malus
                            )
                        self._turn_log.append(f"{fs.name} EW jamming ops against {target_fs.name}")
                    else:
                        self._prev_turn_ops.append("gray_zone")
                        self._turn_log.append(
                            f"{fs.name} attempted gray-zone ops against {target_fs.name} — no deniable assets"
                        )

                elif op.action_type == "coordinate" and target_fid:
                    self._prev_turn_ops.append("coordinate")
                    if is_ally:
                        # High cognitive penalty nullifies coordination
                        if fs.cognitive_penalty > 0.75:
                            self._turn_log.append(
                                f"{fs.name} coordination with {target_fs.name} failed — "
                                f"cognitive degradation too severe ({fs.cognitive_penalty:.0%})"
                            )
                        elif fs.coalition_loyalty < 0.25:
                            self._turn_log.append(
                                f"{fs.name} coordination with {target_fs.name} failed — "
                                f"loyalty too low ({fs.coalition_loyalty:.0%})"
                            )
                        else:
                            loyalty_factor = 1.0
                            if self.tension_level > 0.7 and fs.coalition_loyalty < 0.5:
                                loyalty_factor = fs.coalition_loyalty / 0.5
                            cognitive_factor = 1.0 - (fs.cognitive_penalty * 0.5)
                            bonus = 0.1 * loyalty_factor * cognitive_factor
                            self._coordination_bonuses[fid] = (
                                self._coordination_bonuses.get(fid, 0.0) + bonus
                            )
                            self._coordination_bonuses[target_fid] = (
                                self._coordination_bonuses.get(target_fid, 0.0) + bonus
                            )
                            notes = []
                            if loyalty_factor < 1.0:
                                notes.append(f"loyalty-degraded ×{loyalty_factor:.1f}")
                            if cognitive_factor < 1.0:
                                notes.append(f"cognitive penalty ×{cognitive_factor:.1f}")
                            note = f" ({', '.join(notes)})" if notes else ""
                            self._turn_log.append(
                                f"{fs.name} coordinated with {target_fs.name} "
                                f"(+{bonus:.0%} SDA next snapshot{note})"
                            )
                    else:
                        self._turn_log.append(
                            f"{fs.name} attempted coordination with non-ally {target_fid} — ignored"
                        )
                else:
                    self._prev_turn_ops.append(op.action_type)

            await self.audit.write_decision(turn=turn, decision=decision)

        self._turn_log_summary = self._build_turn_log_summary(turn)

    def resolve_pending_kinetics(self, turn: int) -> None:
        """Resolve kinetic approaches with 2-turn transit (declared N, resolves at N+2)."""
        resolved = [
            a for a in self._pending_kinetic_approaches
            if a.get("approach_type", "kinetic") == "kinetic"
            and a["declared_turn"] == turn - 2
        ]
        for approach in resolved:
            self._resolve_kinetic_approach(approach)
        for a in resolved:
            self._pending_kinetic_approaches.remove(a)

    def _resolve_pending_deniables(self, turn: int) -> None:
        """Resolve delayed deniable co-orbital approaches (1-turn transit)."""
        resolved = [a for a in self._pending_deniable_approaches if a["declared_turn"] == turn - 1]
        for approach in resolved:
            attacker_fid = approach["attacker_fid"]
            target_fid = approach["target_fid"]
            attacker_fs = self.faction_states.get(attacker_fid)
            target_fs = self.faction_states.get(target_fid)
            if not attacker_fs or not target_fs or attacker_fs.assets.asat_deniable == 0:
                self._turn_log.append("Deniable co-orbital approach aborted — no assets remaining")
                continue
            result = self.sim.conflict_resolver.resolve_deniable_asat(
                attacker_assets=attacker_fs.assets,
                defender_sda_level=target_fs.sda_level(),
            )
            nodes_hit = min(result["nodes_destroyed"], target_fs.assets.leo_nodes)
            target_fs.assets.leo_nodes -= nodes_hit
            attacker_fs.assets.asat_deniable -= 1
            self._debris_fields = self.sim.debris_engine.add_debris(
                self._debris_fields, "leo",
                self.sim.debris_engine.DEBRIS_PER_NODE_DENIABLE * nodes_hit
            )
            self.debris_level = max(self._debris_fields.values()) if self._debris_fields else 0.0
            self._escalation_rung = max(self._escalation_rung, 3)
            attacker_fs.disruption_score += nodes_hit * 5
            detected = result["detected"]
            attributed = result["attributed"]
            suffix = (
                f" ({'attributed to ' + attacker_fs.name if attributed else 'detected, origin unclear'})"
                if detected else " (undetected)"
            )
            self._turn_log.append(
                f"[DENIABLE] {attacker_fs.name} co-orbital op vs {target_fs.name}: "
                f"{nodes_hit} nodes disrupted{suffix}"
            )
        for a in resolved:
            self._pending_deniable_approaches.remove(a)

    async def _run_operations_phase(self, turn: int):
        self.resolve_pending_kinetics(turn)
        self._resolve_pending_deniables(turn)
        decisions = await self._collect_decisions(
            Phase.OPERATIONS,
            ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"]
        )
        await self.resolve_operations(turn, decisions)

    def _build_turn_log_summary(self, turn: int) -> str:
        if not self._turn_log:
            return ""
        entries = "\n".join(f"  • {e}" for e in self._turn_log)
        summary = f"Turn {turn} operations:\n{entries}"
        if self.debris_level > 0:
            summary += f"\nCumulative debris field: {self.debris_level:.0%}"
        return summary

    def generate_turn_events(self, turn: int) -> list:
        """Generate crisis events for this turn and apply their effects. Returns list of CrisisEvent."""
        self._event_sda_malus = {}
        all_factions = list(self.faction_states.keys())
        events = self.event_library.generate_events(
            tension_level=self.tension_level,
            affected_factions=all_factions,
            turn=turn,
            prev_ops=self._prev_turn_ops,
        )
        for event in events:
            if event.severity > 0.5:
                self.tension_level = min(self.tension_level + 0.1, 1.0)
            self._apply_event_effect(event)
        self._turn_log_summary = self._build_turn_log_summary(turn)
        return events

    async def resolve_response(self, turn: int, decisions: dict, events: list) -> None:
        """Resolve response decisions. Call after generate_turn_events."""
        from engine.state import Decision
        for event in events:
            await self.audit.write_event(turn=turn, event=event)
            for agent in self.agents.values():
                agent.receive_event(event)

        for fid, raw_decision in decisions.items():
            decision = Decision.model_validate_json(raw_decision) if isinstance(raw_decision, str) else raw_decision
            if decision.response and decision.response.escalate:
                self.tension_level = min(self.tension_level + 0.15, 1.0)
                if decision.response.retaliate and decision.response.target_faction:
                    self._resolve_retaliation(fid, decision.response.target_faction)
            await self.audit.write_decision(turn=turn, decision=decision)
            # De-escalation reduces escalation rung and recovers coalition loyalty
            if decision.response and not decision.response.escalate and decision.response.public_statement:
                self._escalation_rung = max(0, self._escalation_rung - 1)
                fs = self.faction_states.get(fid)
                if fs and fs.coalition_id:
                    fs.coalition_loyalty = min(1.0, fs.coalition_loyalty + 0.02)

        # rog_ascent: resolve same-turn kinetic approaches at end of RESPONSE phase
        rog_ascent_approaches = [
            a for a in self._pending_kinetic_approaches
            if a.get("rog_ascent") and a["declared_turn"] == turn
        ]
        for approach in rog_ascent_approaches:
            self._resolve_kinetic_approach(approach)
            self._pending_kinetic_approaches.remove(approach)

        self._turn_log_summary = self._build_turn_log_summary(turn)
        self._update_coalition_loyalty()

    async def _run_response_phase(self, turn: int):
        events = self.generate_turn_events(turn)
        decisions = await self._collect_decisions(
            Phase.RESPONSE,
            ["escalate", "de_escalate", "retaliate", "emergency_reallocation", "public_statement"]
        )
        await self.resolve_response(turn, decisions, events)

    def _update_faction_metrics(self):
        from engine.tech_tree import apply_passive_effects
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        total_leo = sum(a.leo_nodes for a in all_assets.values())

        for fid, fs in self.faction_states.items():
            # Deterrence: ASAT stockpile (10 pts) + SDA strength (50 pts) + coalition (20 pts)
            fs.deterrence_score = min(100.0,
                fs.assets.asat_kinetic * 10 +
                fs.sda_level() * 50 +
                (20.0 if fs.coalition_id else 0.0)
            )
            # mah_deterrence: +15 deterrence score/turn
            if "mah_deterrence" in fs.unlocked_techs:
                fs.deterrence_score = min(100.0, fs.deterrence_score + 15)

            # Market share: this faction's LEO nodes as fraction of total (com_network includes MEO)
            market_mods = apply_passive_effects(fs, "market_share")
            if market_mods["include_meo"]:
                total_meo = sum(a.meo_nodes for a in all_assets.values())
                weighted = fs.assets.leo_nodes + fs.assets.meo_nodes * 2
                total_weighted = total_leo + total_meo * 2
                fs.market_share = weighted / total_weighted if total_weighted > 0 else 0.0
            else:
                fs.market_share = fs.assets.leo_nodes / total_leo if total_leo > 0 else 0.0

            # JFE: degrades with node loss vs initial position
            if fid in self._initial_assets:
                init = self._initial_assets[fid]
                meo_lost = max(0, init.meo_nodes - fs.assets.meo_nodes)
                geo_lost = max(0, init.geo_nodes - fs.assets.geo_nodes)
                leo_lost_frac = max(0, init.leo_nodes - fs.assets.leo_nodes) / max(init.leo_nodes, 1)
                jfe_loss = meo_lost * 0.10 + geo_lost * 0.15 + leo_lost_frac * 0.30
                fs.joint_force_effectiveness = max(0.0, 1.0 - jfe_loss)

            # Cognitive penalty: JFE loss + SDA degradation from events
            jfe_loss = max(0.0, 1.0 - fs.joint_force_effectiveness)
            sda_malus = self._event_sda_malus.get(fid, 0.0)
            fs.cognitive_penalty = min(1.0, jfe_loss * 0.5 + sda_malus * 1.5)

    def _update_coalition_loyalty(self) -> None:
        """Adjust coalition loyalty based on tension and recent events."""
        for fs in self.faction_states.values():
            if fs.coalition_id is None:
                continue
            # High tension strains coalitions
            if self.tension_level > 0.6:
                strain = (self.tension_level - 0.6) * 0.05
                fs.coalition_loyalty = max(0.0, fs.coalition_loyalty - strain)
            # Defection: loyalty below 0.15 → leave coalition
            if fs.coalition_loyalty < 0.15:
                old_cid = fs.coalition_id
                fs.coalition_id = None
                if old_cid in self.coalition_states:
                    mids = self.coalition_states[old_cid].member_ids
                    if fs.faction_id in mids:
                        self.coalition_states[old_cid].member_ids = [m for m in mids if m != fs.faction_id]
                self._turn_log.append(
                    f"[DEFECTION] {fs.name} has left coalition {old_cid} (loyalty collapsed)"
                )

    def _check_individual_conditions(self, member_ids: list[str]) -> bool:
        individual = self.scenario.victory.individual_conditions
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        for fid in member_ids:
            if fid not in individual:
                continue
            fs = self.faction_states[fid]
            conds = individual[fid]
            if "military_deterrence_score" in conds:
                if fs.deterrence_score < conds["military_deterrence_score"]:
                    return False
            if "commercial_market_share" in conds:
                if fs.market_share < conds["commercial_market_share"]:
                    return False
            if "orbital_dominance_score" in conds:
                faction_dom = self.sim.compute_orbital_dominance(fid, all_assets)
                if faction_dom < conds["orbital_dominance_score"]:
                    return False
            if "disruption_score" in conds:
                if fs.disruption_score < conds["disruption_score"]:
                    return False
        return True

    def _check_victory(self) -> Optional[str]:
        if self._current_turn < 4:
            return None
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        for cid, coalition in self.coalition_states.items():
            dominance = self.sim.compute_coalition_dominance(
                coalition.member_ids, all_assets
            )
            initial = self._initial_dominance.get(cid, 0.0)
            if (dominance >= self.scenario.victory.coalition_orbital_dominance
                    and dominance > initial):
                if (self.scenario.victory.individual_conditions_required
                        and self.scenario.victory.individual_conditions):
                    if not self._check_individual_conditions(coalition.member_ids):
                        continue
                return cid
        return None

    def _compute_result(
        self, turns_completed: int, winner: Optional[str]
    ) -> GameResult:
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        dominance = {
            fid: self.sim.compute_orbital_dominance(fid, all_assets)
            for fid in self.faction_states
        }
        outcomes = {}
        for fid, fs in self.faction_states.items():
            if winner and fs.coalition_id == winner:
                outcomes[fid] = "won"
            elif winner:
                outcomes[fid] = "lost"
            else:
                outcomes[fid] = "draw"
        return GameResult(
            turns_completed=turns_completed,
            winner_coalition=winner,
            faction_outcomes=outcomes,
            final_dominance=dominance,
        )
