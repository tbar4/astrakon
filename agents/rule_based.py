from __future__ import annotations
from typing import Optional
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, OperationalAction, ResponseDecision,
    GameStateSnapshot,
)


def _situation(snap: Optional[GameStateSnapshot]) -> tuple[float, float, float, int, str]:
    """(my_dom, threshold, dom_gap, turns_left, urgency)  — urgency: ahead/normal/urgent/critical."""
    if snap is None:
        return 0.0, 0.65, 0.65, 99, "normal"
    fs = snap.faction_state
    my_cid = fs.coalition_id
    my_dom = snap.coalition_dominance.get(my_cid, 0.0) if my_cid else 0.0
    threshold = snap.victory_threshold
    dom_gap = threshold - my_dom
    turns_left = max(0, snap.total_turns - snap.turn)
    if dom_gap > 0.15 and turns_left <= 3:
        urgency = "critical"
    elif dom_gap > 0.08 and turns_left <= 5:
        urgency = "urgent"
    elif dom_gap <= -0.05:
        urgency = "ahead"
    else:
        urgency = "normal"
    return my_dom, threshold, dom_gap, turns_left, urgency


class MahanianAgent(AgentInterface):
    """Balanced SDA/orbital doctrine — state-aware, shifts toward MEO/GEO when behind."""

    async def submit_decision(self, phase: Phase) -> Decision:
        snap = self._last_snapshot
        if phase == Phase.INVEST:
            return Decision(phase=phase, faction_id=self.faction_id, investment=self._invest(snap))
        if phase == Phase.OPERATIONS:
            return Decision(phase=phase, faction_id=self.faction_id, operations=[self._ops(snap)])
        return Decision(phase=phase, faction_id=self.faction_id, response=self._respond(snap))

    def _invest(self, snap: Optional[GameStateSnapshot]) -> InvestmentAllocation:
        _, _, _, _, urgency = _situation(snap)
        if urgency == "critical":
            return InvestmentAllocation(
                geo_deployment=0.30, cislunar_deployment=0.20, meo_deployment=0.20,
                launch_capacity=0.15, kinetic_weapons=0.15,
                rationale="CRITICAL deficit — maximum high-orbit investment to close dominance gap",
            )
        if urgency == "urgent":
            return InvestmentAllocation(
                geo_deployment=0.25, meo_deployment=0.25, cislunar_deployment=0.10,
                constellation=0.10, launch_capacity=0.10,
                r_and_d=0.10, covert=0.05, diplomacy=0.05,
                rationale="Behind threshold — pivoting to high-weight orbital tiers",
            )
        if urgency == "ahead":
            return InvestmentAllocation(
                r_and_d=0.20, constellation=0.15, meo_deployment=0.10, geo_deployment=0.05,
                launch_capacity=0.10, commercial=0.15, influence_ops=0.10,
                education=0.05, covert=0.05, diplomacy=0.05,
                rationale="Defending lead — consolidating position and hardening assets",
            )
        # Normal: balanced with MEO/GEO priority over LEO
        return InvestmentAllocation(
            r_and_d=0.15, meo_deployment=0.20, geo_deployment=0.15,
            constellation=0.10, launch_capacity=0.10,
            commercial=0.10, influence_ops=0.05, education=0.05,
            covert=0.05, diplomacy=0.05,
            rationale="Balanced Mahanian doctrine — MEO/GEO priority for weighted dominance",
        )

    def _ops(self, snap: Optional[GameStateSnapshot]) -> OperationalAction:
        if snap is None:
            return OperationalAction(
                action_type="task_assets",
                parameters={"mission": "sda_sweep"},
                rationale="Maintaining surveillance posture",
            )
        _, _, _, _, urgency = _situation(snap)
        fs = snap.faction_state
        adversaries = list(snap.adversary_estimates.keys())
        allies = list(snap.ally_states.keys())

        if urgency == "critical" and fs.assets.asat_kinetic > 0 and adversaries:
            return OperationalAction(
                action_type="task_assets",
                target_faction=adversaries[0],
                parameters={"mission": "intercept"},
                rationale="Critical deficit — kinetic intercept to disrupt adversary constellation",
            )
        # Coordinate on even turns when allies are present
        if allies and snap.turn % 2 == 0:
            return OperationalAction(
                action_type="coordinate",
                target_faction=allies[0],
                rationale="Coalition SDA coordination — pooling sensor networks for shared picture",
            )
        if adversaries:
            return OperationalAction(
                action_type="task_assets",
                target_faction=adversaries[0],
                parameters={"mission": "sda_sweep"},
                rationale="Intelligence sweep on adversary orbital assets",
            )
        return OperationalAction(
            action_type="task_assets",
            parameters={"mission": "sda_sweep"},
            rationale="Maintaining domain awareness",
        )

    def _respond(self, snap: Optional[GameStateSnapshot]) -> ResponseDecision:
        if snap is None:
            return ResponseDecision(
                escalate=False,
                public_statement="Monitoring the situation carefully.",
                rationale="De-escalate by default — preserve optionality.",
            )
        _, _, _, _, urgency = _situation(snap)
        fs = snap.faction_state
        adversaries = list(snap.adversary_estimates.keys())

        if snap.incoming_threats:
            target = adversaries[0] if adversaries and fs.assets.asat_deniable > 0 else None
            return ResponseDecision(
                escalate=True,
                retaliate=bool(target),
                target_faction=target,
                public_statement="Hostile orbital approach detected. Activating deterrence posture.",
                rationale="Incoming kinetic threat — escalating to deter further aggression",
            )
        if urgency == "critical":
            return ResponseDecision(
                escalate=True,
                public_statement="Asserting orbital rights. Escalation is necessary to close the gap.",
                rationale="Critical deficit — escalating to force adversary coalition adjustment",
            )
        if urgency == "urgent" and snap.tension_level < 0.7:
            return ResponseDecision(
                escalate=True,
                public_statement="Defending sovereign orbital interests.",
                rationale="Behind threshold with time to act — measured escalation to shift momentum",
            )
        return ResponseDecision(
            escalate=False,
            public_statement="Maintaining stability and sovereign orbital access.",
            rationale="Preserving coalition cohesion and strategic patience",
        )


