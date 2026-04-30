# Astrakon Web Frontend Design Spec

**Date:** 2026-04-29  
**Status:** Approved

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
    phase: Phase
    faction_states: dict[str, FactionState]
    coalition_states: dict[str, CoalitionState]
    tension_level: float
    debris_level: float
    pending_kinetic_approaches: list[dict]
    turn_log: list[str]
    events: list[dict]               # crisis events this turn
    decisions_this_turn: list[dict]  # { faction_id, phase, decision_json } already submitted this turn
    waiting_for_human: bool
    human_snapshot: Optional[GameStateSnapshot]
    total_turns: int
    game_over: bool
    result: Optional[dict]           # serialized GameResult
```

**`GameRunner.advance(session_id, decision=None)`** (`api/runner.py`):
1. Load `GameState` from session store
2. If `decision` provided: record it, mark that faction/phase as resolved
3. Loop through remaining faction/phase combinations in turn order
4. AI agents: `await agent.submit_decision()` (may call Claude API)
5. Human faction: catch `HumanInputRequired` → stop, serialize state, return
6. After all factions resolve a phase: call `SimulationEngine` to resolve outcomes
7. After all three phases: generate crisis events, compute dominance, check win condition, write audit
8. Return updated `GameState`

**Session store:** in-memory `dict[session_id, GameState]` + SQLite persistence via a new `game_sessions` table in the existing audit DB. `GameState` is stored as JSON blob, keyed by `session_id`. Games survive server restarts and can be resumed.

**Unchanged:** `SimulationEngine`, `CrisisEventLibrary`, `AuditTrail`, `AICommanderAgent`, `MahanianAgent`, all `engine/state.py` models.

---

## API Surface

```
GET  /api/scenarios
     → list[{ id, name, description, turns, factions[] }]

POST /api/game/create
     body: { scenario_id: str, agent_config: [{ faction_id, agent_type, use_advisor }] }
     → { session_id: str, state: GameState }

GET  /api/game/{session_id}/state
     → GameState   (used for polling while AI is thinking)

POST /api/game/{session_id}/advance
     → GameState   (run AI phases until human input needed)

POST /api/game/{session_id}/decide
     body: { phase: str, decision: dict }
     → GameState   (apply human decision, then advance)

GET  /api/game/{session_id}/result
     → GameResult  (only valid when game_over=true)

POST /api/game/{session_id}/aar
     → { text: str }   (triggers AfterActionReportGenerator)
```

**`GameState` response fields relevant to frontend:**
- `phase` — `invest | operations | response | summary | game_over`
- `turn` / `total_turns`
- `waiting_for_human` — boolean; frontend stops polling when `true`
- `human_snapshot` — `GameStateSnapshot` for the human faction
- `coalition_dominance` — `dict[coalition_id, float]`
- `events` — crisis events list (shown during `summary` phase)
- `turn_log` — operational log entries
- `error` — optional error message (AI agent failure); frontend shows retry

---

## Data Flow — One Complete Turn

```
GamePage mounts → POST /advance
  Server runs AI INVEST phases → hits human → returns { phase: "invest", waiting_for_human: true }
  → InvestPanel renders

User submits investment → POST /decide { phase: "invest", ... }
  Server runs AI OPS phases → hits human → returns { phase: "operations", waiting_for_human: true }
  → OpsPanel renders

User submits operation → POST /decide { phase: "operations", ... }
  Server runs AI RESPONSE phases → hits human → returns { phase: "response", waiting_for_human: true }
  → ResponsePanel renders

User submits response → POST /decide { phase: "response", ... }
  Server resolves full turn: SimulationEngine, crisis events, dominance, win check, audit
  → returns { phase: "summary", events: [...], turn_log: [...] }
  → TurnSummary overlay renders

User clicks "Next Turn" → POST /advance → cycle repeats

Game over → { game_over: true } → navigate to ResultPage
```

**Polling:** `gameStore` polls `/state` every 1.5s while `waiting_for_human: false` (AI agent calls in progress). Stops when `waiting_for_human: true`.

**Error recovery:** AI agent failure returns last serialized state + `error` field. Frontend shows retry button → calls `/advance` again from checkpoint.

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
      FactionSidebar.tsx       — assets, budget, deferred returns, metrics
      DominanceRail.tsx        — coalition dominance bars + event feed
      TurnSummary.tsx          — end-of-turn overlay (crisis events, ops log)
      AdvisorPanel.tsx         — AI recommendation panel (human+advisor mode)
      phase/
        InvestPanel.tsx        — budget allocation inputs
        OpsPanel.tsx           — action type + target + rationale
        ResponsePanel.tsx      — escalate / retaliate / statement
    store/
      gameStore.ts             — Zustand: session_id, GameState, polling loop
    api/
      client.ts                — typed fetch wrappers for all 7 endpoints
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
│  JFE           │     (invest / ops /      │                  │
│  market share  │      response)           │   event feed     │
│                │                          │                  │
└────────────────┴──────────────────────────┴──────────────────┘
```

### OrbitalMap Component

- SVG with four concentric rings: LEO, MEO, GEO, Cislunar (labeled)
- Earth glyph at center
- Each faction's nodes: glowing colored dots on their ring, count-proportional spacing
- Kinetic approaches: pulsing red threat indicator on target ring
- Hover tooltip: faction name, node count, asset details
- Updates each turn as `GameState` changes

### Visual Aesthetic

- Background: `#020b18` (deep space)
- Accent: `#00d4ff` (cyan), `#00ff88` (green for player), `#ff4499` (red for adversary)
- Typography: monospace for data, system-ui for labels
- Borders: `1px solid #00d4ff33` with subtle glow on active elements
- Animations: pulsing dots for threats, fade transitions between phases

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vite 5, React 19, TypeScript, React Router v7 |
| State | Zustand |
| Styling | Tailwind CSS v4 (dark theme) |
| Backend | FastAPI, uvicorn |
| Persistence | SQLite (extends AuditTrail) |
| Python deps | No new deps beyond FastAPI + uvicorn |

---

## Out of Scope

- Multiplayer (session model is compatible; not implemented now)
- Authentication / user accounts
- Real-time AI progress streaming (loading indicator is sufficient)
- Porting to Rust (this spec is the Python foundation for that migration)
