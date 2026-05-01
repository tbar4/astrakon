# api/models.py
from typing import Optional, Any
from pydantic import BaseModel, Field
from engine.state import Phase, FactionState, CoalitionState, GameStateSnapshot


class GameState(BaseModel):
    session_id: str
    scenario_id: str
    scenario_name: str
    turn: int
    total_turns: int
    current_phase: Phase
    phase_decisions: dict[str, str] = {}     # faction_id → Decision JSON string
    faction_states: dict[str, FactionState]
    coalition_states: dict[str, CoalitionState]
    tension_level: float = 0.2
    debris_level: float = 0.0
    pending_kinetic_approaches: list[dict] = []
    turn_log: list[str] = []
    turn_log_summary: str = ""
    coordination_bonuses: dict[str, float] = {}
    event_sda_malus: dict[str, float] = {}
    prev_turn_ops: list[str] = []
    events: list[dict] = []                  # crisis events this turn (for summary phase)
    human_faction_id: str
    human_faction_ids: list[str] = []       # all web-controlled factions (≥1)
    human_snapshot: Optional[dict] = None   # serialized GameStateSnapshot
    use_advisor: bool = False
    agent_config: list[dict] = []
    game_over: bool = False
    result: Optional[dict] = None
    error: Optional[str] = None
    victory_threshold: float = 0.65
    coalition_colors: dict[str, str] = {}
    awaiting_next_turn: bool = False
    initial_assets: dict[str, dict] = {}  # faction_id → FactionAssets dict (for JFE computation)
    debris_fields: dict[str, float] = Field(default_factory=dict)           # shell → debris severity
    escalation_rung: int = 0                        # 0–5
    access_windows: dict[str, bool] = Field(
        default_factory=lambda: {"leo": True, "meo": True, "geo": True, "cislunar": True}
    )
    human_adversary_estimates: dict[str, dict] = Field(default_factory=dict) # human player's filtered view of adversaries
    pending_deniable_approaches: list[dict] = Field(default_factory=list)    # delayed deniable co-orbital ops
    token_totals: dict[str, dict] = Field(default_factory=dict)              # faction_id → cumulative token counts


class ScenarioFactionSummary(BaseModel):
    faction_id: str
    name: str
    archetype: str
    agent_type: str


class ScenarioSummary(BaseModel):
    id: str
    name: str
    description: str
    turns: int
    factions: list[ScenarioFactionSummary]


class AgentConfigEntry(BaseModel):
    faction_id: str
    agent_type: str   # "web" | "rule_based" | "ai_commander"
    use_advisor: bool = False
    archetype_override: Optional[str] = None
    custom_invest_weights: Optional[dict] = None  # {urgency_state: {invest_key: float}}


class CreateGameRequest(BaseModel):
    scenario_id: str
    agent_config: list[AgentConfigEntry]


class DecideRequest(BaseModel):
    phase: str
    decision: dict[str, Any]


class GameStateResponse(BaseModel):
    state: GameState
    coalition_dominance: dict[str, float]


class AarRequest(BaseModel):
    focus: str = ""
    force: bool = False
