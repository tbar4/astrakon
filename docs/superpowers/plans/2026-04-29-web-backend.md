# Astrakon Web Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI backend that wraps the existing Python game engine and exposes 8 HTTP endpoints for driving the full game loop from a web frontend.

**Architecture:** A `WebAgent` raises `HumanInputRequired` instead of blocking on stdin. A `GameRunner` drives the game turn-by-turn, serializing all state to SQLite after each agent decision. `GameReferee` is refactored to separate decision collection from resolution so the runner can inject pre-collected web decisions.

**Tech Stack:** Python 3.12+, FastAPI, uvicorn, aiosqlite (already a dep), pydantic v2 (already a dep), pytest + httpx for testing.

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `agents/web.py` | Create | WebAgent + HumanInputRequired exception |
| `api/__init__.py` | Create | Package marker |
| `api/models.py` | Create | GameState and all request/response Pydantic models |
| `api/session.py` | Create | In-memory + SQLite session store |
| `api/runner.py` | Create | GameRunner — drives turn loop, checkpoints state |
| `api/routes/__init__.py` | Create | Package marker |
| `api/routes/scenarios.py` | Create | GET /api/scenarios |
| `api/routes/game.py` | Create | All game lifecycle endpoints |
| `api/main.py` | Create | FastAPI app, CORS, static file mount |
| `engine/referee.py` | Modify | Extract resolve_* public methods; add load/dump state |
| `pyproject.toml` | Modify | Add fastapi, uvicorn, httpx deps |
| `tests/test_web_agent.py` | Create | WebAgent unit tests |
| `tests/test_session.py` | Create | Session store tests |
| `tests/test_runner.py` | Create | GameRunner integration tests |
| `tests/test_api.py` | Create | FastAPI endpoint tests |

---

## Task 1: WebAgent

**Files:**
- Create: `agents/web.py`
- Create: `tests/test_web_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_web_agent.py
import pytest
from engine.state import Phase, GameStateSnapshot, FactionState, FactionAssets, CoalitionState
from agents.web import WebAgent, HumanInputRequired


def _make_snapshot() -> GameStateSnapshot:
    fs = FactionState(
        faction_id="ussf", name="USSF", budget_per_turn=100, current_budget=100,
        assets=FactionAssets(),
    )
    return GameStateSnapshot(
        turn=1, phase=Phase.INVEST, faction_id="ussf",
        faction_state=fs, ally_states={}, adversary_estimates={},
        coalition_states={}, available_actions=["allocate_budget"],
    )


@pytest.mark.asyncio
async def test_web_agent_raises_human_input_required():
    agent = WebAgent()
    agent._last_snapshot = _make_snapshot()
    with pytest.raises(HumanInputRequired) as exc_info:
        await agent.submit_decision(Phase.INVEST)
    assert exc_info.value.phase == Phase.INVEST
    assert exc_info.value.snapshot is not None


@pytest.mark.asyncio
async def test_web_agent_is_human():
    agent = WebAgent()
    assert agent.is_human is True


@pytest.mark.asyncio
async def test_human_input_required_carries_snapshot():
    agent = WebAgent()
    snap = _make_snapshot()
    agent._last_snapshot = snap
    with pytest.raises(HumanInputRequired) as exc_info:
        await agent.submit_decision(Phase.OPERATIONS)
    assert exc_info.value.snapshot.faction_id == "ussf"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/tbarnes/projects/agents && source venv/bin/activate && pytest tests/test_web_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'agents.web'`

- [ ] **Step 3: Write the implementation**

```python
# agents/web.py
from engine.state import Phase, Decision, GameStateSnapshot
from agents.base import AgentInterface


class HumanInputRequired(Exception):
    def __init__(self, phase: Phase, snapshot: GameStateSnapshot):
        self.phase = phase
        self.snapshot = snapshot


class WebAgent(AgentInterface):
    is_human: bool = True

    async def submit_decision(self, phase: Phase) -> Decision:
        raise HumanInputRequired(phase, self._last_snapshot)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_web_agent.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add agents/web.py tests/test_web_agent.py
git commit -m "feat: add WebAgent that signals human input needed"
```

---

## Task 2: Update pyproject.toml with new deps

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add fastapi, uvicorn, httpx to dependencies**

Edit `pyproject.toml` — change the `dependencies` list to:

```toml
dependencies = [
    "anthropic>=0.50.0",
    "pydantic>=2.0.0",
    "aiosqlite>=0.20.0",
    "ruamel.yaml>=0.18.0",
    "rich>=13.0.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
]
```

And add `httpx` to the dev optional deps:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=1.0.0,<2.0.0",
    "httpx>=0.27.0",
]
```

- [ ] **Step 2: Install updated deps**

```bash
pip install -e ".[dev]"
```

Expected: Successfully installed fastapi, uvicorn, httpx (plus starlette, anyio etc.)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add fastapi, uvicorn, httpx dependencies"
```

---

## Task 3: Refactor GameReferee — extract resolution methods

**Files:**
- Modify: `engine/referee.py`

The goal: separate "collect decisions" from "resolve phase" so the web runner can inject pre-collected decisions. Existing TUI behavior is unchanged — `_run_*` methods now call the new public methods internally.

- [ ] **Step 1: Run existing tests to establish baseline**

```bash
pytest tests/test_referee.py tests/test_integration.py -v
```

Expected: all pass (note the count)

- [ ] **Step 2: Add `load_mutable_state` and `dump_mutable_state` to GameReferee**

In `engine/referee.py`, add these two methods to the `GameReferee` class (insert after `__init__`):

