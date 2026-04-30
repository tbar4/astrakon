# api/routes/scenarios.py
from pathlib import Path
from fastapi import APIRouter
from scenarios.loader import load_scenario
from api.models import ScenarioSummary, ScenarioFactionSummary

router = APIRouter()
_SCENARIOS_DIR = Path("scenarios")


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
