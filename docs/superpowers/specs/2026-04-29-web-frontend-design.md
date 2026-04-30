# Astrakon Web Frontend Design Spec

**Date:** 2026-04-29  
**Status:** Approved (rev 2 — adversarial review fixes applied)

---

## Overview

Replace the Rich TUI with a web-based command center interface. FastAPI backend wraps the existing Python game engine. Vite + React SPA serves as the frontend. The engine is refactored from a continuous async loop to a step-by-step execution model that serializes state between HTTP requests — designed for a clean future migration to Rust (Axum/Loco.rs).

---

## Goals

- Full game flow in the browser: scenario setup → gameplay → after-action report
- Single human player vs AI opponents (multiplayer-compatible session model)
- Sci-fi space aesthetic: deep space dark, glowing cyan/purple neons, orbital map visualization
- No breaking changes to existing engine logic (SimulationEngine, agents, AuditTrail)

---

## Architecture

Three layers, cleanly separated:

```
web/      — Vite + React SPA (static bundle, served by FastAPI or CDN)
api/      — FastAPI backend (session management, step-by-step game runner)
engine/   — Python game engine (minimally modified for step-by-step execution)
```

FastAPI owns the game loop. All game state is serialized to SQLite between requests — no long-running background tasks. Each HTTP request loads state, advances the engine until the human player needs to act, saves state, and returns.

**Important:** `/advance` and `/decide` are long-running requests — they run AI agent calls (Claude API) synchronously and may take 10–30 seconds for a multi-faction turn. The frontend shows a loading state for the full duration; there is no mid-request polling. The `/state` endpoint exists only for page-refresh resume, not for polling during AI turns.

---

## Engine Refactor

### Problem
`GameReferee.run()` is a continuous `while` loop that cannot be interrupted mid-turn.

### Solution: `GameRunner` + `WebAgent`

**`WebAgent`** (`agents/web.py`) — replaces `HumanAgent` for web sessions:
```python
class HumanInputRequired(Exception):
    def __init__(self, phase: Phase, snapshot: GameStateSnapshot): ...

class WebAgent(AgentInterface):
    async def submit_decision(self, phase: Phase) -> Decision:
        raise HumanInputRequired(phase, self._last_snapshot)
```

**`GameState`** (`api/models.py`) — fully serializable game state stored in SQLite:
```python
class GameState(BaseModel):
    session_id: str
    turn: int
    total_turns: int
    current_phase: Phase                      # phase currently being executed
    phase_decisions: dict[str, str]           # faction_id → decision_json for current phase
    faction_states: dict[str, FactionState]
    coalition_states: dict[str, CoalitionState]
    tension_level: float
    debris_level: float
    pending_kinetic_approaches: list[dict]
    turn_log: list[str]
    events: list[dict]                        # crisis events this turn
    human_faction_id: str
    human_snapshot: Optional[GameStateSnapshot]
    use_advisor: bool
    game_over: bool
    result: Optional[dict]                    # serialized GameResult
    error: Optional[str]                      # set on AI agent failure; cleared on retry
```

**Faction turn order:** deterministic, sorted by `faction_id` alphabetically. The runner iterates factions in this order for every phase, skipping any `faction_id` already present in `phase_decisions`.

**`GameRunner.advance(session_id, decision=None)`** (`api/runner.py`):
1. Load `GameState` from session store
2. If `decision` provided: validate it, add `(human_faction_id → decision_json)` to `phase_decisions`, checkpoint to SQLite
3. Loop through factions in deterministic order for `current_phase`, skipping those in `phase_decisions`
4. AI agents: `await agent.submit_decision()` (may call Claude API) → add to `phase_decisions`, **checkpoint to SQLite after each agent decision**
5. Human faction: catch `HumanInputRequired` → build snapshot, save `GameState`, return immediately
6. When all factions have decided for `current_phase`: call `SimulationEngine` to resolve, clear `phase_decisions`, advance `current_phase`
7. If `current_phase` advances past RESPONSE: generate crisis events, compute dominance, check win condition, write audit, set `current_phase = "summary"`
8. Return updated `GameState`

