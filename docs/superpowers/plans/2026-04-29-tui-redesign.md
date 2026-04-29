# TUI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `tui/` module that replaces all display/input logic in `agents/human.py` and `engine/referee.py` with a phase banner, a live-updating investment table, richer phase collectors, and a paged end-of-turn intelligence summary with bidirectional navigation.

**Architecture:** Five new files under `tui/` (`header.py`, `invest.py`, `phases.py`, `summary.py`, `__init__.py`). Three existing files are modified (`agents/human.py`, `engine/referee.py`, `main.py`). All changes are display/input only — no game logic touched, all existing tests continue to pass.

**Tech Stack:** Python, Rich (`Live`, `Table`, `Panel`, `Rule`, `Prompt`, `Confirm`, `Console`, `Group`, `Text`), existing `engine.state` and `engine.simulation` types.

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `tui/__init__.py` | Create | Empty package marker |
| `tui/header.py` | Create | `GameHeader` (phase banner printer) + `NullGameHeader` (no-op) |
| `tui/invest.py` | Create | `collect_investment()` — full 11-row table with Live in-place update |
| `tui/phases.py` | Create | `display_situation()`, `collect_operations()`, `collect_response()`, `display_recommendation()` |
| `tui/summary.py` | Create | `TurnSummary` — paged end-of-turn briefing with fwd/back nav |
| `agents/human.py` | Modify | Delegate all display/input to `tui/`; add `header` param |
| `engine/referee.py` | Modify | Add `header` param; call phase banner; delegate summary to `TurnSummary` |
| `main.py` | Modify | Instantiate `GameHeader`; wire into referee and human agents |

---

## Task 1: Scaffold `tui/` package and `tui/header.py`

**Files:**
- Create: `tui/__init__.py`
- Create: `tui/header.py`

- [ ] **Step 1: Create the empty package marker**

```python
# tui/__init__.py
```

- [ ] **Step 2: Create `tui/header.py`**

```python
# tui/header.py
from rich.console import Console

console = Console()

_BLOCK_FULL = "█"
_BLOCK_EMPTY = "░"
_BAR_WIDTH = 10


def _dominance_bar(value: float, color: str) -> str:
    filled = round(value * _BAR_WIDTH)
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
```

- [ ] **Step 3: Run existing tests to confirm nothing broke**

```bash
source venv/bin/activate && python -m pytest tests/ -q
```

Expected: `36 passed`

- [ ] **Step 4: Commit**

```bash
git add tui/__init__.py tui/header.py
git commit -m "feat: add tui/header.py — GameHeader phase banner and NullGameHeader no-op"
```

---

## Task 2: `tui/invest.py` — Investment allocation table with Live in-place update

**Files:**
- Create: `tui/invest.py`

The investment table wraps the edit loop in `rich.live.Live(transient=True)`. `transient=True` means when `live.stop()` is called the live region is erased from the terminal (no stacking). `start()` and `stop()` are both idempotent — safe to call multiple times. The sequence per edit: Live renders table → `live.stop()` erases it → prompt appears → user types → `live.start()` re-renders table below the prompt with updated values.

Cost constants come from `InvestmentResolver` class attributes in `engine/simulation.py`:
- `InvestmentResolver.CONSTELLATION_NODE_COST = 5`
- `InvestmentResolver.MEO_NODE_COST = 12`
- `InvestmentResolver.GEO_NODE_COST = 25`
- `InvestmentResolver.CISLUNAR_NODE_COST = 40`
- `InvestmentResolver.LAUNCH_CAPACITY_COST = 15`
- `InvestmentResolver.ASAT_DENIABLE_COST = 25`
- `InvestmentResolver.EW_JAMMER_COST = 12`

- [ ] **Step 1: Create `tui/invest.py`**

