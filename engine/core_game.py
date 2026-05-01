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
