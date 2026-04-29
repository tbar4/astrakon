# TUI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current scrolling Rich output with a hybrid TUI — a phase banner printed at the top of each phase showing live game state, a full non-destructive investment allocation table with live in-place updates, and a paged end-of-turn summary with forwards/backwards navigation.

**Architecture:** New `tui/` module with five focused files. `agents/human.py` and `engine/referee.py` delegate display and input collection to `tui/`. No new library dependencies — all built on Rich (Live, Table, Panel, Prompt, Rule).

**Tech Stack:** Python, Rich (Live, Table, Panel, Prompt, Confirm, Rule), existing engine/state types.

---

## Design Decisions

### Paradigm: Phase banner + Rich Live for interactive widgets (revised from C)

A styled banner is printed once at the top of each phase showing turn, tension, debris, and coalition dominance bars. This is a plain `console.print()` — not Rich Live — which means it scrolls with the terminal naturally. Between phase banners, game events and AI deliberation output scroll below.

Rich Live is used **only inside the investment table edit loop** where in-place updating is genuinely needed. Outside that loop, everything is normal console output. This eliminates the fragile start/stop lifecycle complexity that a "pinned header" would require.

**Why not Rich Live for the header:** Rich Live renders at the cursor position and updates in place at that position — it does not float above scrolling content. A true pinned-to-top bar requires either `screen=True` (full alternate screen, no scroll history) or raw ANSI escape codes. Neither fits this project.

### Investment Phase: Full table, edit by number, with Live in-place update

All 11 categories displayed at once in a Rich Table wrapped in a `rich.live.Live` context. The Live context is **stopped only during the row-edit prompt** (so input can be collected), then restarted after the value is applied. This means exactly one copy of the table exists in the terminal at all times — no stacking.

Each row shows: row number, category name, current allocation %, points spent, and projected output. A budget progress bar above the table updates after each edit.

**Re-edit "remaining" definition:** When editing a row that already has a value, `remaining = 1.0 - sum(allocations for all OTHER rows)`. The current row's old value is freed before applying the new one.

### End-of-Turn Summary: Paged with bidirectional navigation

Sections are built dynamically — a section function returns `None` if there is nothing to show (e.g., no crisis events). The nav bar shows `page X/N` where N is the count of non-empty sections, not a fixed 5.

Navigation:
- `Enter` — next section (or finish on last)
- `b` + `Enter` — previous section (no-op on section 1)
- `q` + `Enter` — skip to end

Every section displays the nav bar at the bottom. On section 1, `[b] back` is dimmed. On the last section, `[Enter]` label changes to `[Enter] continue to Turn N+1`.

---

## File Structure

**New files:**
- `tui/__init__.py` — empty
- `tui/header.py` — `print_phase_banner()` and `NullGameHeader` / `GameHeader`
- `tui/invest.py` — `collect_investment()` with Rich Live table
- `tui/phases.py` — `display_situation()`, `collect_operations()`, `collect_response()`
- `tui/summary.py` — `TurnSummary` class

**Modified files:**
- `agents/human.py` — replace all display/input functions with imports from `tui/`; `HumanAgent.__init__` gains `header: GameHeader = NullGameHeader()`
- `engine/referee.py` — call `header.print_phase_banner(...)` at the top of each phase; replace `_display_turn_summary()` body with `TurnSummary(...).display()`; `GameReferee.__init__` gains `header: GameHeader = NullGameHeader()`
- `main.py` — instantiate `GameHeader(scenario.name, scenario.turns)` after scenario loads; pass to `GameReferee` and each `HumanAgent`

---

## Component Specifications

### `tui/header.py` — `GameHeader` and `NullGameHeader`

`GameHeader` and `NullGameHeader` share the same interface. `NullGameHeader` is the default — all methods are no-ops. Callers never check for `None`.

```python
class GameHeader:
    def __init__(self, scenario_name: str, total_turns: int): ...

    def print_phase_banner(
        self,
        turn: int,
        tension: float,
        debris: float,
        coalition_dominance: dict[str, float],   # cid -> float, ordered
        coalition_colors: dict[str, str],         # cid -> Rich color name
        phase: str,
    ): ...

class NullGameHeader:
    def __init__(self): ...
    def print_phase_banner(self, *args, **kwargs): ...  # no-op
```

`print_phase_banner()` prints a single Rich `Rule` or `Panel` line:

```
══ TURN 4/12 · INVEST ══  artemis ████████░░ 62.4%  │  ascent █████░░░░░ 37.6%  │  TENSION 45%  DEBRIS 12%
```

Dominance bars: 10-char block bar (`█` filled, `░` empty) scaled to the dominance value. Colors are passed in from the caller — derived by coalition index (first coalition in scenario dict = `green`, second = `red`), never hardcoded by name.

### `tui/invest.py` — `collect_investment(budget: int, snapshot: GameStateSnapshot) -> InvestmentAllocation`

Node cost constants imported from `engine.simulation` (`LEO_NODE_COST`, `MEO_NODE_COST`, `GEO_NODE_COST`, `CISLUNAR_NODE_COST`, `LAUNCH_COST`, `JAMMER_COST`, `DENIABLE_ASAT_COST`). The output column stays correct if game balance changes.

Output column values per category:
- `constellation` → `+N LEO nodes` (`floor(pts / LEO_NODE_COST)`)
- `meo_deployment` → `+N MEO nodes` (`floor(pts / MEO_NODE_COST)`)
- `geo_deployment` → `+N GEO nodes` (`floor(pts / GEO_NODE_COST)`)
- `cislunar_deployment` → `+N cislunar` (`floor(pts / CISLUNAR_NODE_COST)`)
- `launch_capacity` → `+N capacity` (`floor(pts / LAUNCH_COST)`)
- `influence_ops` → `+N EW jammers` (`floor(pts / JAMMER_COST)`)
- `covert` → `+N deniable ASAT` (`floor(pts / DENIABLE_ASAT_COST)`)
- `r_and_d` → `deferred return T+3`
- `education` → `deferred return T+6`
- `commercial` → `revenue + influence`
- `diplomacy` → `coalition loyalty +`

Budget progress bar:
```
[ ████████░░░░░░░░░░░░ ]  42% allocated  |  51 pts remaining  |  budget: 120 pts
```
Bar color: green when ≤80% allocated, yellow when 80–99%, red at 100%.

**Edit loop (Live-wrapped):**

```python
allocations: dict[str, float] = {cat: 0.0 for cat in CATEGORIES}
with Live(get_renderable=lambda: _render_table(allocations, budget), refresh_per_second=4) as live:
    while True:
        live.stop()
        raw = Prompt.ask("> edit # (or 'done')")
        live.start()
        if raw.strip().lower() == 'done':
            break
        try:
            idx = int(raw.strip()) - 1
            cat = CATEGORIES[idx]
        except (ValueError, IndexError):
            console.print("[red]Enter a number 1–11 or 'done'.[/red]")
            continue
        remaining = 1.0 - sum(v for k, v in allocations.items() if k != cat)
        live.stop()
        val = float(Prompt.ask(f"  {cat} (current: {allocations[cat]:.0%}, remaining: {remaining:.0%})", default=str(round(allocations[cat], 3))))
        live.start()
        if val > remaining:
            console.print(f"[yellow]Capped to {remaining:.3f} (remaining budget).[/yellow]")
            val = remaining
        allocations[cat] = round(max(0.0, val), 3)

live.stop()
rationale = Prompt.ask("  Strategic rationale")
return InvestmentAllocation(**allocations, rationale=rationale)
```

### `tui/phases.py` — `display_situation()`, `collect_operations()`, `collect_response()`

**`display_situation(snapshot: GameStateSnapshot)`**

Replaces `_display_snapshot()` in `human.py`. Shows:
1. Assets table — all asset types with current counts (LEO, MEO, GEO, cislunar, ASAT-K, ASAT-deniable, EW jammers, SDA sensors, launch capacity)
2. Adversary estimates table — SDA-filtered intel on each adversary (LEO, MEO, GEO, cislunar, ASAT-K)
3. Incoming threats panel (if `snapshot.incoming_threats` is non-empty) — red warning box listing kinetic approaches with attacker and declared turn
4. Key metrics line — deterrence, disruption, market share, JFE for this faction

**`collect_operations(snapshot: GameStateSnapshot) -> list[OperationalAction]`**

Same logic as current `_collect_operations()` in `human.py`. Richer table styling: color-coded action rows (`gray_zone`=yellow, `task_assets`=blue, `coordinate`=cyan, `alliance_move`/`signal`=dim). Mission sub-menu for `task_assets` unchanged.