```python
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
    filled = round(allocated * 20)
    bar = "█" * filled + "░" * (20 - filled)
    color = "red" if allocated >= 1.0 else ("yellow" if allocated >= 0.8 else "green")
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
            str(i), cat,
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
            raw = Prompt.ask("\n> edit # (or 'done')", console=console).strip().lower()
            if raw == "done":
                break
            try:
                idx = int(raw) - 1
                if not (0 <= idx < len(_CATEGORIES)):
                    raise IndexError
                cat = _CATEGORIES[idx]
            except (ValueError, IndexError):
                console.print("[red]Enter a number 1–11 or 'done'.[/red]")
                live.start()
                live.refresh()
                continue

            remaining = round(1.0 - sum(v for k, v in allocations.items() if k != cat), 6)
            val_str = Prompt.ask(
                f"  {cat} (current: {allocations[cat]:.0%}, remaining: {remaining:.0%})",
                default=f"{allocations[cat]:.3f}",
                console=console,
            )
            try:
                val = float(val_str)
            except ValueError:
                console.print("[red]Enter a decimal fraction e.g. 0.30[/red]")
                live.start()
                live.refresh()
                continue
            if val > remaining + 0.001:
                console.print(f"[yellow]Capped to {remaining:.3f} (remaining budget).[/yellow]")
                val = remaining
            allocations[cat] = round(max(0.0, val), 3)
            live.start()
            live.refresh()
    finally:
        live.stop()

    rationale = Prompt.ask("\n  Strategic rationale", console=console)
    return InvestmentAllocation(**allocations, rationale=rationale)
```

- [ ] **Step 2: Run existing tests**

```bash
source venv/bin/activate && python -m pytest tests/ -q
```

Expected: `36 passed`

- [ ] **Step 3: Commit**

```bash
git add tui/invest.py
git commit -m "feat: add tui/invest.py — live investment table with free non-destructive editing"
```

---

## Task 3: `tui/phases.py` — Situation display, phase collectors, advisor panel

**Files:**
- Create: `tui/phases.py`

This file replaces four functions from `agents/human.py`: `_display_snapshot`, `_collect_operations`, `_collect_response`, `_display_recommendation`. It also adds the expanded `display_situation` (with MEO/GEO/cislunar in adversary table and incoming threats panel).

- [ ] **Step 1: Create `tui/phases.py`**

```python
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

    # Last-turn context
    if snapshot.turn_log_summary:
        console.print(f"\n[dim]Last turn: {snapshot.turn_log_summary}[/dim]")


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
```

- [ ] **Step 2: Run existing tests**

```bash
source venv/bin/activate && python -m pytest tests/ -q
```

Expected: `36 passed`

- [ ] **Step 3: Commit**

```bash
git add tui/phases.py
git commit -m "feat: add tui/phases.py — situation display, phase collectors, advisor panel"
```

---

## Task 4: `tui/summary.py` — Paged end-of-turn intelligence summary

**Files:**
- Create: `tui/summary.py`

Each `_section_*` method returns a Rich renderable (`Panel`, `Table`, `Group`) or `None` if empty. The nav loop builds the section list dynamically (skipping `None`), prints each section directly, and re-prints on backward navigation. `Prompt.ask("...", default="")` is used instead of raw `input()` to prevent character echo.

- [ ] **Step 1: Create `tui/summary.py`**

```python
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
            bar = "█" * round(severity * 5) + "░" * (5 - round(severity * 5))
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
            filled = round(dom * 16)
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
```

- [ ] **Step 2: Run existing tests**

```bash
source venv/bin/activate && python -m pytest tests/ -q
```

Expected: `36 passed`

- [ ] **Step 3: Commit**

```bash
git add tui/summary.py
git commit -m "feat: add tui/summary.py — paged end-of-turn briefing with fwd/back nav"
```

---

## Task 5: Refactor `agents/human.py`

**Files:**
- Modify: `agents/human.py`

Replace all module-level display/input functions with imports from `tui/`. Add `header` param to `HumanAgent.__init__`. The `submit_decision` method calls `display_situation`, the phase collector, and `display_recommendation` in the correct order. All existing imports and `HumanAgent.is_human` stay unchanged.

- [ ] **Step 1: Replace `agents/human.py` entirely**

