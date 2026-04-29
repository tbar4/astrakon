import asyncio
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
    ):
        self.scenario = scenario
        self.agents = agents
        self.audit = audit
        self.sim = SimulationEngine()
        self.event_library = CrisisEventLibrary(scenario.crisis_events_library)

        # Initialize mutable game state
        self.faction_states: dict[str, FactionState] = {
            f.faction_id: FactionState(
                faction_id=f.faction_id,
                name=f.name,
                budget_per_turn=f.budget_per_turn,
                current_budget=f.budget_per_turn,
                assets=f.starting_assets.model_copy(deep=True),
                coalition_id=f.coalition_id,
                coalition_loyalty=f.coalition_loyalty,
            )
            for f in scenario.factions
        }
        self.coalition_states: dict[str, CoalitionState] = {
            cid: CoalitionState(coalition_id=cid, member_ids=c.member_ids)
            for cid, c in scenario.coalitions.items()
        }
        self.tension_level: float = 0.2
        self._current_turn: int = 0
        # Track dominance at start of game to detect in-game changes
        self._initial_dominance: dict[str, float] = {}

    async def run(self) -> GameResult:
        # Record initial coalition dominance before any turns are played
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        self._initial_dominance = {
            cid: self.sim.compute_coalition_dominance(coalition.member_ids, all_assets)
            for cid, coalition in self.coalition_states.items()
        }
        for turn in range(1, self.scenario.turns + 1):
            await self.run_turn(turn)
            winner = self._check_victory()
            if winner:
                return self._compute_result(turns_completed=turn, winner=winner)
        return self._compute_result(turns_completed=self.scenario.turns, winner=None)

    async def run_turn(self, turn: int):
        self._current_turn = turn
        self._replenish_budgets(turn)
        await self._run_investment_phase(turn)
        await self._run_operations_phase(turn)
        await self._run_response_phase(turn)

    def _replenish_budgets(self, turn: int):
        for fs in self.faction_states.values():
            fs.current_budget = fs.budget_per_turn
            # Process deferred returns that are due this turn
            due = [r for r in fs.deferred_returns if r["turn_due"] <= turn]
            for r in due:
                if r["category"] == "r_and_d":
                    tech_level = fs.tech_tree.get("r_and_d", 0)
                    fs.tech_tree["r_and_d"] = tech_level + max(1, r["amount"] // 20)
            fs.deferred_returns = [
                r for r in fs.deferred_returns if r["turn_due"] > turn
            ]

    def _build_snapshot(
        self, faction_id: str, phase: Phase, available_actions: list[str]
    ) -> GameStateSnapshot:
        fs = self.faction_states[faction_id]
        coalition_id = fs.coalition_id
        ally_states = {}
        adversary_estimates = {}
        for fid, other_fs in self.faction_states.items():
            if fid == faction_id:
                continue
            if other_fs.coalition_id == coalition_id:
                ally_states[fid] = other_fs
            else:
                adversary_estimates[fid] = self.sim.sda_filter.filter(
                    adversary_assets=other_fs.assets,
                    observer_sda_level=fs.sda_level(),
                )
        return GameStateSnapshot(
            turn=self._current_turn,
            phase=phase,
            faction_id=faction_id,
            faction_state=fs,
            ally_states=ally_states,
            adversary_estimates=adversary_estimates,
            coalition_states=self.coalition_states,
            available_actions=available_actions,
        )

    async def _collect_decisions(
        self, phase: Phase, available_actions: list[str]
    ) -> dict[str, Decision]:
        for faction_id, agent in self.agents.items():
            snapshot = self._build_snapshot(faction_id, phase, available_actions)
            agent.receive_state(snapshot)

        tasks = {
            fid: agent.submit_decision(phase)
            for fid, agent in self.agents.items()
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        decisions = {}
        for fid, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                from agents.rule_based import MahanianAgent
                fallback = MahanianAgent()
                fallback.initialize(
                    next(f for f in self.scenario.factions if f.faction_id == fid)
                )
                snapshot = self._build_snapshot(fid, phase, available_actions)
                fallback.receive_state(snapshot)
                decisions[fid] = await fallback.submit_decision(phase)
            else:
                decisions[fid] = result
        return decisions

    async def _run_investment_phase(self, turn: int):
        decisions = await self._collect_decisions(Phase.INVEST, ["allocate_budget"])
        for fid, decision in decisions.items():
            if decision.investment:
                fs = self.faction_states[fid]
                result = self.sim.investment_resolver.resolve(
                    faction_id=fid,
                    budget=fs.current_budget,
                    allocation=decision.investment,
                    turn=turn,
                )
                fs.assets.leo_nodes += result.immediate_assets.leo_nodes
                fs.assets.asat_deniable += result.immediate_assets.asat_deniable
                fs.assets.ew_jammers += result.immediate_assets.ew_jammers
                if result.immediate_assets.launch_capacity:
                    fs.assets.launch_capacity += result.immediate_assets.launch_capacity
                fs.deferred_returns.extend(result.deferred_returns)
            await self.audit.write_decision(turn=turn, decision=decision)

    async def _run_operations_phase(self, turn: int):
        decisions = await self._collect_decisions(
            Phase.OPERATIONS,
            ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"]
        )
        for fid, decision in decisions.items():
            await self.audit.write_decision(turn=turn, decision=decision)

    async def _run_response_phase(self, turn: int):
        all_factions = list(self.faction_states.keys())
        events = self.event_library.generate_events(
            tension_level=self.tension_level,
            affected_factions=all_factions,
            turn=turn,
        )
        for event in events:
            await self.audit.write_event(turn=turn, event=event)
            for agent in self.agents.values():
                agent.receive_event(event)
            if event.severity > 0.5:
                self.tension_level = min(self.tension_level + 0.1, 1.0)

        decisions = await self._collect_decisions(
            Phase.RESPONSE,
            ["escalate", "de_escalate", "retaliate", "emergency_reallocation", "public_statement"]
        )
        for fid, decision in decisions.items():
            if decision.response and decision.response.escalate:
                self.tension_level = min(self.tension_level + 0.15, 1.0)
            await self.audit.write_decision(turn=turn, decision=decision)

    def _check_victory(self) -> Optional[str]:
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        for cid, coalition in self.coalition_states.items():
            dominance = self.sim.compute_coalition_dominance(
                coalition.member_ids, all_assets
            )
            initial = self._initial_dominance.get(cid, 0.0)
            # Only trigger early exit if threshold is met AND dominance
            # increased beyond the initial position (i.e., earned in-game)
            if (dominance >= self.scenario.victory.coalition_orbital_dominance
                    and dominance > initial):
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
