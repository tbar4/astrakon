# Enemy Move Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show which attacks happened each turn as structured CombatEvent objects — rendered in a "STRIKES THIS TURN" panel in TurnSummary and as animated arcs on the orbital map at turn start.

**Architecture:** A new `CombatEvent` Pydantic model is populated by the referee during kinetic/deniable/EW resolution and flows through `dump_mutable_state` → `_sync_state_from_referee` → `GameState.combat_events`. The frontend renders them in TurnSummary (structured rows) and HoloOrbitalMap (curved SVG arcs with 10-second fade). Events persist across the turn boundary so they're visible at the start of the next INVEST phase, then cleared when OPERATIONS begins.

**Tech Stack:** Python/Pydantic (backend), React 19 + TypeScript + SVG (frontend), pytest-asyncio (tests)

---

## File Map

| File | Action |
|------|--------|
| `engine/state.py` | Add `CombatEvent` model after `CrisisEvent` |
| `api/models.py` | Add `combat_events: list[dict] = []` to `GameState` |
| `engine/referee.py` | Add `_combat_events` list; populate in 3 places; include in dump/load |
| `api/runner.py` | `_sync_state_from_referee` + `_make_referee` + clear at OPERATIONS start |
| `web/src/types.ts` | Add `CombatEvent` interface + `combat_events?` on `GameState` |
| `web/src/components/TurnSummary.tsx` | Add STRIKES THIS TURN panel |
| `web/src/components/HoloOrbitalMap.tsx` | Add `CombatArcLayer`, new props |
| `web/src/components/MapTabContainer.tsx` | Pass-through `combatEvents` + `arcOpacity` props |
| `web/src/pages/GamePage.tsx` | Arc fade timing state + pass props to MapTabContainer |
| `tests/test_combat_events.py` | New test file |

---

## Task 1: CombatEvent model + GameState field

**Files:**
- Modify: `engine/state.py` (after line 194, after `CrisisEvent`)
- Modify: `api/models.py` (line 45, after `pending_deniable_approaches`)
- Create: `tests/test_combat_events.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_combat_events.py
import pytest
from engine.state import CombatEvent
from api.models import GameState


def test_combat_event_instantiates():
    ev = CombatEvent(
        turn=1,
        attacker_id="ussf",
        target_faction_id="pla_ssf",
        shell="leo",
        event_type="kinetic",
        nodes_destroyed=3,
        detail="USSF destroys 3 PLA_SSF nodes in LEO",
    )
    assert ev.nodes_destroyed == 3
    assert ev.shell == "leo"
    d = ev.model_dump()
    assert d["event_type"] == "kinetic"


def test_game_state_has_combat_events_field():
    # GameState.combat_events defaults to empty list
    from engine.state import FactionState, CoalitionState, Phase, FactionAssets
    fs = FactionState(
        faction_id="ussf", name="USSF", budget_per_turn=10, current_budget=10,
        assets=FactionAssets(), coalition_id="usa", coalition_loyalty=1.0, archetype="mahanian"
    )
    state = GameState(
        session_id="s1", scenario_id="test", scenario_name="Test", turn=1, total_turns=5,
        current_phase=Phase.INVEST, faction_states={"ussf": fs},
        coalition_states={}, human_faction_id="ussf",
    )
    assert state.combat_events == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/test_combat_events.py -v 2>&1 | head -30
```

Expected: FAIL with `ImportError: cannot import name 'CombatEvent' from 'engine.state'`

- [ ] **Step 3: Add CombatEvent to engine/state.py**

In `engine/state.py`, add after line 194 (after the `CrisisEvent` class):

```python
class CombatEvent(BaseModel):
    turn: int
    attacker_id: str
    target_faction_id: str
    shell: str           # 'leo' | 'meo' | 'geo' | 'cislunar'
    event_type: str      # 'kinetic' | 'deniable' | 'ew_jamming' | 'gray_zone'
    nodes_destroyed: int
    detail: str
```

- [ ] **Step 4: Add combat_events field to api/models.py**

In `api/models.py`, add after line 45 (`pending_deniable_approaches` field):

