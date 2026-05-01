# Consequence Previews Design

> **For agentic workers:** This spec is the source of truth. Read it fully before implementing. Each section maps to one or more implementation tasks.

## Overview

Before committing to an operation, the player sees a live "ESTIMATED OUTCOME" panel inside OpsPanel — full war-room detail rows (nodes, detection %, attribution %, DV cost, escalation delta, debris, transit timing). Outcomes are computed by the real backend `ConflictResolver` with no state mutation.

When the player executes, the preview is saved as a forecast alongside the decision. After RESPONSE phase resolves, actuals from `combat_events` are reconciled against the forecasts. A new **FORECAST** tab in `MapTabContainer` shows the full turn-by-turn prediction ledger with accuracy grades.

---

## Section 1: Backend — Preview Engine

### `engine/preview.py` (new file)

Define `OperationPreview` Pydantic model:

```python
from pydantic import BaseModel

class OperationPreview(BaseModel):
    available: bool
    unavailable_reason: str = ""
    dv_cost: float = 0.0
    dv_remaining: float = 0.0
    nodes_destroyed_estimate: int = 0
    nodes_destroyed_min: int = 0
    nodes_destroyed_max: int = 0
    detection_prob: float = 0.0
    attribution_prob: float = 0.0
    escalation_delta: int = 0
    escalation_rung_new: int = 0
    debris_estimate: float = 0.0      # new severity in affected shell after this op
    transit_turns: int = 0            # 0=immediate, 1=deniable, 2=kinetic
    target_shell: str = ""            # shell targeted (kinetic: target's primary shell)
    effect_summary: str = ""          # e.g. "SDA malus -15%" for EW
```

Define `PreviewEngine` class with one method:

```python
class PreviewEngine:
    def compute(
        self,
        action_type: str,
        mission: str,
        attacker_fs,          # FactionState
        target_fs,            # FactionState | None
        debris_fields: dict,
        access_windows: dict,
        escalation_rung: int,
    ) -> OperationPreview:
        ...
```

**Implementation rules:**

- **Never mutate** `attacker_fs`, `target_fs`, or any passed-in state. All computations are read-only.
- Instantiate `ConflictResolver` and `ManeuverBudgetEngine` locally (or import singletons).

**`task_assets` / `intercept`:**
- `available=False` if `attacker_fs.assets.asat_kinetic == 0` → `unavailable_reason="No kinetic ASAT assets"`
- `available=False` if `attacker_fs.maneuver_budget < ManeuverBudgetEngine.COSTS['kinetic_intercept']` → `unavailable_reason="Insufficient DV (need 4.0)"`
- `available=False` if `target_fs is None` → `unavailable_reason="No target selected"`
- `target_shell` = target's primary populated shell (leo > meo > geo > cislunar). `available=False` if target has zero nodes in all shells → `unavailable_reason="Target has no orbital assets"`
- Otherwise call `ConflictResolver().resolve_kinetic_asat(attacker_fs.assets, target_fs.assets, attacker_fs.sda_level())` — uses the deterministic formula (nodes_destroyed is deterministic; detected/attributed are probabilistic, use the probability values directly rather than simulating a roll)
- `detection_prob=0.80`, `attribution_prob=attacker_fs.sda_level()`
- `dv_cost=4.0`, `dv_remaining=attacker_fs.maneuver_budget - 4.0`
- `transit_turns=2`
- `escalation_delta = max(0, 3 - escalation_rung)`, `escalation_rung_new = max(escalation_rung, 3)`
- `debris_estimate` = `min(current debris in target shell + DebrisEngine.DEBRIS_PER_NODE_KINETIC * nodes_destroyed_estimate, 1.0)`
- If `access_windows.get(target_shell, True)` is `False`, set `effect_summary="ACCESS WINDOW CLOSED — transit may miss target"` (operation is still available, just warned)

**`task_assets` / `patrol` or `sda_sweep`:**
- `available=True`, all combat fields 0, `effect_summary="Surveillance only — shows resolve"` for patrol, `"Intelligence gathering — no combat effect"` for sda_sweep
- `escalation_delta=0`, `transit_turns=0`

