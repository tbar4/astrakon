import pytest
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, Recommendation,
    GameStateSnapshot, FactionState, FactionAssets, CrisisEvent, CoalitionState
)
from scenarios.loader import Faction


class ConcreteAgent(AgentInterface):
    async def submit_decision(self, phase: Phase) -> Decision:
        return Decision(
            phase=phase, faction_id=self.faction_id,
            investment=InvestmentAllocation(r_and_d=0.5, constellation=0.5, rationale="test")
        )


def test_agent_interface_requires_submit_decision():
    with pytest.raises(TypeError):
        AgentInterface()


async def test_concrete_agent_submit_decision():
    agent = ConcreteAgent()
    faction = Faction(
        faction_id="ussf", name="US Space Force", archetype="mahanian",
        agent_type="rule_based", budget_per_turn=100,
        starting_assets=FactionAssets(leo_nodes=24, sda_sensors=12)
    )
    agent.initialize(faction)
    decision = await agent.submit_decision(Phase.INVEST)
    assert decision.faction_id == "ussf"
    assert decision.phase == Phase.INVEST


from agents.rule_based import MahanianAgent, MaxConstellationAgent


@pytest.fixture
def test_faction():
    return Faction(
        faction_id="ussf", name="US Space Force", archetype="mahanian",
        agent_type="rule_based", budget_per_turn=100,
        starting_assets=FactionAssets(leo_nodes=24, sda_sensors=8)
    )


@pytest.fixture
def test_snapshot(test_faction):
    return GameStateSnapshot(
        turn=1, phase=Phase.INVEST, faction_id="ussf",
        faction_state=FactionState(
            faction_id="ussf", name="US Space Force",
            budget_per_turn=100, current_budget=100,
            assets=test_faction.starting_assets
        ),
        ally_states={}, adversary_estimates={}, coalition_states={},
        available_actions=["allocate_budget"],
    )


async def test_mahanian_agent_invests_in_sda(test_faction, test_snapshot):
    agent = MahanianAgent()
    agent.initialize(test_faction)
    agent.receive_state(test_snapshot)
    decision = await agent.submit_decision(Phase.INVEST)
    assert decision.investment is not None
    assert decision.investment.r_and_d + decision.investment.constellation >= 0.4


async def test_max_constellation_agent(test_faction, test_snapshot):
    agent = MaxConstellationAgent()
    agent.initialize(test_faction)
    agent.receive_state(test_snapshot)
    decision = await agent.submit_decision(Phase.INVEST)
    assert decision.investment.constellation >= 0.6


async def test_rule_based_returns_valid_decision_all_phases(test_faction, test_snapshot):
    agent = MahanianAgent()
    agent.initialize(test_faction)
    agent.receive_state(test_snapshot)
    for phase in [Phase.INVEST, Phase.OPERATIONS, Phase.RESPONSE]:
        test_snapshot.phase = phase
        agent.receive_state(test_snapshot)
        decision = await agent.submit_decision(phase)
        assert decision.faction_id == "ussf"
        assert decision.phase == phase
