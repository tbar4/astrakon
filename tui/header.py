# tui/header.py
from rich.console import Console

console = Console()

_BLOCK_FULL = "█"
_BLOCK_EMPTY = "░"
_BAR_WIDTH = 10


def _dominance_bar(value: float, color: str) -> str:
    filled = round(min(max(value, 0.0), 1.0) * _BAR_WIDTH)
    return f"[{color}]{''.join([_BLOCK_FULL]*filled + [_BLOCK_EMPTY]*(_BAR_WIDTH-filled))}[/{color}]"


def _tension_color(tension: float) -> str:
    if tension >= 0.7:
        return "bold red"
    if tension >= 0.4:
        return "yellow"
    return "green"


class GameHeader:
    def __init__(self, scenario_name: str, total_turns: int):
        self._scenario_name = scenario_name
        self._total_turns = total_turns

    def print_phase_banner(
        self,
        turn: int,
        tension: float,
        debris: float,
        coalition_dominance: dict[str, float],
        coalition_colors: dict[str, str],
        phase: str,
    ) -> None:
        dom_parts = []
        for cid, dom in coalition_dominance.items():
            color = coalition_colors.get(cid, "white")
            bar = _dominance_bar(dom, color)
            dom_parts.append(f"{cid} {bar} [{color}]{dom:.1%}[/{color}]")
        dom_str = "  │  ".join(dom_parts)

        tc = _tension_color(tension)
        title = (
            f"[bold cyan]ASTRAKON[/bold cyan]  [dim]{self._scenario_name}[/dim]"
            f"  Turn [bold]{turn}[/bold][dim]/{self._total_turns}[/dim]"
            f"  [dim]·[/dim]  [bold]{phase.upper()}[/bold]"
            f"  [dim]│[/dim]  {dom_str}"
            f"  [dim]│[/dim]  TENSION [{tc}]{tension:.0%}[/{tc}]"
            f"  DEBRIS [orange3]{debris:.0%}[/orange3]"
        )
        console.rule(title, style="cyan")


class NullGameHeader:
    """No-op header for AI-only games — callers never need to check for None."""
    def print_phase_banner(self, *args, **kwargs) -> None:
        pass