**`collect_response(snapshot: GameStateSnapshot) -> ResponseDecision`**

Same logic as current `_collect_response()`. Prefixes the prompt with `snapshot.turn_log_summary` in a dim panel so the player sees what happened this turn without scrolling up. If `turn_log_summary` is empty, skips the prefix.

### Advisor recommendation display

`_display_recommendation()` in `human.py` currently dumps raw JSON. Replace with a structured Rich Panel:

- **INVEST phase:** Show top 3 non-zero allocations sorted by fraction, rendered as a mini bar list (`constellation 35% ███░░`) + rationale text below. Extract from `rec.top_recommendation.investment`.
- **OPERATIONS phase:** Show `action_type → target_faction` on one line + rationale below. Extract from `rec.top_recommendation.operations[0]`.
- **RESPONSE phase:** Show escalate/retaliate as colored flags (`[red]ESCALATE[/red]` or `[green]stand down[/green]`) + rationale below. Extract from `rec.top_recommendation.response`.

No JSON visible to the player.

### `tui/summary.py` — `TurnSummary`

```python
class TurnSummary:
    def __init__(self,
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
    ): ...

    def display(self): ...  # blocks until player finishes paging
```

`display()` builds sections dynamically:

```python
candidates = [
    _section_crisis(self.events),
    _section_ops_log(self.turn_log),
    _section_observed_ops(self.decisions, self.faction_states),
    _section_dominance(self.dominance, self.coalition_states, self.coalition_colors, self.victory_threshold),
    _section_metrics(self.faction_states),
]
sections = [s for s in candidates if s is not None]
```

Each `_section_*` function returns a `str` (Rich markup rendered via `Console(record=True).export_text()`) or `None` if empty. A section is empty when: crisis list is empty, turn_log is empty, no observable ops/responses exist.

Navigation loop:

```python
idx = 0
n = len(sections)
while True:
    console.print(sections[idx])
    _print_nav_bar(idx, n, self.turn, self.total_turns)
    key = Prompt.ask("", default="").strip().lower()
    if key == 'b' and idx > 0:
        idx -= 1
    elif key == 'q':
        break
    elif idx < n - 1:
        idx += 1
    else:
        break
```

Nav bar per position:
- First section: `[Enter] next  [dim][b] back[/dim]  [q] skip to end  page 1/N`
- Middle: `[Enter] next  [b] back  [q] skip to end  page X/N`
- Last: `[Enter] continue to Turn M  [b] back  page N/N`

Using `Prompt.ask("", default="")` instead of raw `input()` prevents character echo from appearing before the next section renders.

---

## Color Scheme

Coalition colors are assigned by **index** in `scenario.coalitions` (dict iteration order), not by name. First coalition → `green`, second → `red`. Passed as `coalition_colors: dict[str, str]` wherever needed.

| Element | Color |
|---|---|
| Phase banner rule | `cyan` |
| Phase label | `bold cyan` |
| First coalition (by index) | `green` |
| Second coalition (by index) | `red` |
| Crisis events | `yellow` |
| Kinetic/retaliation | `bold red` |
| Gray-zone/jamming | `yellow` |
| Coordination | `cyan` |
| Neutral ops | `dim` |
| Tension | `yellow` |
| Debris | `orange3` |
| Budget bar ≤80% | `green` |
| Budget bar 80–99% | `yellow` |
| Budget bar 100% | `red` |
| Incoming threat warning | `bold red` on `red` panel |

---

## What Does Not Change

- `agents/ai_commander.py` — AI agents are unaffected
- `agents/rule_based.py` — unaffected
- `engine/referee.py` game logic — only `_display_turn_summary()` output changes
- All existing tests — no game logic changes, TUI is display-only
- Scenario YAML files — unchanged
- `output/` module — unchanged

---

## Testing

TUI components are display-only and not unit-tested. Verify manually by running a `human+advisor` game with the `cislunar_crossroads` scenario and confirming:
1. Phase banner appears at the top of each phase with correct turn, tension, dominance
2. Investment table stays in place during edits — no stacking copies in scroll history
3. Re-editing a row correctly frees the old value before applying the new one
4. Projected node outputs match actual game outcomes
5. Paged summary navigates forwards and backwards; empty sections are skipped
6. `page X/N` counter reflects actual section count, not a fixed 5
7. Advisor panel shows no raw JSON
8. Situation display shows assets, adversary intel, and incoming threats
