# tests/test_tech_tree.py
import pytest
from engine.state import FactionState, FactionAssets
from engine.tech_tree import (
    TechNode, TECH_NODES, TRUNK_IDS,
    get_available_nodes, apply_passive_effects, effective_cost,
)


@pytest.fixture
def mahanian_state():
    return FactionState(
        faction_id="ussf", name="USSF",
        budget_per_turn=100, current_budget=100,
        archetype="mahanian",
        assets=FactionAssets(
            leo_nodes=10, launch_capacity=2,
            meo_nodes=0, geo_nodes=0, cislunar_nodes=0
        ),
    )


@pytest.fixture
def gray_zone_state():
    return FactionState(
        faction_id="gz_faction", name="GZ",
        budget_per_turn=80, current_budget=80,
        archetype="gray_zone",
        assets=FactionAssets(leo_nodes=5, launch_capacity=1),
    )


def test_trunk_nodes_available_at_start(mahanian_state):
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    assert "trunk_launch" in ids
    assert "trunk_capacity" in ids
    assert "trunk_budget" in ids
    assert "trunk_sda" in ids
    assert "trunk_resilience" in ids


def test_trunk_nodes_require_rd_points(mahanian_state):
    nodes = get_available_nodes(mahanian_state, rd_points=1)
    # trunk nodes cost 2 pts each (1 pt with discount, but no discount on trunk)
    assert len(nodes) == 0


def test_threat_tree_t1_nodes_require_any_trunk(mahanian_state):
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    # No threat-tree T1 nodes until a trunk is unlocked
    assert "kin_ground_strike" not in ids
    assert "nk_dazzle" not in ids
    assert "ew_jamming" not in ids
    assert "cyber_intrusion" not in ids


def test_threat_tree_t1_nodes_available_after_trunk(mahanian_state):
    mahanian_state.unlocked_techs = ["trunk_launch"]
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    # All 4 threat-tree T1 nodes now accessible (no archetype gating)
    assert "kin_ground_strike" in ids
    assert "nk_dazzle" in ids
    assert "ew_jamming" in ids
    assert "cyber_intrusion" in ids


def test_all_trees_open_to_all_archetypes(gray_zone_state):
    # gray_zone faction can access kinetic tree nodes
    gray_zone_state.unlocked_techs = ["trunk_budget"]
    nodes = get_available_nodes(gray_zone_state, rd_points=10)
    ids = [n.id for n in nodes]
    assert "kin_ground_strike" in ids   # kinetic T1 available to gray_zone
    assert "nk_dazzle" in ids           # non-kinetic T1 available to gray_zone
    assert "cyber_intrusion" in ids     # cyber T1 available to gray_zone
    assert "ew_jamming" in ids          # EW T1 (discounted) available to gray_zone


def test_archetype_discount_reduces_cost(mahanian_state):
    node = next(n for n in TECH_NODES if n.id == "kin_ground_strike")
    assert node.archetype_discount == "mahanian"
    # Mahanian gets -1 discount on kinetic nodes
    assert effective_cost(node, "mahanian") == node.cost - 1
    # Other archetypes pay full price
    assert effective_cost(node, "gray_zone") == node.cost
    assert effective_cost(node, None) == node.cost


def test_archetype_discount_minimum_one(mahanian_state):
    # Cost can never drop below 1
    node = next(n for n in TECH_NODES if n.id == "kin_ground_strike")
    node_cost_1 = TechNode(
        id="test", name="test", desc="", tier=2, cost=1,
        prereqs=[], archetype_discount="mahanian",
        effect_type="test",
    )
    assert effective_cost(node_cost_1, "mahanian") == 1


def test_already_unlocked_node_not_available(mahanian_state):
    mahanian_state.unlocked_techs = ["trunk_launch"]
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    assert "trunk_launch" not in ids