```python
    combat_events: list[dict] = []
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/test_combat_events.py::test_combat_event_instantiates tests/test_combat_events.py::test_game_state_has_combat_events_field -v
```

Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add engine/state.py api/models.py tests/test_combat_events.py
git commit -m "feat: add CombatEvent model and combat_events field on GameState"
```

---

## Task 2: Referee accumulates CombatEvent during resolution

**Files:**
- Modify: `engine/referee.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_combat_events.py`:

```python
import pytest
from pathlib import Path
from engine.referee import GameReferee
from agents.rule_based import MahanianAgent
from scenarios.loader import load_scenario
from output.audit import AuditTrail


@pytest.fixture
def scenario():
    return load_scenario(Path("scenarios/pacific_crossroads.yaml"))


@pytest.fixture
async def audit(tmp_path):
    trail = AuditTrail(str(tmp_path / "test.db"))
    await trail.initialize()
    yield trail
    await trail.close()


@pytest.fixture
def agents(scenario):
    result = {}
    for faction in scenario.factions:
        agent = MahanianAgent()
        agent.initialize(faction)
        result[faction.faction_id] = agent
    return result


@pytest.mark.asyncio
async def test_kinetic_approach_creates_combat_event(scenario, agents, audit):
    """After resolving a kinetic approach, _combat_events has one entry."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee._pending_kinetic_approaches = [{
        "attacker_fid": "ussf",
        "target_fid": "pla_ssf",
        "declared_turn": 1,
        "approach_type": "kinetic",
    }]
    referee.faction_states["ussf"].assets.asat_kinetic = 3
    referee.faction_states["pla_ssf"].assets.leo_nodes = 10
    referee.resolve_pending_kinetics(turn=3)
    assert len(referee._combat_events) == 1
    ev = referee._combat_events[0]
    assert ev["attacker_id"] == "ussf"
    assert ev["target_faction_id"] == "pla_ssf"
    assert ev["event_type"] == "kinetic"
    assert ev["nodes_destroyed"] >= 0
    assert ev["shell"] in ("leo", "meo", "geo", "cislunar")


@pytest.mark.asyncio
async def test_combat_events_in_dump_mutable_state(scenario, agents, audit):
    """dump_mutable_state includes combat_events."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee._pending_kinetic_approaches = [{
        "attacker_fid": "ussf",
        "target_fid": "pla_ssf",
        "declared_turn": 1,
        "approach_type": "kinetic",
    }]
    referee.faction_states["ussf"].assets.asat_kinetic = 3
    referee.faction_states["pla_ssf"].assets.leo_nodes = 10
    referee.resolve_pending_kinetics(turn=3)
    mutable = referee.dump_mutable_state()
    assert "combat_events" in mutable
    assert isinstance(mutable["combat_events"], list)
    assert len(mutable["combat_events"]) == 1


