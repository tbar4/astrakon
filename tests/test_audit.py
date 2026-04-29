import pytest
import aiosqlite
from pathlib import Path
from output.audit import AuditTrail
from engine.state import Phase, Decision, InvestmentAllocation, CrisisEvent


@pytest.fixture
async def audit(tmp_path):
    db_path = tmp_path / "test_game.db"
    trail = AuditTrail(str(db_path))
    await trail.initialize()
    yield trail
    await trail.close()


async def test_write_and_retrieve_decision(audit):
    alloc = InvestmentAllocation(r_and_d=0.5, constellation=0.5, rationale="test")
    decision = Decision(phase=Phase.INVEST, faction_id="ussf", investment=alloc)
    await audit.write_decision(turn=1, decision=decision)
    rows = await audit.get_decisions(turn=1)
    assert len(rows) == 1
    assert rows[0]["faction_id"] == "ussf"
    assert rows[0]["rationale"] == "test"


async def test_write_crisis_event(audit):
    event = CrisisEvent(
        event_id="evt_001", event_type="asat_test",
        description="Adversary ASAT test detected",
        affected_factions=["ussf"], severity=0.7
    )
    await audit.write_event(turn=2, event=event)
    rows = await audit.get_events(turn=2)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "asat_test"


async def test_write_advisor_divergence(audit):
    recommendation = Decision(
        phase=Phase.INVEST, faction_id="ussf",
        investment=InvestmentAllocation(r_and_d=0.40, influence_ops=0.40, constellation=0.20,
                                        rationale="advised")
    )
    final = Decision(
        phase=Phase.INVEST, faction_id="ussf",
        investment=InvestmentAllocation(constellation=0.8, r_and_d=0.2,
                                        rationale="overridden")
    )
    await audit.write_advisor_divergence(turn=1, recommendation=recommendation, final=final)
    rows = await audit.get_advisor_divergences()
    assert len(rows) == 1