```python
def load_mutable_state(
    self,
    faction_states: dict,
    coalition_states: dict,
    tension_level: float,
    debris_level: float,
    turn_log: list,
    turn_log_summary: str,
    coordination_bonuses: dict,
    event_sda_malus: dict,
    prev_turn_ops: list,
    pending_kinetic_approaches: list,
    current_turn: int,
) -> None:
    """Populate internal state from serialized game state (used by web runner)."""
    from engine.state import FactionState, CoalitionState
    self.faction_states = {
        fid: FactionState.model_validate(fs) if isinstance(fs, dict) else fs
        for fid, fs in faction_states.items()
    }
    self.coalition_states = {
        cid: CoalitionState.model_validate(cs) if isinstance(cs, dict) else cs
        for cid, cs in coalition_states.items()
    }
    self.tension_level = tension_level
    self.debris_level = debris_level
    self._turn_log = list(turn_log)
    self._turn_log_summary = turn_log_summary
    self._coordination_bonuses = dict(coordination_bonuses)
    self._event_sda_malus = dict(event_sda_malus)
    self._prev_turn_ops = list(prev_turn_ops)
    self._pending_kinetic_approaches = list(pending_kinetic_approaches)
    self._current_turn = current_turn

def dump_mutable_state(self) -> dict:
    """Return serializable dict of all mutable game state."""
    return {
        "faction_states": {
            fid: fs.model_dump() for fid, fs in self.faction_states.items()
        },
        "coalition_states": {
            cid: cs.model_dump() for cid, cs in self.coalition_states.items()
        },
        "tension_level": self.tension_level,
        "debris_level": self.debris_level,
        "turn_log": list(self._turn_log),
        "turn_log_summary": self._turn_log_summary,
        "coordination_bonuses": dict(self._coordination_bonuses),
        "event_sda_malus": dict(self._event_sda_malus),
        "prev_turn_ops": list(self._prev_turn_ops),
        "pending_kinetic_approaches": list(self._pending_kinetic_approaches),
    }
```

- [ ] **Step 3: Extract `resolve_investment` from `_run_investment_phase`**

Replace the body of `_run_investment_phase` and add a new `resolve_investment` method:

```python
async def resolve_investment(self, turn: int, decisions: dict) -> None:
    """Resolve investment decisions (dict values may be Decision objects or JSON strings)."""
    from engine.state import Decision
    for fid, raw_decision in decisions.items():
        decision = Decision.model_validate_json(raw_decision) if isinstance(raw_decision, str) else raw_decision
        if decision.investment:
            fs = self.faction_states[fid]
            result = self.sim.investment_resolver.resolve(
                faction_id=fid,
                budget=fs.current_budget,
                allocation=decision.investment,
                turn=turn,
            )
            fs.assets.leo_nodes += result.immediate_assets.leo_nodes
            fs.assets.meo_nodes += result.immediate_assets.meo_nodes
            fs.assets.geo_nodes += result.immediate_assets.geo_nodes
            fs.assets.cislunar_nodes += result.immediate_assets.cislunar_nodes
            fs.assets.asat_deniable += result.immediate_assets.asat_deniable
            fs.assets.ew_jammers += result.immediate_assets.ew_jammers
            if result.immediate_assets.launch_capacity:
                fs.assets.launch_capacity += result.immediate_assets.launch_capacity
            fs.deferred_returns.extend(result.deferred_returns)
            fs.current_budget = max(0, fs.current_budget - result.budget_spent)
        await self.audit.write_decision(turn=turn, decision=decision if not isinstance(raw_decision, str) else Decision.model_validate_json(raw_decision))

async def _run_investment_phase(self, turn: int):
    decisions = await self._collect_decisions(Phase.INVEST, ["allocate_budget"])
    await self.resolve_investment(turn, decisions)
```

- [ ] **Step 4: Extract `resolve_operations` from `_run_operations_phase`**

Replace `_run_operations_phase` body and add `resolve_operations`:

```python
async def resolve_operations(self, turn: int, decisions: dict) -> None:
    """Resolve operations decisions. Call after pending kinetics are handled."""
    from engine.state import Decision
    self._prev_turn_ops = []
    self._coordination_bonuses = {}

    for fid, raw_decision in decisions.items():
        decision = Decision.model_validate_json(raw_decision) if isinstance(raw_decision, str) else raw_decision
        if not decision.operations:
            await self.audit.write_decision(turn=turn, decision=decision)
            continue

        fs = self.faction_states[fid]
        for op in decision.operations:
            target_fid = op.target_faction
            target_fs = self.faction_states.get(target_fid) if target_fid else None
            is_adversary = target_fs and target_fs.coalition_id != fs.coalition_id
            is_ally = target_fs and target_fs.coalition_id == fs.coalition_id

            if op.action_type == "task_assets":
                mission = op.parameters.get("mission", "")
                if mission == "intercept" and is_adversary and fs.assets.asat_kinetic > 0:
                    self._pending_kinetic_approaches.append({
                        "attacker_fid": fid,
                        "target_fid": target_fid,
                        "declared_turn": turn,
                    })
                    self._turn_log.append(
                        f"{fs.name} dispatched kinetic interceptor toward "
                        f"{target_fs.name} (arrives turn {turn + 1})"
                    )
                else:
                    self._prev_turn_ops.append("task_assets")
                    if target_fid and is_adversary:
                        self._turn_log.append(
                            f"{fs.name} tasked assets against {target_fs.name} (surveillance)"
                        )

            elif op.action_type == "gray_zone" and is_adversary:
                if fs.assets.asat_deniable > 0:
                    result = self.sim.conflict_resolver.resolve_deniable_asat(
                        attacker_assets=fs.assets,
                        defender_sda_level=target_fs.sda_level(),
                    )
                    nodes_hit = min(result["nodes_destroyed"], target_fs.assets.leo_nodes)
                    target_fs.assets.leo_nodes -= nodes_hit
                    fs.assets.asat_deniable -= 1
                    self.debris_level = min(self.debris_level + 0.05 * nodes_hit, 1.0)
                    fs.disruption_score += nodes_hit * 5
                    self._prev_turn_ops.append("deniable_strike")
                    detected = result["detected"]
                    attributed = result["attributed"]
                    suffix = (
                        f" ({'attributed to ' + fs.name if attributed else 'detected, source unclear'})"
                        if detected else " (undetected)"
                    )
                    self._turn_log.append(
                        f"{fs.name} gray-zone op vs {target_fs.name}: "
                        f"{nodes_hit} nodes disrupted{suffix}"
                    )
                elif fs.assets.ew_jammers > 0:
                    self._prev_turn_ops.append("gray_zone")
                    self._turn_log.append(f"{fs.name} EW jamming ops against {target_fs.name}")
                else:
                    self._prev_turn_ops.append("gray_zone")
                    self._turn_log.append(
                        f"{fs.name} attempted gray-zone ops against {target_fs.name} — no deniable assets"
                    )

            elif op.action_type == "coordinate" and target_fid:
                self._prev_turn_ops.append("coordinate")
                if is_ally:
                    loyalty_factor = 1.0
                    if self.tension_level > 0.7 and fs.coalition_loyalty < 0.6:
                        loyalty_factor = 0.5
                    bonus = 0.1 * loyalty_factor
                    self._coordination_bonuses[fid] = self._coordination_bonuses.get(fid, 0.0) + bonus
                    self._coordination_bonuses[target_fid] = self._coordination_bonuses.get(target_fid, 0.0) + bonus
                    note = " (loyalty-degraded)" if loyalty_factor < 1.0 else ""
                    self._turn_log.append(
                        f"{fs.name} coordinated with {target_fs.name} "
                        f"(+{bonus:.0%} SDA next snapshot{note})"
                    )
                else:
                    self._turn_log.append(
                        f"{fs.name} attempted coordination with non-ally {target_fid} — ignored"
                    )
            else:
                self._prev_turn_ops.append(op.action_type)

        await self.audit.write_decision(turn=turn, decision=decision)

    self._turn_log_summary = self._build_turn_log_summary(turn)

def resolve_pending_kinetics(self, turn: int) -> None:
    """Resolve kinetic approaches from the previous turn. Call at start of OPS phase."""
    resolved = [a for a in self._pending_kinetic_approaches if a["declared_turn"] == turn - 1]
    for approach in resolved:
        self._resolve_kinetic_approach(approach)
    for a in resolved:
        self._pending_kinetic_approaches.remove(a)

async def _run_operations_phase(self, turn: int):
    self.resolve_pending_kinetics(turn)
    decisions = await self._collect_decisions(
        Phase.OPERATIONS,
        ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"]
    )
    await self.resolve_operations(turn, decisions)
```

- [ ] **Step 5: Extract `generate_turn_events` and `resolve_response` from `_run_response_phase`**

```python
def generate_turn_events(self, turn: int) -> list:
    """Generate crisis events for this turn and apply their effects. Returns list of CrisisEvent."""
    self._event_sda_malus = {}
    all_factions = list(self.faction_states.keys())
    events = self.event_library.generate_events(
        tension_level=self.tension_level,
        affected_factions=all_factions,
        turn=turn,
        prev_ops=self._prev_turn_ops,
    )
    for event in events:
        if event.severity > 0.5:
            self.tension_level = min(self.tension_level + 0.1, 1.0)
        self._apply_event_effect(event)
    self._turn_log_summary = self._build_turn_log_summary(turn)
    return events

async def resolve_response(self, turn: int, decisions: dict, events: list) -> None:
    """Resolve response decisions. Call after generate_turn_events."""
    from engine.state import Decision, CrisisEvent
    for event in events:
        await self.audit.write_event(turn=turn, event=event)
        for agent in self.agents.values():
            agent.receive_event(event)

    for fid, raw_decision in decisions.items():
        decision = Decision.model_validate_json(raw_decision) if isinstance(raw_decision, str) else raw_decision
        if decision.response and decision.response.escalate:
            self.tension_level = min(self.tension_level + 0.15, 1.0)
            if decision.response.retaliate and decision.response.target_faction:
                self._resolve_retaliation(fid, decision.response.target_faction)
        await self.audit.write_decision(turn=turn, decision=decision)

    self._turn_log_summary = self._build_turn_log_summary(turn)

async def _run_response_phase(self, turn: int):
    events = self.generate_turn_events(turn)
    self._turn_log_summary = self._build_turn_log_summary(turn)
    decisions = await self._collect_decisions(
        Phase.RESPONSE,
        ["escalate", "de_escalate", "retaliate", "emergency_reallocation", "public_statement"]
    )
    await self.resolve_response(turn, decisions, events)
```

- [ ] **Step 6: Run existing tests to verify nothing broke**

```bash
pytest tests/test_referee.py tests/test_integration.py -v
```

Expected: same count passing as Step 1

- [ ] **Step 7: Commit**

```bash
git add engine/referee.py
git commit -m "refactor: extract resolve_* methods from GameReferee for web runner"
```

---

## Task 4: GameState model and session store

**Files:**
- Create: `api/__init__.py`
- Create: `api/routes/__init__.py`
- Create: `api/models.py`
- Create: `api/session.py`
- Create: `tests/test_session.py`

- [ ] **Step 1: Create package markers**

```bash
touch /Users/tbarnes/projects/agents/api/__init__.py
touch /Users/tbarnes/projects/agents/api/routes/__init__.py
```

- [ ] **Step 2: Write the failing session tests**

