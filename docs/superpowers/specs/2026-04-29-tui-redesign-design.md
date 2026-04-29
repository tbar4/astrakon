# TUI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current scrolling Rich output with a hybrid TUI — a persistent status header (Rich Live) always visible at the top, a full non-destructive investment allocation table, and a paged end-of-turn summary with forwards/backwards navigation.

**Architecture:** New `tui/` module with four focused files. `agents/human.py` and `engine/referee.py` delegate display and input collection to `tui/`. No new library dependencies — all built on Rich (Live, Table, Panel, Prompt).

**Tech Stack:** Python, Rich (Live, Layout, Table, Panel, Prompt, Confirm), existing engine/state types.

---

## Design Decisions

### Paradigm: Rich Live hybrid (C)
Sticky status bar rendered via `rich.live.Live` at the top of the terminal. All game events, prompts, and phase output scroll below it as normal console output. The Live region is updated at the start of each phase (turn number, tension, dominance).

Rich Live and `Prompt.ask` can conflict — the Live context must be stopped before any input prompt is displayed and restarted after. The `GameHeader` class manages this with explicit `start()` / `stop()` / `refresh()` methods so callers control the lifecycle cleanly.

**Header lifecycle ownership:** `HumanAgent` receives the `GameHeader` instance at construction and calls `header.stop()` at the top of `submit_decision()` (before any display or prompt) and `header.start()` at the bottom (after input is collected). `TurnSummary.display()` requires the header to already be stopped by its caller (`GameReferee._display_turn_summary()`) before invoking `display()`, and the caller restarts it after. `GameReferee.__init__` gains an optional `header: GameHeader | None = None` parameter; when `None`, no header lifecycle calls are made (AI-only games).

### Investment Phase: Full table, edit by number (B)
All 11 categories displayed at once in a Rich Table. Each row shows: row number, category name, current allocation %, points spent, and projected output (node gains or descriptive effect). A budget progress bar above the table updates after each edit. The player types a row number to edit, enters a new fraction (validated 0.0–1.0, capped to remaining budget), then types `done` to proceed to rationale entry. They can edit any row any number of times before committing — no destructive sequential flow.

### End-of-Turn Summary: Paged with bidirectional navigation (B)
Five fixed sections rendered in order:
1. Crisis Events
2. Operational Log
3. Observed Operations & Faction Responses
4. Orbital Dominance
5. Faction Metrics

Each section is rendered to a string buffer and stored in a list. The player navigates with:
- `Enter` — next section
- `b` + `Enter` — previous section (no-op on section 1)
- `q` + `Enter` — skip to end

Every section displays a navigation bar at the bottom: `[Enter] next  [b] back  [q] skip to end  page X/5`. On section 1, `[b] back` is dimmed. On section 5, `[Enter] next` changes to `[Enter] continue to Turn N+1`.

---

## File Structure

**New files:**
- `tui/__init__.py` — empty
- `tui/header.py` — `GameHeader` class
- `tui/invest.py` — `InvestmentTable` function
- `tui/phases.py` — `collect_operations()`, `collect_response()` styled replacements
- `tui/summary.py` — `TurnSummary` class

**Modified files:**
- `agents/human.py` — replace `_display_snapshot`, `_collect_investment`, `_collect_operations`, `_collect_response`, `_display_recommendation` with imports from `tui/`; `HumanAgent.__init__` gains `header: GameHeader | None = None` param
- `engine/referee.py` — `GameReferee.__init__` gains `header: GameHeader | None = None`; replace `_display_turn_summary()` body with `header.stop()` + `TurnSummary(...).display()` + `header.start()`; call `header.refresh(...)` at the top of each phase
- `main.py` — instantiate `GameHeader(scenario.name, scenario.turns)` after scenario is loaded; call `header.stop()` before `_configure_agents()` prompt loop; pass `header` to `GameReferee` and to each `HumanAgent`

---

## Component Specifications

### `tui/header.py` — `GameHeader`

Renders a single-line status bar using `rich.live.Live` wrapping a `rich.table.Table` with no borders:

```
ASTRAKON  │  Cislunar Crossroads  │  Turn 4/12  │  artemis ████████░░ 62.4%  │  ascent █████░░░░░ 37.6%  │  TENSION 45%  DEBRIS 12%
```

Public interface:
```python
class GameHeader:
    def __init__(self, scenario_name: str, total_turns: int): ...
    def start(self): ...         # begin Live rendering
    def stop(self): ...          # stop Live, safe to print/prompt
    def refresh(self,            # update all fields
        turn: int,
        tension: float,
        debris: float,
        coalition_dominance: dict[str, float],   # cid -> float
        phase: str,
    ): ...
```

Dominance bars: 10-char block bar (`█` filled, `░` empty) scaled to the value. Color: green if coalition is leading, red if trailing.

