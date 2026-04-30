from engine.state import Phase, Decision, GameStateSnapshot
from agents.base import AgentInterface


class HumanInputRequired(Exception):
    def __init__(self, phase: Phase, snapshot: GameStateSnapshot):
        self.phase = phase
        self.snapshot = snapshot


class WebAgent(AgentInterface):
    is_human: bool = True

    async def submit_decision(self, phase: Phase) -> Decision:
        raise HumanInputRequired(phase, self._last_snapshot)
