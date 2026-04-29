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
        await self._display_turn_summary(turn)

    async def _display_turn_summary(self, turn: int):
        if not any(agent.is_human for agent in self.agents.values()):
            return

        import json
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        _console = Console()
        decisions = await self.audit.get_decisions(turn=turn)
        events = await self.audit.get_events(turn=turn)

        _console.print(f"\n[bold cyan]{'═' * 50}[/bold cyan]")
        _console.print(f"[bold cyan]  END OF TURN {turn} — INTELLIGENCE SUMMARY[/bold cyan]")
        _console.print(f"[bold cyan]{'═' * 50}[/bold cyan]")

        # Crisis events
        if events:
            _console.print("\n[bold yellow]CRISIS EVENTS[/bold yellow]")
            for ev in events:
                severity = ev["severity"]
                bar = "█" * round(severity * 5) + "░" * (5 - round(severity * 5))
                _console.print(
                    f"  [yellow]{bar}[/yellow] [bold]{ev['event_type'].upper()}[/bold]\n"
                    f"       {ev['description']}"
                )
        else:
            _console.print("\n[dim]No crisis events this turn.[/dim]")

        # Operations — public actions only
        _PUBLIC_OPS = {"signal", "alliance_move"}
        _OBSERVABLE_OPS = {"task_assets"}
        ops_rows = []
        for d in decisions:
            if d["phase"] != "operations":
                continue
            fid = d["faction_id"]
            name = self.faction_states[fid].name
            data = json.loads(d["decision_json"])
            for op in (data.get("operations") or []):
                action = op.get("action_type", "")
                if action in _PUBLIC_OPS:
                    ops_rows.append((name, action, op.get("rationale", "—")))
                elif action in _OBSERVABLE_OPS:
                    ops_rows.append((name, action, "[dim](details classified)[/dim]"))
                # gray_zone / coordinate: hidden

        _console.print("\n[bold]OBSERVED OPERATIONS[/bold]")
        if ops_rows:
            ops_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
            ops_table.add_column("Faction")
            ops_table.add_column("Action")
            ops_table.add_column("Statement / Details")
            for row in ops_rows:
                ops_table.add_row(*row)
            _console.print(ops_table)
        else:
            _console.print("  [dim]No publicly observable operations this turn.[/dim]")

        # Response phase — escalation and public statements
        _console.print("\n[bold]FACTION RESPONSES[/bold]")
        resp_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        resp_table.add_column("Faction")
        resp_table.add_column("Posture")
        resp_table.add_column("Public Statement")
        for d in decisions:
            if d["phase"] != "response":
                continue
            fid = d["faction_id"]
            name = self.faction_states[fid].name
            data = json.loads(d["decision_json"])
            resp = data.get("response") or {}
            if resp.get("escalate"):
                posture = "[bold red]ESCALATED[/bold red]"
                if resp.get("retaliate") and resp.get("target_faction"):
                    target_name = self.faction_states.get(
                        resp["target_faction"], type("", (), {"name": resp["target_faction"]})()
                    ).name
                    posture += f" → retaliated vs {target_name}"
            else:
                posture = "[green]stood down[/green]"
            statement = resp.get("public_statement") or "[dim]—[/dim]"
            resp_table.add_row(name, posture, statement)
        _console.print(resp_table)

        # Board state — coalition orbital dominance (publicly observable)
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        _console.print("\n[bold]ORBITAL DOMINANCE[/bold]")
        dom_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        dom_table.add_column("Coalition")
        dom_table.add_column("Members")
        dom_table.add_column("Dominance", justify="right")
        dom_table.add_column("vs. Victory threshold", justify="right")
        threshold = self.scenario.victory.coalition_orbital_dominance
        for cid, coalition in self.coalition_states.items():
            dominance = self.sim.compute_coalition_dominance(coalition.member_ids, all_assets)
            member_names = ", ".join(
                self.faction_states[m].name for m in coalition.member_ids if m in self.faction_states
            )
            pct = f"{dominance:.1%}"
            gap = f"{dominance - threshold:+.1%}"
            color = "green" if dominance >= threshold else "red"
            dom_table.add_row(cid, member_names, pct, f"[{color}]{gap}[/{color}]")
        _console.print(dom_table)
        _console.print(f"  [dim]Board tension: {self.tension_level:.0%}[/dim]\n")

    def _replenish_budgets(self, turn: int):
        for fs in self.faction_states.values():
            fs.current_budget = fs.budget_per_turn
            # Process deferred returns that are due this turn
            due = [r for r in fs.deferred_returns if r["turn_due"] <= turn]
            for r in due:
                if r["category"] == "r_and_d":
                    tech_level = fs.tech_tree.get("r_and_d", 0)
                    fs.tech_tree["r_and_d"] = tech_level + r["amount"] // 20
                elif r["category"] == "education":
                    edu_level = fs.tech_tree.get("education", 0)
                    fs.tech_tree["education"] = edu_level + r["amount"] // 30
                else:
                    raise ValueError(f"Unknown deferred return category: {r['category']}")
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
                ally_states[fid] = other_fs.model_copy(deep=True)
            else:
                adversary_estimates[fid] = self.sim.sda_filter.filter(
                    adversary_assets=other_fs.assets,
                    observer_sda_level=fs.sda_level(),
                )
        return GameStateSnapshot(
            turn=self._current_turn,
            phase=phase,
            faction_id=faction_id,
            faction_state=fs.model_copy(deep=True),
            ally_states=ally_states,
            adversary_estimates=adversary_estimates,
            coalition_states={cid: c.model_copy(deep=True) for cid, c in self.coalition_states.items()},
            available_actions=available_actions,
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

        # AI agents concurrently — show spinner while waiting on API calls
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
                # TODO: decrement fs.current_budget by result.budget_spent for cross-phase accounting
            await self.audit.write_decision(turn=turn, decision=decision)

    async def _run_operations_phase(self, turn: int):
        decisions = await self._collect_decisions(
            Phase.OPERATIONS,
            ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"]
        )
        for fid, decision in decisions.items():
            # TODO: resolve operational actions via ConflictResolver (post-POC)
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
        if self._current_turn < 4:
            return None
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