class GrayZoneAgent(AgentInterface):
    """Deniable ops doctrine — disrupts adversary through co-orbital approaches and EW."""

    async def submit_decision(self, phase: Phase) -> Decision:
        snap = self._last_snapshot
        if phase == Phase.INVEST:
            return Decision(phase=phase, faction_id=self.faction_id, investment=self._invest(snap))
        if phase == Phase.OPERATIONS:
            return Decision(phase=phase, faction_id=self.faction_id, operations=[self._ops(snap)])
        return Decision(phase=phase, faction_id=self.faction_id, response=self._respond(snap))

    def _invest(self, snap: Optional[GameStateSnapshot]) -> InvestmentAllocation:
        _, _, _, _, urgency = _situation(snap)
        if urgency == "critical":
            return InvestmentAllocation(
                covert=0.25, geo_deployment=0.25, meo_deployment=0.20,
                influence_ops=0.15, launch_capacity=0.15,
                rationale="Critical deficit — covert disruption surge plus high-orbit investment",
            )
        if urgency == "ahead":
            return InvestmentAllocation(
                r_and_d=0.15, meo_deployment=0.20, geo_deployment=0.10,
                covert=0.15, influence_ops=0.15,
                commercial=0.10, constellation=0.10, diplomacy=0.05,
                rationale="Consolidating advantage with sustained disruption capability",
            )
        return InvestmentAllocation(
            covert=0.20, constellation=0.10, meo_deployment=0.20,
            geo_deployment=0.15, influence_ops=0.10,
            launch_capacity=0.10, r_and_d=0.10, diplomacy=0.05,
            rationale="Gray zone doctrine — deniable capability paired with orbital mass",
        )

    def _ops(self, snap: Optional[GameStateSnapshot]) -> OperationalAction:
        if snap is None:
            return OperationalAction(
                action_type="task_assets",
                parameters={"mission": "sda_sweep"},
                rationale="Maintaining baseline awareness",
            )
        fs = snap.faction_state
        adversaries = list(snap.adversary_estimates.keys())
        allies = list(snap.ally_states.keys())
        _, _, _, _, urgency = _situation(snap)

        if adversaries and fs.assets.asat_deniable > 0 and urgency in ("urgent", "critical"):
            return OperationalAction(
                action_type="gray_zone",
                target_faction=adversaries[0],
                rationale="Co-orbital deniable approach — disrupting adversary constellation",
            )
        if adversaries and fs.assets.ew_jammers > 0:
            return OperationalAction(
                action_type="gray_zone",
                target_faction=adversaries[0],
                rationale="EW jamming to degrade adversary SDA and command links",
            )
        if allies and snap.turn % 3 != 0:
            return OperationalAction(
                action_type="coordinate",
                target_faction=allies[0],
                rationale="Coalition intelligence sharing for attribution clarity",
            )
        return OperationalAction(
            action_type="task_assets",
            target_faction=adversaries[0] if adversaries else None,
            parameters={"mission": "sda_sweep"},
            rationale="Intelligence sweep — maintaining situational awareness",
        )

    def _respond(self, snap: Optional[GameStateSnapshot]) -> ResponseDecision:
        if snap is None:
            return ResponseDecision(
                escalate=False,
                rationale="Maintaining strategic ambiguity",
            )
        _, _, _, _, urgency = _situation(snap)
        fs = snap.faction_state
        adversaries = list(snap.adversary_estimates.keys())

        if snap.incoming_threats and adversaries and fs.assets.asat_deniable > 0:
            # Deny publicly, retaliate deniably next ops phase
            return ResponseDecision(
                escalate=False,
                public_statement="We categorically deny any hostile intent in orbital space.",
                rationale="Incoming threat detected — deny publicly, deniable assets available for next turn",
            )
        if urgency == "critical" and adversaries:
            return ResponseDecision(
                escalate=True,
                retaliate=bool(fs.assets.asat_deniable > 0),
                target_faction=adversaries[0] if fs.assets.asat_deniable > 0 else None,
                public_statement="We are compelled to protect our orbital infrastructure.",
                rationale="Critical deficit — escalating with deniable retaliation to disrupt adversary",
            )
        return ResponseDecision(
            escalate=False,
            public_statement="We remain committed to peaceful and responsible space operations.",
            rationale="Maintaining strategic ambiguity — gray zone doctrine",
        )