**`gray_zone` with deniable assets (`attacker_fs.assets.asat_deniable > 0`):**
- `available=False` if `attacker_fs.maneuver_budget < ManeuverBudgetEngine.COSTS['deniable_approach']` → `unavailable_reason="Insufficient DV (need 2.0)"`
- `available=False` if `target_fs is None`
- `nodes_destroyed_min=1`, `nodes_destroyed_max=attacker_fs.assets.asat_deniable`
- `nodes_destroyed_estimate=(nodes_destroyed_min + nodes_destroyed_max) // 2`
- `detection_prob=target_fs.sda_level()` (defender's SDA)
- `attribution_prob=target_fs.sda_level() * 0.5`
- `dv_cost=2.0`, `dv_remaining=attacker_fs.maneuver_budget - 2.0`
- `transit_turns=1`
- `escalation_delta = max(0, 2 - escalation_rung)`, `escalation_rung_new = max(escalation_rung, 2)`
- `debris_estimate` = `min(current leo debris + DebrisEngine.DEBRIS_PER_NODE_DENIABLE * nodes_destroyed_estimate, 1.0)`

**`gray_zone` with EW jammers (`attacker_fs.assets.ew_jammers > 0`, no deniable):**
- `available=False` if `target_fs is None`
- `available=True`, all node fields 0, `dv_cost=0.0`, `transit_turns=0`
- `detection_prob=0.0`, `attribution_prob=0.0`
- `escalation_delta=0`, `escalation_rung_new=escalation_rung`
- `effect_summary="Target SDA degraded -15%"` (or `-30%` if `'jamming_radius'` tech unlocked — check `attacker_fs.unlocked_techs`)
- `debris_estimate = debris_fields.get("leo", 0.0)` — EW jamming does not generate debris; no change

**`gray_zone` with neither:**
- `available=False`, `unavailable_reason="No deniable ASAT or EW jammer assets"`

**`coordinate`:**
- `available=True`, all combat fields 0
- `effect_summary="Coordination bonus +SDA"` if `target_fs` is ally and loyalty ≥ 0.25 and cognitive_penalty ≤ 0.75
- `effect_summary="Coordination will fail — loyalty too low"` if loyalty < 0.25
- `effect_summary="Coordination will fail — cognitive degradation too severe"` if cognitive_penalty > 0.75

**`alliance_move`, `signal`:**
- `available=True`, all fields 0, `effect_summary="Diplomatic / signalling action — no direct combat effect"`

---

## Section 2: Backend — Preview Route

### `api/routes/game.py`

Add new request model in the file (above the router):

```python
class PreviewRequest(BaseModel):
    action_type: str
    mission: str = ""
    target_faction_id: str = ""
```

Add new route:

```python
@router.post("/game/{session_id}/preview")
async def preview_operation(session_id: str, req: PreviewRequest):
    runner = get_runner(session_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Session not found")
    state = runner.state
    human_fid = state.human_faction_id
    attacker_fs = state.faction_states.get(human_fid)
    target_fs = state.faction_states.get(req.target_faction_id) if req.target_faction_id else None
    from engine.preview import PreviewEngine
    preview = PreviewEngine().compute(
        action_type=req.action_type,
        mission=req.mission,
        attacker_fs=attacker_fs,
        target_fs=target_fs,
        debris_fields=state.debris_fields,
        access_windows=state.access_windows,
        escalation_rung=state.escalation_rung,
    )
    return preview.model_dump()
```

---

## Section 3: Backend — CombatEvent Extension

### `engine/state.py`

Add `detected` and `attributed` fields to `CombatEvent` (needed for forecast reconciliation):

```python
class CombatEvent(BaseModel):
    turn: int
    attacker_id: str
    target_faction_id: str
    shell: str
    event_type: str
    nodes_destroyed: int
    detail: str
    detected: bool = False
    attributed: bool = False
```

### `engine/referee.py`

In `_resolve_kinetic_approach`, when appending to `self._combat_events`, include `detected` and `attributed` from the resolution result:

```python
self._combat_events.append(CombatEvent(
    turn=self._current_turn,
    attacker_id=...,
    target_faction_id=...,
    shell=regime,
    event_type='kinetic',
    nodes_destroyed=nodes_hit,
    detail=...,
    detected=result["detected"],
    attributed=result["attributed"],
).model_dump())
```

In `_resolve_pending_deniables`, similarly include `detected=result["detected"]` and `attributed=result["attributed"]` when building the `CombatEvent`.

---

## Section 4: Backend — Forecast Ledger

### `api/models.py`

Add `operation_forecasts` to `GameState`:

```python
operation_forecasts: list[dict] = Field(default_factory=list)
```

Add optional forecast field to `DecideRequest`:

```python
class DecideRequest(BaseModel):
    phase: str
    decision: dict[str, Any]
    operation_forecast: Optional[dict] = None
```

### `api/routes/game.py` — `/decide` route

After calling `runner.decide(...)`, if `req.operation_forecast` is present and the phase is `"operations"`:

```python
if req.operation_forecast and req.phase == "operations":
    runner.state.operation_forecasts.append({
        "turn": runner.state.turn,
        "faction_id": runner.state.human_faction_id,
        "action_type": req.operation_forecast.get("action_type", ""),
        "mission": req.operation_forecast.get("mission", ""),
        "target_faction_id": req.operation_forecast.get("target_faction_id", ""),
        "forecast": req.operation_forecast.get("forecast", {}),  # pure OperationPreview fields
        "actual": None,
        "pending": True,
    })
```

### `engine/referee.py`

Add `_reconcile_forecasts(forecasts: list[dict]) -> list[dict]` method. Called at the end of `_resolve_response_phase` (or after `_resolve_pending_kinetics` / `_resolve_pending_deniables` — wherever `_combat_events` is fully populated for the turn):

```python
def _reconcile_forecasts(self, forecasts: list[dict]) -> list[dict]:
    current_turn_events = [e for e in self._combat_events if e["turn"] == self._current_turn]
    for forecast in forecasts:
        if not forecast.get("pending"):
            continue
        match = next(
            (e for e in current_turn_events
             if e["attacker_id"] == forecast["faction_id"]
             and e["target_faction_id"] == forecast.get("target_faction_id")),
            None,
        )
        if match:
            forecast["actual"] = {
                "nodes_destroyed": match["nodes_destroyed"],
                "detected": match.get("detected", False),
                "attributed": match.get("attributed", False),
                "event_type": match["event_type"],
            }
            forecast["pending"] = False
        # If no match (e.g. patrol, coordinate), leave actual=None, set pending=False
        elif forecast.get("action_type") not in ("task_assets",) or forecast.get("mission") not in ("intercept",):
            forecast["pending"] = False
        # kinetic intercept with 2-turn transit stays pending until it resolves
    return forecasts
```

### `api/runner.py` — `_sync_state_from_referee`

After syncing combat_events, add:

```python
state.operation_forecasts = self._reconcile_forecasts(state.operation_forecasts)
```

Where `_reconcile_forecasts` is called via the referee:

```python
state.operation_forecasts = self.referee._reconcile_forecasts(state.operation_forecasts)
```

---

## Section 5: Frontend — Types

### `web/src/types.ts`

Add after `CombatEvent`:

```typescript
export interface OperationPreview {
  available: boolean
  unavailable_reason: string
  dv_cost: number
  dv_remaining: number
  nodes_destroyed_estimate: number
  nodes_destroyed_min: number
  nodes_destroyed_max: number
  detection_prob: number
  attribution_prob: number
  escalation_delta: number
  escalation_rung_new: number
  debris_estimate: number
  transit_turns: number
  target_shell: string
  effect_summary: string
}

export interface OperationForecast {
  turn: number
  faction_id: string
  action_type: string
  mission: string
  target_faction_id: string
  forecast: OperationPreview
  actual: {
    nodes_destroyed: number
    detected: boolean
    attributed: boolean
    event_type: string
  } | null
  pending: boolean
}
```

Add to `GameState`:

```typescript
operation_forecasts?: OperationForecast[]
```

---

## Section 6: Frontend — OpsPanel Live Preview

### `web/src/components/phase/OpsPanel.tsx`

**New props:**

```typescript
sessionId: string
```

**New state:**

```typescript
const [preview, setPreview] = useState<OperationPreview | null>(null)
const [previewLoading, setPreviewLoading] = useState(false)
const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
```

**Import** `OperationPreview` from `../../types`.

**Fetch effect** — watches `[actionType, effectiveTarget, mission]`:

```typescript
useEffect(() => {
  if (debounceRef.current) clearTimeout(debounceRef.current)
  debounceRef.current = setTimeout(async () => {
    setPreviewLoading(true)
    try {
      const res = await fetch(`/api/game/${sessionId}/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_type: actionType,
          mission: actionType === 'task_assets' ? mission : '',
          target_faction_id: effectiveTarget || '',
        }),
      })
      const data = await res.json()
      setPreview(data)
    } finally {
      setPreviewLoading(false)
    }
  }, 300)
  return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
}, [actionType, effectiveTarget, mission, sessionId])
```

**Preview panel** — rendered between rationale textarea and EXECUTE button:

```tsx
{preview && (
  <div style={{
    marginBottom: 12, border: '1px solid rgba(0,212,255,0.2)',
    borderRadius: 2, padding: '8px 10px', background: 'rgba(0,212,255,0.04)',
  }}>
    <div className="panel-title" style={{ fontSize: 11, marginBottom: 6, color: '#00d4ff' }}>
      ◆ ESTIMATED OUTCOME {previewLoading && <span style={{ color: '#334155' }}>…</span>}
    </div>
    {!preview.available ? (
      <div style={{ color: '#f59e0b', fontSize: 12, fontFamily: 'Courier New' }}>
        [BLOCKED] {preview.unavailable_reason}
      </div>
    ) : preview.effect_summary ? (
      <div style={{ color: '#94a3b8', fontSize: 12, fontFamily: 'Courier New' }}>
        {preview.effect_summary}
      </div>
    ) : (
      <PreviewRows preview={preview} />
    )}
  </div>
)}
```

**`PreviewRows`** helper component (defined in same file):

```tsx
function PreviewRows({ preview }: { preview: OperationPreview }) {
  const rows: [string, string][] = []
  if (preview.dv_cost > 0) {
    rows.push(['DV COST', `-${preview.dv_cost.toFixed(1)}`])
    rows.push(['DV REMAINING', preview.dv_remaining.toFixed(1)])
  }
  if (preview.target_shell) rows.push(['TARGET SHELL', preview.target_shell.toUpperCase()])
  if (preview.nodes_destroyed_min === preview.nodes_destroyed_max) {
    rows.push(['EST. NODES', `${preview.nodes_destroyed_estimate}`])
  } else {
    rows.push(['EST. NODES', `${preview.nodes_destroyed_min}–${preview.nodes_destroyed_max}`])
  }
  if (preview.detection_prob > 0) rows.push(['DETECTED', `${Math.round(preview.detection_prob * 100)}%`])
  if (preview.attribution_prob > 0) rows.push(['ATTRIBUTED', `${Math.round(preview.attribution_prob * 100)}%`])
  if (preview.escalation_delta > 0)
    rows.push(['ESCALATION', `→ RNG ${preview.escalation_rung_new}`])
  if (preview.debris_estimate > 0)
    rows.push(['DEBRIS', `+${(preview.debris_estimate * 100).toFixed(0)}%`])
  if (preview.transit_turns > 0)
    rows.push(['TRANSIT', preview.transit_turns === 1 ? '1 TURN' : '2 TURNS'])
  else if (preview.dv_cost === 0 && rows.length > 0)
    rows.push(['TIMING', 'IMMEDIATE'])

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '2px 12px' }}>
      {rows.map(([label, value]) => (
        <>
          <span key={label+'-l'} style={{ fontSize: 11, color: '#475569', fontFamily: 'Courier New' }}>{label}</span>
          <span key={label+'-v'} style={{ fontSize: 11, color: '#e2e8f0', fontFamily: 'Courier New' }}>{value}</span>
        </>
      ))}
    </div>
  )
}
```

**Updated `handleSubmit`** — attach last preview as forecast. The forecast payload wraps the `OperationPreview` fields under a `forecast` key alongside metadata, to match the `OperationForecast` shape expected by the backend:

```typescript
function handleSubmit() {
  const params: Record<string, string> = {}
  if (actionType === 'task_assets') params.mission = mission
  const forecastPayload = preview ? {
    action_type: actionType,
    mission: actionType === 'task_assets' ? mission : '',
    target_faction_id: effectiveTarget || '',
    forecast: preview,   // pure OperationPreview fields only
  } : undefined
  onSubmit(
    {
      operations: [{
        action_type: actionType,
        target_faction: effectiveTarget || undefined,
        parameters: params,
        rationale,
      }],
    },
    forecastPayload,
  )
}
```

**Updated `onSubmit` prop signature:**

```typescript
onSubmit: (decision: Record<string, unknown>, forecast?: Record<string, unknown>) => void
```

### `web/src/pages/GamePage.tsx`

Update the call to `handleDecide` (where `onSubmit` is wired) to accept and forward the `forecast` argument to the decide API call body as `operation_forecast`.

Pass `sessionId={gameState.session_id}` to `OpsPanel` directly from `GamePage` (OpsPanel is rendered from GamePage, not via MapTabContainer).

---

## Section 7: Frontend — ForecastTab

### `web/src/components/ForecastTab.tsx` (new file)

```typescript
import { OperationForecast } from '../types'

