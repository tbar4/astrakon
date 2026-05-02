import pytest
import torch
from pathlib import Path
from training.network import PolicyValueNetwork, load_network


def make_network(input_dim: int = 64, action_dim: int = 134) -> PolicyValueNetwork:
    return PolicyValueNetwork(input_dim=input_dim, action_dim=action_dim)


def test_forward_output_shapes_batch_1():
    net = make_network()
    x = torch.randn(1, 64)
    logits, value = net(x)
    assert logits.shape == (1, 134)
    assert value.shape == (1, 1)


def test_forward_output_shapes_batch_32():
    net = make_network()
    x = torch.randn(32, 64)
    logits, value = net(x)
    assert logits.shape == (32, 134)
    assert value.shape == (32, 1)


def test_value_in_range():
    net = make_network()
    x = torch.randn(16, 64)
    _, value = net(x)
    assert (value >= -1.0).all() and (value <= 1.0).all()


def test_illegal_action_masking():
    net = make_network()
    x = torch.randn(1, 64)
    legal_mask = torch.ones(134, dtype=torch.bool)
    legal_mask[5:50] = False  # mark actions 5-49 as illegal
    logits, _ = net(x, legal_mask=legal_mask.unsqueeze(0))
    assert (logits[0, 5:50] <= -1e7).all()


def test_checkpoint_roundtrip(tmp_path: Path):
    net = make_network(input_dim=64, action_dim=134)
    ckpt_path = tmp_path / "test.pt"
    net.save_checkpoint(ckpt_path, normalization_constants={"max_leo": 100}, scenario_name="test")
    net2 = load_network(ckpt_path)
    for p1, p2 in zip(net.parameters(), net2.parameters()):
        assert torch.allclose(p1, p2)


def test_normalization_constants_saved(tmp_path: Path):
    net = make_network()
    norm = {"max_leo": 100, "max_meo": 40}
    path = tmp_path / "net.pt"
    net.save_checkpoint(path, normalization_constants=norm, scenario_name="pacific_crossroads")
    ckpt = torch.load(path, weights_only=False)
    assert ckpt["normalization_constants"] == norm
    assert ckpt["scenario_name"] == "pacific_crossroads"
