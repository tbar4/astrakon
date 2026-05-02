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


@pytest.mark.asyncio
async def test_cognitive_penalty_computed_from_jfe_and_sda_malus(scenario, agents, audit):
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    fid = list(referee.faction_states.keys())[0]
    referee.faction_states[fid].joint_force_effectiveness = 0.3  # badly degraded
    referee._event_sda_malus[fid] = 0.4
    referee._update_faction_metrics()
    assert referee.faction_states[fid].cognitive_penalty > 0.5

@pytest.mark.asyncio
async def test_coalition_loyalty_drops_under_high_tension(scenario, agents, audit):
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    referee.tension_level = 0.8
    # Find a faction that has a coalition
    fid = next(f.faction_id for f in scenario.factions if f.coalition_id)
    fs = referee.faction_states[fid]
    initial_loyalty = fs.coalition_loyalty
    referee._update_coalition_loyalty()
    assert fs.coalition_loyalty <= initial_loyalty

@pytest.mark.asyncio
async def test_low_loyalty_coordination_fails(scenario, agents, audit):
    """When loyalty < 0.25, coordinate op logs failure."""
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    # Find a faction with an ally
    fid = next(f.faction_id for f in scenario.factions if f.coalition_id)
    coalition_id = referee.faction_states[fid].coalition_id
    cs = referee.coalition_states.get(coalition_id)
    ally_fid = next((mid for mid in cs.member_ids if mid != fid), None)
    if not ally_fid:
        pytest.skip("No ally found")
    referee.faction_states[fid].coalition_loyalty = 0.1  # very low
    from engine.state import Decision, Phase, OperationalAction
    decisions = {
        fid: Decision(
            phase=Phase.OPERATIONS, faction_id=fid,
            operations=[OperationalAction(action_type="coordinate", target_faction=ally_fid, rationale="test")]
        ).model_dump_json()
    }
    for other_fid in referee.faction_states:
        if other_fid != fid:
            decisions[other_fid] = Decision(
                phase=Phase.OPERATIONS, faction_id=other_fid, operations=[]
            ).model_dump_json()
    await referee.resolve_operations(turn=1, decisions=decisions)
    assert any("loyal" in e.lower() or "coordinat" in e.lower() for e in referee._turn_log)


# ── New tech-tree tests ────────────────────────────────────────────────────────

import asyncio
from pathlib import Path
from engine.state import FactionState, FactionAssets, InvestmentAllocation, Decision, Phase
from engine.simulation import SimulationEngine


@pytest.fixture
def minimal_scenario():
    from scenarios.loader import load_scenario
    return load_scenario(Path("scenarios/pacific_crossroads.yaml"))


@pytest.fixture
def referee_with_audit(tmp_path, minimal_scenario):
    import asyncio as _asyncio
    from output.audit import AuditTrail
    from engine.referee import GameReferee
    from agents.rule_based import MahanianAgent

    async def _make():
        audit = AuditTrail(str(tmp_path / "ref_audit.db"))
        await audit.initialize()
        agents = {f.faction_id: MahanianAgent() for f in minimal_scenario.factions}
        for f in minimal_scenario.factions:
            agents[f.faction_id].initialize(f)
        ref = GameReferee(scenario=minimal_scenario, agents=agents, audit=audit)
        return ref, audit

    return _asyncio.get_event_loop().run_until_complete(_make())


def test_rd_yield_doubled(referee_with_audit):
    ref, _ = referee_with_audit
    fid = list(ref.faction_states.keys())[0]
    fs = ref.faction_states[fid]
    # Simulate a deferred r_and_d return of 30 pts
    fs.deferred_returns = [{"faction_id": fid, "category": "r_and_d", "amount": 30, "turn_due": 1}]
    ref._replenish_budgets(turn=1)
    # With divisor 10: 30 // 10 = 3 pts
    assert fs.tech_tree.get("r_and_d", 0) == 3


def test_education_adds_budget(referee_with_audit):
    ref, _ = referee_with_audit
    fid = list(ref.faction_states.keys())[0]
    fs = ref.faction_states[fid]
    fs.tech_tree["education"] = 5  # 5 education pts
    # First replenish to get base budget (before we check the education bonus)
    ref._replenish_budgets(turn=1)
    # Education bonus should add +5 to current_budget beyond the base
    # (hegemony pool may or may not apply — just check that education pts were consumed as budget bonus)
    assert fs.current_budget >= fs.budget_per_turn + 5  # at minimum base + education bonus