interface Props {
  forecasts: OperationForecast[]
  factionNames: Record<string, string>
}
```

Renders a scrollable table. Header row:

```
TURN | ACTION | TARGET | EST.NODES | ACTUAL | DETECTED | ATTRIBUTED | ACCURACY
```

Per-row logic:

- `actual === null && pending` → show `PENDING` in muted cyan (`#00d4ff66`) for combat columns
- `actual === null && !pending` → show `N/A` (non-combat action)
- Otherwise compute accuracy:
  - **A** (green `#00ff88`): `|estimate - actual.nodes_destroyed| <= 1` AND detection matched (predicted ≥ 50% and was detected, or predicted < 50% and not detected)
  - **B** (amber `#f59e0b`): delta ≤ 2 or detection mismatch only
  - **C** (red `#ff4499`): delta > 2

DETECTED column: show forecast % → actual (✓ / ✗). ATTRIBUTED column: same pattern.

Empty state (no forecasts yet): show `NO FORECAST DATA — execute an operation to begin tracking` in muted text.

### `web/src/components/MapTabContainer.tsx`

Add new props:

```typescript
forecasts?: OperationForecast[]
```

Add FORECAST tab to the tab list. Render `<ForecastTab forecasts={forecasts ?? []} factionNames={factionNames} />` when FORECAST tab is active.

