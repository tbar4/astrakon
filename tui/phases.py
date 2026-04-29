# tui/phases.py
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from engine.state import (
    Phase, OperationalAction, ResponseDecision, GameStateSnapshot, Recommendation,
)

console = Console()


# ── Situation display ────────────────────────────────────────────────────────

def display_situation(snapshot: GameStateSnapshot) -> None:
    fs = snapshot.faction_state
    a = fs.assets

    # Assets table
    assets_table = Table(
        title=f"{fs.name} — Assets", show_header=True,
        header_style="bold", box=None, padding=(0, 2),
    )
    assets_table.add_column("Asset", min_width=18)
    assets_table.add_column("Count", justify="right")
    assets_table.add_column("Dom. Weight", justify="right", style="dim")
    for label, val, weight in [
        ("LEO Nodes",       a.leo_nodes,       "1×"),
        ("MEO Nodes",       a.meo_nodes,       "2×"),
        ("GEO Nodes",       a.geo_nodes,       "3×"),
        ("Cislunar Nodes",  a.cislunar_nodes,  "4×"),
        ("ASAT Kinetic",    a.asat_kinetic,    "—"),
        ("ASAT Deniable",   a.asat_deniable,   "—"),
        ("EW Jammers",      a.ew_jammers,      "—"),
        ("SDA Sensors",     a.sda_sensors,     "—"),
        ("Launch Capacity", a.launch_capacity, "—"),
    ]:
        assets_table.add_row(label, str(val), weight)
    console.print(assets_table)

    # Key metrics line
    jfe = fs.joint_force_effectiveness
    jfe_color = "green" if jfe >= 0.8 else ("yellow" if jfe >= 0.5 else "red")
    console.print(
        f"  Budget: [green]{fs.current_budget}[/green] pts  │  "
        f"Deterrence: [cyan]{fs.deterrence_score:.0f}[/cyan]  │  "
        f"Mkt Share: [cyan]{fs.market_share:.1%}[/cyan]  │  "
        f"JFE: [{jfe_color}]{jfe:.0%}[/{jfe_color}]"
    )

    # Adversary estimates (expanded — MEO/GEO/cislunar columns)
    if snapshot.adversary_estimates:
        adv_table = Table(
            title="Adversary Intel (SDA-filtered)", show_header=True,
            header_style="bold", box=None, padding=(0, 2),
        )
        adv_table.add_column("Faction")
        adv_table.add_column("LEO", justify="right")
        adv_table.add_column("MEO", justify="right")
        adv_table.add_column("GEO", justify="right")
        adv_table.add_column("Cislunar", justify="right")
        adv_table.add_column("ASAT-K", justify="right")
        for fid, est in snapshot.adversary_estimates.items():
            adv_table.add_row(
                fid,
                str(est.leo_nodes), str(est.meo_nodes),
                str(est.geo_nodes), str(est.cislunar_nodes),
                str(est.asat_kinetic),
            )
        console.print(adv_table)

    # Incoming threats
    if snapshot.incoming_threats:
        console.print()
        for threat in snapshot.incoming_threats:
            console.print(
                f"  [bold red]⚠ KINETIC APPROACH from {threat['attacker']}"
                f" (declared T{threat['declared_turn']}) — IMPACT IMMINENT[/bold red]"
            )


# ── Advisor recommendation display ───────────────────────────────────────────

def display_recommendation(rec: Recommendation, phase: Phase) -> None:
    content = Text()

    if phase == Phase.INVEST and rec.top_recommendation.investment:
        inv = rec.top_recommendation.investment
        fields = [
            "r_and_d", "constellation", "meo_deployment", "geo_deployment",
            "cislunar_deployment", "launch_capacity", "commercial",
            "influence_ops", "education", "covert", "diplomacy",
        ]
        allocs = {f: getattr(inv, f) for f in fields if getattr(inv, f) > 0}
        for cat, frac in sorted(allocs.items(), key=lambda x: x[1], reverse=True)[:3]:
            filled = round(frac * 10)
            bar = "█" * filled + "░" * (10 - filled)
            content.append(f"  {cat:<24} {frac:.0%}  {bar}\n")

    elif phase == Phase.OPERATIONS and rec.top_recommendation.operations:
        op = rec.top_recommendation.operations[0]
        content.append(f"  {op.action_type}", style="bold")
        if op.target_faction:
            content.append(f" → {op.target_faction}")
        content.append("\n")

    elif phase == Phase.RESPONSE and rec.top_recommendation.response:
        resp = rec.top_recommendation.response
        if resp.escalate:
            content.append("  ESCALATE", style="bold red")
            if resp.retaliate and resp.target_faction:
                content.append(f" + retaliate vs {resp.target_faction}", style="red")
        else:
            content.append("  Stand down — de-escalate", style="green")
        content.append("\n")

    else:
        content.append("  [dim]No structured recommendation available.[/dim]\n")

    content.append(f"\n  {rec.strategic_rationale}", style="dim")
    console.print(Panel(
        content,
        title="[bold yellow]AI ADVISOR RECOMMENDATION[/bold yellow]",
        border_style="yellow",
    ))


