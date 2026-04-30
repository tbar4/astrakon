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
