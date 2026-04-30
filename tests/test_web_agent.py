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
