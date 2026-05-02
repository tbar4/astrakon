from __future__ import annotations
from pathlib import Path
import torch
import torch.nn as nn
from torch import Tensor


class PolicyValueNetwork(nn.Module):
    """Shared-trunk policy + value network for AlphaZero self-play."""
    HIDDEN_DIM = 256

    def __init__(self, input_dim: int, action_dim: int):
        super().__init__()
        self.input_dim = input_dim
        self.action_dim = action_dim

        self.trunk = nn.Sequential(
            nn.Linear(input_dim, self.HIDDEN_DIM),
            nn.LayerNorm(self.HIDDEN_DIM),
            nn.ReLU(),
            nn.Linear(self.HIDDEN_DIM, self.HIDDEN_DIM),
            nn.LayerNorm(self.HIDDEN_DIM),
            nn.ReLU(),
            nn.Linear(self.HIDDEN_DIM, 128),
            nn.ReLU(),
        )
        self.policy_head = nn.Linear(128, action_dim)
        self.value_head = nn.Sequential(
            nn.Linear(128, 1),
            nn.Tanh(),
        )

    def forward(
        self, x: Tensor, legal_mask: Tensor | None = None
    ) -> tuple[Tensor, Tensor]:
        h = self.trunk(x)
        logits = self.policy_head(h)
        if legal_mask is not None:
            logits = logits.masked_fill(~legal_mask, -1e9)
        value = self.value_head(h)
        return logits, value

    def save_checkpoint(
        self,
        path: Path,
        normalization_constants: dict,
        scenario_name: str,
        step: int = 0,
    ) -> None:
        torch.save({
            "state_dict": self.state_dict(),
            "input_dim": self.input_dim,
            "action_dim": self.action_dim,
            "normalization_constants": normalization_constants,
            "scenario_name": scenario_name,
            "step": step,
        }, path)


def load_network(path: Path) -> PolicyValueNetwork:
    ckpt = torch.load(path, weights_only=False)
    net = PolicyValueNetwork(
        input_dim=ckpt["input_dim"],
        action_dim=ckpt["action_dim"],
    )
    net.load_state_dict(ckpt["state_dict"])
    net.eval()
    return net
