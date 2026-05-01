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
        """Stub — filled in Task 8. Clears decisions, advances turn."""
        self._invest_decisions = {}
        self._ops_decisions = {}
        self._response_decisions = {}
        self._turn += 1
        self._phase = Phase.INVEST
        if self._turn > self._total_turns:
            self._draw = True