class RogueAccelerationistAgent(AgentInterface):
    """Kinetic-first doctrine — maximizes ASAT stockpile and escalates deliberately."""

    async def submit_decision(self, phase: Phase) -> Decision:
        snap = self._last_snapshot
        if phase == Phase.INVEST:
            return Decision(phase=phase, faction_id=self.faction_id, investment=self._invest(snap))
        if phase == Phase.OPERATIONS:
            return Decision(phase=phase, faction_id=self.faction_id, operations=[self._ops(snap)])
        return Decision(phase=phase, faction_id=self.faction_id, response=self._respond(snap))

    def _invest(self, snap: Optional[GameStateSnapshot]) -> InvestmentAllocation:
        _, _, _, _, urgency = _situation(snap)
        if urgency == "critical":
            return InvestmentAllocation(
                kinetic_weapons=0.40, meo_deployment=0.25, geo_deployment=0.20,
                launch_capacity=0.15,
                rationale="Maximum armament — kinetic strike capacity for terminal defense of position",
            )
        return InvestmentAllocation(
            kinetic_weapons=0.25, covert=0.10, meo_deployment=0.20,
            geo_deployment=0.15, launch_capacity=0.15, constellation=0.15,
            rationale="Kinetic superiority doctrine — ASAT stockpile alongside orbital expansion",
        )

    def _ops(self, snap: Optional[GameStateSnapshot]) -> OperationalAction:
        if snap is None:
            return OperationalAction(
                action_type="task_assets",
                parameters={"mission": "patrol"},
                rationale="Show of force — projecting orbital presence",
            )
        fs = snap.faction_state
        adversaries = list(snap.adversary_estimates.keys())

        # Rogue doctrine: strike when holding > 1 ASAT to preserve deterrent
        if adversaries and fs.assets.asat_kinetic > 1:
            return OperationalAction(
                action_type="task_assets",
                target_faction=adversaries[0],
                parameters={"mission": "intercept"},
                rationale="Kinetic strike — attriting adversary constellation for dominance shift",
            )
        if adversaries and fs.assets.asat_deniable > 0:
            return OperationalAction(
                action_type="gray_zone",
                target_faction=adversaries[0],
                rationale="Deniable disruption — preserving escalation ambiguity while attriting",
            )
        return OperationalAction(
            action_type="task_assets",
            target_faction=adversaries[0] if adversaries else None,
            parameters={"mission": "patrol"},
            rationale="Patrol — projecting resolve and deterring adversary expansion",
        )

    def _respond(self, snap: Optional[GameStateSnapshot]) -> ResponseDecision:
        if snap is None:
            return ResponseDecision(
                escalate=True,
                rationale="Rogue doctrine — default escalation to create strategic pressure",
            )
        fs = snap.faction_state
        adversaries = list(snap.adversary_estimates.keys())
        has_asats = fs.assets.asat_kinetic > 0 or fs.assets.asat_deniable > 0

        if adversaries and has_asats:
            return ResponseDecision(
                escalate=True,
                retaliate=True,
                target_faction=adversaries[0],
                public_statement="Any provocation will be met with decisive and overwhelming force.",
                rationale="Rogue doctrine — maximum escalation, force adversary compliance or capitulation",
            )
        return ResponseDecision(
            escalate=True,
            public_statement="We claim sovereign rights over strategic orbital regimes.",
            rationale="Escalation as strategy — raising the cost of competition for all parties",
        )