**Checkpointing after each agent decision (fixes error recovery):** If a Claude API call fails mid-turn, the last checkpoint has all decisions made so far. On retry, `/advance` loads from checkpoint and resumes from the first undecided faction — already-decided factions are skipped via `phase_decisions`.

**Session store:** in-memory `dict[session_id, GameState]` + SQLite persistence in a dedicated `output/sessions.db` file (separate from per-game audit DBs, which remain as timestamped files). `GameState` stored as JSON blob keyed by `session_id`.

**Unchanged:** `SimulationEngine`, `CrisisEventLibrary`, `AuditTrail`, `AICommanderAgent`, `MahanianAgent`, all `engine/state.py` models.

---

## API Surface

```
GET  /api/scenarios
     → list[{ id: str, name, description, turns, factions[] }]
     id = filename stem (e.g. "cold_war_redux" for cold_war_redux.yaml)
     Stable as long as .yaml filenames are not renamed.

POST /api/game/create
     body: { scenario_id: str, agent_config: [{ faction_id, agent_type, use_advisor }] }
     → { session_id: str, state: GameState }

GET  /api/game/{session_id}/state
     → GameState
     Used only for page-refresh resume. Not polled during AI turns.

POST /api/game/{session_id}/advance
     → GameState
     Long-running (10–30s). Runs AI agents for current phase until human input needed.
     Frontend shows loading spinner for full duration.

POST /api/game/{session_id}/decide
     body: { phase: str, decision: dict }
     → GameState
     Long-running. Applies human decision, then advances to next human input point.

GET  /api/game/{session_id}/recommend
     query param: phase (invest | operations | response)
     → { recommendation: Recommendation | null }
     Called after /advance returns, before rendering the phase panel.
     Only meaningful when use_advisor=true; returns null otherwise.
     Runs advisor AI call (AICommanderAgent.get_recommendation).

GET  /api/game/{session_id}/result
     → GameResult  (only valid when game_over=true)

POST /api/game/{session_id}/aar
     → { text: str }   (triggers AfterActionReportGenerator)
```

**`GameState` fields the frontend uses:**
- `current_phase` — `invest | operations | response | summary | game_over`
- `turn` / `total_turns`
- `human_snapshot` — `GameStateSnapshot` for the human faction (assets, adversary estimates, threats, deferred returns)
- `coalition_dominance` — computed fresh on each response: `dict[coalition_id, float]`
- `events` — crisis events list (rendered during `summary` phase)
- `turn_log` — operational log entries (rendered during `summary` phase)
- `error` — set on AI agent failure; frontend shows retry button that calls `/advance` again

---

## Data Flow — One Complete Turn

```
GamePage mounts → POST /advance  [loading spinner shown]
  Server runs AI INVEST phases → hits human → saves state → returns
  state { current_phase: "invest", human_snapshot: {...} }
  → if use_advisor: GET /recommend?phase=invest  [loading spinner]
  → InvestPanel renders (with or without AdvisorPanel)

User submits investment → POST /decide { phase: "invest", ... }  [loading spinner]
  Server: records human invest decision → checkpoints → runs AI OPS phases → hits human
  → returns state { current_phase: "operations", human_snapshot: {...} }
  → if use_advisor: GET /recommend?phase=operations
  → OpsPanel renders

User submits operation → POST /decide { phase: "operations", ... }  [loading spinner]
  Server: records → checkpoints → runs AI RESPONSE phases → hits human
  → returns state { current_phase: "response", human_snapshot: {...} }
  → if use_advisor: GET /recommend?phase=response
  → ResponsePanel renders

User submits response → POST /decide { phase: "response", ... }  [loading spinner]
  Server: records → checkpoints → resolves turn (SimulationEngine, crisis events,
  dominance, win check, audit write) → returns state { current_phase: "summary" }
  → TurnSummary overlay renders (events, ops log, dominance)

User clicks "Next Turn" → POST /advance → cycle repeats

state.game_over = true → navigate to ResultPage
```

**Loading state:** frontend disables all inputs and shows a scanning-line animation overlay while any `/advance`, `/decide`, or `/recommend` request is in flight.