# ── Operations collector ─────────────────────────────────────────────────────

_OPS_DESCRIPTIONS = {
    "task_assets":   ("blue",    "Direct satellites/ASATs: surveillance, patrol, or kinetic intercept"),
    "coordinate":    ("cyan",    "Synchronize with coalition ally (+SDA bonus, loyalty-pressure applies)"),
    "gray_zone":     ("yellow",  "Deniable activity — uses ASAT-deniable or EW jamming"),
    "alliance_move": ("dim",     "Diplomatic-military signal: reinforce partner or shift alignment"),
    "signal":        ("dim",     "Deliberate public or back-channel communication"),
}

_TASK_MISSIONS = {
    "sda_sweep": "Sweep for adversary assets — intelligence only",
    "patrol":    "Patrol contested orbital band — shows resolve",
    "intercept": "Dispatch kinetic interceptor — arrives NEXT TURN, visible to SDA ≥ 30%",
}


def collect_operations(snapshot: GameStateSnapshot) -> list[OperationalAction]:
    menu = Table(
        title="Operational Actions", show_header=True,
        header_style="bold", box=None, padding=(0, 2),
    )
    menu.add_column("Action", min_width=14)
    menu.add_column("What it does")
    for action, (color, desc) in _OPS_DESCRIPTIONS.items():
        menu.add_row(f"[{color}]{action}[/{color}]", desc)
    console.print(menu)
    console.print("\n[bold]OPERATIONS PHASE[/bold]\n")

    action_type = Prompt.ask(
        "Action type",
        choices=list(_OPS_DESCRIPTIONS.keys()),
        default="task_assets",
    )
    target = Prompt.ask("Target faction (leave blank for none)", default="")

    params: dict = {}
    if action_type == "task_assets":
        mission_menu = Table(show_header=True, header_style="dim", box=None, padding=(0, 2))
        mission_menu.add_column("Mission")
        mission_menu.add_column("Effect")
        for m, d in _TASK_MISSIONS.items():
            mission_menu.add_row(m, d)
        console.print(mission_menu)
        mission = Prompt.ask("  Mission", choices=list(_TASK_MISSIONS.keys()), default="sda_sweep")
        params = {"mission": mission}

    rationale = Prompt.ask("Rationale")
    return [OperationalAction(
        action_type=action_type,
        target_faction=target if target else None,
        parameters=params,
        rationale=rationale,
    )]


# ── Response collector ───────────────────────────────────────────────────────

def collect_response(snapshot: GameStateSnapshot) -> ResponseDecision:
    if snapshot.turn_log_summary:
        console.print(Panel(
            f"[dim]{snapshot.turn_log_summary}[/dim]",
            title="[dim]This turn's events[/dim]",
            border_style="dim",
        ))

    response_table = Table(
        title="Response Options", show_header=True,
        header_style="bold", box=None, padding=(0, 2),
    )
    response_table.add_column("Option", min_width=16)
    response_table.add_column("Effect")
    for option, desc in [
        ("Escalate",         "Raise crisis level — increases tension, unlocks harder actions next turn"),
        ("Retaliate",        "Target a specific faction with punitive action (requires escalation)"),
        ("Public statement", "Shape the narrative — can reduce tension or signal resolve"),
        ("De-escalate",      "Absorb crisis, preserve coalition stability, accept short-term cost"),
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
        target_faction=target, public_statement=statement, rationale=rationale,
    )
