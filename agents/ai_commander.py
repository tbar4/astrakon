import asyncio
import io
from typing import Optional
import anthropic
from ruamel.yaml import YAML
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, OperationalAction, ResponseDecision,
    GameStateSnapshot, Recommendation
)


INVEST_TOOL = {
    "name": "allocate_budget",
    "description": (
        "Allocate this turn's budget across investment categories. Values must sum to <= 1.0. "
        "Orbital deployment costs and dominance weights: "
        "LEO (constellation) = 5 pts/node, 1× weight; "
        "MEO (meo_deployment) = 12 pts/node, 2× weight (GPS/navigation regime); "
        "GEO (geo_deployment) = 25 pts/node, 3× weight (persistent strategic); "
        "Cislunar (cislunar_deployment) = 40 pts/node, 4× weight (strategic high ground)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "r_and_d":             {"type": "number", "description": "R&D investment fraction (0.0–1.0)"},
            "constellation":       {"type": "number", "description": "LEO node deployment fraction (5 pts/node, 1× weight)"},
            "meo_deployment":      {"type": "number", "description": "MEO node deployment fraction (12 pts/node, 2× dominance weight)"},
            "geo_deployment":      {"type": "number", "description": "GEO node deployment fraction (25 pts/node, 3× dominance weight)"},
            "cislunar_deployment": {"type": "number", "description": "Cislunar node deployment fraction (40 pts/node, 4× dominance weight)"},
            "launch_capacity":     {"type": "number", "description": "Launch capacity investment fraction"},
            "commercial":          {"type": "number", "description": "Commercial partnerships fraction"},
            "influence_ops":       {"type": "number", "description": "Influence operations fraction (EW jammers)"},
            "education":           {"type": "number", "description": "Education/workforce fraction"},
            "covert":              {"type": "number", "description": "Covert programs fraction (deniable ASAT)"},
            "diplomacy":           {"type": "number", "description": "Diplomacy fraction"},
            "rationale":           {"type": "string", "description": "Strategic rationale for this allocation"},
        },
        "required": ["rationale"],
    },
}

OPS_TOOL = {
    "name": "submit_operations",
    "description": "Submit operational orders for this turn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action_type": {
                "type": "string",
                "enum": ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"],
            },
            "target_faction": {"type": "string"},
            "parameters":     {"type": "object"},
            "rationale":      {"type": "string"},
        },
        "required": ["action_type", "rationale"],
    },
}

RESPONSE_TOOL = {
    "name": "submit_response",
    "description": "Submit response to crisis events.",
    "input_schema": {
        "type": "object",
        "properties": {
            "escalate":         {"type": "boolean"},
            "retaliate":        {"type": "boolean"},
            "target_faction":   {"type": "string"},
            "public_statement": {"type": "string"},
            "rationale":        {"type": "string"},
        },
        "required": ["escalate", "rationale"],
    },
}

PHASE_TOOLS = {
    Phase.INVEST:     [INVEST_TOOL],
    Phase.OPERATIONS: [OPS_TOOL],
    Phase.RESPONSE:   [RESPONSE_TOOL],
}


def _build_system_prompt(persona: dict) -> str:
    return f"""You are an AI strategic commander in a space wargame.

FACTION: {persona.get('name', 'Unknown')}
DOCTRINE: {persona.get('doctrine_narrative', '')}
DECISION STYLE: {persona.get('decision_style', 'balanced')}
ESCALATION TOLERANCE: {persona.get('escalation_tolerance', 0.5)}
COALITION LOYALTY: {persona.get('coalition_loyalty', 0.5)}

PERSONA CONTEXT:
{persona.get('system_prompt_context', '')}

You must always use the provided tool to submit your decision. Include a detailed rationale that reflects your doctrine and strategic personality. Be specific about why you are making this choice given the current board state."""


def _parse_snapshot_to_user_message(snapshot: GameStateSnapshot, phase: Phase) -> str:
    fs = snapshot.faction_state
    assets = fs.assets
    lines = [
        f"TURN {snapshot.turn} — PHASE: {phase.value.upper()}",
        f"BUDGET: {fs.current_budget} points",
        f"BOARD TENSION: {snapshot.tension_level:.0%} | DEBRIS FIELD: {snapshot.debris_level:.0%} | "
        f"JOINT FORCE EFFECTIVENESS: {snapshot.joint_force_effectiveness:.0%}",
        "",
        "YOUR ASSETS:",
        f"  LEO nodes: {assets.leo_nodes} (1×) | MEO: {assets.meo_nodes} (2×) | "
        f"GEO: {assets.geo_nodes} (3×) | Cislunar: {assets.cislunar_nodes} (4×)",
        f"  ASAT kinetic: {assets.asat_kinetic} | Deniable ASAT: {assets.asat_deniable}",
        f"  EW jammers: {assets.ew_jammers} | SDA sensors: {assets.sda_sensors}",
        f"  Launch capacity: {assets.launch_capacity}",
        f"  Deterrence: {fs.deterrence_score:.0f} | Disruption: {fs.disruption_score:.0f} | "
        f"Market share: {fs.market_share:.1%}",
        "",
        "ADVERSARY ESTIMATES (SDA-filtered):",
    ]
    for fid, est in snapshot.adversary_estimates.items():
        lines.append(
            f"  {fid}: LEO={est.get('leo_nodes', 0)} MEO={est.get('meo_nodes', 0)} "
            f"GEO={est.get('geo_nodes', 0)} Cislunar={est.get('cislunar_nodes', 0)} "
            f"ASAT-K={est.get('asat_kinetic', 0)}"
        )
    if snapshot.incoming_threats:
        lines.append("")
        lines.append("INCOMING THREATS DETECTED:")
        for threat in snapshot.incoming_threats:
            lines.append(
                f"  ⚠ KINETIC APPROACH from {threat['attacker']} "
                f"(declared turn {threat['declared_turn']}) — impact imminent"
            )
    lines.append("")
    lines.append("AVAILABLE ACTIONS: " + ", ".join(snapshot.available_actions))
    if phase == Phase.OPERATIONS:
        lines.append(
            "  task_assets intercept: set parameters={'mission':'intercept'} to dispatch a "
            "kinetic interceptor (arrives next turn, visible to adversary SDA ≥ 30%)"
        )
    if snapshot.turn_log_summary:
        lines += ["", "LAST TURN EVENTS:", snapshot.turn_log_summary]
    return "\n".join(lines)


