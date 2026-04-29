from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel
from ruamel.yaml import YAML
from engine.state import FactionAssets


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


def load_scenario(path: Path) -> Scenario:
    yaml = YAML()
    raw = yaml.load(path)
    factions = [Faction(**f) for f in raw.get("factions", [])]
    coalitions = {
        k: Coalition(**v)
        for k, v in raw.get("coalitions", {}).items()
    }
    victory_raw = raw.get("victory", {})
    victory = VictoryConditions(**victory_raw)
    return Scenario(
        name=raw["name"],
        description=raw.get("description", ""),
        turns=raw["turns"],
        turn_represents=raw.get("turn_represents", "1 month"),
        factions=factions,
        coalitions=coalitions,
        victory=victory,
        crisis_events_library=raw.get("crisis_events", {}).get("library", "default_2030"),
    )