def test_t2_node_requires_specific_t1_prereq(mahanian_state):
    # kin_rapid_ascent requires kin_da_asat, not just kin_ground_strike
    mahanian_state.unlocked_techs = ["trunk_launch", "kin_ground_strike", "kin_deterrence"]
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    assert "kin_rapid_ascent" not in ids   # needs kin_da_asat
    assert "kin_intercept_k" in ids        # needs kin_deterrence ✓


def test_apply_passive_effects_leo_deploy_default(mahanian_state):
    result = apply_passive_effects(mahanian_state, "leo_deploy")
    assert result == {"cost_divisor": 5}


def test_apply_passive_effects_leo_deploy_with_trunk_launch(mahanian_state):
    mahanian_state.unlocked_techs = ["trunk_launch"]
    result = apply_passive_effects(mahanian_state, "leo_deploy")
    assert result == {"cost_divisor": 4}


def test_apply_passive_effects_budget_replenish_trunk_budget(mahanian_state):
    mahanian_state.unlocked_techs = ["trunk_budget"]
    result = apply_passive_effects(mahanian_state, "budget_replenish")
    assert result["budget_bonus"] == 8


def test_apply_passive_effects_budget_replenish_trunk_capacity(mahanian_state):
    # trunk_capacity is a one-time unlock effect, not a per-turn passive
    mahanian_state.unlocked_techs = ["trunk_capacity"]
    result = apply_passive_effects(mahanian_state, "budget_replenish")
    assert result["budget_bonus"] == 0


def test_apply_passive_effects_budget_replenish_com_revenue(mahanian_state):
    mahanian_state.assets.launch_capacity = 3
    mahanian_state.unlocked_techs = ["com_revenue"]
    result = apply_passive_effects(mahanian_state, "budget_replenish")
    assert result["budget_bonus"] == 9  # 3 * 3


def test_apply_passive_effects_budget_replenish_com_economics(mahanian_state):
    mahanian_state.assets.leo_nodes = 20
    mahanian_state.assets.meo_nodes = 4
    mahanian_state.unlocked_techs = ["com_economics"]
    result = apply_passive_effects(mahanian_state, "budget_replenish")
    # total_nodes = 24, min(24*0.5, 20) = 12
    assert result["budget_bonus"] == 12


def test_apply_passive_effects_com_economics_capped(mahanian_state):
    mahanian_state.assets.leo_nodes = 80
    mahanian_state.unlocked_techs = ["com_economics"]
    result = apply_passive_effects(mahanian_state, "budget_replenish")
    assert result["budget_bonus"] == 20  # capped at 20


def test_apply_passive_effects_asat_kinetic_defaults(mahanian_state):
    result = apply_passive_effects(mahanian_state, "asat_kinetic")
    assert result["nodes_destroyed_bonus"] == 0
    assert result["debris_multiplier"] == 1.0
    assert result["free_strike"] is False


def test_apply_passive_effects_kin_da_asat(mahanian_state):
    mahanian_state.unlocked_techs = ["kin_da_asat"]
    result = apply_passive_effects(mahanian_state, "asat_kinetic")
    assert result["nodes_destroyed_bonus"] == 1


def test_apply_passive_effects_nk_debris_doctrine(mahanian_state):
    mahanian_state.unlocked_techs = ["nk_debris_doctrine"]
    result = apply_passive_effects(mahanian_state, "asat_kinetic")
    assert result["debris_multiplier"] == 2.0


def test_apply_passive_effects_kin_rapid_ascent_free_strike(mahanian_state):
    mahanian_state.unlocked_techs = ["kin_rapid_ascent"]
    mahanian_state.rog_shock_used = False
    result = apply_passive_effects(mahanian_state, "asat_kinetic")
    assert result["free_strike"] is True


def test_apply_passive_effects_kin_rapid_ascent_already_used(mahanian_state):
    mahanian_state.unlocked_techs = ["kin_rapid_ascent"]
    mahanian_state.rog_shock_used = True
    result = apply_passive_effects(mahanian_state, "asat_kinetic")
    assert result["free_strike"] is False


