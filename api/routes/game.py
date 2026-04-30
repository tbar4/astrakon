# api/routes/game.py
from typing import Optional
from fastapi import APIRouter, HTTPException
from api.models import CreateGameRequest, DecideRequest, GameStateResponse
from api import runner
from api.session import load_session

router = APIRouter()


@router.post("/game/create", response_model=GameStateResponse)
async def create_game(req: CreateGameRequest):
    agent_config = [c.model_dump() for c in req.agent_config]
    state = await runner.create_game(req.scenario_id, agent_config)
    from engine.simulation import SimulationEngine
    sim = SimulationEngine()
    dominance = runner._compute_dominance(state, sim)
    return GameStateResponse(state=state, coalition_dominance=dominance)


@router.get("/game/{session_id}/state", response_model=GameStateResponse)
async def get_state(session_id: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    from engine.simulation import SimulationEngine
    sim = SimulationEngine()
    dominance = runner._compute_dominance(state, sim)
    return GameStateResponse(state=state, coalition_dominance=dominance)


@router.post("/game/{session_id}/advance", response_model=GameStateResponse)
async def advance(session_id: str):
    try:
        return await runner.advance(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/game/{session_id}/decide", response_model=GameStateResponse)
async def decide(session_id: str, req: DecideRequest):
    try:
        decision = {"phase": req.phase, "decision": req.decision}
        return await runner.advance(session_id, decision=decision)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/game/{session_id}/recommend")
async def recommend(session_id: str, phase: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not state.use_advisor:
        return {"recommendation": None}
    from scenarios.loader import load_scenario
    from pathlib import Path
    from engine.state import Phase, GameStateSnapshot
    from agents.ai_commander import AICommanderAgent
    from personas.builder import load_archetype
    import io
    from ruamel.yaml import YAML

    scenario = load_scenario(Path("scenarios") / f"{state.scenario_id}.yaml")
    human_faction = next(f for f in scenario.factions if f.faction_id == state.human_faction_id)
    yaml = YAML()
    buf = io.StringIO()
    yaml.dump(load_archetype(human_faction.archetype), buf)
    advisor = AICommanderAgent(persona_yaml=buf.getvalue())
    advisor.initialize(human_faction)

    if state.human_snapshot:
        snapshot = GameStateSnapshot.model_validate(state.human_snapshot)
        advisor.receive_state(snapshot)
        rec = await advisor.get_recommendation(Phase(phase))
        return {"recommendation": rec.model_dump() if rec else None}
    return {"recommendation": None}


@router.get("/game/{session_id}/result")
async def get_result(session_id: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not state.game_over:
        raise HTTPException(status_code=400, detail="Game is not over")
    return state.result


@router.post("/game/{session_id}/aar")
async def generate_aar(session_id: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    from output.aar import AfterActionReportGenerator
    from output.audit import AuditTrail
    from pathlib import Path
    gen = AfterActionReportGenerator()
    audit_path = f"output/game_audit_{state.session_id[:8]}.db"
    audit = AuditTrail(audit_path)
    try:
        text = await gen.generate(audit=audit, scenario_name=state.scenario_name)
    finally:
        await audit.close()
    return {"text": text}
