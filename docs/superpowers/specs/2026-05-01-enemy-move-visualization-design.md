# Enemy Move Visualization Design

> **For agentic workers:** This spec is the source of truth. Read it fully before implementing. Each section maps to one or more implementation tasks.

## Overview

After each turn's RESPONSE phase resolves, the game records which attacks happened as structured `CombatEvent` objects. These appear in two places:

1. A **"STRIKES THIS TURN"** panel in the existing `TurnSummary` overlay (shown at turn end)
2. Animated **curved arc overlays** on the ORBITAL map that appear briefly at the start of the next turn (10-second fade, matching the existing ±N node-delta animation)

## Design Decisions

- **Arc style:** Curved arc + floating mid-path badge (e.g. `"USSF → PLA LEO −3"`). Kinetic = solid red (`#ff4499`). Deniable / EW = dashed amber (`#f59e0b`).
- **Timing:** Arcs appear on both the TurnSummary panel AND briefly on the orbital map at the start of the next turn.
- **Data source:** Structured `combat_events: list[CombatEvent]` field on `GameState` — populated by the referee, not parsed from turn_log text.

---

## Section 1: Backend — CombatEvent Model

### `engine/state.py`

Add a new Pydantic model after `CrisisEvent`:

```python
class CombatEvent(BaseModel):
    turn: int
    attacker_id: str
    target_faction_id: str
    shell: str           # 'leo' | 'meo' | 'geo' | 'cislunar'
    event_type: str      # 'kinetic' | 'deniable' | 'ew_jamming' | 'gray_zone'
    nodes_destroyed: int  # 0 for EW / gray_zone
    detail: str           # "PLA destroys 3 USSF nodes in LEO"
```

### `api/models.py`

Add to `GameState`:

```python
combat_events: list[dict] = []
```

---

## Section 2: Backend — Referee Accumulation

### `engine/referee.py`

Add instance variable in `__init__` (alongside existing `self._pending_kinetics` etc.):

```python
self._combat_events: list = []  # CombatEvent dicts, accumulated per turn
```

**Populate in `_resolve_kinetic_approach`** — after computing `killed` nodes, append:

```python
from engine.state import CombatEvent
self._combat_events.append(CombatEvent(
    turn=turn,
    attacker_id=approach.attacker_id,
    target_faction_id=approach.target_faction_id,
    shell=approach.shell,
    event_type='kinetic',
    nodes_destroyed=killed,
    detail=f"{attacker_name} destroys {killed} {approach.target_faction_id.upper()} nodes in {approach.shell.upper()}",
).model_dump())
```

**Populate in `_resolve_pending_deniables`** — after applying effect, append a `CombatEvent` with `event_type='deniable'`, `nodes_destroyed=0` (deniable ops degrade scores, not nodes directly).

**Populate in `resolve_operations`** — after EW jamming is applied (where `[EW]` is logged), append a `CombatEvent` with `event_type='ew_jamming'`, `nodes_destroyed=0`.

**Include in `dump_mutable_state`:**

```python
"combat_events": self._combat_events,
```

**Restore in `load_mutable_state`:**

```python
self._combat_events = state.get("combat_events", [])
```

---

## Section 3: Backend — Runner Integration

### `api/runner.py`

**`_sync_state_from_referee`** — add:

```python
state.combat_events = mutable.get("combat_events", [])
```

**`advance()`** — at the top of OPERATIONS phase resolution (before calling `resolve_operations`), clear old events:

```python
elif state.current_phase == Phase.OPERATIONS:
    state.combat_events = []   # clear previous turn's events before new combat
    await audit.initialize()
    ...
```

This means combat_events from turn N persist through:
- RESPONSE resolution (populated)
- TurnSummary display (`awaiting_next_turn=True`)
- New turn INVEST phase (arcs visible on orbital map)
- Cleared when OPERATIONS begins (new combat replaces them)

---

## Section 4: Frontend — Types

### `web/src/types.ts`

Add `CombatEvent` interface:

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

Add to `GameState` interface:

```typescript
combat_events?: CombatEvent[]
```

---

## Section 5: Frontend — TurnSummary Panel

### `web/src/components/TurnSummary.tsx`

Add a **"STRIKES THIS TURN"** panel between CRISIS EVENTS and OPERATIONAL LOG. Only render when `gameState.combat_events && gameState.combat_events.length > 0`.

Import `CombatEvent` from `../types`.

Each row renders:
- Attacker faction name (colored by coalition)
- Arrow `→` (kinetic) or `⤳` (deniable/EW)  
- Target faction name
- Shell badge: `[LEO]` / `[MEO]` / `[GEO]` / `[CIS]`
- Event type badge: `[KINETIC]` (red) / `[DENIABLE]` (amber) / `[EW]` (amber)
- Node count: `−N NODES` if `nodes_destroyed > 0`

Panel header style: matches existing CRISIS EVENTS panel (`borderColor: 'rgba(255,68,153,0.3)'`, title color `#ff4499`).

Row colors: kinetic rows use `#ff4499`, deniable/EW rows use `#f59e0b`.

Faction color helper: use same logic as existing `factionColor()` in HoloOrbitalMap — human faction = `#00ff88`, coalition green = `#00ff88`, coalition red = `#ff4499`, neutral/other = `#00d4ff`. Import `GameState` type and pass `gameState` for lookup.

---

## Section 6: Frontend — Orbital Map Arc Overlay

### `web/src/components/HoloOrbitalMap.tsx`

**New props (add to `Props` interface):**

```typescript
combatEvents?: CombatEvent[]
arcOpacity?: number  // 0–1, controlled by parent for fade
```

**Import `CombatEvent` from `../types`.**