```python
# agents/human.py
from typing import Optional
from rich.prompt import Confirm
from agents.base import AgentInterface
from engine.state import Phase, Decision
from tui.header import NullGameHeader
from tui.phases import display_situation, display_recommendation, collect_operations, collect_response
from tui.invest import collect_investment


class HumanAgent(AgentInterface):
    is_human: bool = True

    def __init__(self, advisor: Optional[AgentInterface] = None, header=None):
        super().__init__()
        self._advisor = advisor
        self._header = header if header is not None else NullGameHeader()

    async def submit_decision(self, phase: Phase) -> Decision:
        # Guard: receive_state should always be called first, but fall back if not
        if self._last_snapshot is None:
            from agents.rule_based import MahanianAgent
            fallback = MahanianAgent()
            fallback.faction_id = self.faction_id
            return await fallback.submit_decision(phase)

        display_situation(self._last_snapshot)

        if self._advisor:
            rec = await self._advisor.get_recommendation(phase)
            if rec:
                display_recommendation(rec, phase)
                if Confirm.ask("Accept advisor recommendation?", default=False):
                    return rec.top_recommendation

        if phase == Phase.INVEST:
            alloc = collect_investment(
                budget=self._last_snapshot.faction_state.current_budget,
                snapshot=self._last_snapshot,
            )
            return Decision(phase=phase, faction_id=self.faction_id, investment=alloc)

        if phase == Phase.OPERATIONS:
            ops = collect_operations(self._last_snapshot)
            return Decision(phase=phase, faction_id=self.faction_id, operations=ops)

        resp = collect_response(self._last_snapshot)
        return Decision(phase=phase, faction_id=self.faction_id, response=resp)
```

- [ ] **Step 2: Run existing tests**

```bash
source venv/bin/activate && python -m pytest tests/ -q
```

Expected: `36 passed`

- [ ] **Step 3: Commit**

```bash
git add agents/human.py
git commit -m "refactor: human.py delegates all display/input to tui/ module"
```

---

## Task 6: Refactor `engine/referee.py`

**Files:**
- Modify: `engine/referee.py`

Three changes:
1. `__init__` gains `header: GameHeader | NullGameHeader = NullGameHeader()` and builds `_coalition_colors`.
2. `_collect_decisions` gains a `_print_phase_banner(phase)` call at its top.
3. `_display_turn_summary` body replaced with `TurnSummary(...).display()`.

`_print_phase_banner` is a new private helper that computes dominance and calls `self.header.print_phase_banner(...)`.

- [ ] **Step 1: Add `header` param and `_coalition_colors` to `GameReferee.__init__`**

In `engine/referee.py`, find the `__init__` signature (line 27) and modify it:

```python
def __init__(
    self,
    scenario: "Scenario",
    agents: dict[str, AgentInterface],
    audit: AuditTrail,
    header=None,
):
```

Then inside `__init__`, after `self.event_library = CrisisEventLibrary(scenario.crisis_events_library)`, add:

```python
        from tui.header import NullGameHeader
        self.header = header if header is not None else NullGameHeader()
        self._coalition_colors: dict[str, str] = {
            cid: ("green" if i == 0 else "red")
            for i, cid in enumerate(scenario.coalitions)
        }
```

- [ ] **Step 2: Add `_print_phase_banner` helper method**

Add this method to `GameReferee` (place it just before `_display_turn_summary`):

```python
    def _print_phase_banner(self, phase: Phase) -> None:
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        dominance = {
            cid: self.sim.compute_coalition_dominance(coalition.member_ids, all_assets)
            for cid, coalition in self.coalition_states.items()
        }
        self.header.print_phase_banner(
            turn=self._current_turn,
            tension=self.tension_level,
            debris=self.debris_level,
            coalition_dominance=dominance,
            coalition_colors=self._coalition_colors,
            phase=phase.value,
        )
```

- [ ] **Step 3: Call `_print_phase_banner` at the top of `_collect_decisions`**

Find `_collect_decisions` (line ~340). Add one line immediately after the `from rich.console import Console` import and `_console = Console()` lines:

```python
    async def _collect_decisions(
        self, phase: Phase, available_actions: list[str]
    ) -> dict[str, Decision]:
        from rich.console import Console
        _console = Console()
        self._print_phase_banner(phase)
        # ... rest unchanged
```

- [ ] **Step 4: Replace `_display_turn_summary` body**

Find `_display_turn_summary` (line ~93) and replace its entire body with:

```python
    async def _display_turn_summary(self, turn: int):
        if not any(agent.is_human for agent in self.agents.values()):
            return
        from tui.summary import TurnSummary
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        dominance = {
            cid: self.sim.compute_coalition_dominance(coalition.member_ids, all_assets)
            for cid, coalition in self.coalition_states.items()
        }
        decisions = await self.audit.get_decisions(turn=turn)
        events = await self.audit.get_events(turn=turn)
        TurnSummary(
            turn=turn,
            total_turns=self.scenario.turns,
            events=events,
            turn_log=list(self._turn_log),
            decisions=decisions,
            faction_states=self.faction_states,
            coalition_states=self.coalition_states,
            coalition_colors=self._coalition_colors,
            dominance=dominance,
            victory_threshold=self.scenario.victory.coalition_orbital_dominance,
        ).display()
```

