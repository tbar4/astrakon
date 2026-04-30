# tests/test_api.py
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from api.main import app


def _first_scenario_id() -> str:
    scenarios = list(Path("scenarios").glob("*.yaml"))
    if not scenarios:
        pytest.skip("No scenario files found")
    return scenarios[0].stem


@pytest.mark.asyncio
async def test_list_scenarios():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/scenarios")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]
    assert "name" in data[0]
    assert "factions" in data[0]


@pytest.mark.asyncio
async def test_create_game(tmp_path, monkeypatch):
    monkeypatch.setattr("api.runner._SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setattr("api.session._DEFAULT_DB", str(tmp_path / "s.db"))
    sid = _first_scenario_id()
    from scenarios.loader import load_scenario
    scenario = load_scenario(Path("scenarios") / f"{sid}.yaml")
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {"faction_id": f.faction_id, "agent_type": "web" if f.faction_id == human_fid else "rule_based", "use_advisor": False}
        for f in scenario.factions
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/game/create", json={"scenario_id": sid, "agent_config": agent_config})
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body["state"]
    assert body["state"]["turn"] == 0


@pytest.mark.asyncio
async def test_advance_returns_human_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr("api.runner._SESSIONS_DB", str(tmp_path / "s.db"))
    monkeypatch.setattr("api.session._DEFAULT_DB", str(tmp_path / "s.db"))
    sid = _first_scenario_id()
    from scenarios.loader import load_scenario
    scenario = load_scenario(Path("scenarios") / f"{sid}.yaml")
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {"faction_id": f.faction_id, "agent_type": "web" if f.faction_id == human_fid else "rule_based", "use_advisor": False}
        for f in scenario.factions
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/game/create", json={"scenario_id": sid, "agent_config": agent_config})
        session_id = r.json()["state"]["session_id"]
        r2 = await client.post(f"/api/game/{session_id}/advance")
    assert r2.status_code == 200
    body = r2.json()
    assert body["state"]["human_snapshot"] is not None
    assert body["state"]["turn"] == 1
