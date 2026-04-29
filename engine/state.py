from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, model_validator


class Phase(str, Enum):
    INVEST = "invest"
    OPERATIONS = "operations"
    RESPONSE = "response"


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


class InvestmentAllocation(BaseModel):
    r_and_d: float = 0.0
    constellation: float = 0.0
    launch_capacity: float = 0.0
    commercial: float = 0.0
    influence_ops: float = 0.0
    education: float = 0.0
    covert: float = 0.0
    diplomacy: float = 0.0
    rationale: str = ""

    def total(self) -> float:
        return (self.r_and_d + self.constellation + self.launch_capacity +
                self.commercial + self.influence_ops + self.education +
                self.covert + self.diplomacy)

    @model_validator(mode="after")
    def validate_budget(self) -> "InvestmentAllocation":
        if self.total() > 1.001:
            raise ValueError(f"Investment allocations sum to {self.total():.3f}, must be <= 1.0")
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


class Recommendation(BaseModel):
    phase: Phase
    options: list[dict[str, Any]]
    top_recommendation: Decision
    strategic_rationale: str


class FactionState(BaseModel):
    faction_id: str
    name: str
    budget_per_turn: int
    current_budget: int
    assets: FactionAssets
    tech_tree: dict[str, int] = {}
    coalition_id: Optional[str] = None
    coalition_loyalty: float = 0.5
    deferred_returns: list[dict[str, Any]] = []
    private_victory_achieved: bool = False

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
    adversary_estimates: dict[str, FactionAssets]
    coalition_states: dict[str, CoalitionState]
    available_actions: list[str]
    turn_log_summary: str = ""


class CrisisEvent(BaseModel):
    event_id: str
    event_type: str
    description: str
    triggered_by: Optional[str] = None
    affected_factions: list[str]
    visibility: str = "public"
    severity: float = 0.5
    parameters: dict[str, Any] = {}
