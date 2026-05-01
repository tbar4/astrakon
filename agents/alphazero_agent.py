from __future__ import annotations
from pathlib import Path
from typing import Optional
from agents.mcts_agent import ISMCTSAgent
from engine.state import Phase, Decision
from training.network import load_network, PolicyValueNetwork


class AlphaZeroAgent(ISMCTSAgent):
    """IS-MCTS agent guided by a trained PolicyValueNetwork.

    Inherits ISMCTSAgent's phase-caching (one search per turn; INVEST
    populates OPS and RESPONSE caches). Loads a checkpoint on first use
    and exposes the network for network-guided MCTS evaluation.
    """

    def __init__(self, checkpoint_path: Path, n_simulations: int = 800):
        super().__init__(n_simulations=n_simulations, rollout_policy="network")
        self.checkpoint_path = Path(checkpoint_path)
        self._network: Optional[PolicyValueNetwork] = None
        self._normalization_constants: dict = {}

    def _load_network(self) -> PolicyValueNetwork:
        if self._network is None:
            import torch
            self._network = load_network(self.checkpoint_path)
            ckpt = torch.load(self.checkpoint_path, weights_only=False)
            self._normalization_constants = ckpt.get("normalization_constants", {})
        return self._network

    def _run_search(self, phase: Phase) -> Decision:
        self._load_network()
        return super()._run_search(phase)
