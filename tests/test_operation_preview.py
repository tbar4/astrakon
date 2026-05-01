# tests/test_operation_preview.py
import pytest
from engine.preview import OperationPreview, PreviewEngine
from engine.state import FactionState, FactionAssets


def _make_faction(
    faction_id="ussf",
    asat_kinetic=2, asat_deniable=0, ew_jammers=0,
    leo_nodes=5, meo_nodes=0, geo_nodes=0, cislunar_nodes=0,
    maneuver_budget=10.0, sda_sensors=12,
    unlocked_techs=None, coalition_id="usa",
) -> FactionState:
    return FactionState(
        faction_id=faction_id, name=faction_id.upper(),
        budget_per_turn=100, current_budget=100,
        assets=FactionAssets(
            asat_kinetic=asat_kinetic, asat_deniable=asat_deniable,
            ew_jammers=ew_jammers, leo_nodes=leo_nodes, meo_nodes=meo_nodes,
            geo_nodes=geo_nodes, cislunar_nodes=cislunar_nodes, sda_sensors=sda_sensors,
        ),
        maneuver_budget=maneuver_budget,
        unlocked_techs=unlocked_techs or [],
        coalition_id=coalition_id,
        coalition_loyalty=0.8,
        archetype="mahanian",
    )


ENGINE = PreviewEngine()
ALL_WINDOWS_OPEN = {"leo": True, "meo": True, "geo": True, "cislunar": True}


def test_kinetic_intercept_available():
    attacker = _make_faction(asat_kinetic=2)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is True
    assert p.dv_cost == 4.0
    assert p.transit_turns == 2
    assert p.nodes_destroyed_estimate > 0


def test_kinetic_intercept_no_asat():
    attacker = _make_faction(asat_kinetic=0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False
    assert p.unavailable_reason != ""


def test_kinetic_intercept_insufficient_dv():
    attacker = _make_faction(asat_kinetic=2, maneuver_budget=1.0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False


def test_kinetic_intercept_no_target():
    attacker = _make_faction(asat_kinetic=2)
    p = ENGINE.compute("task_assets", "intercept", attacker, None, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False


def test_kinetic_intercept_target_no_nodes():
    attacker = _make_faction(asat_kinetic=2)
    target = _make_faction(faction_id="pla", leo_nodes=0, meo_nodes=0, geo_nodes=0, cislunar_nodes=0, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False
    assert "no orbital" in p.unavailable_reason.lower()


def test_kinetic_intercept_access_window_closed():
    attacker = _make_faction(asat_kinetic=2)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    windows = {"leo": False, "meo": True, "geo": True, "cislunar": True}
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {}, windows, 0)
    assert p.available is True
    assert "ACCESS WINDOW" in p.effect_summary


def test_kinetic_debris_capped_at_one():
    attacker = _make_faction(asat_kinetic=5)
    target = _make_faction(faction_id="pla", leo_nodes=20, coalition_id="china")
    p = ENGINE.compute("task_assets", "intercept", attacker, target, {"leo": 0.95}, ALL_WINDOWS_OPEN, 0)
    assert p.debris_estimate <= 1.0


def test_deniable_gray_zone():
    attacker = _make_faction(asat_deniable=3, asat_kinetic=0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("gray_zone", "", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is True
    assert p.dv_cost == 2.0
    assert p.transit_turns == 1
    assert p.nodes_destroyed_min == 1
    assert p.nodes_destroyed_max == 3


def test_ew_gray_zone():
    attacker = _make_faction(ew_jammers=2, asat_deniable=0, asat_kinetic=0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("gray_zone", "", attacker, target, {"leo": 0.3}, ALL_WINDOWS_OPEN, 0)
    assert p.available is True
    assert p.transit_turns == 0
    assert p.dv_cost == 0.0
    assert p.nodes_destroyed_estimate == 0
    assert p.debris_estimate == pytest.approx(0.3)  # no change


def test_gray_zone_no_assets():
    attacker = _make_faction(asat_deniable=0, ew_jammers=0, asat_kinetic=0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    p = ENGINE.compute("gray_zone", "", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert p.available is False


def test_preview_engine_does_not_mutate_maneuver_budget():
    attacker = _make_faction(asat_kinetic=2, maneuver_budget=10.0)
    target = _make_faction(faction_id="pla", leo_nodes=5, coalition_id="china")
    ENGINE.compute("task_assets", "intercept", attacker, target, {}, ALL_WINDOWS_OPEN, 0)
    assert attacker.maneuver_budget == 10.0
