import pytest
import asyncio
from pathlib import Path
from agents.mcts_agent import ISMCTSAgent
from engine.state import Phase, GameStateSnapshot, FactionState, FactionAssets, CoalitionState
from scenarios.loader import load_scenario

SCENARIO = load_scenario(Path("scenarios/pacific_crossroads.yaml"))


def make_snapshot(faction_id: str = "ussf", turn: int = 1) -> GameStateSnapshot:
    fs = FactionState(
        faction_id=faction_id, name="US Space Force",
        budget_per_turn=100, current_budget=100,
        assets=FactionAssets(leo_nodes=30, geo_nodes=6, sda_sensors=12, launch_capacity=3),
        coalition_id="blue",
    )
    return GameStateSnapshot(
        turn=turn, phase=Phase.INVEST, faction_id=faction_id, faction_state=fs,
        ally_states={
            "nexus_corp": FactionState(
                faction_id="nexus_corp", name="Nexus",
                budget_per_turn=75, current_budget=75,
                assets=FactionAssets(leo_nodes=25, geo_nodes=2),
                coalition_id="blue",
            )
        },
        adversary_estimates={
            "pla_ssf": {"leo_nodes": 30, "meo_nodes": 3, "geo_nodes": 3,
                        "cislunar_nodes": 0, "asat_kinetic": 5},
            "russia_vks": {"leo_nodes": 10, "meo_nodes": 3, "asat_kinetic": 6,
                           "ew_jammers": 5},
        },
        coalition_states={},
        available_actions=["task_assets", "coordinate", "gray_zone", "signal"],
        coalition_dominance={"blue": 0.52, "red": 0.48},
        victory_threshold=0.68,
        total_turns=14,
    )


def test_agent_initializes():
    agent = ISMCTSAgent(n_simulations=10, rollout_policy="rule_based")
    assert agent.n_simulations == 10


def test_receive_state_clears_cache():
    agent = ISMCTSAgent(n_simulations=10)
    agent._cached_ops_action = 105
    agent._cached_response_action = 140
    agent.receive_state(make_snapshot())
    assert agent._cached_ops_action is None
    assert agent._cached_response_action is None


def test_invest_decision_valid():
    agent = ISMCTSAgent(n_simulations=20)
    agent.faction_id = "ussf"
    agent._archetype = "mahanian"
    agent._scenario_path = "scenarios/pacific_crossroads.yaml"
    agent.receive_state(make_snapshot("ussf", turn=1))
    decision = asyncio.get_event_loop().run_until_complete(
        agent.submit_decision(Phase.INVEST)
    )
    assert decision.phase == Phase.INVEST
    assert decision.investment is not None
    assert decision.investment.total() <= 1.001


def test_invest_populates_ops_cache():
    agent = ISMCTSAgent(n_simulations=20)
    agent.faction_id = "ussf"
    agent._archetype = "mahanian"
    agent._scenario_path = "scenarios/pacific_crossroads.yaml"
    agent.receive_state(make_snapshot("ussf", turn=1))
    asyncio.get_event_loop().run_until_complete(agent.submit_decision(Phase.INVEST))
    assert agent._cached_ops_action is not None
    assert agent._cached_response_action is not None


def test_ops_returns_cached_without_new_search():
    agent = ISMCTSAgent(n_simulations=20)
    agent.faction_id = "ussf"
    agent._archetype = "mahanian"
    agent._scenario_path = "scenarios/pacific_crossroads.yaml"
    agent.receive_state(make_snapshot("ussf", turn=1))
    asyncio.get_event_loop().run_until_complete(agent.submit_decision(Phase.INVEST))
    agent.n_simulations = 0  # would fail if search runs again
    decision = asyncio.get_event_loop().run_until_complete(agent.submit_decision(Phase.OPERATIONS))
    assert decision.phase == Phase.OPERATIONS
    assert decision.operations is not None


def test_all_three_phases():
    for faction_id in ["ussf", "pla_ssf"]:
        agent = ISMCTSAgent(n_simulations=10)
        agent.faction_id = faction_id
        agent._archetype = "mahanian"
        agent._scenario_path = "scenarios/pacific_crossroads.yaml"
        snap = make_snapshot(faction_id, turn=1)
        agent.receive_state(snap)
        for phase in [Phase.INVEST, Phase.OPERATIONS, Phase.RESPONSE]:
            d = asyncio.get_event_loop().run_until_complete(agent.submit_decision(phase))
            assert d.phase == phase