### `web/src/pages/GamePage.tsx`

Pass `forecasts={gameState.operation_forecasts}` to `MapTabContainer`.

---

## Section 8: Tests

### `tests/test_operation_preview.py` (new file)

1. Kinetic intercept with assets → `available=True`, `dv_cost=4.0`, `transit_turns=2`, `nodes_destroyed_estimate > 0`
2. Kinetic intercept with `asat_kinetic=0` → `available=False`, `unavailable_reason` non-empty
3. Kinetic intercept with `maneuver_budget=1.0` → `available=False`
4. Kinetic intercept with `target_fs=None` → `available=False`
5. Kinetic intercept with target having zero nodes in all shells → `available=False`, `unavailable_reason` contains "no orbital assets"
6. Kinetic intercept with `access_windows={"leo": False, ...}` and target's primary shell being LEO → `available=True`, `effect_summary` contains "ACCESS WINDOW CLOSED"
7. Kinetic intercept `debris_estimate` does not exceed 1.0 when existing debris is already 0.95
8. Deniable gray_zone with `asat_deniable=3` → `available=True`, `dv_cost=2.0`, `transit_turns=1`, `nodes_destroyed_min=1`, `nodes_destroyed_max=3`
9. EW gray_zone (`ew_jammers=2`, `asat_deniable=0`) → `available=True`, `transit_turns=0`, `dv_cost=0.0`, `nodes_destroyed_estimate=0`, `debris_estimate` equals existing leo debris (no change)
10. Gray_zone with neither assets → `available=False`
11. `PreviewEngine.compute()` does not mutate `attacker_fs.maneuver_budget`

