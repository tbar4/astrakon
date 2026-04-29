# agents/human.py
from typing import Optional
from rich.prompt import Confirm
from agents.base import AgentInterface
from engine.state import Phase, Decision
from tui.phases import display_situation, display_recommendation, collect_operations, collect_response
from tui.invest import collect_investment


class HumanAgent(AgentInterface):
    is_human: bool = True

    def __init__(self, advisor: Optional[AgentInterface] = None):
        super().__init__()
        self._advisor = advisor

    async def submit_decision(self, phase: Phase) -> Decision:
        # Guard: receive_state should always be called first, but fall back if not
        if self._last_snapshot is None:
            from agents.rule_based import MahanianAgent
            fallback = MahanianAgent()
            fallback.faction_id = self.faction_id
            return await fallback.submit_decision(phase)

        display_situation(self._last_snapshot)

        if self._advisor:
            rec = await self._advisor.get_recommendation(phase)
            if rec:
                display_recommendation(rec, phase)
                if Confirm.ask("Accept advisor recommendation?", default=False):
                    return rec.top_recommendation

        if phase == Phase.INVEST:
            alloc = collect_investment(
                budget=self._last_snapshot.faction_state.current_budget,
                snapshot=self._last_snapshot,
            )
            return Decision(phase=phase, faction_id=self.faction_id, investment=alloc)

        if phase == Phase.OPERATIONS:
            ops = collect_operations(self._last_snapshot)
            return Decision(phase=phase, faction_id=self.faction_id, operations=ops)

        resp = collect_response(self._last_snapshot)
        return Decision(phase=phase, faction_id=self.faction_id, response=resp)
