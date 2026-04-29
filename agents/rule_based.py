from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, OperationalAction, ResponseDecision
)


class MahanianAgent(AgentInterface):
    """Prioritizes SDA and constellation balance — sea control doctrine."""

    async def submit_decision(self, phase: Phase) -> Decision:
        if phase == Phase.INVEST:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                investment=InvestmentAllocation(
                    r_and_d=0.20, constellation=0.30,
                    launch_capacity=0.10, commercial=0.10,
                    influence_ops=0.05, education=0.10,
                    covert=0.05, diplomacy=0.10,
                    rationale="Mahanian balance: SDA, constellation, and diplomatic positioning."
                )
            )
        if phase == Phase.OPERATIONS:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                operations=[OperationalAction(
                    action_type="task_assets",
                    parameters={"mission": "sda_sweep"},
                    rationale="Prioritize intelligence advantage this turn."
                )]
            )
        return Decision(
            phase=phase, faction_id=self.faction_id,
            response=ResponseDecision(
                escalate=False, retaliate=False,
                public_statement="We are monitoring the situation carefully.",
                rationale="De-escalate by default; preserve optionality."
            )
        )


class MaxConstellationAgent(AgentInterface):
    """Dumps everything into constellation nodes — aggressive expansion."""

    async def submit_decision(self, phase: Phase) -> Decision:
        if phase == Phase.INVEST:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                investment=InvestmentAllocation(
                    constellation=0.80, launch_capacity=0.20,
                    rationale="Maximum constellation expansion. Nodes are power."
                )
            )
        if phase == Phase.OPERATIONS:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                operations=[OperationalAction(
                    action_type="task_assets",
                    parameters={"mission": "constellation_expansion"},
                    rationale="Deploy newly built nodes."
                )]
            )
        return Decision(
            phase=phase, faction_id=self.faction_id,
            response=ResponseDecision(
                escalate=False, rationale="Ignore events; keep expanding."
            )
        )
