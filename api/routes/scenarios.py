# api/routes/scenarios.py
import re
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ruamel.yaml import YAML
from scenarios.loader import load_scenario, Scenario, Faction, Coalition, VictoryConditions
from api.models import ScenarioSummary, ScenarioFactionSummary

router = APIRouter()
_SCENARIOS_DIR = Path("scenarios")
_yaml = YAML()
_yaml.default_flow_style = False


def _name_to_id(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def _scenario_to_dict(s: Scenario) -> dict:
    return {
        "name": s.name,
        "description": s.description,
        "turns": s.turns,
        "turn_represents": s.turn_represents,
        "coalitions": {
            cid: {
                "member_ids": list(c.member_ids),
                "shared_intel": c.shared_intel,
                "hegemony_pool": c.hegemony_pool,
            }
            for cid, c in s.coalitions.items()
        },
        "factions": [
            {k: v for k, v in {
                "faction_id": f.faction_id,
                "name": f.name,
                "archetype": f.archetype,
                "agent_type": f.agent_type,
                "budget_per_turn": f.budget_per_turn,
                "coalition_id": f.coalition_id,
                "coalition_loyalty": f.coalition_loyalty,
                "starting_assets": {
                    k: v for k, v in f.starting_assets.model_dump().items() if v != 0
                },
            }.items() if v is not None}
            for f in s.factions
        ],
        "victory": {
            "coalition_orbital_dominance": s.victory.coalition_orbital_dominance,
            "individual_conditions_required": s.victory.individual_conditions_required,
            "individual_conditions": s.victory.individual_conditions,
        },
        "crisis_events": {"library": s.crisis_events_library},
    }


def _save_yaml(path: Path, data: dict) -> None:
    _SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        _yaml.dump(data, f)


class ScenarioWrite(BaseModel):
    name: str
    description: str = ""
    turns: int = 12
    turn_represents: str = "3 months"
    coalitions: dict[str, Any] = {}
    factions: list[Any] = []
    victory: dict[str, Any] = {}
    crisis_events_library: str = "default_2030"


@router.get("/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios():
    results = []
    for path in sorted(_SCENARIOS_DIR.glob("*.yaml")):
        scenario = load_scenario(path)
        results.append(ScenarioSummary(
            id=path.stem,
            name=scenario.name,
            description=scenario.description,
            turns=scenario.turns,
            factions=[
                ScenarioFactionSummary(
                    faction_id=f.faction_id,
                    name=f.name,
                    archetype=f.archetype,
                    agent_type=f.agent_type,
                )
                for f in scenario.factions
            ],
        ))
    return results


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    path = _SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")
    scenario = load_scenario(path)
    return _scenario_to_dict(scenario)


@router.post("/scenarios", status_code=201)
async def create_scenario(data: ScenarioWrite):
    scenario_id = _name_to_id(data.name)
    path = _SCENARIOS_DIR / f"{scenario_id}.yaml"
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Scenario '{scenario_id}' already exists")
    yml = _scenario_to_dict(Scenario(
        name=data.name, description=data.description, turns=data.turns,
        turn_represents=data.turn_represents,
        factions=[Faction.model_validate(f) for f in data.factions],
        coalitions={k: Coalition.model_validate(v) for k, v in data.coalitions.items()},
        victory=VictoryConditions.model_validate(data.victory) if data.victory else VictoryConditions(),
        crisis_events_library=data.crisis_events_library,
    ))
    _save_yaml(path, yml)
    return {"scenario_id": scenario_id}


@router.put("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, data: ScenarioWrite):
    path = _SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")
    yml = _scenario_to_dict(Scenario(
        name=data.name, description=data.description, turns=data.turns,
        turn_represents=data.turn_represents,
        factions=[Faction.model_validate(f) for f in data.factions],
        coalitions={k: Coalition.model_validate(v) for k, v in data.coalitions.items()},
        victory=VictoryConditions.model_validate(data.victory) if data.victory else VictoryConditions(),
        crisis_events_library=data.crisis_events_library,
    ))
    _save_yaml(path, yml)
    return {"scenario_id": scenario_id}


@router.delete("/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: str):
    path = _SCENARIOS_DIR / f"{scenario_id}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")
    path.unlink()
