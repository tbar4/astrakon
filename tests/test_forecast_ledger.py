# tests/test_forecast_ledger.py
import pytest
from pathlib import Path
from api.runner import create_game, advance
from api.models import GameState
from engine.state import Phase
from engine.preview import OperationPreview


def _first_scenario_id() -> str:
    scenarios = list((Path(__file__).parent.parent / "scenarios").glob("*.yaml"))
    if not scenarios:
        pytest.skip("No scenario files found")
    return scenarios[0].stem


@pytest.fixture
async def fresh_game(tmp_path):
    """Create a game at OPERATIONS phase with a human player ready to decide."""
    sid = _first_scenario_id()
    scenario_path = Path(__file__).parent.parent / "scenarios" / f"{sid}.yaml"
    from scenarios.loader import load_scenario
    scenario = load_scenario(scenario_path)
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
    # Submit invest decision — this will auto-advance AI factions and resolve INVEST,
    # leaving state at OPERATIONS phase for the human
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
    # Drive to OPERATIONS in case AI factions haven't decided yet
    while resp.state.current_phase != Phase.OPERATIONS:
        resp = await advance(resp.state.session_id, db_path=db)
    return resp.state, db


_NOOP_INVEST = {
    "phase": "invest",
    "decision": {"investment": {
        "constellation": 0.0, "kinetic_weapons": 0.0,
        "r_and_d": 0.0, "meo_deployment": 0.0, "geo_deployment": 0.0,
        "cislunar_deployment": 0.0, "launch_capacity": 0.0, "commercial": 0.0,
        "influence_ops": 0.0, "education": 0.0, "covert": 0.0,
        "diplomacy": 0.0, "rationale": "skip",
    }},
}

_NOOP_RESPONSE = {
    "phase": "response",
    "decision": {"response": {
        "escalate": False,
        "retaliate": False,
        "target_faction": None,
        "public_statement": "",
        "rationale": "skip",
    }},
}


async def _drive_to_operations(resp, db):
    """Advance through any pending INVEST or RESPONSE decisions until at OPERATIONS."""
    while resp.state.current_phase != Phase.OPERATIONS:
        if resp.state.current_phase == Phase.INVEST:
            resp = await advance(resp.state.session_id, decision=_NOOP_INVEST, db_path=db)
        elif resp.state.current_phase == Phase.RESPONSE:
            resp = await advance(resp.state.session_id, decision=_NOOP_RESPONSE, db_path=db)
        else:
            resp = await advance(resp.state.session_id, db_path=db)
    return resp


async def test_forecast_saved_when_decision_submitted(fresh_game):
    state, db = fresh_game  # auto-awaited by pytest-asyncio
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
    # gray_zone is not a kinetic intercept — reconciled immediately after OPERATIONS resolves
    assert fc["pending"] is False


async def test_non_combat_forecast_reconciled_after_operations(fresh_game):
    """A patrol forecast gets pending=False after OPERATIONS resolves (actual=None = no combat)."""
    state, db = fresh_game

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
    # Drive through remaining OPERATIONS + RESPONSE until next INVEST/OPERATIONS
    resp = await _drive_to_operations(resp, db)

    fc = next(
        (f for f in resp.state.operation_forecasts if f["action_type"] == "task_assets"),
        None,
    )
    assert fc is not None
    assert fc["pending"] is False
    assert fc["actual"] is None


async def test_kinetic_forecast_stays_pending_then_reconciles(fresh_game):
    """Kinetic intercept forecast: pending=True for 2 turns, then reconciled with actual."""
    state, db = fresh_game
    human_fid = state.human_faction_id

    # Give the human faction kinetic ASATs and DV for the test
    from api.session import load_session, save_session
    s = await load_session(state.session_id, db_path=db)
    s.faction_states[human_fid].assets.asat_kinetic = 3
    s.faction_states[human_fid].maneuver_budget = 20.0
    # Find an adversary faction with LEO nodes
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

    # Drive to end of turn N (through RESPONSE, into next INVEST/OPERATIONS)
    start_turn = state.turn
    resp = await _drive_to_operations(resp, db)
    # We should now be at turn N+1 OPERATIONS
    # After turn N completes, kinetic intercept is still in transit — should still be pending
    fc = next(
        (f for f in resp.state.operation_forecasts
         if f["action_type"] == "task_assets" and f["mission"] == "intercept"),
        None,
    )
    assert fc is not None, "Forecast should still exist after turn N"
    assert fc["pending"] is True, "Kinetic intercept should still be pending (2-turn transit)"

    # Submit a no-op ops decision for turn N+1 and drive to turn N+2 OPERATIONS
    noop_ops_decision = {
        "phase": "operations",
        "decision": {"operations": []},
    }
    resp = await advance(resp.state.session_id, decision=noop_ops_decision, db_path=db)
    resp = await _drive_to_operations(resp, db)

    # Now at turn N+2 OPERATIONS — kinetics fired at end of INVEST N+2, forecast should be reconciled
    fc = next(
        (f for f in resp.state.operation_forecasts
         if f["action_type"] == "task_assets" and f["mission"] == "intercept"),
        None,
    )
    assert fc is not None, "Forecast should still exist after turn N+2"
    assert fc["pending"] is False, "Kinetic intercept should be reconciled after 2 turns"
    assert fc["actual"] is not None, "Actual outcome should be recorded"
    assert "nodes_destroyed" in fc["actual"]