class CommercialBrokerAgent(AgentInterface):
    """Commercial-first doctrine — market share and satellite services over military posture."""

    async def submit_decision(self, phase: Phase) -> Decision:
        snap = self._last_snapshot
        if phase == Phase.INVEST:
            return Decision(phase=phase, faction_id=self.faction_id, investment=self._invest(snap))
        if phase == Phase.OPERATIONS:
            return Decision(phase=phase, faction_id=self.faction_id, operations=[self._ops(snap)])
        return Decision(phase=phase, faction_id=self.faction_id, response=self._respond(snap))

    def _invest(self, snap: Optional[GameStateSnapshot]) -> InvestmentAllocation:
        _, _, _, _, urgency = _situation(snap)
        if urgency == "critical":
            return InvestmentAllocation(
                constellation=0.25, meo_deployment=0.20, commercial=0.15,
                geo_deployment=0.15, launch_capacity=0.15, r_and_d=0.10,
                rationale="Crisis pivot — maintaining commercial resilience while building orbital mass",
            )
        if urgency == "ahead":
            return InvestmentAllocation(
                commercial=0.25, constellation=0.15, meo_deployment=0.15,
                r_and_d=0.15, education=0.10, launch_capacity=0.10, diplomacy=0.10,
                rationale="Market leadership — expanding commercial presence and strategic depth",
            )
        return InvestmentAllocation(
            commercial=0.25, constellation=0.20, launch_capacity=0.15,
            r_and_d=0.15, meo_deployment=0.10, education=0.10, diplomacy=0.05,
            rationale="Commercial broker doctrine — market share via constellation density and launch capacity",
        )

    def _ops(self, snap: Optional[GameStateSnapshot]) -> OperationalAction:
        if snap is None:
            return OperationalAction(action_type="task_assets", parameters={"mission": "sda_sweep"},
                                     rationale="Baseline market surveillance")
        allies = list(snap.ally_states.keys())
        adversaries = list(snap.adversary_estimates.keys())
        if allies:
            return OperationalAction(action_type="coordinate", target_faction=allies[0],
                                     rationale="Coalition commercial integration — pooling launch capacity and market access")
        if adversaries:
            return OperationalAction(action_type="task_assets", target_faction=adversaries[0],
                                     parameters={"mission": "sda_sweep"},
                                     rationale="Market intelligence sweep — tracking adversary constellation growth")
        return OperationalAction(action_type="task_assets", parameters={"mission": "sda_sweep"},
                                 rationale="Maintaining commercial domain awareness")

    def _respond(self, snap: Optional[GameStateSnapshot]) -> ResponseDecision:
        if snap is None:
            return ResponseDecision(escalate=False,
                                    public_statement="Committed to commercial space operations and international cooperation.",
                                    rationale="De-escalate — protect commercial assets and market reputation")
        _, _, _, _, urgency = _situation(snap)
        if snap.incoming_threats:
            return ResponseDecision(escalate=False,
                                    public_statement="We call on all parties to respect commercial satellite infrastructure.",
                                    rationale="Under threat — appeal to international norms, protect commercial reputation")
        if urgency == "critical":
            return ResponseDecision(escalate=True,
                                    public_statement="Protecting critical commercial space infrastructure.",
                                    rationale="Critical deficit — minimal escalation to signal resolve")
        return ResponseDecision(escalate=False,
                                public_statement="Advancing peaceful commercial use of orbital space.",
                                rationale="Commercial broker doctrine — de-escalation protects market access")


class ParameterizedRuleAgent(AgentInterface):
    """Rule-based agent with custom investment weights. OPS/RESPONSE delegate to a base archetype."""

    def __init__(self, base_archetype: str = "mahanian", invest_weights: dict | None = None):
        super().__init__()
        self._base_archetype = base_archetype
        self._invest_weights: dict = invest_weights or {}
        self._base: AgentInterface | None = None

    def initialize(self, faction) -> None:
        super().initialize(faction)
        self._base = _rule_agent_for_archetype(self._base_archetype)
        self._base.initialize(faction)

    def receive_state(self, snapshot: GameStateSnapshot) -> None:
        super().receive_state(snapshot)
        if self._base:
            self._base.receive_state(snapshot)

    async def submit_decision(self, phase: Phase) -> Decision:
        snap = self._last_snapshot
        if phase == Phase.INVEST and self._invest_weights:
            _, _, _, _, urgency = _situation(snap)
            weights = self._invest_weights.get(urgency) or self._invest_weights.get("normal") or {}
            if weights:
                try:
                    return Decision(
                        phase=phase, faction_id=self.faction_id,
                        investment=InvestmentAllocation(
                            **{k: float(v) for k, v in weights.items() if k != "rationale"},
                            rationale=weights.get("rationale", "Custom investment profile"),
                        )
                    )
                except Exception:
                    pass
        if self._base:
            return await self._base.submit_decision(phase)
        fallback = MahanianAgent()
        fallback.faction_id = self.faction_id
        if snap:
            fallback.receive_state(snap)
        return await fallback.submit_decision(phase)


# Legacy name kept for backwards compatibility with tests and any external imports
MaxConstellationAgent = RogueAccelerationistAgent