```python
# tests/test_session.py
import pytest
import tempfile
import os
from engine.state import Phase, FactionState, FactionAssets, CoalitionState
from api.models import GameState
from api.session import save_session, load_session, clear_session


def _make_game_state(session_id: str = "test-123") -> GameState:
    return GameState(
        session_id=session_id,
        scenario_id="test_scenario",
        scenario_name="Test Scenario",
        turn=1,
        total_turns=8,
        current_phase=Phase.INVEST,
        phase_decisions={},
        faction_states={
            "ussf": FactionState(
                faction_id="ussf", name="USSF",
                budget_per_turn=100, current_budget=100,
                assets=FactionAssets(),
            )
        },
        coalition_states={
            "west": CoalitionState(coalition_id="west", member_ids=["ussf"])
        },
        human_faction_id="ussf",
        victory_threshold=0.65,
        coalition_colors={"west": "green"},
    )


@pytest.mark.asyncio
async def test_save_and_load_session(tmp_path):
    db = str(tmp_path / "sessions.db")
    state = _make_game_state()
    await save_session(state, db_path=db)
    loaded = await load_session("test-123", db_path=db)
    assert loaded is not None
    assert loaded.session_id == "test-123"
    assert loaded.turn == 1
    assert loaded.human_faction_id == "ussf"


@pytest.mark.asyncio
async def test_load_missing_session_returns_none(tmp_path):
    db = str(tmp_path / "sessions.db")
    result = await load_session("nonexistent", db_path=db)
    assert result is None


@pytest.mark.asyncio
async def test_save_overwrites_existing(tmp_path):
    db = str(tmp_path / "sessions.db")
    state = _make_game_state()
    await save_session(state, db_path=db)
    state.turn = 3
    await save_session(state, db_path=db)
    loaded = await load_session("test-123", db_path=db)
    assert loaded.turn == 3
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'api.models'`

- [ ] **Step 4: Create `api/models.py`**

```python
# api/models.py
from typing import Optional, Any
from pydantic import BaseModel
from engine.state import Phase, FactionState, CoalitionState, GameStateSnapshot


class GameState(BaseModel):
    session_id: str
    scenario_id: str
    scenario_name: str
    turn: int
    total_turns: int
    current_phase: Phase
    phase_decisions: dict[str, str] = {}     # faction_id → Decision JSON string
    faction_states: dict[str, FactionState]
    coalition_states: dict[str, CoalitionState]
    tension_level: float = 0.2
    debris_level: float = 0.0
    pending_kinetic_approaches: list[dict] = []
    turn_log: list[str] = []
    turn_log_summary: str = ""
    coordination_bonuses: dict[str, float] = {}
    event_sda_malus: dict[str, float] = {}
    prev_turn_ops: list[str] = []
    events: list[dict] = []                  # crisis events this turn (for summary phase)
    human_faction_id: str
    human_snapshot: Optional[dict] = None   # serialized GameStateSnapshot
    use_advisor: bool = False
    agent_config: list[dict] = []
    game_over: bool = False
    result: Optional[dict] = None
    error: Optional[str] = None
    victory_threshold: float = 0.65
    coalition_colors: dict[str, str] = {}


class ScenarioFactionSummary(BaseModel):
    faction_id: str
    name: str
    archetype: str
    agent_type: str


class ScenarioSummary(BaseModel):
    id: str
    name: str
    description: str
    turns: int
    factions: list[ScenarioFactionSummary]


class AgentConfigEntry(BaseModel):
    faction_id: str
    agent_type: str   # "web" | "rule_based" | "ai_commander"
    use_advisor: bool = False


class CreateGameRequest(BaseModel):
    scenario_id: str
    agent_config: list[AgentConfigEntry]


class DecideRequest(BaseModel):
    phase: str
    decision: dict[str, Any]


class GameStateResponse(BaseModel):
    state: GameState
    coalition_dominance: dict[str, float]
```

- [ ] **Step 5: Create `api/session.py`**

```python
# api/session.py
import aiosqlite
from pathlib import Path
from api.models import GameState

_sessions: dict[str, GameState] = {}
_DEFAULT_DB = "output/sessions.db"


async def _ensure_table(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.commit()


async def save_session(state: GameState, db_path: str = _DEFAULT_DB) -> None:
    _sessions[state.session_id] = state
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await _ensure_table(db)
        await db.execute(
            "INSERT OR REPLACE INTO sessions (session_id, state_json) VALUES (?, ?)",
            (state.session_id, state.model_dump_json()),
        )
        await db.commit()


async def load_session(session_id: str, db_path: str = _DEFAULT_DB) -> GameState | None:
    if session_id in _sessions:
        return _sessions[session_id]
    try:
        async with aiosqlite.connect(db_path) as db:
            await _ensure_table(db)
            async with db.execute(
                "SELECT state_json FROM sessions WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    state = GameState.model_validate_json(row[0])
                    _sessions[session_id] = state
                    return state
    except Exception:
        pass
    return None


async def clear_session(session_id: str, db_path: str = _DEFAULT_DB) -> None:
    _sessions.pop(session_id, None)
    try:
        async with aiosqlite.connect(db_path) as db:
            await _ensure_table(db)
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()
    except Exception:
        pass
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_session.py -v
```

Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add api/__init__.py api/routes/__init__.py api/models.py api/session.py tests/test_session.py
git commit -m "feat: add GameState model and SQLite session store"
```

---

## Task 5: GameRunner

**Files:**
- Create: `api/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write the failing runner tests**

