from __future__ import annotations
import torch
import torch.nn.functional as F
from pathlib import Path
from training.network import PolicyValueNetwork, load_network
from training.replay_buffer import ReplayBuffer

MIN_BUFFER_SIZE = 10_000


class AlphaZeroTrainer:
    def __init__(
        self,
        network: PolicyValueNetwork,
        buffer: ReplayBuffer,
        lr: float = 1e-3,
        checkpoint_dir: Path = Path("training/checkpoints"),
        normalization_constants: dict | None = None,
    ):
        self.network = network
        self.buffer = buffer
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._optimizer = torch.optim.Adam(network.parameters(), lr=lr)
        self._normalization_constants = normalization_constants or {}
        self._scenario_name = "unknown"
        self._step = 0

    def train_step(self, batch_size: int = 512) -> dict[str, float]:
        if len(self.buffer) < MIN_BUFFER_SIZE:
            raise RuntimeError(
                f"Buffer has {len(self.buffer)} examples; need {MIN_BUFFER_SIZE:,} to start training"
            )
        states, mcts_policies, game_returns = self.buffer.sample(batch_size)
        self.network.train()
        logits, values = self.network(states)
        policy_loss = -(mcts_policies * F.log_softmax(logits, dim=-1)).sum(dim=-1).mean()
        value_loss = F.mse_loss(values.squeeze(-1), game_returns)
        total_loss = policy_loss + value_loss
        self._optimizer.zero_grad()
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.network.parameters(), max_norm=1.0)
        self._optimizer.step()
        self._step += 1
        return {
            "policy_loss": float(policy_loss),
            "value_loss": float(value_loss),
            "total_loss": float(total_loss),
        }

    def save_checkpoint(self, step: int | None = None) -> Path:
        if step is None:
            step = self._step
        path = self.checkpoint_dir / f"{self._scenario_name}_step_{step:07d}.pt"
        self.network.save_checkpoint(
            path,
            normalization_constants=self._normalization_constants,
            scenario_name=self._scenario_name,
            step=step,
        )
        return path

    def load_checkpoint(self, path: Path) -> None:
        ckpt = torch.load(path, weights_only=False)
        self.network.load_state_dict(ckpt["state_dict"])
        self._step = ckpt.get("step", 0)
        self._normalization_constants = ckpt.get("normalization_constants", {})
        self._scenario_name = ckpt.get("scenario_name", "unknown")
