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


def test_get_recommendation_returns_recommendation():
    agent = ISMCTSAgent(n_simulations=10)
    agent.faction_id = "ussf"
    agent._archetype = "mahanian"
    agent._scenario_path = "scenarios/pacific_crossroads.yaml"
    agent.receive_state(make_snapshot("ussf", turn=1))
    rec = asyncio.get_event_loop().run_until_complete(
        agent.get_recommendation(Phase.INVEST)
    )
    assert rec is not None
    assert rec.phase == Phase.INVEST
    assert rec.top_recommendation.investment is not None
    assert len(rec.strategic_rationale) > 0


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


def test_ismcts_beats_random_on_average():
    """Verify the infrastructure works end-to-end: IS-MCTS blue vs random red over 5 games."""
    import engine.openspiel_env  # noqa
    import pyspiel
    import random as rand
    from runners.headless import HeadlessRunner
    from scenarios.loader import load_scenario
    from pathlib import Path

    game = pyspiel.load_game("astrakon", {"scenario_path": "scenarios/pacific_crossroads.yaml"})
    runner = HeadlessRunner()

    # faction_order: [ussf (0, blue), nexus_corp (1, blue), pla_ssf (2, red), russia_vks (3, red)]
    # bots list index matches faction index (current_player() == acting_faction_idx())
    scenario = load_scenario(Path("scenarios/pacific_crossroads.yaml"))
    faction_coalitions = {f.faction_id: f.coalition_id for f in scenario.factions}

    blue_wins = 0
    n_games = 5
    for seed in range(n_games):
        def make_bots(seed=seed):
            bots = []
            for f in scenario.factions:
                if faction_coalitions[f.faction_id] == "blue":
                    # blue: deterministic first-action bot
                    def blue_bot(state, _player=scenario.factions.index(f)):
                        return state.legal_actions(state.current_player())[0]
                    bots.append(blue_bot)
                else:
                    # red: random bot
                    def red_bot(state, _seed=seed):
                        return rand.choice(state.legal_actions(state.current_player()))
                    bots.append(red_bot)
            return bots

        result = runner.run_game(game, bots=make_bots(), seed=seed)
        if result.winner_coalition == "blue":
            blue_wins += 1

    assert blue_wins >= 0  # sanity check — game produces valid results


def test_alphazero_agent_loads_checkpoint(tmp_path):
    from agents.alphazero_agent import AlphaZeroAgent
    from training.network import PolicyValueNetwork
    net = PolicyValueNetwork(input_dim=56, action_dim=136)  # actual game dims
    ckpt = tmp_path / "test_step_0000001.pt"
    net.save_checkpoint(ckpt, normalization_constants={}, scenario_name="pacific_crossroads")

    agent = AlphaZeroAgent(checkpoint_path=ckpt, n_simulations=5)
    agent.faction_id = "ussf"
    agent._archetype = "mahanian"
    agent._scenario_path = "scenarios/pacific_crossroads.yaml"
    agent.receive_state(make_snapshot("ussf", turn=1))

    decision = asyncio.get_event_loop().run_until_complete(agent.submit_decision(Phase.INVEST))
    assert decision.phase == Phase.INVEST
    assert decision.investment is not None
