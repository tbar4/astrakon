import pytest
from engine.state import (
    Phase, InvestmentAllocation, OperationalAction, ResponseDecision,
    Decision, FactionAssets, FactionState, CoalitionState,
    GameStateSnapshot, CrisisEvent, Recommendation,
)


def test_investment_allocation_sums_to_one():
    alloc = InvestmentAllocation(
        r_and_d=0.30, constellation=0.20, launch_capacity=0.10,
        commercial=0.10, influence_ops=0.10, education=0.10,
        covert=0.05, diplomacy=0.05, rationale="test"
    )
    assert abs(alloc.total() - 1.0) < 0.001


def test_investment_allocation_rejects_over_budget():
    with pytest.raises(ValueError):
        InvestmentAllocation(
            r_and_d=0.60, constellation=0.60,
            rationale="too much"
        )


def test_investment_allocation_rejects_negative():
    with pytest.raises(ValueError, match="must be >= 0.0"):
        InvestmentAllocation(r_and_d=-0.10, constellation=0.50, rationale="negative")


def test_faction_assets_default_empty():
    assets = FactionAssets()
    assert assets.leo_nodes == 0
    assert assets.sda_sensors == 0


def test_decision_invest_phase():
    alloc = InvestmentAllocation(
        r_and_d=0.50, constellation=0.50, rationale="test"
    )
    decision = Decision(phase=Phase.INVEST, faction_id="ussf", investment=alloc)
    assert decision.phase == Phase.INVEST
    assert decision.investment.r_and_d == 0.50


def test_game_state_snapshot_serializes():
    snapshot = GameStateSnapshot(
        turn=1, phase=Phase.INVEST, faction_id="ussf",
        faction_state=FactionState(
            faction_id="ussf", name="US Space Force",
            budget_per_turn=100, current_budget=100,
            assets=FactionAssets()
        ),
        ally_states={}, adversary_estimates={}, coalition_states={},
        available_actions=["allocate_budget"],
    )
    data = snapshot.model_dump()
    assert data["turn"] == 1
    assert data["faction_id"] == "ussf"


def test_faction_state_has_maneuver_budget():
    fs = FactionState(faction_id="x", name="X", budget_per_turn=100,
                      current_budget=100, assets=FactionAssets())
    assert fs.maneuver_budget == 10.0


def test_faction_state_has_cognitive_penalty():
    fs = FactionState(faction_id="x", name="X", budget_per_turn=100,
                      current_budget=100, assets=FactionAssets())
    assert fs.cognitive_penalty == 0.0


def test_game_state_snapshot_has_debris_fields():
    snap = GameStateSnapshot(
        turn=1, phase=Phase.INVEST, faction_id="x",
        faction_state=FactionState(faction_id="x", name="X",
                                   budget_per_turn=100, current_budget=100,
                                   assets=FactionAssets()),
        ally_states={}, adversary_estimates={}, coalition_states={},
        available_actions=[],
    )
    assert snap.debris_fields == {}
    assert snap.access_windows == {"leo": True, "meo": True, "geo": True, "cislunar": True}
    assert snap.escalation_rung == 0


def test_faction_state_has_archetype_field():
    fs = FactionState(
        faction_id="ussf", name="USSF",
        budget_per_turn=100, current_budget=100,
        archetype="mahanian",
        assets=FactionAssets(),
    )
    assert fs.archetype == "mahanian"


def test_faction_state_archetype_defaults_empty():
    fs = FactionState(
        faction_id="ussf", name="USSF",
        budget_per_turn=100, current_budget=100,
        assets=FactionAssets(),
    )
    # Task 1 added archetype as Optional[str] = None; None is acceptable here
    assert fs.archetype is None or fs.archetype == ""


def test_faction_state_has_unlocked_techs():
    fs = FactionState(
        faction_id="ussf", name="USSF",
        budget_per_turn=100, current_budget=100,
        assets=FactionAssets(),
    )
    assert fs.unlocked_techs == []


def test_faction_state_has_rog_shock_used():
    fs = FactionState(
        faction_id="ussf", name="USSF",
        budget_per_turn=100, current_budget=100,
        assets=FactionAssets(),
    )
    assert fs.rog_shock_used is False


def test_decision_has_tech_unlocks():
    from engine.state import Phase, InvestmentAllocation
    d = Decision(
        phase=Phase.INVEST,
        faction_id="ussf",
        investment=InvestmentAllocation(constellation=1.0, rationale="test"),
        tech_unlocks=["trunk_launch"],
    )
    assert d.tech_unlocks == ["trunk_launch"]


def test_decision_tech_unlocks_defaults_empty():
    from engine.state import Phase, InvestmentAllocation
    d = Decision(
        phase=Phase.INVEST,
        faction_id="ussf",
        investment=InvestmentAllocation(constellation=1.0, rationale="test"),
    )
    assert d.tech_unlocks == []
