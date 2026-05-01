# api/routes/game.py
import asyncio
import json as _json
from typing import Optional
import aiosqlite
from fastapi import APIRouter, HTTPException
from api.models import AarRequest, CreateGameRequest, DecideRequest, GameStateResponse
from api import runner
from api.session import load_session, _DEFAULT_DB
from pydantic import BaseModel as _BaseModel


class PreviewRequest(_BaseModel):
    action_type: str
    mission: str = ""
    target_faction_id: str = ""

# Only one AAR generation runs at a time to avoid exceeding the API rate limit.
_aar_semaphore = asyncio.Semaphore(1)

router = APIRouter()


@router.get("/sessions")
async def list_sessions():
    try:
        async with aiosqlite.connect(_DEFAULT_DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            async with db.execute("""
                SELECT
                    session_id,
                    json_extract(state_json, '$.scenario_name') AS scenario_name,
                    json_extract(state_json, '$.turn')          AS turn,
                    json_extract(state_json, '$.total_turns')   AS total_turns,
                    json_extract(state_json, '$.game_over')     AS game_over,
                    json_extract(state_json, '$.human_faction_id') AS human_faction_id,
                    json_extract(state_json, '$.result')        AS result_json,
                    updated_at
                FROM sessions
                ORDER BY updated_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
        sessions = []
        for row in rows:
            result_json = row[6]
            winner = None
            if result_json:
                result = _json.loads(result_json)
                winner = result.get("winner_coalition")
            sessions.append({
                "session_id": row[0],
                "scenario_name": row[1],
                "turn": row[2],
                "total_turns": row[3],
                "game_over": bool(row[4]),
                "human_faction_id": row[5],
                "winner_coalition": winner,
                "updated_at": row[7],
            })
        return sessions
    except Exception:
        return []


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
        return await runner.advance(
            session_id,
            decision=decision,
            operation_forecast=req.operation_forecast,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/game/{session_id}/preview")
async def preview_operation(session_id: str, req: PreviewRequest):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    attacker_fs = state.faction_states.get(state.human_faction_id)
    if attacker_fs is None:
        raise HTTPException(status_code=400, detail="Human faction not found")
    target_fs = state.faction_states.get(req.target_faction_id) if req.target_faction_id else None
    from engine.preview import PreviewEngine
    preview = PreviewEngine().compute(
        action_type=req.action_type,
        mission=req.mission,
        attacker_fs=attacker_fs,
        target_fs=target_fs,
        debris_fields=state.debris_fields,
        access_windows=state.access_windows,
        escalation_rung=state.escalation_rung,
    )
    return preview.model_dump()


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

        t = advisor.token_totals
        if any(v > 0 for v in t.values()):
            from output.audit import AuditTrail
            audit = AuditTrail(f"output/game_audit_{state.session_id[:8]}.db")
            try:
                await audit.initialize()
                await audit.write_token_usage(state.human_faction_id, "advisor", advisor._model, t)
            finally:
                await audit.close()

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


@router.get("/game/{session_id}/history")
async def get_history(session_id: str):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    from output.audit import AuditTrail
    audit = AuditTrail(f"output/game_audit_{session_id[:8]}.db")
    try:
        await audit.initialize()
        log = await audit.get_full_game_log()
        tokens = await audit.get_token_summary()
        return {**log, "token_summary": tokens}
    except Exception:
        return {"decisions": [], "events": [], "divergences": [], "token_summary": []}
    finally:
        await audit.close()


@router.get("/game/{session_id}/aars")
async def list_aars(session_id: str):
    from api.session import list_aars as _list_aars
    return await _list_aars(session_id)


@router.post("/game/{session_id}/aar")
async def generate_aar(session_id: str, req: AarRequest = AarRequest()):
    state = await load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    focus: str = req.focus
    force: bool = req.force

    from api.session import load_aar, save_aar
    if not force:
        cached = await load_aar(session_id, focus)
        if cached:
            return {"text": cached, "cached": True, "focus": focus}

    from output.aar import AfterActionReportGenerator
    from output.audit import AuditTrail
    import anthropic as _anthropic

    gen = AfterActionReportGenerator()
    audit_path = f"output/game_audit_{state.session_id[:8]}.db"
    audit = AuditTrail(audit_path)
    await audit.initialize()
    try:
        async with _aar_semaphore:
            text, aar_usage = await gen.generate(audit=audit, scenario_name=state.scenario_name, focus=focus)
    except _anthropic.RateLimitError as exc:
        raise HTTPException(
            status_code=503,
            detail="API rate limit reached — another report is already generating. Wait a minute and try again.",
        ) from exc
    except _anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"AI API error: {exc}") from exc
    finally:
        await audit.close()

    await save_aar(session_id, focus, text)
    return {"text": text, "cached": False, "focus": focus, "usage": aar_usage}