```python
# tests/test_runner.py
import pytest
from pathlib import Path
from api.runner import create_game, advance
from api.models import GameState
from engine.state import Phase


SCENARIO_ID = "two_superpowers"  # use the first .yaml in scenarios/


def _first_scenario_id() -> str:
    scenarios = list((Path(__file__).parent.parent / "scenarios").glob("*.yaml"))
    if not scenarios:
        pytest.skip("No scenario files found")
    return scenarios[0].stem


@pytest.mark.asyncio
async def test_create_game_returns_game_state(tmp_path):
    sid = _first_scenario_id()
    from scenarios.loader import load_scenario
    from pathlib import Path as P
    scenario = load_scenario(P("scenarios") / f"{sid}.yaml")
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {"faction_id": f.faction_id, "agent_type": "web" if f.faction_id == human_fid else "rule_based", "use_advisor": False}
        for f in scenario.factions
    ]
    state = await create_game(sid, agent_config, db_path=str(tmp_path / "s.db"))
    assert state.session_id
    assert state.turn == 0
    assert state.human_faction_id == human_fid
    assert state.game_over is False


@pytest.mark.asyncio
async def test_advance_returns_waiting_for_human(tmp_path):
    sid = _first_scenario_id()
    from scenarios.loader import load_scenario
    from pathlib import Path as P
    scenario = load_scenario(P("scenarios") / f"{sid}.yaml")
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {"faction_id": f.faction_id, "agent_type": "web" if f.faction_id == human_fid else "rule_based", "use_advisor": False}
        for f in scenario.factions
    ]
    state = await create_game(sid, agent_config, db_path=str(tmp_path / "s.db"))
    response = await advance(state.session_id, db_path=str(tmp_path / "s.db"))
    assert response.state.turn == 1
    assert response.state.current_phase == Phase.INVEST
    assert response.state.human_snapshot is not None
    assert response.coalition_dominance


@pytest.mark.asyncio
async def test_advance_after_decision_advances_phase(tmp_path):
    sid = _first_scenario_id()
    from scenarios.loader import load_scenario
    from pathlib import Path as P
    scenario = load_scenario(P("scenarios") / f"{sid}.yaml")
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {"faction_id": f.faction_id, "agent_type": "web" if f.faction_id == human_fid else "rule_based", "use_advisor": False}
        for f in scenario.factions
    ]
    state = await create_game(sid, agent_config, db_path=str(tmp_path / "s.db"))
    await advance(state.session_id, db_path=str(tmp_path / "s.db"))

    invest_decision = {
        "phase": "invest",
        "decision": {
            "investment": {
                "constellation": 0.5,
                "r_and_d": 0.5,
                "rationale": "test",
            }
        }
    }
    response = await advance(state.session_id, decision=invest_decision, db_path=str(tmp_path / "s.db"))
    assert response.state.current_phase in (Phase.OPERATIONS, Phase.RESPONSE)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_runner.py -v
```

Expected: `ModuleNotFoundError: No module named 'api.runner'`

- [ ] **Step 3: Create `api/runner.py`**