### `tests/test_forecast_ledger.py` (new file)

12. Submitting ops decision with `operation_forecast` → `GameState.operation_forecasts` has one entry with `actual=None`, `pending=True`
13. After RESPONSE phase with matching kinetic combat event → forecast `actual` is filled with `nodes_destroyed`, `detected`, `attributed`
14. Forecast for patrol action (no combat event) → stays `actual=None`, `pending=False` after reconcile
15. Kinetic intercept forecast (2-turn transit): after turn N's RESPONSE phase, `pending=True` (no match yet); after turn N+2's RESPONSE phase (when kinetic resolves), `pending=False` and `actual` is filled in

---

## File Map

| File | Action |
|------|--------|
| `engine/preview.py` | New — `OperationPreview` model + `PreviewEngine` |
| `engine/state.py` | Add `detected`, `attributed` fields to `CombatEvent` |
| `engine/referee.py` | Populate `detected`/`attributed` in CombatEvent appends; add `_reconcile_forecasts()` |
| `api/models.py` | Add `operation_forecasts` to `GameState`; add `operation_forecast` to `DecideRequest` |
| `api/routes/game.py` | Add `PreviewRequest` model + `/preview` route; update `/decide` to save forecast |
| `api/runner.py` | Call `referee._reconcile_forecasts()` in `_sync_state_from_referee` |
| `web/src/types.ts` | Add `OperationPreview`, `OperationForecast`, update `GameState` |
| `web/src/components/phase/OpsPanel.tsx` | Add `sessionId` prop, preview fetch + panel, updated `onSubmit` |
| `web/src/components/ForecastTab.tsx` | New — forecast accuracy table |
| `web/src/components/MapTabContainer.tsx` | Add FORECAST tab + `forecasts` prop pass-through |
| `web/src/pages/GamePage.tsx` | Wire `sessionId`, `forecasts`; forward forecast on decide |
| `tests/test_operation_preview.py` | New — PreviewEngine unit tests |
| `tests/test_forecast_ledger.py` | New — forecast ledger integration tests |
