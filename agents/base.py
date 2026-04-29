from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from engine.state import (
    Phase, Decision, Recommendation, GameStateSnapshot, CrisisEvent
)

if TYPE_CHECKING:
    from scenarios.loader import Faction


class AgentInterface(ABC):
    is_human: bool = False

    def __init__(self):
        self.faction_id: str = ""
        self.faction_name: str = ""
        self._last_snapshot: Optional[GameStateSnapshot] = None

    def initialize(self, faction: "Faction") -> None:
        self.faction_id = faction.faction_id
        self.faction_name = faction.name

    def receive_state(self, snapshot: GameStateSnapshot) -> None:
        self._last_snapshot = snapshot

    def receive_event(self, event: CrisisEvent) -> None:
        pass

    @abstractmethod
    async def submit_decision(self, phase: Phase) -> Decision:
        ...

    async def get_recommendation(self, phase: Phase) -> Optional[Recommendation]:
        return None  # override in AI advisor
