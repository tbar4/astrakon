# tui/summary.py
import json
from typing import Optional, Any
from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from engine.state import FactionState, CoalitionState

console = Console()

RenderableType = Any  # rich.console.RenderableType


class TurnSummary:
    def __init__(
        self,
        turn: int,
        total_turns: int,
        events: list[dict],
        turn_log: list[str],
        decisions: list[dict],
        faction_states: dict[str, FactionState],
        coalition_states: dict[str, CoalitionState],
        coalition_colors: dict[str, str],
        dominance: dict[str, float],
        victory_threshold: float,
    ):
        self.turn = turn
        self.total_turns = total_turns
        self.events = events
        self.turn_log = turn_log
        self.decisions = decisions
        self.faction_states = faction_states
        self.coalition_states = coalition_states
        self.coalition_colors = coalition_colors
        self.dominance = dominance
        self.victory_threshold = victory_threshold

    def display(self) -> None:
        sections = [s for s in [
            self._section_crisis(),
            self._section_ops_log(),
            self._section_observed_ops(),
            self._section_dominance(),
            self._section_metrics(),
        ] if s is not None]

        if not sections:
            console.print("[dim]No intelligence to report this turn.[/dim]")
            return

        n = len(sections)
        idx = 0
        while True:
            console.print(f"\n[bold cyan]══ END OF TURN {self.turn} — INTELLIGENCE SUMMARY ══[/bold cyan]")
            console.print(sections[idx])
            console.print(self._nav_bar(idx, n))

            key = Prompt.ask("", default="", console=console).strip().lower()
            if key == "b" and idx > 0:
                idx -= 1
            elif key == "q":
                break
            elif idx < n - 1:
                idx += 1
            else:
                break  # last section, Enter pressed

    def _nav_bar(self, idx: int, n: int) -> str:
        back = "[b] back" if idx > 0 else "[dim][b] back[/dim]"
        if idx == n - 1:
            next_label = (
                f"[Enter] continue to Turn {self.turn + 1}"
                if self.turn < self.total_turns else "[Enter] finish"
            )
        else:
            next_label = "[Enter] next"
        return f"\n  [dim]{next_label}  {back}  [q] skip to end  page {idx+1}/{n}[/dim]"

    def _section_crisis(self) -> Optional[RenderableType]:
        if not self.events:
            return None
        content = Text()
        for ev in self.events:
            severity = ev["severity"]
            filled = min(5, max(0, round(severity * 5)))
            bar = "█" * filled + "░" * (5 - filled)
            content.append(f"  {bar} {ev['event_type'].upper()}\n", style="yellow")
            content.append(f"       {ev['description']}\n")
        return Panel(content, title="[bold yellow]CRISIS EVENTS[/bold yellow]", border_style="yellow")

    def _section_ops_log(self) -> Optional[RenderableType]:
        if not self.turn_log:
            return None
        content = Text()
        for entry in self.turn_log:
            if "[KINETIC]" in entry or "[RETALIATION" in entry:
                content.append(f"  {entry}\n", style="bold red")
            elif "disrupted" in entry or "gray-zone" in entry.lower() or "EW jamming" in entry:
                content.append(f"  {entry}\n", style="yellow")
            elif "coordinated" in entry:
                content.append(f"  {entry}\n", style="cyan")
            else:
                content.append(f"  {entry}\n", style="dim")
        return Panel(content, title="[bold]OPERATIONAL LOG[/bold]", border_style="dim")

    def _section_observed_ops(self) -> Optional[RenderableType]:
        _PUBLIC = {"signal", "alliance_move"}
        _OBSERVABLE = {"task_assets"}
        ops_rows, resp_rows = [], []

        for d in self.decisions:
            fid = d["faction_id"]
            name = self.faction_states[fid].name
            data = json.loads(d["decision_json"])

            if d["phase"] == "operations":
                for op in (data.get("operations") or []):
                    action = op.get("action_type", "")
                    if action in _PUBLIC:
                        ops_rows.append((name, action, op.get("rationale", "—")))
                    elif action in _OBSERVABLE:
                        ops_rows.append((name, action, "[dim](details classified)[/dim]"))

            elif d["phase"] == "response":
                resp = data.get("response") or {}
                if resp.get("escalate"):
                    posture = "[bold red]ESCALATED[/bold red]"
                    if resp.get("retaliate") and resp.get("target_faction"):
                        tfid = resp["target_faction"]
                        tname = self.faction_states.get(
                            tfid, type("_", (), {"name": tfid})()
                        ).name
                        posture += f" → retaliated vs {tname}"
                else:
                    posture = "[green]stood down[/green]"
                statement = resp.get("public_statement") or "[dim]—[/dim]"
                resp_rows.append((name, posture, statement))

        if not ops_rows and not resp_rows:
            return None

        renderables = []
        if ops_rows:
            t = Table(title="OBSERVED OPERATIONS", show_header=True, header_style="bold", box=None, padding=(0, 2))
            t.add_column("Faction")
            t.add_column("Action")
            t.add_column("Statement / Details")
            for row in ops_rows:
                t.add_row(*row)
            renderables.append(t)

        if resp_rows:
            t = Table(title="FACTION RESPONSES", show_header=True, header_style="bold", box=None, padding=(0, 2))
            t.add_column("Faction")
            t.add_column("Posture")
            t.add_column("Public Statement")
            for row in resp_rows:
                t.add_row(*row)
            renderables.append(t)

        return Group(*renderables)

    def _section_dominance(self) -> Optional[RenderableType]:
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Coalition", min_width=12)
        table.add_column("Dominance", justify="right")
        table.add_column("Bar")
        table.add_column("vs. Threshold", justify="right")
        for cid in self.coalition_states:
            dom = self.dominance.get(cid, 0.0)
            color = self.coalition_colors.get(cid, "white")
            filled = min(16, max(0, round(dom * 16)))
            bar = f"[{color}]{'█'*filled}{'░'*(16-filled)}[/{color}]"
            gap = dom - self.victory_threshold
            gap_color = "green" if gap >= 0 else "red"
            table.add_row(
                cid,
                f"[{color}]{dom:.1%}[/{color}]",
                bar,
                f"[{gap_color}]{gap:+.1%}[/{gap_color}]",
            )
        return Panel(table, title="[bold]ORBITAL DOMINANCE[/bold]", border_style="cyan")

    def _section_metrics(self) -> Optional[RenderableType]:
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Faction")
        table.add_column("Deterrence", justify="right")
        table.add_column("Disruption", justify="right")
        table.add_column("Mkt Share", justify="right")
        table.add_column("JFE", justify="right")
        for fid, fs in self.faction_states.items():
            jfe = fs.joint_force_effectiveness
            jfe_color = "green" if jfe >= 0.8 else ("yellow" if jfe >= 0.5 else "red")
            table.add_row(
                fs.name,
                f"{fs.deterrence_score:.0f}",
                f"{fs.disruption_score:.0f}",
                f"{fs.market_share:.1%}",
                f"[{jfe_color}]{jfe:.0%}[/{jfe_color}]",
            )
        return Panel(table, title="[bold]FACTION METRICS[/bold]", border_style="dim")
