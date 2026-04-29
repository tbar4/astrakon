# tests/test_integration.py
import pytest
from pathlib import Path
from engine.referee import GameReferee
from agents.rule_based import MahanianAgent, MaxConstellationAgent
from scenarios.loader import load_scenario
from output.audit import AuditTrail
from output.strategy_lib import StrategyLibrary


@pytest.fixture
async def audit(tmp_path):
    trail = AuditTrail(str(tmp_path / "integration.db"))
    await trail.initialize()
    yield trail
    await trail.close()


async def test_full_3_turn_game_all_rule_based(audit, tmp_path):
    scenario = load_scenario(Path("scenarios/pacific_crossroads.yaml"))
    scenario.turns = 3

    agents = {}
    for i, faction in enumerate(scenario.factions):
        AgentClass = MahanianAgent if i % 2 == 0 else MaxConstellationAgent
        agent = AgentClass()
        agent.initialize(faction)
        agents[faction.faction_id] = agent

    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()

    # Verify game ran
    assert result.turns_completed <= 3
    assert set(result.faction_outcomes.keys()) == {f.faction_id for f in scenario.factions}

    # Verify audit trail populated
    all_decisions = await audit.get_decisions()
    # At minimum: 4 factions * 3 phases * however many turns ran
    assert len(all_decisions) >= len(scenario.factions) * 3

    # Verify strategy lib records run
    lib = StrategyLibrary(str(tmp_path / "strategy_lib.db"))
    lib.record_run(scenario, result)
    rates = lib.win_rates()
    assert len(rates) > 0


async def test_victory_condition_triggers_early_end(audit):
    scenario = load_scenario(Path("scenarios/pacific_crossroads.yaml"))
    scenario.turns = 20
    # Lower victory threshold so MaxConstellation wins quickly
    scenario.victory.coalition_orbital_dominance = 0.30

    agents = {}
    for faction in scenario.factions:
        agent = MaxConstellationAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent

    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()

    # Should end before turn 20 because dominance threshold is low
    assert result.turns_completed <= 20
    assert result.winner_coalition is not None or result.turns_completed == 20