@pytest.mark.asyncio
async def test_tech_unlock_valid(tmp_path, minimal_scenario):
    from output.audit import AuditTrail
    from engine.referee import GameReferee
    from agents.rule_based import MahanianAgent
    audit = AuditTrail(str(tmp_path / "ref_tech.db"))
    await audit.initialize()
    agents = {f.faction_id: MahanianAgent() for f in minimal_scenario.factions}
    for f in minimal_scenario.factions:
        agents[f.faction_id].initialize(f)
    ref = GameReferee(scenario=minimal_scenario, agents=agents, audit=audit)

    fid = minimal_scenario.factions[0].faction_id
    fs = ref.faction_states[fid]
    fs.tech_tree["r_and_d"] = 10  # enough to unlock trunk_launch (cost 2)

    decisions = {
        fid: Decision(
            phase=Phase.INVEST,
            faction_id=fid,
            investment=InvestmentAllocation(constellation=1.0, rationale="test"),
            tech_unlocks=["trunk_launch"],
        )
        for fid in ref.faction_states
    }
    await ref.resolve_investment(turn=1, decisions=decisions)

    assert "trunk_launch" in ref.faction_states[fid].unlocked_techs
    assert ref.faction_states[fid].tech_tree.get("r_and_d", 0) == 8  # 10 - 2


@pytest.mark.asyncio
async def test_tech_unlock_insufficient_rd_rejected(tmp_path, minimal_scenario):
    from output.audit import AuditTrail
    from engine.referee import GameReferee
    from agents.rule_based import MahanianAgent
    audit = AuditTrail(str(tmp_path / "ref_tech2.db"))
    await audit.initialize()
    agents = {f.faction_id: MahanianAgent() for f in minimal_scenario.factions}
    for f in minimal_scenario.factions:
        agents[f.faction_id].initialize(f)
    ref = GameReferee(scenario=minimal_scenario, agents=agents, audit=audit)

    fid = minimal_scenario.factions[0].faction_id
    fs = ref.faction_states[fid]
    fs.tech_tree["r_and_d"] = 1  # NOT enough for trunk_launch (cost 2)

    decisions = {
        fid: Decision(
            phase=Phase.INVEST,
            faction_id=fid,
            investment=InvestmentAllocation(constellation=1.0, rationale="test"),
            tech_unlocks=["trunk_launch"],
        )
        for fid in ref.faction_states
    }
    await ref.resolve_investment(turn=1, decisions=decisions)

    assert "trunk_launch" not in ref.faction_states[fid].unlocked_techs
    assert ref.faction_states[fid].tech_tree.get("r_and_d", 0) == 1  # unchanged


@pytest.mark.asyncio
async def test_kin_intercept_k_adds_asat_when_struck(tmp_path, minimal_scenario):
    from output.audit import AuditTrail
    from engine.referee import GameReferee
    from agents.rule_based import MahanianAgent
    audit = AuditTrail(str(tmp_path / "ref_mah.db"))
    await audit.initialize()
    agents = {f.faction_id: MahanianAgent() for f in minimal_scenario.factions}
    for f in minimal_scenario.factions:
        agents[f.faction_id].initialize(f)
    ref = GameReferee(scenario=minimal_scenario, agents=agents, audit=audit)

    attacker_fid = minimal_scenario.factions[0].faction_id
    target_fid = minimal_scenario.factions[1].faction_id
    ref.faction_states[attacker_fid].assets.asat_kinetic = 2
    ref.faction_states[attacker_fid].assets.leo_nodes = 5
    # Give target kin_intercept_k (emergency procurement on being struck)
    ref.faction_states[target_fid].unlocked_techs = ["kin_intercept_k"]
    ref.faction_states[target_fid].assets.leo_nodes = 20
    initial_asat = ref.faction_states[target_fid].assets.asat_kinetic

    approach = {
        "attacker_fid": attacker_fid,
        "target_fid": target_fid,
        "declared_turn": 1,
        "approach_type": "kinetic",
    }
    ref._resolve_kinetic_approach(approach)
    # kin_intercept_k should have added +1 to target's asat_kinetic
    assert ref.faction_states[target_fid].assets.asat_kinetic == initial_asat + 1
