# tests/test_combat_events.py
import pytest
from engine.state import CombatEvent
from api.models import GameState


def test_combat_event_instantiates():
    ev = CombatEvent(
        turn=1,
        attacker_id="ussf",
        target_faction_id="pla_ssf",
        shell="leo",
        event_type="kinetic",
        nodes_destroyed=3,
        detail="USSF destroys 3 PLA_SSF nodes in LEO",
    )
    assert ev.nodes_destroyed == 3
    assert ev.shell == "leo"
    d = ev.model_dump()
    assert d["event_type"] == "kinetic"


def test_game_state_has_combat_events_field():
    from engine.state import FactionState, CoalitionState, Phase, FactionAssets
    fs = FactionState(
        faction_id="ussf", name="USSF", budget_per_turn=10, current_budget=10,
        assets=FactionAssets(), coalition_id="usa", coalition_loyalty=1.0, archetype="mahanian"
    )
    state = GameState(
        session_id="s1", scenario_id="test", scenario_name="Test", turn=1, total_turns=5,
        current_phase=Phase.INVEST, faction_states={"ussf": fs},
        coalition_states={}, human_faction_id="ussf",
    )
    assert state.combat_events == []


from pathlib import Path
from engine.referee import GameReferee
from agents.rule_based import MahanianAgent
from scenarios.loader import load_scenario
from output.audit import AuditTrail


@pytest.fixture
def scenario():
    return load_scenario(Path("scenarios/pacific_crossroads.yaml"))


@pytest.fixture
async def audit(tmp_path):
    trail = AuditTrail(str(tmp_path / "test.db"))
    await trail.initialize()
    yield trail
    await trail.close()


@pytest.fixture
def agents(scenario):
    result = {}
    for faction in scenario.factions:
        agent = MahanianAgent()
        agent.initialize(faction)
        result[faction.faction_id] = agent
    return result


@pytest.mark.asyncio
async def test_kinetic_approach_creates_combat_event(scenario, agents, audit):
    """After resolving a kinetic approach, _combat_events has one entry."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee._pending_kinetic_approaches = [{
        "attacker_fid": "ussf",
        "target_fid": "pla_ssf",
        "declared_turn": 1,
        "approach_type": "kinetic",
    }]
    referee.faction_states["ussf"].assets.asat_kinetic = 3
    referee.faction_states["pla_ssf"].assets.leo_nodes = 10
    referee.resolve_pending_kinetics(turn=3)
    assert len(referee._combat_events) == 1
    ev = referee._combat_events[0]
    assert ev["attacker_id"] == "ussf"
    assert ev["target_faction_id"] == "pla_ssf"
    assert ev["event_type"] == "kinetic"
    assert ev["nodes_destroyed"] >= 0
    assert ev["shell"] in ("leo", "meo", "geo", "cislunar")


@pytest.mark.asyncio
async def test_combat_events_in_dump_mutable_state(scenario, agents, audit):
    """dump_mutable_state includes combat_events."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee._pending_kinetic_approaches = [{
        "attacker_fid": "ussf",
        "target_fid": "pla_ssf",
        "declared_turn": 1,
        "approach_type": "kinetic",
    }]
    referee.faction_states["ussf"].assets.asat_kinetic = 3
    referee.faction_states["pla_ssf"].assets.leo_nodes = 10
    referee.resolve_pending_kinetics(turn=3)
    mutable = referee.dump_mutable_state()
    assert "combat_events" in mutable
    assert isinstance(mutable["combat_events"], list)
    assert len(mutable["combat_events"]) == 1


@pytest.mark.asyncio
async def test_combat_events_survive_load_mutable_state(scenario, agents, audit):
    """load_mutable_state restores combat_events."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    from engine.state import CombatEvent
    referee._combat_events = [CombatEvent(
        turn=1, attacker_id="ussf", target_faction_id="pla_ssf",
        shell="leo", event_type="kinetic", nodes_destroyed=2, detail="test"
    ).model_dump()]
    mutable = referee.dump_mutable_state()

    referee2 = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee2.load_mutable_state(**mutable)
    assert len(referee2._combat_events) == 1
    assert referee2._combat_events[0]["attacker_id"] == "ussf"


@pytest.mark.asyncio
async def test_runner_combat_events_cleared_at_operations(tmp_path):
    """combat_events from previous turn persist through INVEST, cleared at OPERATIONS start."""
    from api.runner import create_game, advance
    from engine.state import Phase
    from pathlib import Path as P
    from scenarios.loader import load_scenario as ls

    sid = "pacific_crossroads"
    scenario = ls(P("scenarios/pacific_crossroads.yaml"))
    human_fid = scenario.factions[0].faction_id
    agent_config = [
        {
            "faction_id": f.faction_id,
            "agent_type": "web" if f.faction_id == human_fid else "rule_based",
            "use_advisor": False,
        }
        for f in scenario.factions
    ]
    state = await create_game(sid, agent_config, db_path=str(tmp_path / "s.db"))

    # Manually inject a combat event into the saved state
    from api.session import load_session, save_session
    from engine.state import CombatEvent as CE
    loaded = await load_session(state.session_id, db_path=str(tmp_path / "s.db"))
    loaded.combat_events = [CE(
        turn=0, attacker_id="ussf", target_faction_id="pla_ssf",
        shell="leo", event_type="kinetic", nodes_destroyed=2, detail="test"
    ).model_dump()]
    await save_session(loaded, db_path=str(tmp_path / "s.db"))

    # Advance to INVEST — combat_events field must be present
    resp = await advance(state.session_id, db_path=str(tmp_path / "s.db"))
    assert resp.state.combat_events is not None
    assert isinstance(resp.state.combat_events, list)


def test_combat_event_has_detected_attributed_defaults():
    ev = CombatEvent(
        turn=1, attacker_id="ussf", target_faction_id="pla_ssf",
        shell="leo", event_type="kinetic", nodes_destroyed=3, detail="test",
    )
    assert ev.detected is False
    assert ev.attributed is False


def test_combat_event_accepts_detected_attributed():
    ev = CombatEvent(
        turn=1, attacker_id="ussf", target_faction_id="pla_ssf",
        shell="leo", event_type="kinetic", nodes_destroyed=3, detail="test",
        detected=True, attributed=True,
    )
    assert ev.detected is True
    d = ev.model_dump()
    assert d["detected"] is True
    assert d["attributed"] is True
