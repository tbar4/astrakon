from __future__ import annotations
from pathlib import Path
from typing import Optional
from agents.base import AgentInterface
from engine.state import Phase, Decision, Recommendation, GameStateSnapshot


class ISMCTSAgent(AgentInterface):
    """IS-MCTS agent using OpenSpiel's ISMCTSBot.

    Runs one search per turn during INVEST phase, caching the OPS and RESPONSE
    actions from the highest-value simulation paths. Subsequent phase calls
    return the cached values without running a second search.
    """

    def __init__(self, n_simulations: int = 800, rollout_policy: str = "rule_based"):
        super().__init__()
        self.n_simulations = n_simulations
        self.rollout_policy = rollout_policy
        self._cached_ops_action: Optional[int] = None
        self._cached_response_action: Optional[int] = None
        self._scenario_path: Optional[str] = None

    def initialize(self, faction) -> None:
        super().initialize(faction)
        self._archetype = getattr(faction, "archetype", "mahanian")

    def receive_state(self, snapshot: GameStateSnapshot) -> None:
        super().receive_state(snapshot)
        self._cached_ops_action = None
        self._cached_response_action = None

    async def submit_decision(self, phase: Phase) -> Decision:
        raise NotImplementedError("Implemented in Task 3")

    async def get_recommendation(self, phase: Phase) -> Optional[Recommendation]:
        return None  # Implemented in Task 4