`GameReferee` holds an optional `GameHeader` reference. It calls `header.refresh(...)` at the top of each phase and `header.stop()` / `header.start()` around `TurnSummary.display()`. `HumanAgent` holds its own reference and manages stop/start around its own prompts.

### `tui/invest.py` — `collect_investment(budget: int, snapshot: GameStateSnapshot) -> InvestmentAllocation`

Renders a Rich Table with columns: `#`, `Category`, `Alloc %`, `Pts`, `Output`.

Budget progress bar above table (Rich text, not a separate widget):
```
[ ████████░░░░░░░░░░░░ ]  42% allocated  |  51 pts remaining  |  budget: 120 pts
```

Output column values per category:
- `constellation` → `+N LEO nodes` (floor(pts / 5))
- `meo_deployment` → `+N MEO nodes` (floor(pts / 12))
- `geo_deployment` → `+N GEO nodes` (floor(pts / 25))
- `cislunar_deployment` → `+N cislunar nodes` (floor(pts / 40))
- `launch_capacity` → `+N capacity` (floor(pts / 15))
- `influence_ops` → `+N EW jammers` (floor(pts / 12))
- `covert` → `+N deniable ASAT` (floor(pts / 25))
- `r_and_d` → `deferred return T+3`
- `education` → `deferred return T+6`
- `commercial` → `revenue + influence`
- `diplomacy` → `coalition loyalty +`

Edit loop:
```
> edit # (or 'done'):
```
Input `1`–`11` → prompt `  constellation (current: 30%, remaining: 58%): ` → validate float, cap to remaining, update table and bar, re-render. Input `done` → prompt for rationale → return `InvestmentAllocation`.

Validation: non-numeric input prints `[red]Enter a number 1–11 or 'done'.[/red]` and re-prompts. Fraction > remaining is silently capped and noted: `[yellow]Capped to 0.48 (remaining budget).[/yellow]`.

### `tui/phases.py` — `collect_operations()` and `collect_response()`

`collect_operations(snapshot: GameStateSnapshot) -> list[OperationalAction]`: Same logic as current `_collect_operations()` in `human.py` but with richer table styling — color-coded action rows (gray_zone=yellow, task_assets=blue, coordinate=cyan, alliance_move/signal=dim). Mission sub-menu for `task_assets` unchanged.

`collect_response(snapshot: GameStateSnapshot) -> ResponseDecision`: Same logic as current `_collect_response()` but prefixes the prompt with `snapshot.turn_log_summary` so the player sees what happened this turn without scrolling up.

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
        dominance: dict[str, float],
        victory_threshold: float,
    ): ...

    def display(self): ...  # blocks until player finishes paging
```

`display()` builds 5 section strings (using Rich's `Console(record=True)` to capture rendered output), then runs the navigation loop:

```python
sections = [_section_crisis(...), _section_ops_log(...), _section_observed_ops(...),
            _section_dominance(...), _section_metrics(...)]
idx = 0
while True:
    _print_section(sections[idx], idx, len(sections), is_last_turn=...)
    key = input()  # raw input — header is stopped before this
    if key.strip() == 'b' and idx > 0:
        idx -= 1
    elif key.strip() == 'q':
        break
    elif idx < len(sections) - 1:
        idx += 1
    else:
        break  # past last section
```

Nav bar (rendered at bottom of each section):
- Section 1: `[Enter] next  [dim][b] back[/dim]  [q] skip to end  page 1/5`
- Middle: `[Enter] next  [b] back  [q] skip to end  page N/5`
- Last: `[Enter] continue to Turn N+1  [b] back  page 5/5`

### Advisor recommendation display

`_display_recommendation()` in `human.py` currently dumps raw JSON. Replace with a structured panel:

- For INVEST phase: show top 3 non-zero allocations as a mini bar list + rationale text
- For OPERATIONS phase: show `action_type → target` + rationale
- For RESPONSE phase: show escalate/retaliate flags + rationale

No JSON visible to the player.

---

## Color Scheme

| Element | Color |
|---|---|
| Header bar background | `#161b22` (Rich `on grey7`) |
| Header border | `cyan` |
| Artemis coalition | `green` |
| Ascent coalition | `red` |
| Crisis events | `yellow` |
| Kinetic/retaliation | `bold red` |
| Gray-zone/jamming | `yellow` |
| Coordination | `cyan` |
| Neutral ops | `dim` |
| Tension | `yellow` |
| Debris | `orange3` |
| Budget bar (healthy) | `green` |
| Budget bar (>80% spent) | `yellow` |
| Budget bar (100% spent) | `red` |

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
1. Header updates correctly each phase
2. Investment table allows free editing and correct node projections
3. Paged summary navigates forwards and backwards correctly
4. Advisor panel shows no raw JSON