```python
# api/runner.py
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime

from engine.state import Phase, Decision, FactionState, CoalitionState
from engine.simulation import SimulationEngine
from engine.referee import GameReferee
from agents.base import AgentInterface
from agents.web import WebAgent, HumanInputRequired
from agents.rule_based import MahanianAgent
from scenarios.loader import load_scenario, Scenario
from output.audit import AuditTrail
from tui.header import NullGameHeader
from api.models import GameState, GameStateResponse
from api.session import save_session, load_session

_SCENARIOS_DIR = Path("scenarios")
_SESSIONS_DB = "output/sessions.db"


def _load_scenario(scenario_id: str) -> Scenario:
    return load_scenario(_SCENARIOS_DIR / f"{scenario_id}.yaml")


def _make_agents(scenario: Scenario, agent_config: list[dict]) -> dict[str, AgentInterface]:
    cfg_map = {c["faction_id"]: c for c in agent_config}
    agents = {}
    for faction in scenario.factions:
        cfg = cfg_map.get(faction.faction_id, {})
        agent_type = cfg.get("agent_type", "rule_based")
        if agent_type == "web":
            agent = WebAgent()
        elif agent_type == "ai_commander":
            from agents.ai_commander import AICommanderAgent
            from personas.builder import load_archetype
            import io
            from ruamel.yaml import YAML
            yaml = YAML()
            buf = io.StringIO()
            yaml.dump(load_archetype(faction.archetype), buf)
            agent = AICommanderAgent(persona_yaml=buf.getvalue())
        else:
            agent = MahanianAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent
    return agents


def _make_referee(scenario: Scenario, agents: dict, state: GameState) -> GameReferee:
    """Create a GameReferee pre-loaded with serialized game state."""
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    Path("output").mkdir(exist_ok=True)
    audit = AuditTrail(f"output/game_audit_{state.session_id[:8]}_{ts}.db")
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit, header=NullGameHeader())
    referee.load_mutable_state(
        faction_states=state.faction_states,
        coalition_states=state.coalition_states,
        tension_level=state.tension_level,
        debris_level=state.debris_level,
        turn_log=state.turn_log,
        turn_log_summary=state.turn_log_summary,
        coordination_bonuses=state.coordination_bonuses,
        event_sda_malus=state.event_sda_malus,
        prev_turn_ops=state.prev_turn_ops,
        pending_kinetic_approaches=state.pending_kinetic_approaches,
        current_turn=state.turn,
    )
    return referee, audit


def _sync_state_from_referee(state: GameState, referee: GameReferee) -> None:
    """Write referee's mutable state back into GameState."""
    mutable = referee.dump_mutable_state()
    from engine.state import FactionState, CoalitionState
    state.faction_states = {
        fid: FactionState.model_validate(fs) for fid, fs in mutable["faction_states"].items()
    }
    state.coalition_states = {
        cid: CoalitionState.model_validate(cs) for cid, cs in mutable["coalition_states"].items()
    }
    state.tension_level = mutable["tension_level"]
    state.debris_level = mutable["debris_level"]
    state.turn_log = mutable["turn_log"]
    state.turn_log_summary = mutable["turn_log_summary"]
    state.coordination_bonuses = mutable["coordination_bonuses"]
    state.event_sda_malus = mutable["event_sda_malus"]
    state.prev_turn_ops = mutable["prev_turn_ops"]
    state.pending_kinetic_approaches = mutable["pending_kinetic_approaches"]


def _compute_dominance(state: GameState, sim: SimulationEngine) -> dict[str, float]:
    all_assets = {fid: fs.assets for fid, fs in state.faction_states.items()}
    return {
        cid: sim.compute_coalition_dominance(cs.member_ids, all_assets)
        for cid, cs in state.coalition_states.items()
    }


def _check_victory(state: GameState, sim: SimulationEngine, scenario: Scenario) -> Optional[str]:
    dominance = _compute_dominance(state, sim)
    for cid, dom in dominance.items():
        if dom >= state.victory_threshold:
            return cid
    return None


async def create_game(
    scenario_id: str,
    agent_config: list[dict],
    db_path: str = _SESSIONS_DB,
) -> GameState:
    scenario = _load_scenario(scenario_id)
    session_id = str(uuid.uuid4())
    human_faction_id = next(
        c["faction_id"] for c in agent_config if c["agent_type"] == "web"
    )
    use_advisor = next(
        (c.get("use_advisor", False) for c in agent_config if c["faction_id"] == human_faction_id),
        False,
    )
    faction_states = {
        f.faction_id: FactionState(
            faction_id=f.faction_id,
            name=f.name,
            budget_per_turn=f.budget_per_turn,
            current_budget=f.budget_per_turn,
            assets=f.starting_assets.model_copy(deep=True),
            coalition_id=f.coalition_id,
            coalition_loyalty=f.coalition_loyalty,
        )
        for f in scenario.factions
    }
    coalition_states = {
        cid: CoalitionState(coalition_id=cid, member_ids=c.member_ids)
        for cid, c in scenario.coalitions.items()
    }
    coalition_colors = {
        cid: ("green" if i == 0 else "red")
        for i, cid in enumerate(scenario.coalitions)
    }
    state = GameState(
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario.name,
        turn=0,
        total_turns=scenario.turns,
        current_phase=Phase.INVEST,
        faction_states=faction_states,
        coalition_states=coalition_states,
        human_faction_id=human_faction_id,
        use_advisor=use_advisor,
        agent_config=agent_config,
        victory_threshold=scenario.victory.coalition_orbital_dominance,
        coalition_colors=coalition_colors,
    )
    await save_session(state, db_path=db_path)
    return state


async def advance(
    session_id: str,
    decision: Optional[dict] = None,
    db_path: str = _SESSIONS_DB,
) -> GameStateResponse:
    state = await load_session(session_id, db_path=db_path)
    if state is None:
        raise ValueError(f"Session {session_id} not found")

    state.error = None
    scenario = _load_scenario(state.scenario_id)
    sim = SimulationEngine()

    # Start turn 1 if new game
    if state.turn == 0:
        state.turn = 1
        state.turn_log = []
        state.events = []
        state.phase_decisions = {}
        _replenish_budgets(state, scenario)
        await save_session(state, db_path=db_path)

    # Apply human decision if provided
    if decision:
        phase = Phase(decision["phase"])
        dec_payload = {
            "phase": phase.value,
            "faction_id": state.human_faction_id,
        }
        # Merge decision fields into payload
        for k, v in decision.get("decision", {}).items():
            dec_payload[k] = v
        dec = Decision.model_validate(dec_payload)
        state.phase_decisions[state.human_faction_id] = dec.model_dump_json()
        await save_session(state, db_path=db_path)

    # Drive turn loop until human input needed or game over
    faction_ids = sorted(state.faction_states.keys())
    agents = _make_agents(scenario, state.agent_config)

    while not state.game_over:
        undecided = [fid for fid in faction_ids if fid not in state.phase_decisions]

        if not undecided:
            # All decided — resolve this phase
            referee, audit = _make_referee(scenario, agents, state)
            try:
                if state.current_phase == Phase.INVEST:
                    await audit.initialize()
                    await referee.resolve_investment(state.turn, state.phase_decisions)
                    _sync_state_from_referee(state, referee)
                    state.phase_decisions = {}
                    state.current_phase = Phase.OPERATIONS
                    referee.resolve_pending_kinetics(state.turn)
                    _sync_state_from_referee(state, referee)

                elif state.current_phase == Phase.OPERATIONS:
                    await audit.initialize()
                    await referee.resolve_operations(state.turn, state.phase_decisions)
                    _sync_state_from_referee(state, referee)
                    state.phase_decisions = {}
                    # Generate events before RESPONSE
                    events = referee.generate_turn_events(state.turn)
                    _sync_state_from_referee(state, referee)
                    state.events = [
                        {
                            "event_id": e.event_id,
                            "event_type": e.event_type,
                            "description": e.description,
                            "severity": e.severity,
                            "affected_factions": e.affected_factions,
                        }
                        for e in events
                    ]
                    state.current_phase = Phase.RESPONSE

                elif state.current_phase == Phase.RESPONSE:
                    await audit.initialize()
                    from engine.state import CrisisEvent
                    crisis_events = [CrisisEvent.model_validate(e) for e in state.events]
                    await referee.resolve_response(state.turn, state.phase_decisions, crisis_events)
                    _sync_state_from_referee(state, referee)
                    referee._update_faction_metrics()
                    _sync_state_from_referee(state, referee)
                    state.phase_decisions = {}
                    state.current_phase = Phase.INVEST  # signals "summary" to frontend
                    state.game_over = False

                    # Check victory
                    winner = _check_victory(state, sim, scenario)
                    if winner or state.turn >= state.total_turns:
                        state.game_over = True
                        state.result = {
                            "turns_completed": state.turn,
                            "winner_coalition": winner,
                            "final_dominance": _compute_dominance(state, sim),
                        }
                    else:
                        # Advance to next turn — but return summary first
                        # We signal "summary" by keeping current_phase as INVEST and turn unchanged
                        # Frontend shows TurnSummary then calls /advance to start next turn
                        await save_session(state, db_path=db_path)
                        break  # return state to frontend for summary display

            finally:
                await audit.close()

            await save_session(state, db_path=db_path)
            continue

        # Process next undecided faction
        next_fid = undecided[0]
        agent = agents[next_fid]

        if next_fid == state.human_faction_id:
            # Build snapshot for human
            referee, audit = _make_referee(scenario, agents, state)
            available = {
                Phase.INVEST: ["allocate_budget"],
                Phase.OPERATIONS: ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"],
                Phase.RESPONSE: ["escalate", "de_escalate", "retaliate", "public_statement"],
            }[state.current_phase]
            state.human_snapshot = referee._build_snapshot(
                state.human_faction_id, state.current_phase, available
            ).model_dump()
            await save_session(state, db_path=db_path)
            break  # waiting for human

        # AI agent
        referee, audit = _make_referee(scenario, agents, state)
        available = {
            Phase.INVEST: ["allocate_budget"],
            Phase.OPERATIONS: ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"],
            Phase.RESPONSE: ["escalate", "de_escalate", "retaliate", "public_statement"],
        }[state.current_phase]
        agent.receive_state(referee._build_snapshot(next_fid, state.current_phase, available))

        try:
            dec = await agent.submit_decision(state.current_phase)
            state.phase_decisions[next_fid] = dec.model_dump_json()
        except Exception:
            fallback = MahanianAgent()
            fallback.initialize(next(f for f in scenario.factions if f.faction_id == next_fid))
            fallback.receive_state(referee._build_snapshot(next_fid, state.current_phase, available))
            dec = await fallback.submit_decision(state.current_phase)
            state.phase_decisions[next_fid] = dec.model_dump_json()

        await save_session(state, db_path=db_path)  # checkpoint after each agent

    dominance = _compute_dominance(state, sim)
    return GameStateResponse(state=state, coalition_dominance=dominance)


def _replenish_budgets(state: GameState, scenario: Scenario) -> None:
    for faction in scenario.factions:
        fs = state.faction_states.get(faction.faction_id)
        if not fs:
            continue
        fs.current_budget = faction.budget_per_turn
        cid = faction.coalition_id
        if cid and cid in scenario.coalitions and scenario.coalitions[cid].hegemony_pool:
            fs.current_budget = int(fs.current_budget * 1.1)
        # Process deferred returns
        due = [r for r in fs.deferred_returns if r["turn_due"] <= state.turn]
        for r in due:
            if r["category"] == "r_and_d":
                fs.tech_tree["r_and_d"] = fs.tech_tree.get("r_and_d", 0) + r["amount"] // 20
            elif r["category"] == "education":
                fs.tech_tree["education"] = fs.tech_tree.get("education", 0) + r["amount"] // 30
        fs.deferred_returns = [r for r in fs.deferred_returns if r["turn_due"] > state.turn]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_runner.py -v
```

