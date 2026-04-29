# scenarios/loader.py — minimal stub for Task 4; Task 5 will replace this fully
from pydantic import BaseModel
from engine.state import FactionAssets


class VictoryConditions(BaseModel):
    orbital_dominance: float = 0.65
    turns_to_hegemony: int = 12


class Faction(BaseModel):
    faction_id: str
    name: str
    archetype: str
    agent_type: str
    budget_per_turn: int
    starting_assets: FactionAssets = FactionAssets()
    coalition_id: str | None = None
    persona_path: str | None = None


class Scenario(BaseModel):
    name: str
    turns: int
    factions: list[Faction] = []
    victory: VictoryConditions = VictoryConditions()
    crisis_events_library: str = "default_2030"
