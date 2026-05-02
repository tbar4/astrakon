import pytest
from engine.simulation import (
    SimulationEngine, InvestmentResolver, SDAFilter, ConflictResolver
)
from engine.state import FactionAssets, FactionState, InvestmentAllocation


@pytest.fixture
def base_assets():
    return FactionAssets(leo_nodes=24, sda_sensors=8, launch_capacity=2)


@pytest.fixture
def base_state(base_assets):
    return FactionState(
        faction_id="ussf", name="US Space Force",
        budget_per_turn=100, current_budget=100,
        assets=base_assets
    )


def test_investment_resolver_queues_deferred_returns():
    resolver = InvestmentResolver()
    alloc = InvestmentAllocation(r_and_d=0.30, constellation=0.70, rationale="test")
    result = resolver.resolve(faction_id="ussf", budget=100, allocation=alloc, turn=1)
    # Constellation returns immediately; R&D is deferred
    assert result.immediate_assets.leo_nodes > 0
    assert any(r["category"] == "r_and_d" for r in result.deferred_returns)


def test_investment_resolver_constellation_adds_nodes():
    resolver = InvestmentResolver()
    alloc = InvestmentAllocation(constellation=1.0, rationale="all in")
    result = resolver.resolve(faction_id="ussf", budget=100, allocation=alloc, turn=1)
    assert result.immediate_assets.leo_nodes > 0


def test_sda_filter_low_investment_obscures_adversary():
    sda_filter = SDAFilter()
    adversary = FactionAssets(leo_nodes=50, asat_kinetic=10, asat_deniable=5)
    filtered = sda_filter.filter(adversary_assets=adversary, observer_sda_level=0.1)
    # At low SDA, deniable assets are invisible
    assert filtered.asat_deniable == 0

def test_sda_filter_high_investment_reveals_adversary():
    sda_filter = SDAFilter()
    adversary = FactionAssets(leo_nodes=50, asat_kinetic=10, asat_deniable=5)
    filtered = sda_filter.filter(adversary_assets=adversary, observer_sda_level=0.9)
    assert filtered.asat_kinetic > 0


def test_orbital_dominance_calculation():
    engine = SimulationEngine()
    faction_assets = {
        "ussf": FactionAssets(leo_nodes=60, geo_nodes=8),
        "pla":  FactionAssets(leo_nodes=20, geo_nodes=2),
    }
    dominance = engine.compute_orbital_dominance("ussf", faction_assets)
    assert dominance > 0.5


from engine.simulation import DebrisEngine

def test_debris_engine_add_debris_to_shell():
    engine = DebrisEngine()
    fields = engine.add_debris({}, "leo", 0.3)
    assert abs(fields["leo"] - 0.3) < 0.01

def test_debris_engine_clamps_at_1():
    engine = DebrisEngine()
    fields = engine.add_debris({"leo": 0.8}, "leo", 0.5)
    assert fields["leo"] == 1.0

def test_debris_engine_decay_reduces_severity():
    engine = DebrisEngine()
    fields = {"leo": 0.5, "geo": 0.3}
    decayed = engine.decay(fields)
    assert decayed["leo"] < 0.5
    assert decayed["geo"] < 0.3

def test_debris_engine_leo_decays_faster_than_geo():
    engine = DebrisEngine()
    fields = {"leo": 0.5, "geo": 0.5}
    decayed = engine.decay(fields)
    assert decayed["leo"] < decayed["geo"]

def test_debris_engine_kessler_shell_unusable():
    engine = DebrisEngine()
    penalty = engine.operational_penalty({"leo": 0.9}, "leo")
    assert penalty >= 1.0

def test_debris_engine_apply_effects_damages_nodes():
    import random
    random.seed(42)
    engine = DebrisEngine()
    from engine.state import FactionState, FactionAssets
    faction_states = {
        "ussf": FactionState(faction_id="ussf", name="USSF",
                             budget_per_turn=100, current_budget=100,
                             assets=FactionAssets(leo_nodes=20)),
    }
    fields = {"leo": 0.9}  # near Kessler
    updated, log = engine.apply_debris_effects(faction_states, fields)
    assert updated["ussf"].assets.leo_nodes < 20
    assert len(log) > 0


from engine.simulation import AccessWindowEngine, ManeuverBudgetEngine

def test_access_window_leo_alternates():
    engine = AccessWindowEngine()
    assert engine.compute(1)["leo"] is True
    assert engine.compute(2)["leo"] is False
    assert engine.compute(3)["leo"] is True

def test_access_window_geo_always_open():
    engine = AccessWindowEngine()
    for turn in range(1, 10):
        assert engine.compute(turn)["geo"] is True

def test_access_window_cislunar_every_four():
    engine = AccessWindowEngine()
    assert engine.compute(1)["cislunar"] is True
    assert engine.compute(2)["cislunar"] is False
    assert engine.compute(5)["cislunar"] is True

def test_maneuver_budget_kinetic_cost():
    engine = ManeuverBudgetEngine()
    from engine.state import FactionState, FactionAssets
    fs = FactionState(faction_id="x", name="X", budget_per_turn=100,
                      current_budget=100, assets=FactionAssets(), maneuver_budget=10.0)
    ok, msg = engine.spend(fs, "kinetic_intercept")
    assert ok
    assert fs.maneuver_budget < 10.0

def test_maneuver_budget_insufficient_returns_false():
    engine = ManeuverBudgetEngine()
    from engine.state import FactionState, FactionAssets
    fs = FactionState(faction_id="x", name="X", budget_per_turn=100,
                      current_budget=100, assets=FactionAssets(), maneuver_budget=0.5)
    ok, msg = engine.spend(fs, "kinetic_intercept")
    assert not ok

