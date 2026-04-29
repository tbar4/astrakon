from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, OperationalAction,
    ResponseDecision, GameStateSnapshot, Recommendation
)

console = Console()


def _display_snapshot(snapshot: GameStateSnapshot):
    fs = snapshot.faction_state
    console.print(f"\n[bold cyan]TURN {snapshot.turn} — {snapshot.phase.value.upper()} PHASE[/bold cyan]")
    console.print(f"Faction: [bold]{fs.name}[/bold] | Budget: [green]{fs.current_budget}[/green] pts")

    assets_table = Table(title="Your Assets", show_header=True)
    assets_table.add_column("Asset Type")
    assets_table.add_column("Count", justify="right")
    a = fs.assets
    for name, val in [
        ("LEO Nodes", a.leo_nodes), ("MEO Nodes", a.meo_nodes), ("GEO Nodes", a.geo_nodes),
        ("ASAT Kinetic", a.asat_kinetic), ("ASAT Deniable", a.asat_deniable),
        ("EW Jammers", a.ew_jammers), ("SDA Sensors", a.sda_sensors),
        ("Launch Capacity", a.launch_capacity),
    ]:
        assets_table.add_row(name, str(val))
    console.print(assets_table)

    if snapshot.adversary_estimates:
        adv_table = Table(title="Adversary Estimates (SDA-filtered)", show_header=True)
        adv_table.add_column("Faction")
        adv_table.add_column("LEO", justify="right")
        adv_table.add_column("ASAT-K", justify="right")
        adv_table.add_column("Deniable", justify="right")
        for fid, est in snapshot.adversary_estimates.items():
            adv_table.add_row(fid, str(est.leo_nodes), str(est.asat_kinetic), str(est.asat_deniable))
        console.print(adv_table)


def _display_recommendation(rec: Recommendation):
    console.print(Panel(
        f"[bold yellow]AI ADVISOR RECOMMENDATION[/bold yellow]\n\n"
        f"{rec.strategic_rationale}\n\n"
        f"[dim]Top suggestion: {rec.top_recommendation.model_dump_json(indent=2)}[/dim]",
        border_style="yellow"
    ))


_INVEST_DESCRIPTIONS = {
    "r_and_d":         "Tech tree advancement — deferred return in 3 turns",
    "constellation":   "Deploy LEO nodes immediately (5 pts/node)",
    "launch_capacity": "Increase launch throughput (15 pts/unit)",
    "commercial":      "Commercial partnerships — revenue and soft influence",
    "influence_ops":   "EW jammers and information operations (12 pts/jammer)",
    "education":       "Workforce development — deferred return in 6 turns",
    "covert":          "Deniable ASAT capability (25 pts/unit)",
    "diplomacy":       "Coalition cohesion and treaty leverage",
}


def _collect_investment() -> InvestmentAllocation:
    menu = Table(title="Investment Categories", show_header=True, header_style="bold")
    menu.add_column("#", justify="right", style="dim")
    menu.add_column("Category")
    menu.add_column("Effect")
    for i, (cat, desc) in enumerate(_INVEST_DESCRIPTIONS.items(), 1):
        menu.add_row(str(i), cat, desc)
    console.print(menu)
    console.print("[bold]INVESTMENT ALLOCATION[/bold] (fractions, must sum to ≤ 1.0)\n")

    categories = list(_INVEST_DESCRIPTIONS.keys())
    values = {}
    remaining = 1.0
    for cat in categories:
        if remaining <= 0.001:
            values[cat] = 0.0
            continue
        val = float(Prompt.ask(f"  {cat} (remaining: {remaining:.2f})", default="0.0"))
        val = min(val, remaining)
        values[cat] = round(val, 3)
        remaining -= val
    rationale = Prompt.ask("  Rationale for this allocation")
    return InvestmentAllocation(**values, rationale=rationale)


_OPS_DESCRIPTIONS = {
    "task_assets":    "Direct your satellites/ASATs to a specific mission (surveillance, patrol, intercept)",
    "coordinate":     "Synchronize operations with a coalition ally this turn",
    "gray_zone":      "Conduct deniable activity — jamming, spoofing, or proximity ops below threshold",
    "alliance_move":  "Diplomatic-military signal: reinforce a partner, extend deterrence, or shift alignment",
    "signal":         "Deliberate public or back-channel communication to shape adversary expectations",
}


def _collect_operations() -> list[OperationalAction]:
    menu = Table(title="Operational Actions", show_header=True, header_style="bold")
    menu.add_column("Action")
    menu.add_column("What it does")
    for action, desc in _OPS_DESCRIPTIONS.items():
        menu.add_row(action, desc)
    console.print(menu)
    console.print("\n[bold]OPERATIONS PHASE[/bold]\n")

    actions = list(_OPS_DESCRIPTIONS.keys())
    action_type = Prompt.ask("Action type", choices=actions, default="task_assets")
    target = Prompt.ask("Target faction (leave blank for none)", default="")
    rationale = Prompt.ask("Rationale")
    return [OperationalAction(
        action_type=action_type,
        target_faction=target if target else None,
        rationale=rationale,
    )]


def _collect_response() -> ResponseDecision:
    response_table = Table(title="Response Options", show_header=True, header_style="bold")
    response_table.add_column("Option")
    response_table.add_column("Effect")
    for option, desc in [
        ("Escalate",         "Raise the crisis level — increases board tension, unlocks harder actions next turn"),
        ("Retaliate",        "Target a specific faction with a punitive action (requires escalation)"),
        ("Public statement", "Shape the narrative — can reduce tension or signal resolve to all actors"),
        ("De-escalate",      "Say no to both — absorb the crisis, preserve coalition stability, accept short-term cost"),
    ]:
        response_table.add_row(option, desc)
    console.print(response_table)
    console.print("\n[bold]RESPONSE PHASE[/bold]\n")

    escalate = Confirm.ask("Escalate?", default=False)
    retaliate = False
    target = None
    if escalate:
        retaliate = Confirm.ask("Retaliate against a specific faction?", default=False)
        if retaliate:
            target = Prompt.ask("Target faction ID")
    statement = Prompt.ask("Public statement (leave blank to skip)", default="")
    rationale = Prompt.ask("Rationale")
    return ResponseDecision(
        escalate=escalate, retaliate=retaliate,
        target_faction=target, public_statement=statement, rationale=rationale
    )


class HumanAgent(AgentInterface):
    def __init__(self, advisor: Optional[AgentInterface] = None):
        super().__init__()
        self._advisor = advisor

    async def submit_decision(self, phase: Phase) -> Decision:
        if self._last_snapshot:
            _display_snapshot(self._last_snapshot)

        if self._advisor and self._last_snapshot:
            rec = await self._advisor.get_recommendation(phase)
            if rec:
                _display_recommendation(rec)
                if Confirm.ask("Accept advisor recommendation?", default=False):
                    return rec.top_recommendation

        if phase == Phase.INVEST:
            alloc = _collect_investment()
            return Decision(phase=phase, faction_id=self.faction_id, investment=alloc)

        if phase == Phase.OPERATIONS:
            ops = _collect_operations()
            return Decision(phase=phase, faction_id=self.faction_id, operations=ops)

        resp = _collect_response()
        return Decision(phase=phase, faction_id=self.faction_id, response=resp)