Expected: 3 passed (tests may be slow due to MahanianAgent AI calls — that's OK)

- [ ] **Step 5: Commit**

```bash
git add api/runner.py tests/test_runner.py
git commit -m "feat: add GameRunner with step-by-step turn execution"
```

---

## Task 6: FastAPI app and routes

**Files:**
- Create: `api/main.py`
- Create: `api/routes/scenarios.py`
- Create: `api/routes/game.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
# tests/test_api.py
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from api.main import app


def _first_scenario_id() -> str:
    scenarios = list(Path("scenarios").glob("*.yaml"))
    if not scenarios:
        pytest.skip("No scenario files found")
    return scenarios[0].stem


@pytest.mark.asyncio
async def test_list_scenarios():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/scenarios")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]
    assert "factions" in data[0]


@pytest.mark.asyncio
async def test_create_game(tmp_path, monkeypatch):
    monkeypatch.setattr("api.runner._SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setattr("api.session._DEFAULT_DB", str(tmp_path / "s.db"))
    sid = _first_scenario_id()
    from scenarios.loader import load_scenario
    scenario = load_scenario(Path("scenarios") / f"{sid}.yaml")
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {"faction_id": f.faction_id, "agent_type": "web" if f.faction_id == human_fid else "rule_based", "use_advisor": False}
        for f in scenario.factions
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/game/create", json={"scenario_id": sid, "agent_config": agent_config})
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body["state"]
    assert body["state"]["turn"] == 0


@pytest.mark.asyncio
async def test_advance_returns_human_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr("api.runner._SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setattr("api.session._DEFAULT_DB", str(tmp_path / "s.db"))
    sid = _first_scenario_id()
    from scenarios.loader import load_scenario
    scenario = load_scenario(Path("scenarios") / f"{sid}.yaml")
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {"faction_id": f.faction_id, "agent_type": "web" if f.faction_id == human_fid else "rule_based", "use_advisor": False}
        for f in scenario.factions
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/game/create", json={"scenario_id": sid, "agent_config": agent_config})
        session_id = r.json()["state"]["session_id"]
        r2 = await client.post(f"/api/game/{session_id}/advance")
    assert r2.status_code == 200
    body = r2.json()
    assert body["state"]["human_snapshot"] is not None
    assert body["state"]["turn"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 3: Create `api/routes/scenarios.py`**

```python
# api/routes/scenarios.py
from pathlib import Path
from fastapi import APIRouter
from scenarios.loader import load_scenario
from api.models import ScenarioSummary, ScenarioFactionSummary

router = APIRouter()
_SCENARIOS_DIR = Path("scenarios")


@router.get("/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios():
    results = []
    for path in sorted(_SCENARIOS_DIR.glob("*.yaml")):
        scenario = load_scenario(path)
        results.append(ScenarioSummary(
            id=path.stem,
            name=scenario.name,
            description=scenario.description,
            turns=scenario.turns,
            factions=[
                ScenarioFactionSummary(
                    faction_id=f.faction_id,
                    name=f.name,
                    archetype=f.archetype,
                    agent_type=f.agent_type,
                )
                for f in scenario.factions
            ],
        ))
    return results
```

- [ ] **Step 4: Create `api/routes/game.py`**

```python
# api/routes/game.py
from typing import Optional
from fastapi import APIRouter, HTTPException
from api.models import CreateGameRequest, DecideRequest, GameStateResponse
from api import runner
from api.session import load_session

router = APIRouter()


@router.post("/game/create", response_model=GameStateResponse)
async def create_game(req: CreateGameRequest):
    agent_config = [c.model_dump() for c in req.agent_config]
    state = await runner.create_game(req.scenario_id, agent_config)
    from engine.simulation import SimulationEngine
    sim = SimulationEngine()
    dominance = runner._compute_dominance(state, sim)
    return GameStateResponse(state=state, coalition_dominance=dominance)


@router.get("/game/{session_id}/state", response_model=GameStateResponse)
async def get_state(session_id: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    from engine.simulation import SimulationEngine
    sim = SimulationEngine()
    dominance = runner._compute_dominance(state, sim)
    return GameStateResponse(state=state, coalition_dominance=dominance)


@router.post("/game/{session_id}/advance", response_model=GameStateResponse)
async def advance(session_id: str):
    try:
        return await runner.advance(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/game/{session_id}/decide", response_model=GameStateResponse)
async def decide(session_id: str, req: DecideRequest):
    try:
        decision = {"phase": req.phase, "decision": req.decision}
        return await runner.advance(session_id, decision=decision)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/game/{session_id}/recommend")
async def recommend(session_id: str, phase: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not state.use_advisor:
        return {"recommendation": None}
    from scenarios.loader import load_scenario
    from pathlib import Path
    from engine.state import Phase, GameStateSnapshot
    from agents.ai_commander import AICommanderAgent
    from personas.builder import load_archetype
    from engine.referee import GameReferee
    from agents.web import WebAgent
    from tui.header import NullGameHeader
    import io
    from ruamel.yaml import YAML

    scenario = load_scenario(Path("scenarios") / f"{state.scenario_id}.yaml")
    human_faction = next(f for f in scenario.factions if f.faction_id == state.human_faction_id)
    yaml = YAML()
    buf = io.StringIO()
    yaml.dump(load_archetype(human_faction.archetype), buf)
    advisor = AICommanderAgent(persona_yaml=buf.getvalue())
    advisor.initialize(human_faction)

    if state.human_snapshot:
        snapshot = GameStateSnapshot.model_validate(state.human_snapshot)
        advisor.receive_state(snapshot)
        rec = await advisor.get_recommendation(Phase(phase))
        return {"recommendation": rec.model_dump() if rec else None}
    return {"recommendation": None}


@router.get("/game/{session_id}/result")
async def get_result(session_id: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not state.game_over:
        raise HTTPException(status_code=400, detail="Game is not over")
    return state.result


@router.post("/game/{session_id}/aar")
async def generate_aar(session_id: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    # AAR requires audit trail — look up session's audit DB
    from output.aar import AfterActionReportGenerator
    gen = AfterActionReportGenerator()
    # We don't have a direct audit handle here; use the scenario name for context
    text = await gen.generate(audit=None, scenario_name=state.scenario_name)
    return {"text": text}
```

- [ ] **Step 5: Create `api/main.py`**

```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from api.routes.scenarios import router as scenarios_router
from api.routes.game import router as game_router

app = FastAPI(title="Astrakon API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios_router, prefix="/api")
app.include_router(game_router, prefix="/api")

# Serve built frontend if present
_web_dist = Path("web/dist")
if _web_dist.exists():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="static")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: 3 passed

- [ ] **Step 7: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add api/main.py api/routes/scenarios.py api/routes/game.py tests/test_api.py
git commit -m "feat: add FastAPI app with scenario and game endpoints"
```

---

## Task 7: Launch script and manual smoke test

**Files:**
- Create: `run_api.py`

- [ ] **Step 1: Create launch script**

```python
# run_api.py
"""Run the Astrakon API server."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: Start the server**

```bash
python run_api.py
```

Expected: `Uvicorn running on http://0.0.0.0:8000`

- [ ] **Step 3: Smoke test — list scenarios**

In a new terminal:

```bash
curl http://localhost:8000/api/scenarios | python3 -m json.tool
```

Expected: JSON array with at least one scenario object containing `id`, `name`, `factions`.

- [ ] **Step 4: Smoke test — create game**

```bash
# Replace VALUES with first faction_id and second faction_id from step 3 output
curl -s -X POST http://localhost:8000/api/game/create \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "FIRST_SCENARIO_ID", "agent_config": [{"faction_id": "HUMAN_FACTION_ID", "agent_type": "web", "use_advisor": false}, {"faction_id": "AI_FACTION_ID", "agent_type": "rule_based", "use_advisor": false}]}' \
  | python3 -m json.tool | head -20
```

Expected: JSON with `state.session_id` and `state.turn: 0`.

- [ ] **Step 5: Stop server, commit**

```bash
git add run_api.py
git commit -m "feat: add uvicorn launch script"
```

---

## Final check

- [ ] **Run full test suite**

```bash
pytest -v
```

Expected: all tests pass with no failures.

- [ ] **Check .gitignore has output/ covered**

```bash
grep -E "^output/" .gitignore || echo "output/ NOT in .gitignore"
```

If missing, add `output/` to `.gitignore`:

```bash
echo "output/" >> .gitignore && git add .gitignore && git commit -m "chore: ignore output/ directory"
```
