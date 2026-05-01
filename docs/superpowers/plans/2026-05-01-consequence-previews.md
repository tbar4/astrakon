# Consequence Previews Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live backend-computed "ESTIMATED OUTCOME" panel in OpsPanel, save forecasts alongside decisions, reconcile predictions against actual combat outcomes, and display a turn-by-turn accuracy ledger in a new FORECAST tab.

**Architecture:** A new `PreviewEngine` in `engine/preview.py` computes read-only outcome estimates using the real `ConflictResolver`; a `POST /preview` route exposes it. Forecasts are saved in `GameState.operation_forecasts` when the player executes, then reconciled against `combat_events` in `GameReferee._reconcile_forecasts()` after each combat phase. The frontend polls `/preview` with a 300 ms debounce and renders a new `ForecastTab` table in `MapTabContainer`.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI, React 19, TypeScript, Courier New monospace UI

---

## File Map

| File | Change |
|------|--------|
| `engine/state.py` | Add `detected`, `attributed` to `CombatEvent` |
| `engine/referee.py` | Populate `detected`/`attributed` in CombatEvent appends; add `_reconcile_forecasts()` |
| `engine/preview.py` | **New** — `OperationPreview` model + `PreviewEngine` |
| `api/models.py` | Add `operation_forecasts` to `GameState`; add `operation_forecast` to `DecideRequest` |
| `api/routes/game.py` | Add `PreviewRequest` + `POST /preview` route; pass forecast through `/decide` |
| `api/runner.py` | Add `operation_forecast` param to `advance()`; call `_resolve_pending_deniables`; call `_reconcile_forecasts` after each combat phase |
| `web/src/types.ts` | Add `OperationPreview`, `OperationForecast`; extend `CombatEvent`; extend `GameState` |
| `web/src/api/client.ts` | Add optional `operationForecast` param to `decide()` |
| `web/src/components/phase/OpsPanel.tsx` | Add `sessionId` prop, preview fetch + panel, updated `onSubmit` |
| `web/src/pages/GamePage.tsx` | Pass `sessionId` to OpsPanel; forward forecast from `handleDecision` |
| `web/src/components/ForecastTab.tsx` | **New** — forecast accuracy table |
| `web/src/components/MapTabContainer.tsx` | Add FORECAST tab + `forecasts` prop |
| `tests/test_operation_preview.py` | **New** — PreviewEngine unit tests |
| `tests/test_forecast_ledger.py` | **New** — forecast ledger integration tests |

---

## Task 1: Extend CombatEvent with detected/attributed

**Files:**
- Modify: `engine/state.py:198-205`
- Modify: `engine/referee.py:539-550`
- Modify: `engine/referee.py:833-844`
- Test: `tests/test_combat_events.py`

- [ ] **Step 1: Write the failing test**

Add to the end of `tests/test_combat_events.py`:

```python
def test_combat_event_has_detected_attributed_defaults():
    ev = CombatEvent(
        turn=1, attacker_id="ussf", target_faction_id="pla_ssf",
        shell="leo", event_type="kinetic", nodes_destroyed=3, detail="test",
    )
    assert ev.detected is False
    assert ev.attributed is False


def test_combat_event_accepts_detected_attributed():
    ev = CombatEvent(
        turn=1, attacker_id="ussf", target_faction_id="pla_ssf",
        shell="leo", event_type="kinetic", nodes_destroyed=3, detail="test",
        detected=True, attributed=True,
    )
    assert ev.detected is True
    d = ev.model_dump()
    assert d["detected"] is True
    assert d["attributed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_combat_events.py::test_combat_event_has_detected_attributed_defaults -v
```

Expected: FAIL — `CombatEvent` has no `detected` field.

- [ ] **Step 3: Add fields to CombatEvent in engine/state.py**

`engine/state.py` lines 198-205. Replace:

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

With:

```python
class CombatEvent(BaseModel):
    turn: int
    attacker_id: str
    target_faction_id: str
    shell: str           # 'leo' | 'meo' | 'geo' | 'cislunar'
    event_type: str      # 'kinetic' | 'deniable' | 'ew_jamming' | 'gray_zone'
    nodes_destroyed: int
    detail: str
    detected: bool = False
    attributed: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_combat_events.py::test_combat_event_has_detected_attributed_defaults tests/test_combat_events.py::test_combat_event_accepts_detected_attributed -v
```

Expected: PASS

- [ ] **Step 5: Populate detected/attributed in kinetic CombatEvent append (engine/referee.py ~line 539)**

Find the `self._combat_events.append(CombatEvent(` block that starts at line ~539. Replace it:

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
            detected=detected,
            attributed=attributed,
        ).model_dump())
