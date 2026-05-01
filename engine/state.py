from enum import Enum
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field, model_validator


class Phase(str, Enum):
    INVEST = "invest"
    OPERATIONS = "operations"
    RESPONSE = "response"


ESCALATION_RUNG_NAMES: dict[int, str] = {
    0: "Peacetime Competition",
    1: "Contested — EW/Jamming Active",
    2: "Degraded — Reversible Interference",
    3: "Threshold — Co-orbital Approaches Declared",
    4: "Kinetic — Debris-Creating Strikes",
    5: "Escalatory — Cross-Domain Retaliation",
}


class FactionAssets(BaseModel):
    leo_nodes: int = 0
    meo_nodes: int = 0
    geo_nodes: int = 0
    cislunar_nodes: int = 0
    asat_kinetic: int = 0
    asat_deniable: int = 0
    ew_jammers: int = 0
    sda_sensors: int = 0
    relay_nodes: int = 0
    launch_capacity: int = 1

    def total_orbital_nodes(self) -> int:
        return self.leo_nodes + self.meo_nodes + self.geo_nodes + self.cislunar_nodes

    def weighted_orbital_nodes(self) -> float:
        """Strategic value weight: cislunar=4×, GEO=3×, MEO=2×, LEO=1×."""
        return (
            self.leo_nodes * 1.0 +
            self.meo_nodes * 2.0 +
            self.geo_nodes * 3.0 +
            self.cislunar_nodes * 4.0
        )


class InvestmentAllocation(BaseModel):
    r_and_d: float = 0.0
    constellation: float = 0.0        # LEO node deployment (5 pts/node)
    meo_deployment: float = 0.0       # MEO node deployment (12 pts/node, 2× dominance weight)
    geo_deployment: float = 0.0       # GEO node deployment (25 pts/node, 3× dominance weight)
    cislunar_deployment: float = 0.0  # Cislunar node deployment (40 pts/node, 4× dominance weight)
    launch_capacity: float = 0.0
    commercial: float = 0.0
    influence_ops: float = 0.0
    education: float = 0.0
    covert: float = 0.0
    diplomacy: float = 0.0
    kinetic_weapons: float = 0.0  # direct-ascent ASAT interceptors (40 pts each, triggers escalation)
    rationale: str = ""

    def total(self) -> float:
        return (
            self.r_and_d + self.constellation + self.meo_deployment +
            self.geo_deployment + self.cislunar_deployment +
            self.launch_capacity + self.commercial + self.influence_ops +
            self.education + self.covert + self.diplomacy + self.kinetic_weapons
        )

    @model_validator(mode="after")
    def validate_budget(self) -> "InvestmentAllocation":
        fields = [
            self.r_and_d, self.constellation, self.meo_deployment,
            self.geo_deployment, self.cislunar_deployment,
            self.launch_capacity, self.commercial, self.influence_ops,
            self.education, self.covert, self.diplomacy, self.kinetic_weapons,
        ]
        if any(f < 0.0 for f in fields):
            raise ValueError("All investment allocations must be >= 0.0")
        t = self.total()
        if t > 1.001:
            raise ValueError(f"Investment allocations sum to {t:.3f}, must be <= 1.0")
        return self


class OperationalAction(BaseModel):
    action_type: str
    target_faction: Optional[str] = None
    parameters: dict[str, Any] = {}
    rationale: str = ""


class ResponseDecision(BaseModel):
    escalate: bool = False
    retaliate: bool = False
    target_faction: Optional[str] = None
    emergency_reallocation: Optional[InvestmentAllocation] = None
    public_statement: str = ""
    rationale: str = ""


class Decision(BaseModel):
    phase: Phase
    faction_id: str
    investment: Optional[InvestmentAllocation] = None
    operations: Optional[list[OperationalAction]] = None
    response: Optional[ResponseDecision] = None
    tech_unlocks: list[str] = []

    @model_validator(mode="after")
    def validate_phase_payload(self) -> "Decision":
        if self.phase == Phase.INVEST and self.investment is None:
            raise ValueError("INVEST phase Decision must include investment allocation")
        if self.phase == Phase.OPERATIONS and self.operations is None:
            raise ValueError("OPERATIONS phase Decision must include operations list")
        if self.phase == Phase.RESPONSE and self.response is None:
            raise ValueError("RESPONSE phase Decision must include response decision")
        return self


class Recommendation(BaseModel):
    phase: Phase
    options: list[dict[str, Any]]
    top_recommendation: Decision
    strategic_rationale: str


class FactionState(BaseModel):
    faction_id: str
    name: str
    budget_per_turn: int = Field(ge=0)
    current_budget: int = Field(ge=0)
    assets: FactionAssets
    tech_tree: dict[str, int] = {}
    archetype: Optional[str] = None
    unlocked_techs: list[str] = []
    rog_shock_used: bool = False
    coalition_id: Optional[str] = None
    coalition_loyalty: float = 0.5
    deferred_returns: list[dict[str, Any]] = []
    private_victory_achieved: bool = False
    # Per-faction victory metrics (updated each turn)
    deterrence_score: float = 0.0
    disruption_score: float = 0.0
    market_share: float = 0.0
    joint_force_effectiveness: float = 1.0
    maneuver_budget: float = 10.0       # delta-v pool; replenishes each turn
    cognitive_penalty: float = 0.0      # 0.0–1.0; degrades SDA and coordination
    partial_invest: dict[str, int] = Field(default_factory=dict)  # banked remainder pts per category

    def sda_level(self) -> float:
        # 0.0–1.0 based on sensor count; 12 sensors = ~0.5, 24 = ~1.0
        return min(self.assets.sda_sensors / 24.0, 1.0)


class CoalitionState(BaseModel):
    coalition_id: str
    member_ids: list[str]
    hegemony_score: float = 0.0


class GameStateSnapshot(BaseModel):
    turn: int
    phase: Phase
    faction_id: str
    faction_state: FactionState
    ally_states: dict[str, FactionState]
    adversary_estimates: dict[str, dict]  # faction_id → filtered FactionAssets dict
    coalition_states: dict[str, CoalitionState]
    available_actions: list[str]
    turn_log_summary: str = ""
    tension_level: float = 0.0
    debris_level: float = 0.0
    joint_force_effectiveness: float = 1.0
    incoming_threats: list[dict[str, Any]] = []  # kinetic approaches visible via SDA
    faction_names: dict[str, str] = {}  # faction_id -> display name for all factions
    debris_fields: dict[str, float] = Field(default_factory=dict)  # shell → severity 0.0–1.0
    access_windows: dict[str, bool] = Field(
        default_factory=lambda: {"leo": True, "meo": True, "geo": True, "cislunar": True}
    )
    escalation_rung: int = 0               # 0–5 named escalation level
    total_turns: int = 0
    coalition_dominance: dict[str, float] = Field(default_factory=dict)
    victory_threshold: float = 0.65


class CrisisEvent(BaseModel):
    event_id: str
    event_type: str
    description: str
    triggered_by: Optional[str] = None
    affected_factions: list[str]
    visibility: Literal["public", "private", "faction-only"] = "public"
    severity: float = 0.5
    parameters: dict[str, Any] = {}


class CombatEvent(BaseModel):
    turn: int
    attacker_id: str
    target_faction_id: str
    shell: str           # 'leo' | 'meo' | 'geo' | 'cislunar'
    event_type: str      # 'kinetic' | 'deniable' | 'ew_jamming' | 'gray_zone'
    nodes_destroyed: int
    detail: str
    detected: bool = False
    attributed: bool = False
