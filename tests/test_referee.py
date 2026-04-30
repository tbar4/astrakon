import pytest
from pathlib import Path
from engine.referee import GameReferee
from engine.state import Phase, Decision
from agents.base import AgentInterface
from agents.rule_based import MahanianAgent, MaxConstellationAgent
from scenarios.loader import load_scenario, Faction
from engine.state import FactionAssets
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


async def test_referee_runs_one_turn(scenario, agents, audit):
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    await referee.run_turn(turn=1)
    decisions = await audit.get_decisions(turn=1)
    # Should have one decision per faction per phase (3 phases * 4 factions = 12)
    assert len(decisions) == len(scenario.factions) * 3


async def test_referee_completes_full_scenario(scenario, audit):
    # Use a short scenario (3 turns) for the test
    scenario.turns = 3
    agents = {}
    for faction in scenario.factions:
        agent = MahanianAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()
    assert result.turns_completed == 3
    all_decisions = await audit.get_decisions()
    assert len(all_decisions) == len(scenario.factions) * 3 * 3


async def test_referee_checks_victory_conditions(scenario, audit):
    scenario.turns = 1
    agents = {}
    for faction in scenario.factions:
        agent = MaxConstellationAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()
    assert result is not None
    assert hasattr(result, "winner_coalition")


async def test_fallback_agent_on_exception(scenario, audit):
    """When an agent raises on submit_decision, referee falls back to MahanianAgent."""
    class FailingAgent(AgentInterface):
        async def submit_decision(self, phase: Phase) -> Decision:
            raise RuntimeError("simulated agent failure")

    scenario.turns = 1
    agents = {}
    for faction in scenario.factions:
        agent = FailingAgent() if faction.faction_id == "ussf" else MahanianAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent

    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()

    assert result.turns_completed == 1

    decisions = await audit.get_decisions(turn=1)
    ussf_decisions = [d for d in decisions if d["faction_id"] == "ussf"]
    assert len(ussf_decisions) > 0


async def test_kinetic_strike_adds_shell_debris(scenario, agents, audit):
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
    leo_debris = referee._debris_fields.get("leo", 0.0)
    assert leo_debris > 0.0


async def test_escalation_rung_rises_on_kinetic(scenario, agents, audit):
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
    assert referee._escalation_rung >= 4  # Kinetic strike = rung 4


async def test_maneuver_budget_replenished_each_turn(scenario, agents, audit):
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    fid = list(referee.faction_states.keys())[0]
    referee.faction_states[fid].maneuver_budget = 5.0
    referee._replenish_budgets(turn=1)
    assert referee.faction_states[fid].maneuver_budget > 5.0


@pytest.mark.asyncio
async def test_kinetic_requires_two_turn_transit(scenario, agents, audit):
    """Kinetic declared turn 1 should NOT resolve on turn 2, only on turn 3."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee._pending_kinetic_approaches = [{
        "attacker_fid": "ussf", "target_fid": "pla_ssf",
        "declared_turn": 1, "approach_type": "kinetic",
    }]
    referee.faction_states["ussf"].assets.asat_kinetic = 3
    referee.faction_states["pla_ssf"].assets.leo_nodes = 10
    referee.resolve_pending_kinetics(turn=2)  # too early — should not resolve
    assert referee.faction_states["pla_ssf"].assets.leo_nodes == 10  # unchanged


@pytest.mark.asyncio
async def test_kinetic_resolves_on_turn_three(scenario, agents, audit):
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee._pending_kinetic_approaches = [{
        "attacker_fid": "ussf", "target_fid": "pla_ssf",
        "declared_turn": 1, "approach_type": "kinetic",
    }]
    referee.faction_states["ussf"].assets.asat_kinetic = 3
    referee.faction_states["pla_ssf"].assets.leo_nodes = 10
    referee.resolve_pending_kinetics(turn=3)  # correct window (declared_turn + 2 = 3)
    # kinetic was attempted — log should have something
    assert len(referee._turn_log) > 0


@pytest.mark.asyncio
async def test_deniable_approach_resolves_after_one_turn(scenario, agents, audit):
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee._pending_deniable_approaches = [{
        "attacker_fid": "ussf", "target_fid": "pla_ssf",
        "declared_turn": 1,
    }]
    referee.faction_states["ussf"].assets.asat_deniable = 2
    referee.faction_states["pla_ssf"].assets.leo_nodes = 10
    referee._resolve_pending_deniables(turn=2)
    assert len(referee._turn_log) > 0


@pytest.mark.asyncio
async def test_access_window_leo_closed_on_even_turn(scenario, agents, audit):
    """AccessWindowEngine returns closed for LEO on even turns."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee._current_turn = 2  # even turn → LEO window closed
    windows = referee.sim.access_window_engine.compute(2)
    assert windows["leo"] is False


@pytest.mark.asyncio
async def test_access_window_meo_open_on_turn_two(scenario, agents, audit):
    """MEO is open on turn 2 (2%3 != 0)."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    windows = referee.sim.access_window_engine.compute(2)
    assert windows["meo"] is True
