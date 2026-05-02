import pytest
from pathlib import Path
from training.network import PolicyValueNetwork
from training.replay_buffer import ReplayBuffer
from training.trainer import AlphaZeroTrainer
from training.self_play import SelfPlayRunner
from training.league import LeagueTrainer


def make_league(tmp_path: Path, pool_size: int = 6):
    net = PolicyValueNetwork(input_dim=56, action_dim=136)  # actual game dims
    buf = ReplayBuffer(max_size=100)
    trainer = AlphaZeroTrainer(net, buf, lr=1e-3, checkpoint_dir=tmp_path)
    trainer._scenario_name = "pacific_crossroads"
    runner = SelfPlayRunner(net, {"scenario_path": "scenarios/pacific_crossroads.yaml"}, n_simulations=5)
    return LeagueTrainer(
        trainer=trainer, runner=runner, pool_size=pool_size,
        games_per_iter=2, train_steps_per_iter=3,
    )


def test_initial_pool_has_4_permanent_agents():
    league = make_league(Path("/tmp"))
    permanent = [e for e in league.pool if e.get("permanent")]
    assert len(permanent) == 4


def test_permanent_agents_never_evicted(tmp_path: Path):
    league = make_league(tmp_path, pool_size=6)
    for _ in range(5):
        league._add_checkpoint_to_pool(tmp_path / "dummy.pt", elo=1000.0)
    permanent = [e for e in league.pool if e.get("permanent")]
    assert len(permanent) == 4


def test_nonpermanent_pool_size_capped(tmp_path: Path):
    league = make_league(tmp_path, pool_size=6)
    for i in range(10):
        league._add_checkpoint_to_pool(tmp_path / f"ckpt_{i}.pt", elo=float(1000 + i))
    nonpermanent = [e for e in league.pool if not e.get("permanent")]
    assert len(nonpermanent) <= league.pool_size - 4


def test_one_iteration_generates_games_and_trains(tmp_path: Path):
    league = make_league(tmp_path)
    # Prefill buffer to 10,001 so training steps can run
    from tests.test_trainer import make_example
    for i in range(10_001):
        league.trainer.buffer.add([make_example(i % 50)])
    n_games_before = league._total_games_generated
    league.run(total_iterations=1)
    assert league._total_games_generated > n_games_before
