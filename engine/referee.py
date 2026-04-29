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
    ):
        self.scenario = scenario
        self.agents = agents
        self.audit = audit
        self.sim = SimulationEngine()
        self.event_library = CrisisEventLibrary(scenario.crisis_events_library)

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
        self.debris_level: float = 0.0
        self._turn_log: list[str] = []
        self._turn_log_summary: str = ""
        self._coordination_bonuses: dict[str, float] = {}
        self._event_sda_malus: dict[str, float] = {}
        self._prev_turn_ops: list[str] = []
        self._pending_kinetic_approaches: list[dict] = []
        self._current_turn: int = 0
        self._initial_dominance: dict[str, float] = {}
        self._initial_assets: dict[str, FactionAssets] = {}

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
        self._replenish_budgets(turn)
        await self._run_investment_phase(turn)
        await self._run_operations_phase(turn)
        await self._run_response_phase(turn)
        self._update_faction_metrics()
        await self._display_turn_summary(turn)

    async def _display_turn_summary(self, turn: int):
        if not any(agent.is_human for agent in self.agents.values()):
            return

        import json
        from rich.console import Console
        from rich.table import Table

        _console = Console()
        decisions = await self.audit.get_decisions(turn=turn)
        events = await self.audit.get_events(turn=turn)

        _console.print(f"\n[bold cyan]{'═' * 56}[/bold cyan]")
        _console.print(f"[bold cyan]  END OF TURN {turn} — INTELLIGENCE SUMMARY[/bold cyan]")
        _console.print(f"[bold cyan]{'═' * 56}[/bold cyan]")

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

        # Operational log (turn-log entries from ops + response phase)
        if self._turn_log:
            _console.print("\n[bold]OPERATIONAL LOG[/bold]")
            for entry in self._turn_log:
                if "[KINETIC]" in entry or "[RETALIATION" in entry:
                    _console.print(f"  [red]{entry}[/red]")
                elif "disrupted" in entry or "gray-zone" in entry.lower() or "EW jamming" in entry:
                    _console.print(f"  [yellow]{entry}[/yellow]")
                elif "coordinated" in entry:
                    _console.print(f"  [cyan]{entry}[/cyan]")
                else:
                    _console.print(f"  [dim]{entry}[/dim]")

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

        # Board state — coalition orbital dominance
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        _console.print("\n[bold]ORBITAL DOMINANCE[/bold]")
        dom_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        dom_table.add_column("Coalition")
        dom_table.add_column("Members")
        dom_table.add_column("Dominance", justify="right")
        dom_table.add_column("vs. Threshold", justify="right")
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

        # Per-faction metrics
        _console.print("\n[bold]FACTION METRICS[/bold]")
        metrics_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        metrics_table.add_column("Faction")
        metrics_table.add_column("Deterrence", justify="right")
        metrics_table.add_column("Disruption", justify="right")
        metrics_table.add_column("Mkt Share", justify="right")
        metrics_table.add_column("JFE", justify="right")
        for fid, fs in self.faction_states.items():
            jfe_color = "green" if fs.joint_force_effectiveness >= 0.8 else (
                "yellow" if fs.joint_force_effectiveness >= 0.5 else "red"
            )
            metrics_table.add_row(
                fs.name,
                f"{fs.deterrence_score:.0f}",
                f"{fs.disruption_score:.0f}",
                f"{fs.market_share:.1%}",
                f"[{jfe_color}]{fs.joint_force_effectiveness:.0%}[/{jfe_color}]",
            )
        _console.print(metrics_table)
        _console.print(
            f"  [dim]Board tension: {self.tension_level:.0%}  |  "
            f"Debris field: {self.debris_level:.0%}[/dim]\n"
        )

    def _replenish_budgets(self, turn: int):
        for fs in self.faction_states.values():
            fs.current_budget = fs.budget_per_turn
            # Coalition hegemony pool: +10% budget for members
            cid = fs.coalition_id
            if cid and cid in self.scenario.coalitions:
                if self.scenario.coalitions[cid].hegemony_pool:
                    fs.current_budget = int(fs.current_budget * 1.1)
            # Process deferred returns due this turn
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
            fs.deferred_returns = [r for r in fs.deferred_returns if r["turn_due"] > turn]

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
                )

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
                fs.assets.meo_nodes += result.immediate_assets.meo_nodes
                fs.assets.geo_nodes += result.immediate_assets.geo_nodes
                fs.assets.cislunar_nodes += result.immediate_assets.cislunar_nodes
                fs.assets.asat_deniable += result.immediate_assets.asat_deniable
                fs.assets.ew_jammers += result.immediate_assets.ew_jammers
                if result.immediate_assets.launch_capacity:
                    fs.assets.launch_capacity += result.immediate_assets.launch_capacity
                fs.deferred_returns.extend(result.deferred_returns)
                fs.current_budget = max(0, fs.current_budget - result.budget_spent)
            await self.audit.write_decision(turn=turn, decision=decision)

    def _resolve_kinetic_approach(self, approach: dict):
        attacker_fid = approach["attacker_fid"]
        target_fid = approach["target_fid"]
        attacker_fs = self.faction_states.get(attacker_fid)
        target_fs = self.faction_states.get(target_fid)
        if not attacker_fs or not target_fs or attacker_fs.assets.asat_kinetic == 0:
            self._turn_log.append(
                f"Kinetic approach toward {target_fid} aborted — no ASATs remaining"
            )
            return
        result = self.sim.conflict_resolver.resolve_kinetic_asat(
            attacker_assets=attacker_fs.assets,
            target_assets=target_fs.assets,
            attacker_sda_level=attacker_fs.sda_level(),
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

        attacker_fs.assets.asat_kinetic -= 1
        self.debris_level = min(self.debris_level + 0.1 * nodes_hit, 1.0)
        self._prev_turn_ops.append("kinetic_strike")
        attacker_fs.disruption_score += nodes_hit * 5

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
            self.debris_level = min(self.debris_level + 0.05 * nodes_hit, 1.0)
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
            self.debris_level = min(self.debris_level + 0.1 * nodes_hit, 1.0)
            self._turn_log.append(
                f"[RETALIATION-KINETIC] {attacker_fs.name} kinetic strike on "
                f"{target_fs.name} ({regime.upper()}): {nodes_hit} nodes destroyed"
            )
            attacker_fs.disruption_score += nodes_hit * 5
            self._prev_turn_ops.append("kinetic_strike")

    def _apply_event_effect(self, event: CrisisEvent):
        if event.event_type == "asat_test":
            self.debris_level = min(self.debris_level + 0.08, 1.0)
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

    async def _run_operations_phase(self, turn: int):
        # Resolve pending kinetic approaches from prior turn before new orders
        resolved = [a for a in self._pending_kinetic_approaches if a["declared_turn"] == turn - 1]
        for approach in resolved:
            self._resolve_kinetic_approach(approach)
        for a in resolved:
            self._pending_kinetic_approaches.remove(a)

        decisions = await self._collect_decisions(
            Phase.OPERATIONS,
            ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"]
        )

        self._turn_log = self._turn_log or []  # preserve kinetic approach log entries above
        self._prev_turn_ops = []
        self._coordination_bonuses = {}

        for fid, decision in decisions.items():
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
                    if mission == "intercept" and is_adversary and fs.assets.asat_kinetic > 0:
                        # Queue a kinetic strike — arrives next turn, detectable via SDA
                        self._pending_kinetic_approaches.append({
                            "attacker_fid": fid,
                            "target_fid": target_fid,
                            "declared_turn": turn,
                        })
                        self._turn_log.append(
                            f"{fs.name} dispatched kinetic interceptor toward "
                            f"{target_fs.name} (arrives turn {turn + 1})"
                        )
                    else:
                        self._prev_turn_ops.append("task_assets")
                        if target_fid and is_adversary:
                            self._turn_log.append(
                                f"{fs.name} tasked assets against {target_fs.name} (surveillance)"
                            )

                elif op.action_type == "gray_zone" and is_adversary:
                    if fs.assets.asat_deniable > 0:
                        result = self.sim.conflict_resolver.resolve_deniable_asat(
                            attacker_assets=fs.assets,
                            defender_sda_level=target_fs.sda_level(),
                        )
                        nodes_hit = min(result["nodes_destroyed"], target_fs.assets.leo_nodes)
                        target_fs.assets.leo_nodes -= nodes_hit
                        fs.assets.asat_deniable -= 1
                        self.debris_level = min(self.debris_level + 0.05 * nodes_hit, 1.0)
                        fs.disruption_score += nodes_hit * 5
                        self._prev_turn_ops.append("deniable_strike")
                        detected = result["detected"]
                        attributed = result["attributed"]
                        suffix = (
                            f" ({'attributed to ' + fs.name if attributed else 'detected, source unclear'})"
                            if detected else " (undetected)"
                        )
                        self._turn_log.append(
                            f"{fs.name} gray-zone op vs {target_fs.name}: "
                            f"{nodes_hit} nodes disrupted{suffix}"
                        )
                    elif fs.assets.ew_jammers > 0:
                        self._prev_turn_ops.append("gray_zone")
                        self._turn_log.append(
                            f"{fs.name} EW jamming ops against {target_fs.name}"
                        )
                    else:
                        self._prev_turn_ops.append("gray_zone")
                        self._turn_log.append(
                            f"{fs.name} attempted gray-zone ops against {target_fs.name} — no deniable assets"
                        )

                elif op.action_type == "coordinate" and target_fid:
                    self._prev_turn_ops.append("coordinate")
                    if is_ally:
                        # Loyalty pressure: under high tension, low-loyalty factions hedge
                        loyalty_factor = 1.0
                        if self.tension_level > 0.7 and fs.coalition_loyalty < 0.6:
                            loyalty_factor = 0.5
                        bonus = 0.1 * loyalty_factor
                        self._coordination_bonuses[fid] = (
                            self._coordination_bonuses.get(fid, 0.0) + bonus
                        )
                        self._coordination_bonuses[target_fid] = (
                            self._coordination_bonuses.get(target_fid, 0.0) + bonus
                        )
                        note = " (loyalty-degraded)" if loyalty_factor < 1.0 else ""
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

    def _build_turn_log_summary(self, turn: int) -> str:
        if not self._turn_log:
            return ""
        entries = "\n".join(f"  • {e}" for e in self._turn_log)
        summary = f"Turn {turn} operations:\n{entries}"
        if self.debris_level > 0:
            summary += f"\nCumulative debris field: {self.debris_level:.0%}"
        return summary

    async def _run_response_phase(self, turn: int):
        self._event_sda_malus = {}  # fresh each turn

        all_factions = list(self.faction_states.keys())
        events = self.event_library.generate_events(
            tension_level=self.tension_level,
            affected_factions=all_factions,
            turn=turn,
            prev_ops=self._prev_turn_ops,
        )
        for event in events:
            await self.audit.write_event(turn=turn, event=event)
            for agent in self.agents.values():
                agent.receive_event(event)
            if event.severity > 0.5:
                self.tension_level = min(self.tension_level + 0.1, 1.0)
            self._apply_event_effect(event)

        # Rebuild turn log summary to include event effects before response decisions
        self._turn_log_summary = self._build_turn_log_summary(turn)

        decisions = await self._collect_decisions(
            Phase.RESPONSE,
            ["escalate", "de_escalate", "retaliate", "emergency_reallocation", "public_statement"]
        )
        for fid, decision in decisions.items():
            if decision.response and decision.response.escalate:
                self.tension_level = min(self.tension_level + 0.15, 1.0)
                if decision.response.retaliate and decision.response.target_faction:
                    self._resolve_retaliation(fid, decision.response.target_faction)
            await self.audit.write_decision(turn=turn, decision=decision)

        # Rebuild summary again to include retaliation entries
        self._turn_log_summary = self._build_turn_log_summary(turn)

    def _update_faction_metrics(self):
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        total_leo = sum(a.leo_nodes for a in all_assets.values())

        for fid, fs in self.faction_states.items():
            # Deterrence: ASAT stockpile (10 pts) + SDA strength (50 pts) + coalition (20 pts)
            fs.deterrence_score = min(100.0,
                fs.assets.asat_kinetic * 10 +
                fs.sda_level() * 50 +
                (20.0 if fs.coalition_id else 0.0)
            )

            # Market share: this faction's LEO nodes as fraction of total
            fs.market_share = fs.assets.leo_nodes / total_leo if total_leo > 0 else 0.0

            # JFE: degrades with node loss vs initial position
            if fid in self._initial_assets:
                init = self._initial_assets[fid]
                meo_lost = max(0, init.meo_nodes - fs.assets.meo_nodes)
                geo_lost = max(0, init.geo_nodes - fs.assets.geo_nodes)
                leo_lost_frac = max(0, init.leo_nodes - fs.assets.leo_nodes) / max(init.leo_nodes, 1)
                jfe_loss = meo_lost * 0.10 + geo_lost * 0.15 + leo_lost_frac * 0.30
                fs.joint_force_effectiveness = max(0.0, 1.0 - jfe_loss)

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
