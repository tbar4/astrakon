import pytest
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, Recommendation,
    GameStateSnapshot, FactionState, FactionAssets, CrisisEvent
)


class ConcreteAgent(AgentInterface):
    async def submit_decision(self, phase: Phase) -> Decision:
        return Decision(
            phase=phase, faction_id=self.faction_id,
            investment=InvestmentAllocation(r_and_d=0.5, constellation=0.5, rationale="test")
        )


def test_agent_interface_requires_submit_decision():
    from abc import ABC
    assert issubclass(AgentInterface, ABC)


async def test_concrete_agent_submit_decision():
    from engine.state import FactionState, FactionAssets
    from scenarios.loader import Faction, Scenario, VictoryConditions
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
