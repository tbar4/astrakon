import pytest
import torch
from pathlib import Path
from training.self_play import TrainingExample, SelfPlayRunner
from training.network import PolicyValueNetwork


def make_runner(n_simulations: int = 10):
    net = PolicyValueNetwork(input_dim=56, action_dim=136)
    return SelfPlayRunner(
        network=net,
        game_params={"scenario_path": "scenarios/pacific_crossroads.yaml"},
        n_simulations=n_simulations,
    )


def test_training_example_fields():
    ex = TrainingExample(
        info_state=torch.randn(56),
        mcts_policy=torch.softmax(torch.randn(136), dim=0),
        game_return=1.0,
    )
    assert ex.info_state.shape == (56,)
    assert ex.mcts_policy.shape == (136,)
    assert isinstance(ex.game_return, float)


def test_generate_game_returns_examples():
    runner = make_runner(n_simulations=5)
    examples = runner.generate_game(seed=42)
    assert len(examples) > 0
    for ex in examples:
        assert not torch.isnan(ex.info_state).any()
        assert not torch.isnan(ex.mcts_policy).any()
        assert ex.game_return in (-1.0, 0.0, 1.0)


def test_generate_game_reproducible():
    runner = make_runner(n_simulations=5)
    ex1 = runner.generate_game(seed=7)
    ex2 = runner.generate_game(seed=7)
    assert len(ex1) == len(ex2)
    assert torch.allclose(ex1[0].info_state, ex2[0].info_state)
    assert ex1[0].game_return == ex2[0].game_return


def test_mcts_policy_sums_to_one():
    runner = make_runner(n_simulations=5)
    examples = runner.generate_game(seed=0)
    for ex in examples:
        assert abs(ex.mcts_policy.sum().item() - 1.0) < 1e-5
