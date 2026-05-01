from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING
from pydantic import BaseModel
from ruamel.yaml import YAML
from engine.state import FactionAssets

if TYPE_CHECKING:
    from agents.base import AgentInterface


class VictoryConditions(BaseModel):
    coalition_orbital_dominance: float = 0.65
    individual_conditions_required: bool = True
    individual_conditions: dict[str, dict[str, Any]] = {}


class Faction(BaseModel):
    faction_id: str
    name: str
    archetype: str
    agent_type: str
    budget_per_turn: int
    coalition_id: Optional[str] = None
    coalition_loyalty: float = 0.5
    starting_assets: FactionAssets = FactionAssets()
    persona_path: Optional[str] = None
    checkpoint_path: Optional[str] = None


class Coalition(BaseModel):
    member_ids: list[str]
    shared_intel: bool = True
    hegemony_pool: bool = True


class Scenario(BaseModel):
    name: str
    description: str = ""
    turns: int
    turn_represents: str = "1 month"
    factions: list[Faction]
    coalitions: dict[str, Coalition]
    victory: VictoryConditions = VictoryConditions()
    crisis_events_library: str = "default_2030"


def _rule_agent_for_archetype(archetype: str) -> "AgentInterface":
    """Return the appropriate rule-based agent for a given faction archetype."""
    from agents.rule_based import (
        MahanianAgent, GrayZoneAgent, RogueAccelerationistAgent, CommercialBrokerAgent,
    )
    return {
        "mahanian":               MahanianAgent,
        "commercial_broker":      CommercialBrokerAgent,
        "gray_zone":              GrayZoneAgent,
        "patient_dragon":         GrayZoneAgent,
        "rogue_accelerationist":  RogueAccelerationistAgent,
        "iron_napoleon":          RogueAccelerationistAgent,
    }.get(archetype, MahanianAgent)()


def make_agent(faction: "Faction") -> "AgentInterface":
    """Dispatch factory: create the appropriate agent for a faction."""
    match faction.agent_type:
        case "human" | "human+advisor":
            from agents.human import HumanAgent
            return HumanAgent()
        case "is_mcts":
            from agents.mcts_agent import ISMCTSAgent
            return ISMCTSAgent(n_simulations=800)
        case "is_mcts_fast":
            from agents.mcts_agent import ISMCTSAgent
            return ISMCTSAgent(n_simulations=200)
        case "rule_based":
            return _rule_agent_for_archetype(faction.archetype)
        case "ai_commander":
            from agents.ai_commander import AICommanderAgent
            if not faction.persona_path:
                raise ValueError(
                    f"ai_commander faction {faction.faction_id} requires persona_path"
                )
            raw_yaml = Path(faction.persona_path).read_text()
            return AICommanderAgent(raw_yaml)
        case "alphazero":
            from agents.alphazero_agent import AlphaZeroAgent  # type: ignore[import]
            if not faction.checkpoint_path:
                raise ValueError(
                    f"alphazero faction {faction.faction_id} requires checkpoint_path"
                )
            return AlphaZeroAgent(Path(faction.checkpoint_path))
        case _:
            raise ValueError(f"Unknown agent_type: {faction.agent_type!r}")


def load_scenario(path: Path) -> Scenario:
    yaml = YAML()
    raw = yaml.load(path)
    try:
        name = raw["name"]
        turns = raw["turns"]
    except KeyError as e:
        raise ValueError(f"Scenario file {path} is missing required field: {e}") from e
    factions = [Faction.model_validate(dict(f)) for f in raw.get("factions", [])]
    coalitions = {
        k: Coalition.model_validate(dict(v))
        for k, v in raw.get("coalitions", {}).items()
    }
    victory = VictoryConditions.model_validate(dict(raw.get("victory", {})))
    return Scenario(
        name=name,
        description=raw.get("description", ""),
        turns=turns,
        turn_represents=raw.get("turn_represents", "1 month"),
        factions=factions,
        coalitions=coalitions,
        victory=victory,
        crisis_events_library=raw.get("crisis_events", {}).get("library", "default_2030"),
    )