class AICommanderAgent(AgentInterface):
    def __init__(self, persona_yaml: str, model: str = "claude-sonnet-4-6"):
        super().__init__()
        yaml = YAML()
        self._persona: dict = yaml.load(io.StringIO(persona_yaml)).get("persona", {})
        self._model = model
        self._client = anthropic.Anthropic()
        self._system_prompt = _build_system_prompt(self._persona)
        self._token_totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
        }

    @property
    def token_totals(self) -> dict:
        return dict(self._token_totals)

    def _build_decision(self, phase: Phase, inp: dict) -> Decision:
        if phase == Phase.INVEST:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                investment=InvestmentAllocation(
                    r_and_d=inp.get("r_and_d", 0),
                    constellation=inp.get("constellation", 0),
                    meo_deployment=inp.get("meo_deployment", 0),
                    geo_deployment=inp.get("geo_deployment", 0),
                    cislunar_deployment=inp.get("cislunar_deployment", 0),
                    launch_capacity=inp.get("launch_capacity", 0),
                    commercial=inp.get("commercial", 0),
                    influence_ops=inp.get("influence_ops", 0),
                    education=inp.get("education", 0),
                    covert=inp.get("covert", 0),
                    diplomacy=inp.get("diplomacy", 0),
                    rationale=inp.get("rationale", ""),
                )
            )
        if phase == Phase.OPERATIONS:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                operations=[OperationalAction(
                    action_type=inp.get("action_type", "task_assets"),
                    target_faction=inp.get("target_faction"),
                    parameters=inp.get("parameters", {}),
                    rationale=inp.get("rationale", ""),
                )]
            )
        return Decision(
            phase=phase, faction_id=self.faction_id,
            response=ResponseDecision(
                escalate=inp.get("escalate", False),
                retaliate=inp.get("retaliate", False),
                target_faction=inp.get("target_faction"),
                public_statement=inp.get("public_statement", ""),
                rationale=inp.get("rationale", ""),
            )
        )

    async def _call_claude(self, user_message: str, phase: Phase):
        response = await asyncio.to_thread(
            self._client.messages.create,
            model=self._model,
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": self._system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_message}],
            tools=PHASE_TOOLS[phase],
            tool_choice={"type": "any"},
        )
        u = response.usage
        self._token_totals["input_tokens"] += u.input_tokens
        self._token_totals["output_tokens"] += u.output_tokens
        self._token_totals["cache_read_tokens"] += getattr(u, "cache_read_input_tokens", 0) or 0
        self._token_totals["cache_creation_tokens"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        return response

    async def submit_decision(self, phase: Phase) -> Decision:
        if self._last_snapshot is None:
            from agents.rule_based import MahanianAgent
            fallback = MahanianAgent()
            fallback.faction_id = self.faction_id
            return await fallback.submit_decision(phase)

        user_message = _parse_snapshot_to_user_message(self._last_snapshot, phase)
        response = await self._call_claude(user_message, phase)

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            from agents.rule_based import MahanianAgent
            fallback = MahanianAgent()
            fallback.faction_id = self.faction_id
            return await fallback.submit_decision(phase)

        return self._build_decision(phase, tool_use.input)

    async def get_recommendation(self, phase: Phase) -> Optional[Recommendation]:
        if self._last_snapshot is None:
            return None
        try:
            advisory_message = (
                "ADVISORY MODE: A human commander is requesting your strategic recommendation.\n"
                "Analyze the situation and provide your recommended decision with a clear rationale.\n\n"
            ) + _parse_snapshot_to_user_message(self._last_snapshot, phase)

            response = await self._call_claude(advisory_message, phase)
            tool_use = next((b for b in response.content if b.type == "tool_use"), None)
            if not tool_use:
                return None

            inp = tool_use.input
            decision = self._build_decision(phase, inp)
            return Recommendation(
                phase=phase,
                options=[],
                top_recommendation=decision,
                strategic_rationale=inp.get("rationale", ""),
            )
        except Exception:
            return None