**Error recovery:** `state.error` is set when an AI agent call fails. Frontend shows a "Retry" button. Retry calls `/advance` with no decision — runner loads checkpoint (last successful agent decision), resumes from next undecided faction. Error is cleared on successful advance.

**Frontend validation errors** (HTTP 422 from FastAPI): shown inline in the phase panel (e.g., "Budget allocation exceeds 100%"). Do not dismiss the panel.

---

## Frontend Structure

```
web/
  index.html
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    App.tsx                    — React Router: Setup / Game / Result routes
    pages/
      SetupPage.tsx            — scenario picker + per-faction agent config
      GamePage.tsx             — main command center layout (persistent)
      ResultPage.tsx           — winner display + AAR generation
    components/
      OrbitalMap.tsx           — SVG orbital visualization
      FactionSidebar.tsx       — assets, budget, deferred returns, JFE, market share
      DominanceRail.tsx        — coalition dominance bars + event feed
      TurnSummary.tsx          — end-of-turn overlay (crisis events, ops log)
      AdvisorPanel.tsx         — AI recommendation panel (human+advisor mode only)
      LoadingOverlay.tsx       — scanning-line overlay during long requests
      phase/
        InvestPanel.tsx        — budget allocation inputs
        OpsPanel.tsx           — action type + target + rationale
        ResponsePanel.tsx      — escalate / retaliate / statement
    store/
      gameStore.ts             — Zustand: session_id, GameState, loading state, error
    api/
      client.ts                — typed fetch wrappers for all 8 endpoints
```

### GamePage Layout

```
┌──────────────────────────────────────────────────────────────┐
│  ASTRAKON  ·  Turn 3 / 8  ·  INVEST PHASE          [faction] │
├────────────────┬──────────────────────────┬──────────────────┤
│                │                          │                  │
│  FACTION       │     ORBITAL MAP          │   DOMINANCE      │
│  SIDEBAR       │     (SVG, always         │   RAIL           │
│                │      visible)            │                  │
│  assets        ├──────────────────────────┤   coalition      │
│  budget        │     PHASE PANEL          │   bars           │
│  deferred      │     (invest / ops /      │                  │
│  returns       │      response)           │   event feed     │
│  JFE           │                          │                  │
│  market share  │  [AdvisorPanel if mode]  │                  │
└────────────────┴──────────────────────────┴──────────────────┘
```

### FactionSidebar — Deferred Returns

When `human_snapshot.faction_state.deferred_returns` is non-empty, render a "Pending Returns" sub-section below the assets table showing: category (R&D / Education), points, and due turn. Matches the existing TUI display in `tui/phases.py:display_situation()`.

### OrbitalMap Component

- SVG with four concentric rings: LEO, MEO, GEO, Cislunar (labeled)
- Earth glyph at center
- Each faction's nodes: glowing colored dots evenly spaced on their ring
- **Cap:** max 8 visible dots per faction per ring. If a faction has > 8 nodes on a ring, show 8 dots + a count badge (e.g. `×14`) instead of overflowing the ring
- Kinetic approaches: pulsing red threat indicator on target ring
- Hover tooltip: faction name, exact node count per ring, asset details
- Updates each turn as `GameState` changes

### Visual Aesthetic

- Background: `#020b18` (deep space)
- Accent: `#00d4ff` (cyan), `#00ff88` (green for player), `#ff4499` (red for adversary)
- Typography: monospace for data, system-ui for labels
- Borders: `1px solid #00d4ff33` with subtle glow on active elements
- Animations: pulsing dots for threats, fade transitions between phases, scanning-line loading overlay

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vite 5, React 19, TypeScript, React Router v7 |
| State | Zustand |
| Styling | Tailwind CSS v4 (dark theme) |
| Backend | FastAPI, uvicorn |
| Session persistence | `output/sessions.db` (SQLite, separate from per-game audit DBs) |
| Python deps | No new deps beyond FastAPI + uvicorn |

---

## Out of Scope

- Multiplayer (session model is compatible; not implemented now)
- Authentication / user accounts
- Real-time AI progress streaming (loading indicator is sufficient)
- Porting to Rust (this spec is the Python foundation for that migration)