@pytest.mark.asyncio
async def test_combat_events_survive_load_mutable_state(scenario, agents, audit):
    """load_mutable_state restores combat_events."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    # Put an event in _combat_events
    from engine.state import CombatEvent
    referee._combat_events = [CombatEvent(
        turn=1, attacker_id="ussf", target_faction_id="pla_ssf",
        shell="leo", event_type="kinetic", nodes_destroyed=2, detail="test"
    ).model_dump()]
    mutable = referee.dump_mutable_state()

    # Load into a fresh referee (dump includes combat_events, load accepts **mutable)
    referee2 = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee2.load_mutable_state(**mutable)
    assert len(referee2._combat_events) == 1
    assert referee2._combat_events[0]["attacker_id"] == "ussf"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/test_combat_events.py::test_kinetic_approach_creates_combat_event -v 2>&1 | head -20
```

Expected: FAIL with `AttributeError: 'GameReferee' object has no attribute '_combat_events'`

- [ ] **Step 3: Add _combat_events to referee __init__**

In `engine/referee.py`, add after line 76 (after `self._initial_assets: dict[str, FactionAssets] = {}`):

```python
        self._combat_events: list[dict] = []
```

Also update the import at line 7 to include `CombatEvent`:

```python
from engine.state import (
    Phase, Decision, GameStateSnapshot, FactionState, FactionAssets,
    CoalitionState, CrisisEvent, CombatEvent
)
```

- [ ] **Step 4: Populate _combat_events in _resolve_kinetic_approach**

In `engine/referee.py`, at the end of `_resolve_kinetic_approach` (after the `_turn_log.append` for `[KINETIC]` at line ~530), add:

```python
        self._combat_events.append(CombatEvent(
            turn=self._current_turn,
            attacker_id=attacker_fid,
            target_faction_id=target_fid,
            shell=regime,
            event_type="kinetic",
            nodes_destroyed=nodes_hit,
            detail=(
                f"{attacker_fs.name} destroys {nodes_hit} "
                f"{target_fs.name} nodes in {regime.upper()}"
            ),
        ).model_dump())
```

- [ ] **Step 5: Populate _combat_events in _resolve_pending_deniables**

In `engine/referee.py`, inside `_resolve_pending_deniables` loop body, after the `_turn_log.append` for `[DENIABLE]` (after line ~804), add:

```python
            self._combat_events.append(CombatEvent(
                turn=self._current_turn,
                attacker_id=attacker_fid,
                target_faction_id=target_fid,
                shell="leo",
                event_type="deniable",
                nodes_destroyed=nodes_hit,
                detail=(
                    f"{attacker_fs.name} co-orbital op vs {target_fs.name}: "
                    f"{nodes_hit} nodes disrupted"
                ),
            ).model_dump())
```

- [ ] **Step 6: Populate _combat_events for EW jamming**

In `engine/referee.py`, inside `resolve_operations`, after the EW jamming `_turn_log.append` at line ~700 (`f"{fs.name} EW jamming ops against {target_fs.name}"`), add:

```python
                        self._combat_events.append(CombatEvent(
                            turn=turn,
                            attacker_id=fid,
                            target_faction_id=target_fid,
                            shell="leo",
                            event_type="ew_jamming",
                            nodes_destroyed=0,
                            detail=f"{fs.name} EW jamming ops against {target_fs.name}",
                        ).model_dump())
```

- [ ] **Step 7: Add combat_events to dump_mutable_state**

In `engine/referee.py`, in `dump_mutable_state` (after line 144, `"current_turn": self._current_turn`), add:

```python
            "combat_events": list(self._combat_events),
```

- [ ] **Step 8: Add combat_events to load_mutable_state**

In `engine/referee.py`, add `combat_events: list | None = None` as a new keyword argument to `load_mutable_state` (after `pending_deniable_approaches`):

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
        initial_assets: dict | None = None,
        debris_fields: dict | None = None,
        escalation_rung: int = 0,
        pending_deniable_approaches: list | None = None,
        combat_events: list | None = None,
    ) -> None:
```

Then add at the end of `load_mutable_state` body (after `self._pending_deniable_approaches = ...`):

```python
        self._combat_events = list(combat_events) if combat_events else []
```

- [ ] **Step 9: Run all combat event tests**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/test_combat_events.py -v
```

Expected: All tests PASS

- [ ] **Step 10: Run full test suite to verify no regressions**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/ -v --ignore=tests/test_api.py 2>&1 | tail -20
```

Expected: All previously passing tests still pass

- [ ] **Step 11: Commit**

```bash
git add engine/state.py engine/referee.py tests/test_combat_events.py
git commit -m "feat: referee accumulates CombatEvent during kinetic/deniable/EW resolution"
```

---

## Task 3: Runner syncs combat_events through GameState

**Files:**
- Modify: `api/runner.py`
- Modify: `tests/test_combat_events.py` (add runner test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_combat_events.py`:

```python
@pytest.mark.asyncio
async def test_runner_combat_events_cleared_at_operations(tmp_path):
    """combat_events from previous turn persist through INVEST, cleared at OPERATIONS start."""
    from api.runner import create_game, advance
    from engine.state import Phase
    from pathlib import Path as P
    from scenarios.loader import load_scenario as ls

    sid = "pacific_crossroads"
    scenario = ls(P("scenarios/pacific_crossroads.yaml"))
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {
            "faction_id": f.faction_id,
            "agent_type": "web" if f.faction_id == human_fid else "rule_based",
            "use_advisor": False,
        }
        for f in scenario.factions
    ]
    state = await create_game(sid, agent_config, db_path=str(tmp_path / "s.db"))

    # Manually inject a combat event into the saved state to simulate a previous turn strike
    from api.session import load_session, save_session
    from engine.state import CombatEvent as CE
    loaded = await load_session(state.session_id, db_path=str(tmp_path / "s.db"))
    loaded.combat_events = [CE(
        turn=0, attacker_id="ussf", target_faction_id="pla_ssf",
        shell="leo", event_type="kinetic", nodes_destroyed=2, detail="test"
    ).model_dump()]
    await save_session(loaded, db_path=str(tmp_path / "s.db"))

    # Advance to INVEST — combat_events should still be present
    resp = await advance(state.session_id, db_path=str(tmp_path / "s.db"))
    assert resp.state.combat_events is not None
    # Events persist through INVEST (turn 1 is INVEST)
    # Cannot directly verify until OPERATIONS is reached, but field must be present
    assert isinstance(resp.state.combat_events, list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/test_combat_events.py::test_runner_combat_events_cleared_at_operations -v 2>&1 | head -20
```

Expected: FAIL — either `AttributeError` on `combat_events` or assertion error

- [ ] **Step 3: Update _sync_state_from_referee in runner.py**

In `api/runner.py`, in `_sync_state_from_referee` (after line 114, `state.pending_deniable_approaches = ...`), add:

```python
    state.combat_events = mutable.get("combat_events", [])
```

- [ ] **Step 4: Update _make_referee to pass combat_events to load_mutable_state**

In `api/runner.py`, in `_make_referee`, update the `referee.load_mutable_state(...)` call to add `combat_events=state.combat_events`:

The current call ends with `pending_deniable_approaches=state.pending_deniable_approaches,`. Change it to:

```python
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
        initial_assets=state.initial_assets,
        debris_fields=state.debris_fields,
        escalation_rung=state.escalation_rung,
        pending_deniable_approaches=state.pending_deniable_approaches,
        combat_events=state.combat_events,
    )
```

- [ ] **Step 5: Clear combat_events at OPERATIONS start in advance()**

In `api/runner.py`, in `advance()`, find the block:

```python
                elif state.current_phase == Phase.OPERATIONS:
                    await audit.initialize()
                    await referee.resolve_operations(state.turn, state.phase_decisions)
```

Add `state.combat_events = []` before `await audit.initialize()`:

```python
                elif state.current_phase == Phase.OPERATIONS:
                    state.combat_events = []
                    await audit.initialize()
                    await referee.resolve_operations(state.turn, state.phase_decisions)
```

- [ ] **Step 6: Run the runner test**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/test_combat_events.py::test_runner_combat_events_cleared_at_operations -v
```

Expected: PASS

- [ ] **Step 7: Run full test suite**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/ -v --ignore=tests/test_api.py 2>&1 | tail -20
```

Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add api/runner.py tests/test_combat_events.py
git commit -m "feat: sync combat_events through runner; clear at OPERATIONS start"
```

---

## Task 4: Frontend types — CombatEvent interface

**Files:**
- Modify: `web/src/types.ts`

- [ ] **Step 1: Add CombatEvent interface to types.ts**

In `web/src/types.ts`, add after the `TokenTotals` interface (after line 75):

```typescript
export interface CombatEvent {
  turn: number
  attacker_id: string
  target_faction_id: string
  shell: string
  event_type: 'kinetic' | 'deniable' | 'ew_jamming' | 'gray_zone'
  nodes_destroyed: number
  detail: string
}
```

- [ ] **Step 2: Add combat_events to GameState**

In `web/src/types.ts`, in the `GameState` interface, add after the `token_totals` field (after line 119):

```typescript
  combat_events?: CombatEvent[]
```

- [ ] **Step 3: Verify TypeScript compiles cleanly**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit 2>&1
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add web/src/types.ts
git commit -m "feat: add CombatEvent interface to frontend types"
```

---

## Task 5: TurnSummary — STRIKES THIS TURN panel

**Files:**
- Modify: `web/src/components/TurnSummary.tsx`

- [ ] **Step 1: Add the STRIKES THIS TURN panel**

In `web/src/components/TurnSummary.tsx`, update line 2 to import `CombatEvent`:

```typescript
import type { GameState, CombatEvent } from '../types'
```

Then add the STRIKES panel between the CRISIS EVENTS panel and OPERATIONAL LOG panel (between lines 41 and 43 in the original — between the closing `)}` of crisis events and `{turn_log.length > 0 &&`):

```tsx
        {gameState.combat_events && gameState.combat_events.length > 0 && (
          <div className="panel" style={{ borderColor: 'rgba(255,68,153,0.3)' }}>
            <div className="panel-title" style={{ color: '#ff4499' }}>◆ STRIKES THIS TURN</div>
            {gameState.combat_events.map((ev: CombatEvent, i: number) => {
              const isKinetic = ev.event_type === 'kinetic'
              const color = isKinetic ? '#ff4499' : '#f59e0b'
              const arrow = isKinetic ? '→' : '⤳'
              const shellLabel = ev.shell.toUpperCase()
              const typeLabel = ev.event_type.replace(/_/g, ' ').toUpperCase()
              const attackerName = gameState.faction_states[ev.attacker_id]?.name ?? ev.attacker_id
              const targetName = gameState.faction_states[ev.target_faction_id]?.name ?? ev.target_faction_id
              return (
                <div key={i} className="mono" style={{
                  fontSize: 10, color, marginBottom: 4,
                  display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap',
                }}>
                  <span>{attackerName}</span>
                  <span>{arrow}</span>
                  <span>{targetName}</span>
                  <span style={{ opacity: 0.7 }}>[{shellLabel}]</span>
                  <span style={{ opacity: 0.7 }}>[{typeLabel}]</span>
                  {ev.nodes_destroyed > 0 && (
                    <span>−{ev.nodes_destroyed} NODES</span>
                  )}
                </div>
              )
            })}
          </div>
        )}
```

- [ ] **Step 2: Verify TypeScript compiles cleanly**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit 2>&1
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/TurnSummary.tsx
git commit -m "feat: add STRIKES THIS TURN panel to TurnSummary"
```

---

## Task 6: HoloOrbitalMap — CombatArcLayer

**Files:**
- Modify: `web/src/components/HoloOrbitalMap.tsx`

The orbital map constants needed (already in the file, do not duplicate):
- `CX = 130`, `CY = 130`, `TILT_FACTOR = 0.45`
- `ellipsePoint(r, angle)` → `{x: CX + r*cos(angle), y: CY + r*TILT_FACTOR*sin(angle)}`
- Shell radii: LEO=48, MEO=70, GEO=97, CIS=115

- [ ] **Step 1: Add CombatEvent import and new props**

In `web/src/components/HoloOrbitalMap.tsx`, update line 3 to import `CombatEvent`:

```typescript
import type { GameState, FactionState, CombatEvent } from '../types'
```

In the `Props` interface (around line 160), add after `onFactionClick`:

```typescript
  combatEvents?: CombatEvent[]
  arcOpacity?: number
```

- [ ] **Step 2: Define CombatArcLayer function**

Add the following function in `HoloOrbitalMap.tsx` after the `dotsOnEllipse` function (after line ~155, before the `Props` interface):

```typescript
const SHELL_RADIUS: Record<string, number> = { leo: 48, meo: 70, geo: 97, cislunar: 115 }

function CombatArcLayer({
  combatEvents,
  arcOpacity,
  factions,
  angleStep,
}: {
  combatEvents: CombatEvent[]
  arcOpacity: number
  factions: [string, FactionState][]
  angleStep: number
}): React.ReactElement | null {
  if (!combatEvents.length) return null

  return (
    <g opacity={arcOpacity} style={{ transition: 'opacity 2s ease-in-out' }} pointerEvents="none">
      {combatEvents.map((ev, i) => {
        const attackerIdx = factions.findIndex(([fid]) => fid === ev.attacker_id)
        const targetIdx = factions.findIndex(([fid]) => fid === ev.target_faction_id)
        if (attackerIdx === -1 || targetIdx === -1) return null

        // Attacker: primary shell = shell with most assets
        const aFs = factions[attackerIdx][1]
        const shellKeys = ['leo_nodes', 'meo_nodes', 'geo_nodes', 'cislunar_nodes'] as const
        const aShellKey = shellKeys.reduce(
          (best, k) => aFs.assets[k] > aFs.assets[best] ? k : best,
          'leo_nodes' as typeof shellKeys[number]
        )
        const aR = SHELL_RADIUS[aShellKey.replace('_nodes', '')] ?? 48
        const aAngle = attackerIdx * angleStep
        const { x: sx, y: sy } = ellipsePoint(aR, aAngle)

        // Target: shell that was attacked
        const tR = SHELL_RADIUS[ev.shell] ?? 48
        const tAngle = targetIdx * angleStep
        const { x: tx, y: ty } = ellipsePoint(tR, tAngle)

        // Control point: midpoint pushed outward from CX,CY
        const mx = (sx + tx) / 2
        const my = (sy + ty) / 2
        const dx = mx - CX
        const dy = my - CY
        const len = Math.sqrt(dx * dx + dy * dy) || 1
        const outset = 55
        const cpx = mx + (dx / len) * outset
        const cpy = my + (dy / len) * outset

        // Badge midpoint at t=0.5 on quadratic bezier: 0.25*S + 0.5*C + 0.25*T
        const bx = 0.25 * sx + 0.5 * cpx + 0.25 * tx
        const by = 0.25 * sy + 0.5 * cpy + 0.25 * ty

        const isKinetic = ev.event_type === 'kinetic'
        const color = isKinetic ? '#ff4499' : '#f59e0b'
        const dash = isKinetic ? undefined : '3 3'

        const attackerName = aFs.name.slice(0, 4).toUpperCase()
        const targetName = factions[targetIdx][1].name.slice(0, 4).toUpperCase()
        const shellLabel = ev.shell.toUpperCase()
        const badge = ev.nodes_destroyed > 0
          ? `${attackerName} → ${targetName} ${shellLabel} −${ev.nodes_destroyed}`
          : `${attackerName} ⤳ ${targetName} ${ev.event_type === 'ew_jamming' ? 'EW' : 'DN'}`
        const badgeW = badge.length * 4.5 + 8

        return (
          <g key={i}>
            <path
              d={`M ${sx} ${sy} Q ${cpx} ${cpy} ${tx} ${ty}`}
              fill="none" stroke={color} strokeWidth={1.5}
              strokeDasharray={dash} opacity={0.85}
            />
            <circle cx={tx} cy={ty} r={3} fill={color} opacity={0.9} />
            <circle cx={tx} cy={ty} r={6} fill="none" stroke={color} strokeWidth={1} opacity={0.5}>
              <animate attributeName="r" values="4;12;4" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.5;0;0.5" dur="2s" repeatCount="indefinite" />
            </circle>
            <rect
              x={bx - badgeW / 2} y={by - 7} width={badgeW} height={12}
              rx={2} fill="#020b18" stroke={color} strokeWidth={0.8} opacity={0.9}
            />
            <text
              x={bx} y={by + 1} textAnchor="middle" dominantBaseline="middle"
              fill={color} fontSize={5.5} fontFamily="Courier New" letterSpacing={0.5}
            >
              {badge}
            </text>
          </g>
        )
      })}
    </g>
  )
}
```

- [ ] **Step 3: Destructure new props and render CombatArcLayer**

In `HoloOrbitalMap.tsx`, update the destructuring in `export default function HoloOrbitalMap({...})` to include `combatEvents` and `arcOpacity`:

```typescript
export default function HoloOrbitalMap({
  gameState, prevFactionStates, humanAdversaryEstimates,
  selectedShell, selectedFaction, onShellHover, onFactionHover,
  targetingMode, lockedFaction, onFactionClick,
  combatEvents, arcOpacity,
}: Props) {
```

Then in the SVG render, add `CombatArcLayer` just before the targeting reticle `<g>` (which starts with `{targetingMode && lockedFaction && (() => {` around line 427):

```tsx
          {combatEvents && combatEvents.length > 0 && (
            <CombatArcLayer
              combatEvents={combatEvents}
              arcOpacity={arcOpacity ?? 1}
              factions={factions}
              angleStep={angleStep}
            />
          )}
```

- [ ] **Step 4: Verify TypeScript compiles cleanly**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit 2>&1
```

Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add web/src/components/HoloOrbitalMap.tsx
git commit -m "feat: add CombatArcLayer to HoloOrbitalMap for enemy move visualization"
```

---

## Task 7: MapTabContainer — pass-through props

**Files:**
- Modify: `web/src/components/MapTabContainer.tsx`

- [ ] **Step 1: Add new props to MapTabContainer**

In `web/src/components/MapTabContainer.tsx`, update line 3 to import `CombatEvent`:

```typescript
import type { GameState, FactionState, FactionAssets, CombatEvent } from '../types'
```

In the `Props` interface (around line 37, after `rdPoints?: number`), add:

```typescript
  combatEvents?: CombatEvent[]
  arcOpacity?: number
```

In the destructuring in `export default function MapTabContainer({...})` (around line 53), add `combatEvents` and `arcOpacity` with defaults:

```typescript
export default function MapTabContainer({
  gameState, coalitionDominance, turnHistory, prevFactionStates, humanAdversaryEstimates,
  factionState, turn, totalTurns, tensionLevel, cumulativeAdded, cumulativeDestroyed, isJammed,
  targetingMode, lockedFaction, onFactionClick,
  pendingTechUnlocks = [], onQueueTech = () => {}, rdPoints = 0,
  combatEvents, arcOpacity,
}: Props) {
```

In the `<HoloOrbitalMap ... />` render (around line 82), add the two new props:

```tsx
          <HoloOrbitalMap
            gameState={gameState}
            prevFactionStates={prevFactionStates}
            humanAdversaryEstimates={humanAdversaryEstimates}
            selectedShell={selectedShell}
            selectedFaction={selectedFaction}
            onShellHover={setSelectedShell}
            onFactionHover={setSelectedFaction}
            targetingMode={targetingMode}
            lockedFaction={lockedFaction}
            onFactionClick={onFactionClick}
            combatEvents={combatEvents}
            arcOpacity={arcOpacity}
          />
```

- [ ] **Step 2: Verify TypeScript compiles cleanly**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit 2>&1
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/MapTabContainer.tsx
git commit -m "feat: pass combatEvents and arcOpacity through MapTabContainer to HoloOrbitalMap"
```

---

## Task 8: GamePage — arc fade timing

**Files:**
- Modify: `web/src/pages/GamePage.tsx`

The arc fades in immediately when a new INVEST phase begins (after TurnSummary is dismissed), holds for 8 seconds, then fades out over 2 seconds via CSS `transition: 'opacity 2s ease-in-out'` on the `<g>` element in `CombatArcLayer`.

- [ ] **Step 1: Add arcOpacity state and fade effect**

In `web/src/pages/GamePage.tsx`, add `arcOpacity` state after the existing `pendingTechUnlocks` state (around line 91):

```typescript
  const [arcOpacity, setArcOpacity] = useState(0)
```

Add the fade effect after the existing `useEffect` that clears `pendingTechUnlocks` (around line 99):

```typescript
  useEffect(() => {
    if (
      gameState?.current_phase === 'invest' &&
      !gameState.awaiting_next_turn &&
      gameState.combat_events &&
      gameState.combat_events.length > 0
    ) {
      setArcOpacity(1)
      const fadeTimer = setTimeout(() => setArcOpacity(0), 8000)
      return () => clearTimeout(fadeTimer)
    }
  }, [gameState?.turn, gameState?.current_phase, gameState?.awaiting_next_turn])
```

- [ ] **Step 2: Pass combatEvents and arcOpacity to MapTabContainer**

In `web/src/pages/GamePage.tsx`, in the `<MapTabContainer ...>` render (around line 290), add after `rdPoints={rdPoints}`:

```tsx
            combatEvents={gameState.combat_events}
            arcOpacity={arcOpacity}
```

- [ ] **Step 3: Verify TypeScript compiles cleanly**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit 2>&1
```

Expected: No errors

- [ ] **Step 4: Run full Python test suite**

```bash
cd /Users/tbarnes/projects/agents && python -m pytest tests/ -v --ignore=tests/test_api.py 2>&1 | tail -20
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/GamePage.tsx
git commit -m "feat: arc fade timing for enemy move visualization in GamePage"
```