def test_maneuver_budget_replenish():
    engine = ManeuverBudgetEngine()
    from engine.state import FactionState, FactionAssets
    fs = FactionState(faction_id="x", name="X", budget_per_turn=100,
                      current_budget=100, assets=FactionAssets(launch_capacity=2),
                      maneuver_budget=3.0)
    engine.replenish(fs)
    assert fs.maneuver_budget > 3.0


def test_trunk_launch_reduces_leo_cost_divisor():
    resolver = InvestmentResolver()
    alloc = InvestmentAllocation(constellation=1.0, rationale="test")
    result_default = resolver.resolve("ussf", 100, alloc, 1, unlocked_techs=[])
    assert result_default.immediate_assets.leo_nodes == 20  # 100 // 5
    result_tech = resolver.resolve("ussf", 100, alloc, 1, unlocked_techs=["trunk_launch"])
    assert result_tech.immediate_assets.leo_nodes == 25  # 100 // 4


def test_nk_power_projection_boosts_geo_nodes():
    resolver = InvestmentResolver()
    alloc = InvestmentAllocation(geo_deployment=1.0, rationale="test")
    result_default = resolver.resolve("ussf", 100, alloc, 1, unlocked_techs=[])
    assert result_default.immediate_assets.geo_nodes == 4  # 100 // 25
    result_tech = resolver.resolve("ussf", 100, alloc, 1, unlocked_techs=["nk_power_projection"])
    assert result_tech.immediate_assets.geo_nodes == 5  # int(100*1.25)=125 // 25


def test_com_market_generates_commercial_income_deferred():
    resolver = InvestmentResolver()
    alloc = InvestmentAllocation(commercial=0.5, constellation=0.5, rationale="test")
    result = resolver.resolve("ussf", 100, alloc, 1, unlocked_techs=["com_market"])
    commercial_deferred = [r for r in result.deferred_returns if r["category"] == "commercial_income"]
    assert len(commercial_deferred) == 1
    assert commercial_deferred[0]["amount"] == 80  # 50 * 1.6


def test_commercial_income_default_multiplier():
    resolver = InvestmentResolver()
    alloc = InvestmentAllocation(commercial=0.5, constellation=0.5, rationale="test")
    result = resolver.resolve("ussf", 100, alloc, 1, unlocked_techs=[])
    commercial_deferred = [r for r in result.deferred_returns if r["category"] == "commercial_income"]
    assert len(commercial_deferred) == 1
    assert commercial_deferred[0]["amount"] == 50  # 50 * 1.0


def test_ew_signature_mask_hides_asat_deniable():
    sda = SDAFilter()
    adversary = FactionAssets(leo_nodes=20, asat_deniable=5)
    result = sda.filter(adversary, observer_sda_level=0.9)
    assert result.asat_deniable > 0
    result_masked = sda.filter(adversary, observer_sda_level=0.9,
                               adversary_tech_mods={"asat_deniable_visible": False,
                                                    "leo_visibility_fraction": 1.0})
    assert result_masked.asat_deniable == 0


def test_ew_signature_mask_reduces_visible_leo_nodes():
    sda = SDAFilter()
    adversary = FactionAssets(leo_nodes=20)
    result_normal = sda.filter(adversary, observer_sda_level=1.0)
    result_ghost = sda.filter(adversary, observer_sda_level=1.0,
                               adversary_tech_mods={"asat_deniable_visible": True,
                                                    "leo_visibility_fraction": 0.75})
    assert result_ghost.leo_nodes == int(result_normal.leo_nodes * 0.75)


def test_kin_da_asat_adds_nodes_destroyed_bonus():
    resolver = ConflictResolver()
    attacker = FactionAssets(asat_kinetic=1, sda_sensors=24)
    target = FactionAssets(leo_nodes=50)
    result_default = resolver.resolve_kinetic_asat(attacker, target, attacker_sda_level=1.0)
    result_strike = resolver.resolve_kinetic_asat(
        attacker, target, attacker_sda_level=1.0,
        attacker_tech_mods={"nodes_destroyed_bonus": 1, "debris_multiplier": 1.0, "free_strike": False}
    )
    assert result_strike["nodes_destroyed"] == result_default["nodes_destroyed"] + 1


def test_kin_cascade_doctrine_immune_faction_skips_adjacent_shell_damage():
    import random as _random
    from engine.simulation import DebrisEngine
    engine = DebrisEngine()
    faction_states = {
        "immune": FactionState(faction_id="immune", name="I",
                               budget_per_turn=0, current_budget=0,
                               assets=FactionAssets(leo_nodes=100)),
        "normal": FactionState(faction_id="normal", name="N",
                               budget_per_turn=0, current_budget=0,
                               assets=FactionAssets(leo_nodes=100)),
    }
    # Force damage to occur: seed RNG so random.random() < penalty
    _random.seed(0)
    # LEO has debris pressure; MEO is Kessler (adjacent to LEO)
    fields = {"leo": 0.8, "meo": 1.0}  # leo debris causes damage; meo is Kessler
    updated, _ = engine.apply_debris_effects(
        faction_states, fields,
        cascade_immune_factions={"immune"},
        kessler_shells={"meo"},
    )
    # Immune faction should NOT take damage in LEO (adjacent to Kessler MEO)
    assert updated["immune"].assets.leo_nodes == 100
    # Normal faction SHOULD take damage
    assert updated["normal"].assets.leo_nodes < 100
