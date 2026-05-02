from __future__ import annotations
from collections import deque
import random
import torch
from torch import Tensor


class ReplayBuffer:
    def __init__(self, max_size: int = 500_000):
        self._buffer: deque = deque(maxlen=max_size)

    def add(self, examples: list) -> None:
        self._buffer.extend(examples)

    def sample(self, batch_size: int) -> tuple[Tensor, Tensor, Tensor]:
        if len(self._buffer) < batch_size:
            raise ValueError(
                f"Buffer has {len(self._buffer)} examples, need {batch_size} to sample"
            )
        batch = random.sample(list(self._buffer), batch_size)
        states = torch.stack([e.info_state for e in batch])
        policies = torch.stack([e.mcts_policy for e in batch])
        values = torch.tensor([e.game_return for e in batch], dtype=torch.float32)
        return states, policies, values

    def __len__(self) -> int:
        return len(self._buffer)