```

(Note: `detected` and `attributed` are already extracted at lines ~529-530 as `detected = result["detected"]` and `attributed = result["attributed"]`.)

- [ ] **Step 6: Populate detected/attributed in deniable CombatEvent append (engine/referee.py ~line 833)**

Find the `self._combat_events.append(CombatEvent(` block inside `_resolve_pending_deniables`. Replace it:

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
                detected=detected,
                attributed=attributed,
            ).model_dump())
```

(Note: `detected` and `attributed` are already extracted at lines ~823-824 as `detected = result["detected"]` and `attributed = result["attributed"]`.)

- [ ] **Step 7: Run full combat events test suite**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_combat_events.py -v
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add engine/state.py engine/referee.py tests/test_combat_events.py
git commit -m "feat: add detected/attributed fields to CombatEvent"
```

---

## Task 2: PreviewEngine

**Files:**
- Create: `engine/preview.py`
- Create: `tests/test_operation_preview.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_operation_preview.py`:

```python
# tests/test_operation_preview.py
import pytest
from engine.preview import OperationPreview, PreviewEngine
from engine.state import FactionState, FactionAssets


def _make_faction(
    faction_id="ussf",
    asat_kinetic=2, asat_deniable=0, ew_jammers=0,
    leo_nodes=5, meo_nodes=0, geo_nodes=0, cislunar_nodes=0,
    maneuver_budget=10.0, sda_sensors=12,
    unlocked_techs=None, coalition_id="usa",
) -> FactionState:
    return FactionState(
        faction_id=faction_id, name=faction_id.upper(),
        budget_per_turn=100, current_budget=100,
        assets=FactionAssets(
            asat_kinetic=asat_kinetic, asat_deniable=asat_deniable,
            ew_jammers=ew_jammers, leo_nodes=leo_nodes, meo_nodes=meo_nodes,
            geo_nodes=geo_nodes, cislunar_nodes=cislunar_nodes, sda_sensors=sda_sensors,
        ),
        maneuver_budget=maneuver_budget,
        unlocked_techs=unlocked_techs or [],
        coalition_id=coalition_id,
        coalition_loyalty=0.8,
        archetype="mahanian",
    )


ENGINE = PreviewEngine()
ALL_WINDOWS_OPEN = {"leo": True, "meo": True, "geo": True, "cislunar": True}


def test_kinetic_intercept_available():
    attacker = _make_faction(asat_kinetic=2)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is True
    assert p.dv_cost == 4.0
    assert p.transit_turns == 2
    assert p.nodes_destroyed_estimate > 0


def test_kinetic_intercept_no_asat():
    attacker = _make_faction(asat_kinetic=0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False
    assert p.unavailable_reason != ""


def test_kinetic_intercept_insufficient_dv():
    attacker = _make_faction(asat_kinetic=2, maneuver_budget=1.0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False


def test_kinetic_intercept_no_target():
    attacker = _make_faction(asat_kinetic=2)
    p = ENGINE.compute("task_assets", "intercept", attacker, None, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False


def test_kinetic_intercept_target_no_nodes():
    attacker = _make_faction(asat_kinetic=2)
    target = _make_faction(faction_id="pla", leo_nodes=0, meo_nodes=0, geo_nodes=0, cislunar_nodes=0, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False
    assert "no orbital" in p.unavailable_reason.lower()


def test_kinetic_intercept_access_window_closed():
    attacker = _make_faction(asat_kinetic=2)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    windows = {"leo": False, "meo": True, "geo": True, "cislunar": True}
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, windows, 0)
    assert p.available is True
    assert "ACCESS WINDOW" in p.effect_summary


def test_kinetic_debris_capped_at_one():
    attacker = _make_faction(asat_kinetic=5)
    target = _make_faction(faction_id="pla", leo_nodes=20, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {"leo": 0.95}, ALL_WINDOWS_OPEN, 0)
    assert p.debris_estimate <= 1.0


def test_deniable_gray_zone():
    attacker = _make_faction(asat_deniable=3, asat_kinetic=0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("gray_zone", "", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is True
    assert p.dv_cost == 2.0
    assert p.transit_turns == 1
    assert p.nodes_destroyed_min == 1
    assert p.nodes_destroyed_max == 3


def test_ew_gray_zone():
    attacker = _make_faction(ew_jammers=2, asat_deniable=0, asat_kinetic=0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("gray_zone", "", attacker, target, {"leo": 0.3}, ALL_WINDOWS_OPEN, 0)
    assert p.available is True
    assert p.transit_turns == 0
    assert p.dv_cost == 0.0
    assert p.nodes_destroyed_estimate == 0
    assert p.debris_estimate == pytest.approx(0.3)  # no change


def test_gray_zone_no_assets():
    attacker = _make_faction(asat_deniable=0, ew_jammers=0, asat_kinetic=0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("gray_zone", "", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False


def test_preview_engine_does_not_mutate_maneuver_budget():
    attacker = _make_faction(asat_kinetic=2, maneuver_budget=10.0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert attacker.maneuver_budget == 10.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_operation_preview.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'engine.preview'`

- [ ] **Step 3: Create engine/preview.py**

```python
# engine/preview.py
from pydantic import BaseModel
from engine.state import FactionState
from engine.simulation import ConflictResolver, ManeuverBudgetEngine, DebrisEngine


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
    debris_estimate: float = 0.0
    transit_turns: int = 0
    target_shell: str = ""
    effect_summary: str = ""


class PreviewEngine:
    def compute(
        self,
        action_type: str,
        mission: str,
        attacker_fs: FactionState,
        target_fs: "FactionState | None",
        debris_fields: dict,
        access_windows: dict,
        escalation_rung: int,
    ) -> OperationPreview:
        if action_type == "task_assets":
            return self._preview_task_assets(
                mission, attacker_fs, target_fs, debris_fields, access_windows, escalation_rung
            )
        if action_type == "gray_zone":
            return self._preview_gray_zone(attacker_fs, target_fs, debris_fields, escalation_rung)
        if action_type == "coordinate":
            return self._preview_coordinate(attacker_fs, target_fs)
        return OperationPreview(
            available=True,
            effect_summary="Diplomatic / signalling action — no direct combat effect",
        )

    def _preview_task_assets(
        self, mission, attacker_fs, target_fs, debris_fields, access_windows, escalation_rung
    ) -> OperationPreview:
        if mission == "intercept":
            return self._preview_intercept(
                attacker_fs, target_fs, debris_fields, access_windows, escalation_rung
            )
        summary = (
            "Surveillance only — shows resolve"
            if mission == "patrol"
            else "Intelligence gathering — no combat effect"
        )
        return OperationPreview(available=True, effect_summary=summary)

    def _preview_intercept(
        self, attacker_fs, target_fs, debris_fields, access_windows, escalation_rung
    ) -> OperationPreview:
        if attacker_fs.assets.asat_kinetic == 0:
            return OperationPreview(available=False, unavailable_reason="No kinetic ASAT assets")
        dv_needed = ManeuverBudgetEngine.COSTS["kinetic_intercept"]
        if attacker_fs.maneuver_budget < dv_needed:
            return OperationPreview(
                available=False, unavailable_reason=f"Insufficient DV (need {dv_needed:.1f})"
            )
        if target_fs is None:
            return OperationPreview(available=False, unavailable_reason="No target selected")

        if target_fs.assets.leo_nodes > 0:
            target_shell = "leo"
        elif target_fs.assets.meo_nodes > 0:
            target_shell = "meo"
        elif target_fs.assets.geo_nodes > 0:
            target_shell = "geo"
        elif target_fs.assets.cislunar_nodes > 0:
            target_shell = "cislunar"
        else:
            return OperationPreview(
                available=False, unavailable_reason="Target has no orbital assets"
            )

        result = ConflictResolver().resolve_kinetic_asat(
            attacker_assets=attacker_fs.assets,
            target_assets=target_fs.assets,
            attacker_sda_level=attacker_fs.sda_level(),
        )
        nodes_est = result["nodes_destroyed"]
        current_debris = debris_fields.get(target_shell, 0.0)
        debris_est = min(
            current_debris + DebrisEngine.DEBRIS_PER_NODE_KINETIC * nodes_est, 1.0
        )
        effect_summary = ""
        if not access_windows.get(target_shell, True):
            effect_summary = "ACCESS WINDOW CLOSED — transit may miss target"

        return OperationPreview(
            available=True,
            dv_cost=dv_needed,
            dv_remaining=attacker_fs.maneuver_budget - dv_needed,
            nodes_destroyed_estimate=nodes_est,
            nodes_destroyed_min=nodes_est,
            nodes_destroyed_max=nodes_est,
            detection_prob=0.80,
            attribution_prob=attacker_fs.sda_level(),
            escalation_delta=max(0, 3 - escalation_rung),
            escalation_rung_new=max(escalation_rung, 3),
            debris_estimate=debris_est,
            transit_turns=2,
            target_shell=target_shell,
            effect_summary=effect_summary,
        )

    def _preview_gray_zone(
        self, attacker_fs, target_fs, debris_fields, escalation_rung
    ) -> OperationPreview:
        if target_fs is None:
            return OperationPreview(available=False, unavailable_reason="No target selected")

        if attacker_fs.assets.asat_deniable > 0:
            dv_needed = ManeuverBudgetEngine.COSTS["deniable_approach"]
            if attacker_fs.maneuver_budget < dv_needed:
                return OperationPreview(
                    available=False,
                    unavailable_reason=f"Insufficient DV (need {dv_needed:.1f})",
                )
            n_min = 1
            n_max = attacker_fs.assets.asat_deniable
            n_est = (n_min + n_max) // 2
            current_leo = debris_fields.get("leo", 0.0)
            debris_est = min(
                current_leo + DebrisEngine.DEBRIS_PER_NODE_DENIABLE * n_est, 1.0
            )
            return OperationPreview(
                available=True,
                dv_cost=dv_needed,
                dv_remaining=attacker_fs.maneuver_budget - dv_needed,
                nodes_destroyed_estimate=n_est,
                nodes_destroyed_min=n_min,
                nodes_destroyed_max=n_max,
                detection_prob=target_fs.sda_level(),
                attribution_prob=target_fs.sda_level() * 0.5,
                escalation_delta=max(0, 2 - escalation_rung),
                escalation_rung_new=max(escalation_rung, 2),
                debris_estimate=debris_est,
                transit_turns=1,
            )

        if attacker_fs.assets.ew_jammers > 0:
            sda_pct = 30 if "jamming_radius" in (attacker_fs.unlocked_techs or []) else 15
            return OperationPreview(
                available=True,
                dv_cost=0.0,
                transit_turns=0,
                debris_estimate=debris_fields.get("leo", 0.0),
                effect_summary=f"Target SDA degraded -{sda_pct}%",
            )

        return OperationPreview(
            available=False,
            unavailable_reason="No deniable ASAT or EW jammer assets",
        )

    def _preview_coordinate(self, attacker_fs, target_fs) -> OperationPreview:
        if target_fs is None or target_fs.coalition_id != attacker_fs.coalition_id:
            return OperationPreview(
                available=True,
                effect_summary="Coordination bonus +SDA (requires allied target)",
            )
        if attacker_fs.cognitive_penalty > 0.75:
            return OperationPreview(
                available=True,
                effect_summary="Coordination will fail — cognitive degradation too severe",
            )
        if attacker_fs.coalition_loyalty < 0.25:
            return OperationPreview(
                available=True,
                effect_summary="Coordination will fail — loyalty too low",
            )
        return OperationPreview(available=True, effect_summary="Coordination bonus +SDA")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_operation_preview.py -v
```

Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add engine/preview.py tests/test_operation_preview.py
git commit -m "feat: add PreviewEngine with OperationPreview model"
```

---

## Task 3: Preview API Route

**Files:**
- Modify: `api/routes/game.py:1-14` (imports + PreviewRequest model)
- Test: manual curl (no new test file — covered by integration in Task 11)

- [ ] **Step 1: Add PreviewRequest model and route to api/routes/game.py**

At the top of `api/routes/game.py`, add `PreviewRequest` to the imports block and define it just before the `router = APIRouter()` line:

```python
from api.models import AarRequest, CreateGameRequest, DecideRequest, GameStateResponse
```

becomes:

```python
from api.models import AarRequest, CreateGameRequest, DecideRequest, GameStateResponse
from pydantic import BaseModel as _BaseModel


class PreviewRequest(_BaseModel):
    action_type: str
    mission: str = ""
    target_faction_id: str = ""
```

Then add the route after the existing `/decide` route (after line 99):

```python
@router.post("/game/{session_id}/preview")
async def preview_operation(session_id: str, req: PreviewRequest):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    attacker_fs = state.faction_states.get(state.human_faction_id)
    if attacker_fs is None:
        raise HTTPException(status_code=400, detail="Human faction not found")
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

- [ ] **Step 2: Run existing API tests to confirm no regressions**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_api.py -v
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add api/routes/game.py
git commit -m "feat: add POST /preview route for operation outcome preview"
```

---

## Task 4: Forecast Ledger Models

**Files:**
- Modify: `api/models.py:44-46` (GameState — add field after combat_events)
- Modify: `api/models.py:77-79` (DecideRequest — add optional field)

- [ ] **Step 1: Write failing test**

Add to `tests/test_combat_events.py`:

```python
def test_game_state_has_operation_forecasts_field():
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
    assert state.operation_forecasts == []


def test_decide_request_accepts_operation_forecast():
    from api.models import DecideRequest
    req = DecideRequest(
        phase="operations",
        decision={"operations": []},
        operation_forecast={"action_type": "task_assets", "forecast": {}},
    )
    assert req.operation_forecast is not None

    req_no_forecast = DecideRequest(phase="operations", decision={})
    assert req_no_forecast.operation_forecast is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_combat_events.py::test_game_state_has_operation_forecasts_field tests/test_combat_events.py::test_decide_request_accepts_operation_forecast -v
```

Expected: FAIL

- [ ] **Step 3: Update api/models.py**

In `GameState`, after line 45 (`combat_events: list[dict] = Field(default_factory=list)`), add:

```python
    operation_forecasts: list[dict] = Field(default_factory=list)
```

In `DecideRequest` (lines 77-79), replace:

```python
class DecideRequest(BaseModel):
    phase: str
    decision: dict[str, Any]
```

With:

```python
class DecideRequest(BaseModel):
    phase: str
    decision: dict[str, Any]
    operation_forecast: Optional[dict] = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_combat_events.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add api/models.py tests/test_combat_events.py
git commit -m "feat: add operation_forecasts to GameState, operation_forecast to DecideRequest"
```

---

## Task 5: Forecast Save, Deniables Fix, and Reconciliation

**Files:**
- Modify: `engine/referee.py` (add `_reconcile_forecasts` method)
- Modify: `api/runner.py:191-235` (add `operation_forecast` param, deniables call, reconcile calls)
- Modify: `api/routes/game.py:93-99` (pass `operation_forecast` to runner)

- [ ] **Step 1: Add `_reconcile_forecasts` to GameReferee (engine/referee.py)**

Add the following method to `GameReferee`, after `_resolve_pending_deniables` (around line 846):

```python
    def _reconcile_forecasts(self, forecasts: list[dict]) -> list[dict]:
        """Match pending forecasts to actual combat_events for the current turn."""
        current_turn_events = [
            e for e in self._combat_events if e["turn"] == self._current_turn
        ]
        for forecast in forecasts:
            if not forecast.get("pending"):
                continue
            match = next(
                (
                    e for e in current_turn_events
                    if e["attacker_id"] == forecast["faction_id"]
                    and e["target_faction_id"] == forecast.get("target_faction_id")
                ),
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
            elif (forecast.get("action_type"), forecast.get("mission")) != (
                "task_assets",
                "intercept",
            ):
                # Non-kinetic-intercept: finalize (actual=None means no combat occurred)
                forecast["pending"] = False
            # kinetic intercept with 2-turn transit stays pending until it fires
        return forecasts
```

- [ ] **Step 2: Update runner.py — add operation_forecast param + save forecast**

In `api/runner.py`, the `advance` function signature at line 191. Replace:

```python
async def advance(
    session_id: str,
    decision: Optional[dict] = None,
    db_path: str = _SESSIONS_DB,
) -> GameStateResponse:
```

With:

```python
async def advance(
    session_id: str,
    decision: Optional[dict] = None,
    operation_forecast: Optional[dict] = None,
    db_path: str = _SESSIONS_DB,
) -> GameStateResponse:
```

Then in the "Apply human decision if provided" block (around line 224), after:
```python
        state.phase_decisions[state.human_faction_id] = dec.model_dump_json()
```

Add (before `await save_session`):
```python
        if operation_forecast and phase == Phase.OPERATIONS:
            state.operation_forecasts.append({
                "turn": state.turn,
                "faction_id": state.human_faction_id,
                "action_type": operation_forecast.get("action_type", ""),
                "mission": operation_forecast.get("mission", ""),
                "target_faction_id": operation_forecast.get("target_faction_id", ""),
                "forecast": operation_forecast.get("forecast", {}),
                "actual": None,
                "pending": True,
            })
```

- [ ] **Step 3: Update runner.py — add deniables call + reconcile calls**

In the INVEST block of `advance()` (around line 248), add reconcile after the kinetics sync:

```python
                if state.current_phase == Phase.INVEST:
                    await audit.initialize()
                    await referee.resolve_investment(state.turn, state.phase_decisions)
                    _sync_state_from_referee(state, referee)
                    state.phase_decisions = {}
                    state.current_phase = Phase.OPERATIONS
                    referee.resolve_pending_kinetics(state.turn)
                    _sync_state_from_referee(state, referee)
                    state.operation_forecasts = referee._reconcile_forecasts(state.operation_forecasts)
```

In the OPERATIONS block (around line 257), add the deniables call and reconcile:

```python
                elif state.current_phase == Phase.OPERATIONS:
                    state.combat_events = []
                    await audit.initialize()
                    referee._resolve_pending_deniables(state.turn)
                    await referee.resolve_operations(state.turn, state.phase_decisions)
                    _sync_state_from_referee(state, referee)
                    state.operation_forecasts = referee._reconcile_forecasts(state.operation_forecasts)
                    state.phase_decisions = {}
                    # Generate events before RESPONSE
                    events = referee.generate_turn_events(state.turn)
                    _sync_state_from_referee(state, referee)
                    state.events = [...]
                    state.current_phase = Phase.RESPONSE
```

In the RESPONSE block (around line 278), add reconcile after the first sync:

```python
                elif state.current_phase == Phase.RESPONSE:
                    await audit.initialize()
                    from engine.state import CrisisEvent
                    crisis_events = [CrisisEvent.model_validate(e) for e in state.events]
                    await referee.resolve_response(state.turn, state.phase_decisions, crisis_events)
                    _sync_state_from_referee(state, referee)
                    state.operation_forecasts = referee._reconcile_forecasts(state.operation_forecasts)
                    referee._update_faction_metrics()
                    _sync_state_from_referee(state, referee)
                    state.phase_decisions = {}
                    state.current_phase = Phase.INVEST
```

- [ ] **Step 4: Update /decide route to pass operation_forecast**

In `api/routes/game.py`, the `/decide` route (lines 93-99). Replace:

```python
@router.post("/game/{session_id}/decide", response_model=GameStateResponse)
async def decide(session_id: str, req: DecideRequest):
    try:
        decision = {"phase": req.phase, "decision": req.decision}
        return await runner.advance(session_id, decision=decision)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

With:

```python
@router.post("/game/{session_id}/decide", response_model=GameStateResponse)
async def decide(session_id: str, req: DecideRequest):
    try:
        decision = {"phase": req.phase, "decision": req.decision}
        return await runner.advance(
            session_id,
            decision=decision,
            operation_forecast=req.operation_forecast,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 5: Run runner tests to confirm no regressions**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_runner.py tests/test_combat_events.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add engine/referee.py api/runner.py api/routes/game.py
git commit -m "feat: save and reconcile operation forecasts; fix deniable resolution in runner"
```

---

## Task 6: Frontend Types

**Files:**
- Modify: `web/src/types.ts:77-131`

- [ ] **Step 1: Update CombatEvent, add OperationPreview and OperationForecast, extend GameState**

In `web/src/types.ts`, replace the `CombatEvent` interface (lines 77-85):

```typescript
export interface CombatEvent {
  turn: number
  attacker_id: string
  target_faction_id: string
  shell: string
  event_type: 'kinetic' | 'deniable' | 'ew_jamming' | 'gray_zone'
  nodes_destroyed: number
  detail: string
  detected?: boolean
  attributed?: boolean
}
```

After `CombatEvent` and before `GameState`, add:

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

In the `GameState` interface, after `combat_events?: CombatEvent[]` (line 130), add:

```typescript
  operation_forecasts?: OperationForecast[]
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/types.ts
git commit -m "feat: add OperationPreview, OperationForecast types; extend CombatEvent"
```

---

## Task 7: API Client + OpsPanel Live Preview

**Files:**
- Modify: `web/src/api/client.ts:46-58`
- Modify: `web/src/components/phase/OpsPanel.tsx`

- [ ] **Step 1: Update client.ts decide() to accept operationForecast**

In `web/src/api/client.ts`, replace the `decide` function (lines 46-58):

```typescript
export async function decide(
  sessionId: string,
  phase: string,
  decision: Record<string, unknown>,
  operationForecast?: Record<string, unknown>,
): Promise<GameStateResponse> {
  return json(
    await fetch(`${BASE}/game/${sessionId}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phase,
        decision,
        operation_forecast: operationForecast ?? null,
      }),
    }),
  )
}
```

- [ ] **Step 2: Update OpsPanel — add sessionId prop, preview state, fetch effect**

In `web/src/components/phase/OpsPanel.tsx`, replace the entire file:

```tsx
// web/src/components/phase/OpsPanel.tsx
import { useState, useEffect, useRef } from 'react'
import type { OperationPreview } from '../../types'

interface Props {
  factionNames: Record<string, string>
  humanFactionId: string
  asatKinetic: number
  sessionId: string
  onSubmit: (decision: Record<string, unknown>, forecast?: Record<string, unknown>) => void
  disabled: boolean
  mapTarget?: string | null
  onClearMapTarget?: () => void
}

const ACTION_TYPES = [
  { key: 'task_assets', label: 'Task Assets', desc: 'Surveillance, patrol, or kinetic intercept' },
  { key: 'coordinate', label: 'Coordinate', desc: 'Synchronize with coalition ally (+SDA bonus)' },
  { key: 'gray_zone', label: 'Gray Zone', desc: 'Deniable activity — ASAT-deniable or EW jamming' },
  { key: 'alliance_move', label: 'Alliance Move', desc: 'Reinforce partner or shift alignment' },
  { key: 'signal', label: 'Signal', desc: 'Deliberate public or back-channel communication' },
] as const

const MISSIONS = [
  { key: 'sda_sweep', label: 'SDA Sweep — intelligence only' },
  { key: 'patrol', label: 'Patrol — shows resolve' },
  { key: 'intercept', label: 'Intercept — kinetic, arrives next turn' },
] as const

type ActionKey = typeof ACTION_TYPES[number]['key']

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

  if (rows.length === 0) return null

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '2px 12px' }}>
      {rows.map(([label, value]) => (
        <span key={label + '-row'} style={{ display: 'contents' }}>
          <span style={{ fontSize: 11, color: '#475569', fontFamily: 'Courier New' }}>{label}</span>
          <span style={{ fontSize: 11, color: '#e2e8f0', fontFamily: 'Courier New' }}>{value}</span>
        </span>
      ))}
    </div>
  )
}

export default function OpsPanel({
  factionNames, humanFactionId, asatKinetic, sessionId,
  onSubmit, disabled, mapTarget, onClearMapTarget,
}: Props) {
  const [actionType, setActionType] = useState<ActionKey>('task_assets')
  const [target, setTarget] = useState('')
  const [mission, setMission] = useState('sda_sweep')
  const [rationale, setRationale] = useState('')
  const [preview, setPreview] = useState<OperationPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (mapTarget != null) setTarget(mapTarget)
  }, [mapTarget])

  const otherFactions = Object.entries(factionNames).filter(([fid]) => fid !== humanFactionId)
  const effectiveTarget = mapTarget ?? target

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
        if (res.ok) setPreview(await res.json())
      } finally {
        setPreviewLoading(false)
      }
    }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [actionType, effectiveTarget, mission, sessionId])

  function handleSubmit() {
    const params: Record<string, string> = {}
    if (actionType === 'task_assets') params.mission = mission
    const forecastPayload = preview ? {
      action_type: actionType,
      mission: actionType === 'task_assets' ? mission : '',
      target_faction_id: effectiveTarget || '',
      forecast: preview,
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

  return (
    <div>
      <div className="panel-title">◆ OPERATIONS PHASE</div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>ACTION TYPE</div>
        {ACTION_TYPES.map(({ key, label, desc }) => (
          <label key={key} style={{
            display: 'flex', alignItems: 'flex-start', gap: 8,
            padding: '6px 0', borderBottom: '1px solid #00d4ff08', cursor: 'pointer',
          }}>
            <input
              type="radio" name="action" value={key}
              checked={actionType === key}
              onChange={() => setActionType(key)}
              disabled={disabled}
              style={{ marginTop: 3, accentColor: '#00d4ff' }}
            />
            <div>
              <div style={{ fontSize: 13, color: '#e2e8f0' }}>{label}</div>
              <div style={{ fontSize: 12, color: '#475569' }}>{desc}</div>
            </div>
          </label>
        ))}
      </div>

      {actionType === 'task_assets' && (
        <div style={{ marginBottom: 12 }}>
          <div className="panel-title" style={{ fontSize: 11 }}>MISSION</div>
          {MISSIONS.map(({ key, label }) => {
            const noAsats = key === 'intercept' && asatKinetic === 0
            return (
              <label key={key} style={{ display: 'flex', gap: 8, padding: '4px 0', cursor: noAsats ? 'not-allowed' : 'pointer', opacity: noAsats ? 0.4 : 1 }}>
                <input
                  type="radio" name="mission" value={key}
                  checked={mission === key}
                  onChange={() => setMission(key)}
                  disabled={disabled || noAsats}
                  style={{ accentColor: '#00d4ff' }}
                />
                <span style={{ fontSize: 13, color: '#94a3b8' }}>
                  {label}{noAsats ? ' — no kinetic ASATs' : ''}
                </span>
              </label>
            )
          })}
        </div>
      )}

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>
          TARGET FACTION {!mapTarget && <span style={{ color: '#334155' }}>(optional — or click map)</span>}
        </div>
        {mapTarget ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '6px 8px', border: '1px solid #f59e0b66', borderRadius: 2,
            background: 'rgba(245,158,11,0.06)',
          }}>
            <span style={{ fontFamily: 'Courier New', fontSize: 13, color: '#f59e0b', letterSpacing: 1 }}>
              ◎ {factionNames[mapTarget] ?? mapTarget}
            </span>
            <button
              onClick={() => { onClearMapTarget?.(); setTarget('') }}
              disabled={disabled}
              style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14, padding: '0 4px', lineHeight: 1 }}
            >
              ×
            </button>
          </div>
        ) : (
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={disabled}
            style={{
              width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
              color: '#94a3b8', padding: '6px 8px', fontFamily: 'Courier New',
              fontSize: 13, borderRadius: 2,
            }}
          >
            <option value="">— none —</option>
            {otherFactions.map(([fid, name]) => (
              <option key={fid} value={fid}>{name}</option>
            ))}
          </select>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <div className="panel-title" style={{ fontSize: 11 }}>RATIONALE</div>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Operational rationale..."
          disabled={disabled}
          style={{
            width: '100%', background: '#020b18', border: '1px solid #00d4ff22',
            color: '#94a3b8', padding: '6px 8px', fontFamily: 'system-ui',
            fontSize: 13, resize: 'vertical', minHeight: 60, borderRadius: 2,
            boxSizing: 'border-box',
          }}
        />
      </div>

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

      <button
        className="btn-primary"
        onClick={handleSubmit}
        disabled={disabled || !rationale.trim()}
        style={{ width: '100%' }}
      >
        [ EXECUTE OPERATION ]
      </button>
    </div>
  )
}
```

- [ ] **Step 3: Type-check**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add web/src/api/client.ts web/src/components/phase/OpsPanel.tsx
git commit -m "feat: live preview panel in OpsPanel with 300ms debounce"
```

---

## Task 8: GamePage Wiring

**Files:**
- Modify: `web/src/pages/GamePage.tsx:136-160` (handleDecision)
- Modify: `web/src/pages/GamePage.tsx:359-368` (OpsPanel usage)

- [ ] **Step 1: Update handleDecision to accept and forward forecast**

In `web/src/pages/GamePage.tsx`, replace `handleDecision` (lines 136-160):

```typescript
  async function handleDecision(
    decision: Record<string, unknown>,
    forecast?: Record<string, unknown>,
  ) {
    if (!sessionId || !gameState) return
    const prevHumanId = gameState.human_faction_id
    setLoading(true)
    setError(null)
    setRecommendation(null)
    setRecommendationWarnings([])
    try {
      const res = await decide(sessionId, gameState.current_phase as string, decision, forecast)
      setGameState(res.state, res.coalition_dominance)
      // Hot-seat: detect player switch
      if (res.state.human_faction_id !== prevHumanId && !res.state.game_over && !res.state.awaiting_next_turn) {
        const toName = res.state.faction_states[res.state.human_faction_id]?.name ?? res.state.human_faction_id
        setHandoff({ toName })
      } else if (res.state.current_phase === 'invest' && !res.state.game_over && res.state.turn > gameState.turn) {
        setShowSummary(true)
      } else if (res.state.human_snapshot && gameState.use_advisor) {
        await fetchRecommendation(res.state.current_phase as 'invest' | 'operations' | 'response')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }
```

- [ ] **Step 2: Pass sessionId to OpsPanel**

In `web/src/pages/GamePage.tsx`, find the OpsPanel usage (around line 359). Replace:

```tsx
          {phase === 'operations' && (
            <OpsPanel
              factionNames={factionNames}
              humanFactionId={gameState.human_faction_id}
              asatKinetic={fs.assets.asat_kinetic}
              onSubmit={handleDecision}
              disabled={isLoading}
              mapTarget={pendingTarget}
              onClearMapTarget={() => setPendingTarget(null)}
            />
          )}
```

With:

```tsx
          {phase === 'operations' && (
            <OpsPanel
              factionNames={factionNames}
              humanFactionId={gameState.human_faction_id}
              asatKinetic={fs.assets.asat_kinetic}
              sessionId={sessionId!}
              onSubmit={handleDecision}
              disabled={isLoading}
              mapTarget={pendingTarget}
              onClearMapTarget={() => setPendingTarget(null)}
            />
          )}
```

- [ ] **Step 3: Type-check**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/GamePage.tsx
git commit -m "feat: wire sessionId to OpsPanel; forward forecast through handleDecision"
```

---

## Task 9: ForecastTab Component

**Files:**
- Create: `web/src/components/ForecastTab.tsx`

- [ ] **Step 1: Create web/src/components/ForecastTab.tsx**

```tsx
// web/src/components/ForecastTab.tsx
import type { OperationForecast } from '../types'

interface Props {
  forecasts: OperationForecast[]
  factionNames: Record<string, string>
}

function accuracyGrade(forecast: OperationForecast): { grade: string; color: string } | null {
  if (!forecast.actual) return null
  const isCombat = forecast.action_type === 'task_assets'
    ? forecast.mission === 'intercept'
    : forecast.action_type === 'gray_zone'
  if (!isCombat) return null

  const delta = Math.abs(
    forecast.forecast.nodes_destroyed_estimate - forecast.actual.nodes_destroyed
  )
  const detectionPredicted = forecast.forecast.detection_prob >= 0.5
  const detectionMatched = detectionPredicted === forecast.actual.detected

  if (delta <= 1 && detectionMatched) return { grade: 'A', color: '#00ff88' }
  if (delta <= 2) return { grade: 'B', color: '#f59e0b' }
  return { grade: 'C', color: '#ff4499' }
}

const COL = {
  header: {
    fontFamily: 'Courier New', fontSize: 10, color: '#475569',
    letterSpacing: 1, padding: '4px 8px', borderBottom: '1px solid #00d4ff22',
    whiteSpace: 'nowrap' as const,
  },
  cell: {
    fontFamily: 'Courier New', fontSize: 11, color: '#94a3b8',
    padding: '4px 8px', borderBottom: '1px solid #00d4ff0a',
    whiteSpace: 'nowrap' as const,
  },
}

export default function ForecastTab({ forecasts, factionNames }: Props) {
  if (forecasts.length === 0) {
    return (
      <div style={{
        height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ fontFamily: 'Courier New', fontSize: 11, color: '#334155', letterSpacing: 2, textAlign: 'center' }}>
          NO FORECAST DATA<br />
          <span style={{ fontSize: 10 }}>Execute an operation to begin tracking</span>
        </div>
      </div>
    )
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '10px 14px' }}>
      <div className="panel-title" style={{ marginBottom: 8 }}>◆ FORECAST ACCURACY LEDGER</div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['TURN', 'ACTION', 'TARGET', 'EST.NODES', 'ACTUAL', 'DETECTED', 'ATTRIBUTED', 'ACCURACY'].map(h => (
              <th key={h} style={COL.header}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {forecasts.map((fc, i) => {
            const targetName = factionNames[fc.target_faction_id] ?? fc.target_faction_id ?? '—'
            const action = fc.action_type === 'task_assets' ? (fc.mission || 'patrol') : fc.action_type
            const isCombatAction = fc.action_type === 'task_assets'
              ? fc.mission === 'intercept'
              : fc.action_type === 'gray_zone'
            const grade = accuracyGrade(fc)

            let estNodes: string
            if (!isCombatAction) estNodes = '—'
            else if (fc.forecast.nodes_destroyed_min !== fc.forecast.nodes_destroyed_max)
              estNodes = `${fc.forecast.nodes_destroyed_min}–${fc.forecast.nodes_destroyed_max}`
            else estNodes = String(fc.forecast.nodes_destroyed_estimate)

            const pendingCell = <span style={{ color: '#00d4ff44' }}>PENDING</span>
            const naCell = <span style={{ color: '#334155' }}>N/A</span>

            return (
              <tr key={i}>
                <td style={COL.cell}>{fc.turn}</td>
                <td style={{ ...COL.cell, color: '#00d4ff', textTransform: 'uppercase' as const }}>{action.replace('_', ' ')}</td>
                <td style={COL.cell}>{targetName}</td>
                <td style={COL.cell}>{estNodes}</td>
                <td style={COL.cell}>
                  {!isCombatAction ? naCell
                    : fc.pending ? pendingCell
                    : fc.actual ? String(fc.actual.nodes_destroyed)
                    : naCell}
                </td>
                <td style={COL.cell}>
                  {!isCombatAction ? naCell
                    : fc.pending ? pendingCell
                    : fc.actual
                      ? <span>
                          <span style={{ color: '#64748b' }}>{Math.round(fc.forecast.detection_prob * 100)}% → </span>
                          <span style={{ color: fc.actual.detected ? '#00ff88' : '#ff4499' }}>
                            {fc.actual.detected ? '✓' : '✗'}
                          </span>
                        </span>
                      : naCell}
                </td>
                <td style={COL.cell}>
                  {!isCombatAction ? naCell
                    : fc.pending ? pendingCell
                    : fc.actual
                      ? <span>
                          <span style={{ color: '#64748b' }}>{Math.round(fc.forecast.attribution_prob * 100)}% → </span>
                          <span style={{ color: fc.actual.attributed ? '#00ff88' : '#ff4499' }}>
                            {fc.actual.attributed ? '✓' : '✗'}
                          </span>
                        </span>
                      : naCell}
                </td>
                <td style={{ ...COL.cell, fontWeight: 700 }}>
                  {grade
                    ? <span style={{ color: grade.color }}>{grade.grade}</span>
                    : naCell}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ForecastTab.tsx
git commit -m "feat: add ForecastTab component with accuracy ledger"
```

---

## Task 10: MapTabContainer FORECAST Tab + GamePage Wiring

**Files:**
- Modify: `web/src/components/MapTabContainer.tsx:3-175`
- Modify: `web/src/pages/GamePage.tsx:304-325`

- [ ] **Step 1: Add FORECAST tab to MapTabContainer**

In `web/src/components/MapTabContainer.tsx`:

1. Add import at the top (after existing imports):

```typescript
import ForecastTab from './ForecastTab'
import type { OperationForecast } from '../types'
```

2. Add `'forecast'` to the `Tab` type (line 12):

```typescript
type Tab = 'orbital' | 'deltav' | 'ops' | 'trends' | 'log' | 'tech' | 'forecast'
```

3. Add `forecasts` to `Props` interface (after `arcOpacity?: number`):

```typescript
  forecasts?: OperationForecast[]
```

4. Add `forecasts = []` to the destructured props in the function signature:

```typescript
export default function MapTabContainer({
  ..., combatEvents, arcOpacity, forecasts = [],
}: Props) {
```

5. Add FORECAST entry to `TAB_LABELS` (after `tech`):

```typescript
const TAB_LABELS: { id: Tab; label: string }[] = [
  { id: 'orbital', label: 'ORBITAL' },
  { id: 'deltav',  label: 'DELTA-V' },
  { id: 'ops',     label: 'OPS' },
  { id: 'trends',  label: 'TRENDS' },
  { id: 'log',     label: 'LOG' },
  { id: 'tech',    label: 'TECH' },
  { id: 'forecast', label: 'FORECAST' },
]
```

6. Add FORECAST tab content in the `{/* Tab content */}` section, after the `tech` block:

```tsx
        {activeTab === 'forecast' && (
          <ForecastTab
            forecasts={forecasts}
            factionNames={Object.fromEntries(
              Object.entries(gameState.faction_states).map(([fid, fs]) => [fid, fs.name])
            )}
          />
        )}
```

- [ ] **Step 2: Pass forecasts from GamePage to MapTabContainer**

In `web/src/pages/GamePage.tsx`, find the `<MapTabContainer` usage (around line 304). Add `forecasts` prop:

```tsx
          <MapTabContainer
            gameState={gameState}
            coalitionDominance={coalitionDominance}
            turnHistory={turnHistory}
            prevFactionStates={prevFactionStates}
            humanAdversaryEstimates={gameState.human_adversary_estimates ?? {}}
            factionState={fs}
            turn={gameState.turn}
            totalTurns={gameState.total_turns}
            tensionLevel={gameState.tension_level}
            cumulativeAdded={cumulativeAdded}
            cumulativeDestroyed={cumulativeDestroyed}
            isJammed={isJammed}
            targetingMode={phase === 'operations' && !isLoading}
            lockedFaction={pendingTarget}
            onFactionClick={setPendingTarget}
            pendingTechUnlocks={pendingTechUnlocks}
            onQueueTech={handleQueueTech}
            rdPoints={rdPoints}
            combatEvents={gameState.combat_events}
            arcOpacity={arcOpacity}
            forecasts={gameState.operation_forecasts ?? []}
          />
```

- [ ] **Step 3: Type-check**

```bash
cd /Users/tbarnes/projects/agents/web && npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add web/src/components/MapTabContainer.tsx web/src/pages/GamePage.tsx
git commit -m "feat: add FORECAST tab to MapTabContainer; wire operation_forecasts from GamePage"
```

---

## Task 11: Forecast Ledger Tests

**Files:**
- Create: `tests/test_forecast_ledger.py`

- [ ] **Step 1: Write the tests**

Create `tests/test_forecast_ledger.py`:

```python
# tests/test_forecast_ledger.py
import pytest
import json
from pathlib import Path
from api.runner import create_game, advance
from api.models import GameState
from engine.state import Phase, FactionState, FactionAssets
from engine.referee import GameReferee
from engine.preview import OperationPreview


def _first_scenario_id() -> str:
    scenarios = list((Path(__file__).parent.parent / "scenarios").glob("*.yaml"))
    if not scenarios:
        pytest.skip("No scenario files found")
    return scenarios[0].stem


@pytest.fixture
async def fresh_game(tmp_path):
    """Create a game at OPERATIONS phase, ready for a decision."""
    sid = _first_scenario_id()
    from scenarios.loader import load_scenario
    scenario = load_scenario(Path("scenarios") / f"{sid}.yaml")
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {
            "faction_id": f.faction_id,
            "agent_type": "web" if f.faction_id == human_fid else "rule_based",
            "use_advisor": False,
        }
        for f in scenario.factions
    ]
    db = str(tmp_path / "s.db")
    state = await create_game(sid, agent_config, db_path=db)
    # Advance to OPERATIONS: submit invest decision
    invest_decision = {
        "phase": "invest",
        "decision": {"investment": {
            "constellation": 0.5, "kinetic_weapons": 0.0,
            "r_and_d": 0.0, "meo_deployment": 0.0, "geo_deployment": 0.0,
            "cislunar_deployment": 0.0, "launch_capacity": 0.0, "commercial": 0.0,
            "influence_ops": 0.5, "education": 0.0, "covert": 0.0,
            "diplomacy": 0.0, "rationale": "test invest",
        }},
    }
    resp = await advance(state.session_id, decision=invest_decision, db_path=db)
    # Should be at OPERATIONS now (or still INVEST if other factions not yet decided — drive to OPERATIONS)
    while resp.state.current_phase != Phase.OPERATIONS:
        resp = await advance(resp.state.session_id, db_path=db)
    return resp.state, db


@pytest.mark.asyncio
async def test_forecast_saved_when_decision_submitted(fresh_game):
    state, db = await fresh_game
    human_fid = state.human_faction_id

    preview = OperationPreview(
        available=True, dv_cost=0.0, effect_summary="EW test",
    )
    forecast_payload = {
        "action_type": "gray_zone",
        "mission": "",
        "target_faction_id": "",
        "forecast": preview.model_dump(),
    }
    ops_decision = {
        "phase": "operations",
        "decision": {"operations": [{
            "action_type": "gray_zone",
            "target_faction": None,
            "parameters": {},
            "rationale": "test",
        }]},
    }
    resp = await advance(
        state.session_id,
        decision=ops_decision,
        operation_forecast=forecast_payload,
        db_path=db,
    )
    assert len(resp.state.operation_forecasts) == 1
    fc = resp.state.operation_forecasts[0]
    assert fc["faction_id"] == human_fid
    assert fc["action_type"] == "gray_zone"
    assert fc["actual"] is None
    assert fc["pending"] is True


@pytest.mark.asyncio
async def test_non_combat_forecast_reconciled_after_operations(fresh_game):
    """A patrol forecast gets actual=None, pending=False after OPERATIONS resolves."""
    state, db = await fresh_game

    preview = OperationPreview(available=True, effect_summary="Surveillance only")
    forecast_payload = {
        "action_type": "task_assets",
        "mission": "patrol",
        "target_faction_id": "",
        "forecast": preview.model_dump(),
    }
    ops_decision = {
        "phase": "operations",
        "decision": {"operations": [{
            "action_type": "task_assets",
            "target_faction": None,
            "parameters": {"mission": "patrol"},
            "rationale": "test patrol",
        }]},
    }
    resp = await advance(
        state.session_id,
        decision=ops_decision,
        operation_forecast=forecast_payload,
        db_path=db,
    )
    # Drive to end of OPERATIONS (other factions decide) and RESPONSE
    while resp.state.current_phase in (Phase.OPERATIONS, Phase.RESPONSE):
        resp = await advance(resp.state.session_id, db_path=db)

    fc = next(
        (f for f in resp.state.operation_forecasts if f["action_type"] == "task_assets"),
        None,
    )
    assert fc is not None
    assert fc["pending"] is False
    assert fc["actual"] is None


@pytest.mark.asyncio
async def test_kinetic_forecast_stays_pending_then_reconciles(fresh_game):
    """Kinetic intercept forecast: pending=True for 2 turns, then reconciled."""
    state, db = await fresh_game
    human_fid = state.human_faction_id

    # Give the human faction kinetic ASATs and DV for the test
    from api.session import load_session, save_session
    s = await load_session(state.session_id, db_path=db)
    s.faction_states[human_fid].assets.asat_kinetic = 3
    s.faction_states[human_fid].maneuver_budget = 20.0
    # Find an adversary faction
    adversary_fid = next(
        fid for fid, fs in s.faction_states.items()
        if fs.coalition_id != s.faction_states[human_fid].coalition_id
    )
    s.faction_states[adversary_fid].assets.leo_nodes = 5
    await save_session(s, db_path=db)

    preview = OperationPreview(
        available=True, dv_cost=4.0, transit_turns=2, nodes_destroyed_estimate=3,
        nodes_destroyed_min=3, nodes_destroyed_max=3, detection_prob=0.8,
    )
    forecast_payload = {
        "action_type": "task_assets",
        "mission": "intercept",
        "target_faction_id": adversary_fid,
        "forecast": preview.model_dump(),
    }
    ops_decision = {
        "phase": "operations",
        "decision": {"operations": [{
            "action_type": "task_assets",
            "target_faction": adversary_fid,
            "parameters": {"mission": "intercept"},
            "rationale": "test intercept",
        }]},
    }
    resp = await advance(
        state.session_id,
        decision=ops_decision,
        operation_forecast=forecast_payload,
        db_path=db,
    )

    # Drive to end of turn (RESPONSE + next INVEST)
    while resp.state.current_phase != Phase.OPERATIONS or resp.state.turn == state.turn:
        resp = await advance(resp.state.session_id, db_path=db)

    # After completing turn N, forecast should still be pending (kinetic fires at turn N+2)
    fc = next(
        (f for f in resp.state.operation_forecasts if f["action_type"] == "task_assets" and f["mission"] == "intercept"),
        None,
    )
    assert fc is not None
    assert fc["pending"] is True

    # Complete turn N+1 entirely
    turn_n1 = resp.state.turn
    while resp.state.turn == turn_n1 or resp.state.current_phase != Phase.OPERATIONS:
        resp = await advance(resp.state.session_id, db_path=db)

    # Now at turn N+2 INVEST — kinetics fired, forecast should be reconciled
    fc = next(
        (f for f in resp.state.operation_forecasts if f["action_type"] == "task_assets" and f["mission"] == "intercept"),
        None,
    )
    assert fc is not None
    assert fc["pending"] is False
    assert fc["actual"] is not None
    assert "nodes_destroyed" in fc["actual"]
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/test_forecast_ledger.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/tbarnes/projects/agents && .venv/bin/python -m pytest tests/ -v --tb=short
```

Expected: All PASS (or pre-existing failures only)

- [ ] **Step 4: Commit**

```bash
git add tests/test_forecast_ledger.py
git commit -m "test: forecast ledger integration tests including 2-turn kinetic reconciliation"
```