- [ ] **Step 5: Run existing tests**

```bash
source venv/bin/activate && python -m pytest tests/ -q
```

Expected: `36 passed`

- [ ] **Step 6: Commit**

```bash
git add engine/referee.py
git commit -m "refactor: referee uses GameHeader phase banner and TurnSummary for end-of-turn display"
```

---

## Task 7: Update `main.py`

**Files:**
- Modify: `main.py`

Three changes:
1. `_configure_agents` gains a `header` parameter and passes it to `HumanAgent`.
2. After `load_scenario`, instantiate `GameHeader`.
3. Pass `header` to `_configure_agents` and `GameReferee`.

- [ ] **Step 1: Add `header` parameter to `_configure_agents`**

Find `_configure_agents` (line 32). Change its signature from:

```python
def _configure_agents(scenario, persona_dir: Path = Path("personas")) -> dict:
```

to:

```python
def _configure_agents(scenario, persona_dir: Path = Path("personas"), header=None) -> dict:
```

Then find the line creating `HumanAgent` (line ~64):

```python
            agent = HumanAgent(advisor=advisor)
```

Change to:

```python
            agent = HumanAgent(advisor=advisor, header=header)
```

- [ ] **Step 2: Instantiate `GameHeader` and pass it through in `main()`**

Find in `main()` the block after `scenario = load_scenario(scenario_path)` (line ~141). Add immediately after that line:

```python
    from tui.header import GameHeader
    header = GameHeader(scenario.name, scenario.turns)
```

Then find the `_configure_agents(scenario)` call (line ~145) and change it to:

```python
    agents = _configure_agents(scenario, header=header)
```

Then find `GameReferee(scenario=scenario, agents=agents, audit=audit)` (line ~156) and change it to:

```python
        referee = GameReferee(scenario=scenario, agents=agents, audit=audit, header=header)
```

- [ ] **Step 3: Run full test suite**

```bash
source venv/bin/activate && python -m pytest tests/ -q
```

Expected: `36 passed`

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: wire GameHeader through main.py into referee and human agents"
```

---

## Task 8: End-to-end verification

Run a full game session with `human+advisor` to verify all TUI components work together.

- [ ] **Step 1: Run a game**

```bash
source venv/bin/activate && python main.py
```

Select `cislunar_crossroads`. Set `nasa_ussf` to `human+advisor`, all others to `ai_commander`.

- [ ] **Step 2: Verify phase banner**

At the start of each phase (INVEST, OPERATIONS, RESPONSE), confirm a `─── ASTRAKON … ───` rule line appears showing turn number, coalition dominance bars with percentages, TENSION %, and DEBRIS %.

- [ ] **Step 3: Verify investment table**

During the INVEST phase:
- All 11 categories appear in a single table
- Budget bar is visible above the table
- Enter `1` and change constellation allocation — table updates in place below the prompt (no duplicate tables)
- Enter `1` again and change it — remaining budget correctly excludes the old value (freed before new value applied)
- Projected node outputs match the budget spent (e.g. 36 pts ÷ 5 = 7 LEO nodes)
- Enter `done` and provide rationale — game proceeds to OPERATIONS phase

- [ ] **Step 4: Verify situation display**

At each phase, confirm the assets table includes MEO, GEO, and cislunar columns. Confirm the adversary estimates table includes MEO/GEO/cislunar columns (values may be 0 if SDA is low). Confirm the advisor panel shows structured text (no raw JSON).

- [ ] **Step 5: Verify paged summary**

At end of turn 1:
- Summary appears one section at a time
- `[Enter] next  [b] back  [q] skip to end  page X/N` nav bar appears on every section
- `[b]` is dimmed on section 1
- Press `b` on section 2 — section 1 re-prints correctly above section 2
- Press `q` — summary exits immediately
- `page X/N` counter reflects actual non-empty section count (not always 5)

- [ ] **Step 6: Final commit if any last fixes needed**

```bash
git add -p  # stage any fixups discovered during verification
git commit -m "fix: tui verification fixups"
git push
```