def test_apply_passive_effects_adversary_estimate_defaults(mahanian_state):
    result = apply_passive_effects(mahanian_state, "adversary_estimate")
    assert result["asat_deniable_visible"] is True
    assert result["leo_visibility_fraction"] == 1.0


def test_apply_passive_effects_ew_signature_mask_hides_deniable(mahanian_state):
    mahanian_state.unlocked_techs = ["ew_signature_mask"]
    result = apply_passive_effects(mahanian_state, "adversary_estimate")
    assert result["asat_deniable_visible"] is False


def test_apply_passive_effects_ew_signature_mask_reduces_leo_visibility(mahanian_state):
    mahanian_state.unlocked_techs = ["ew_signature_mask"]
    result = apply_passive_effects(mahanian_state, "adversary_estimate")
    assert result["leo_visibility_fraction"] == 0.75


def test_apply_passive_effects_market_share(mahanian_state):
    result = apply_passive_effects(mahanian_state, "market_share")
    assert result["include_meo"] is False
    mahanian_state.unlocked_techs = ["com_network"]
    result = apply_passive_effects(mahanian_state, "market_share")
    assert result["include_meo"] is True


def test_apply_passive_effects_gray_zone_loyalty(mahanian_state):
    result = apply_passive_effects(mahanian_state, "gray_zone_loyalty")
    assert result["loyalty_reduction"] == pytest.approx(0.05)
    mahanian_state.unlocked_techs = ["ew_deep_influence"]
    result = apply_passive_effects(mahanian_state, "gray_zone_loyalty")
    assert result["loyalty_reduction"] == pytest.approx(0.15)


def test_apply_passive_effects_jamming_radius(mahanian_state):
    result = apply_passive_effects(mahanian_state, "jamming_radius")
    assert result["extend_to_adjacent"] is False
    mahanian_state.unlocked_techs = ["ew_wideband"]
    result = apply_passive_effects(mahanian_state, "jamming_radius")
    assert result["extend_to_adjacent"] is True


def test_apply_passive_effects_resilience(mahanian_state):
    result = apply_passive_effects(mahanian_state, "resilience")
    assert result["damage_reduction"] == 0
    mahanian_state.unlocked_techs = ["trunk_resilience"]
    result = apply_passive_effects(mahanian_state, "resilience")
    assert result["damage_reduction"] == 1


def test_apply_passive_effects_ew_spoofing(mahanian_state):
    result = apply_passive_effects(mahanian_state, "ew_spoofing")
    assert result["intercept_accuracy_penalty"] == pytest.approx(0.0)
    mahanian_state.unlocked_techs = ["ew_spoofing"]
    result = apply_passive_effects(mahanian_state, "ew_spoofing")
    assert result["intercept_accuracy_penalty"] == pytest.approx(0.2)


def test_all_29_nodes_defined():
    assert len(TECH_NODES) == 29


def test_trunk_ids_constant():
    assert set(TRUNK_IDS) == {"trunk_launch", "trunk_capacity", "trunk_budget", "trunk_sda", "trunk_resilience"}


def test_apply_passive_effects_unknown_context_raises(mahanian_state):
    with pytest.raises(ValueError, match="Unknown tech effect context"):
        apply_passive_effects(mahanian_state, "nonexistent_context")


def test_geo_deploy_nk_power_projection(mahanian_state):
    result = apply_passive_effects(mahanian_state, "geo_deploy")
    assert result["pts_multiplier"] == pytest.approx(1.0)
    mahanian_state.unlocked_techs = ["nk_power_projection"]
    result = apply_passive_effects(mahanian_state, "geo_deploy")
    assert result["pts_multiplier"] == pytest.approx(1.25)


def test_commercial_income_com_market(mahanian_state):
    result = apply_passive_effects(mahanian_state, "commercial_income")
    assert result["income_multiplier"] == pytest.approx(1.0)
    mahanian_state.unlocked_techs = ["com_market"]
    result = apply_passive_effects(mahanian_state, "commercial_income")
    assert result["income_multiplier"] == pytest.approx(1.6)
