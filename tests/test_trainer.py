import pytest
import torch
from training.replay_buffer import ReplayBuffer


def make_example(seed: int = 0):
    torch.manual_seed(seed)
    from training.self_play import TrainingExample
    return TrainingExample(
        info_state=torch.randn(64),
        mcts_policy=torch.softmax(torch.randn(134), dim=0),
        game_return=1.0,
    )


def test_buffer_add_and_len():
    buf = ReplayBuffer(max_size=100)
    assert len(buf) == 0
    for i in range(10):
        buf.add([make_example(i)])
    assert len(buf) == 10


def test_buffer_sample_shapes():
    buf = ReplayBuffer(max_size=100)
    for i in range(20):
        buf.add([make_example(i)])
    states, policies, values = buf.sample(batch_size=8)
    assert states.shape == (8, 64)
    assert policies.shape == (8, 134)
    assert values.shape == (8,)


def test_buffer_fifo_eviction():
    buf = ReplayBuffer(max_size=10)
    for i in range(15):
        buf.add([make_example(i)])
    assert len(buf) == 10


def test_buffer_raises_if_too_small_to_sample():
    buf = ReplayBuffer(max_size=100)
    buf.add([make_example(0)])
    with pytest.raises(ValueError):
        buf.sample(batch_size=8)


from training.network import PolicyValueNetwork
from training.trainer import AlphaZeroTrainer
from pathlib import Path


def make_trainer(tmp_path: Path):
    net = PolicyValueNetwork(input_dim=64, action_dim=134)
    buf = ReplayBuffer(max_size=100_000)
    return AlphaZeroTrainer(
        network=net, buffer=buf,
        lr=1e-3, checkpoint_dir=tmp_path,
    ), net, buf


def test_train_step_raises_with_small_buffer(tmp_path: Path):
    trainer, _, buf = make_trainer(tmp_path)
    for i in range(100):
        buf.add([make_example(i)])
    with pytest.raises(RuntimeError, match="10,000"):
        trainer.train_step(batch_size=32)


def test_train_step_produces_finite_losses(tmp_path: Path):
    trainer, net, buf = make_trainer(tmp_path)
    for i in range(10_001):
        buf.add([make_example(i % 50)])
    losses = trainer.train_step(batch_size=32)
    assert "policy_loss" in losses
    assert "value_loss" in losses
    assert "total_loss" in losses
    for v in losses.values():
        assert torch.isfinite(torch.tensor(v))


def test_checkpoint_save_load(tmp_path: Path):
    trainer, net, buf = make_trainer(tmp_path)
    trainer._scenario_name = "pacific_crossroads"
    path = trainer.save_checkpoint(step=42)
    assert path.exists()

    net2 = PolicyValueNetwork(input_dim=64, action_dim=134)
    trainer2 = AlphaZeroTrainer(
        network=net2, buffer=buf, lr=1e-3, checkpoint_dir=tmp_path
    )
    trainer2.load_checkpoint(path)
    for p1, p2 in zip(net.parameters(), net2.parameters()):
        assert torch.allclose(p1, p2)