**`CombatArcLayer` helper function** (defined inside the module, above the component):

```typescript
function CombatArcLayer({
  combatEvents, arcOpacity, factions, angleStep,
}: {
  combatEvents: CombatEvent[]
  arcOpacity: number
  factions: [string, FactionState][]
  angleStep: number
}): React.ReactElement | null {
  if (!combatEvents.length) return null

  const shellRadius: Record<string, number> = {
    leo: 48, meo: 70, geo: 97, cislunar: 115,
  }

  return (
    <g opacity={arcOpacity} style={{ transition: 'opacity 2s ease-in-out' }} pointerEvents="none">
      {combatEvents.map((ev, i) => {
        const attackerIdx = factions.findIndex(([fid]) => fid === ev.attacker_id)
        const targetIdx = factions.findIndex(([fid]) => fid === ev.target_faction_id)
        if (attackerIdx === -1 || targetIdx === -1) return null

        // Attacker: primary shell = highest-asset shell
        const aFs = factions[attackerIdx][1]
        const aShell = (['leo_nodes', 'meo_nodes', 'geo_nodes', 'cislunar_nodes'] as const)
          .reduce((best, k) => aFs.assets[k] > aFs.assets[best] ? k : best, 'leo_nodes' as const)
        const aR = shellRadius[aShell.replace('_nodes', '')]
        const aAngle = attackerIdx * angleStep
        const { x: sx, y: sy } = ellipsePoint(aR, aAngle)

        // Target: use the shell that was attacked
        const tR = shellRadius[ev.shell] ?? 48
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

        const attackerName = factions[attackerIdx][1].name.slice(0, 4).toUpperCase()
        const targetName = factions[targetIdx][1].name.slice(0, 4).toUpperCase()
        const shellLabel = ev.shell.toUpperCase()
        const badge = ev.nodes_destroyed > 0
          ? `${attackerName} → ${targetName} ${shellLabel} −${ev.nodes_destroyed}`
          : `${attackerName} ⤳ ${targetName} ${ev.event_type === 'ew_jamming' ? 'EW' : 'DN'}`
        const badgeW = badge.length * 4.5 + 8

        return (
          <g key={i}>
            {/* Arc */}
            <path
              d={`M ${sx} ${sy} Q ${cpx} ${cpy} ${tx} ${ty}`}
              fill="none" stroke={color} strokeWidth={1.5}
              strokeDasharray={dash} opacity={0.85}
            />
            {/* Arrowhead at target */}
            <circle cx={tx} cy={ty} r={3} fill={color} opacity={0.9} />
            {/* Pulsing ring at target */}
            <circle cx={tx} cy={ty} r={6} fill="none" stroke={color} strokeWidth={1} opacity={0.5}>
              <animate attributeName="r" values="4;12;4" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.5;0;0.5" dur="2s" repeatCount="indefinite" />
            </circle>
            {/* Floating mid-path badge */}
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

**Render `CombatArcLayer`** inside the SVG, after the existing dot/annotation layers (just before the targeting reticle `<g>`):

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

---

## Section 7: Frontend — GamePage Arc Timing

### `web/src/pages/GamePage.tsx`

Add state and effect for arc fade timing:

```typescript
const [arcOpacity, setArcOpacity] = useState(0)

useEffect(() => {
  if (gameState.current_phase === 'invest' && !gameState.awaiting_next_turn
      && gameState.combat_events && gameState.combat_events.length > 0) {
    setArcOpacity(1)
    const fadeTimer = setTimeout(() => setArcOpacity(0), 8000)
    return () => clearTimeout(fadeTimer)
  }
}, [gameState.turn, gameState.current_phase, gameState.awaiting_next_turn])
```

Pass to `HoloOrbitalMap` (inside `MapTabContainer` → `HoloOrbitalMap`):

```tsx
combatEvents={gameState.combat_events}
arcOpacity={arcOpacity}
```

**Wire through `MapTabContainer`:** Add `combatEvents?: CombatEvent[]` and `arcOpacity?: number` to `MapTabContainer`'s Props, pass them through to `HoloOrbitalMap`.

---

## Section 8: Tests

### `tests/test_combat_events.py` (new file)

Test that the referee populates `combat_events` correctly:

1. Run a scenario turn with a kinetic approach; verify `combat_events` has one entry with correct `attacker_id`, `shell`, `nodes_destroyed > 0`, `event_type='kinetic'`.
2. Verify `nodes_destroyed` matches the delta in target faction assets.
3. Verify `detail` string contains the target faction name and shell.
4. Verify EW jamming appends a `CombatEvent` with `event_type='ew_jamming'` and `nodes_destroyed=0`.
5. Verify `combat_events` is cleared at the top of OPERATIONS resolution in `advance()` (via two consecutive turn advances).

---

## File Map

| File | Action |
|------|--------|
| `engine/state.py` | Add `CombatEvent` model |
| `api/models.py` | Add `combat_events: list[dict] = []` to `GameState` |
| `engine/referee.py` | Add `self._combat_events`, populate in kinetic/deniable/EW handlers, include in dump/load |
| `api/runner.py` | `_sync_state_from_referee` + clear at OPERATIONS start |
| `web/src/types.ts` | Add `CombatEvent` interface + field on `GameState` |
| `web/src/components/TurnSummary.tsx` | Add STRIKES THIS TURN panel |
| `web/src/components/HoloOrbitalMap.tsx` | Add `CombatArcLayer`, new props |
| `web/src/components/MapTabContainer.tsx` | Pass-through new props |
| `web/src/pages/GamePage.tsx` | Arc fade timing + pass props |
| `tests/test_combat_events.py` | New test file |
