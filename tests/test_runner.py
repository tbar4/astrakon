# tests/test_runner.py
import pytest
from pathlib import Path
from api.runner import create_game, advance
from api.models import GameState
from engine.state import Phase


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
