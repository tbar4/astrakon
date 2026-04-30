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
