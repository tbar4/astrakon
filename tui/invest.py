# tui/invest.py
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt
from engine.state import InvestmentAllocation, GameStateSnapshot
from engine.simulation import InvestmentResolver

console = Console()

_CATEGORIES = [
    "r_and_d", "constellation", "meo_deployment", "geo_deployment",
    "cislunar_deployment", "launch_capacity", "commercial",
    "influence_ops", "education", "covert", "diplomacy",
]

_CATEGORY_LABELS = {
    "r_and_d":             "R&D",
    "constellation":       "Constellation (LEO)",
    "meo_deployment":      "MEO Deployment",
    "geo_deployment":      "GEO Deployment",
    "cislunar_deployment": "Cislunar",
    "launch_capacity":     "Launch Capacity",
    "commercial":          "Commercial",
    "influence_ops":       "Influence Ops",
    "education":           "Education",
    "covert":              "Covert",
    "diplomacy":           "Diplomacy",
}

_CATEGORY_COLORS = {
    "constellation": "green", "meo_deployment": "blue", "geo_deployment": "cyan",
    "cislunar_deployment": "bright_cyan", "covert": "red", "influence_ops": "yellow",
    "r_and_d": "magenta", "education": "magenta",
    "commercial": "white", "launch_capacity": "white", "diplomacy": "white",
}


def _output_str(cat: str, pts: int) -> str:
    if pts == 0:
        return "—"
    r = InvestmentResolver
    if cat == "constellation":
        return f"+{pts // r.CONSTELLATION_NODE_COST} LEO nodes"
    if cat == "meo_deployment":
        return f"+{pts // r.MEO_NODE_COST} MEO nodes"
    if cat == "geo_deployment":
        return f"+{pts // r.GEO_NODE_COST} GEO nodes"
    if cat == "cislunar_deployment":
        return f"+{pts // r.CISLUNAR_NODE_COST} cislunar nodes"
    if cat == "launch_capacity":
        return f"+{pts // r.LAUNCH_CAPACITY_COST} capacity"
    if cat == "influence_ops":
        return f"+{pts // r.EW_JAMMER_COST} EW jammers"
    if cat == "covert":
        return f"+{pts // r.ASAT_DENIABLE_COST} deniable ASAT"
    if cat == "r_and_d":
        return "deferred return T+3"
    if cat == "education":
        return "deferred return T+6"
    if cat == "commercial":
        return "revenue + influence"
    if cat == "diplomacy":
        return "coalition loyalty +"
    return "—"


def _budget_bar(allocated: float) -> Text:
    filled = min(20, max(0, round(allocated * 20)))
    bar = "█" * filled + "░" * (20 - filled)
    color = "red" if allocated > 1.0 else ("yellow" if allocated >= 0.8 else "green")
    t = Text()
    t.append(f"[ {bar} ]", style=color)
    t.append(f"  {allocated:.0%} allocated", style=color)
    return t


def _render_table(allocations: dict[str, float], budget: int) -> Table:
    table = Table(
        show_header=True, header_style="bold", box=None, padding=(0, 2),
        title=f"Investment Allocation — {budget} pts budget",
    )
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Category", min_width=22)
    table.add_column("Alloc", justify="right", width=7)
    table.add_column("Pts", justify="right", width=5)
    table.add_column("Output", min_width=26)
    for i, cat in enumerate(_CATEGORIES, 1):
        frac = allocations[cat]
        pts = round(frac * budget)
        color = _CATEGORY_COLORS.get(cat, "white")
        style = color if frac > 0 else "dim"
        table.add_row(
            str(i), _CATEGORY_LABELS.get(cat, cat),
            f"{frac:.0%}" if frac > 0 else "—",
            str(pts) if pts > 0 else "—",
            _output_str(cat, pts),
            style=style,
        )
    return table


def collect_investment(budget: int, snapshot: GameStateSnapshot) -> InvestmentAllocation:
    allocations: dict[str, float] = {cat: 0.0 for cat in _CATEGORIES}

    def _renderable():
        total = sum(allocations.values())
        pts_remaining = round((1.0 - total) * budget)
        bar = _budget_bar(total)
        bar.append(f"  |  {pts_remaining} pts remaining", style="dim")
        return Group(bar, _render_table(allocations, budget))

    live = Live(get_renderable=_renderable, console=console, transient=True, auto_refresh=False)
    live.start()
    live.refresh()

    try:
        while True:
            live.stop()
            raw = Prompt.ask("\n> Row to edit (1–11), or 'done'", console=console).strip().lower()
            if raw == "done":
                break
            try:
                idx = int(raw) - 1
                if not (0 <= idx < len(_CATEGORIES)):
                    raise IndexError
                cat = _CATEGORIES[idx]
            except (ValueError, IndexError):
                console.print("[red]Enter a row number 1–11, or 'done'.[/red]")
                live.start()
                live.refresh()
                continue

            remaining_frac = round(1.0 - sum(v for k, v in allocations.items() if k != cat), 6)
            current_pts = round(allocations[cat] * budget)
            remaining_pts = round(remaining_frac * budget)
            label = _CATEGORY_LABELS.get(cat, cat)
            pts_str = Prompt.ask(
                f"  [bold]{label}[/bold] — points to allocate"
                f" (currently [cyan]{current_pts}[/cyan] pts,"
                f" up to [green]{remaining_pts}[/green] pts available)",
                default=str(current_pts),
                console=console,
            )
            try:
                new_pts = int(pts_str)
                if new_pts < 0:
                    raise ValueError
            except ValueError:
                console.print("[red]Enter a whole number of points (e.g. 40).[/red]")
                live.start()
                live.refresh()
                continue
            if new_pts > remaining_pts:
                console.print(f"[yellow]Capped to {remaining_pts} pts (remaining budget).[/yellow]")
                new_pts = remaining_pts
            allocations[cat] = round(max(0.0, new_pts / budget), 6)
            live.start()
            live.refresh()
    finally:
        live.stop()

    rationale = Prompt.ask("\n  Strategic rationale", console=console)
    return InvestmentAllocation(**allocations, rationale=rationale)
