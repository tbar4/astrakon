# tests/test_tech_tree.py
import pytest
from engine.state import FactionState, FactionAssets
from engine.tech_tree import (
    TechNode, TECH_NODES, TRUNK_IDS,
    get_available_nodes, apply_passive_effects,
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


def test_trunk_nodes_available_at_start(mahanian_state):
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    assert "trunk_launch" in ids
    assert "trunk_capacity" in ids
    assert "trunk_budget" in ids


def test_trunk_nodes_require_rd_points(mahanian_state):
    nodes = get_available_nodes(mahanian_state, rd_points=1)
    # trunk nodes cost 2 pts each
    assert len(nodes) == 0


def test_branch_nodes_require_any_trunk(mahanian_state):
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    # No branch nodes without a trunk node unlocked
    assert "mah_strike" not in ids
    assert "mah_deterrence" not in ids


def test_branch_nodes_available_after_trunk(mahanian_state):
    mahanian_state.unlocked_techs = ["trunk_launch"]
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    assert "mah_strike" in ids
    assert "mah_deterrence" in ids


def test_branch_nodes_require_archetype_match(mahanian_state):
    mahanian_state.unlocked_techs = ["trunk_launch"]
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    # commercial_broker nodes not available to mahanian
    assert "com_market" not in ids
    assert "gz_masking" not in ids
    assert "rog_debris" not in ids


def test_already_unlocked_node_not_available(mahanian_state):
    mahanian_state.unlocked_techs = ["trunk_launch"]
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    assert "trunk_launch" not in ids


def test_tier3_requires_specific_tier2_prereq(mahanian_state):
    # mah_escalation requires mah_strike, not just any trunk
    mahanian_state.unlocked_techs = ["trunk_launch", "mah_deterrence"]
    nodes = get_available_nodes(mahanian_state, rd_points=10)
    ids = [n.id for n in nodes]
    assert "mah_escalation" not in ids  # needs mah_strike, not mah_deterrence
    assert "mah_projection" in ids       # needs mah_deterrence ✓


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
    assert result["launch_capacity_bonus"] == 0


def test_apply_passive_effects_budget_replenish_trunk_capacity(mahanian_state):
    mahanian_state.unlocked_techs = ["trunk_capacity"]
    result = apply_passive_effects(mahanian_state, "budget_replenish")
    assert result["launch_capacity_bonus"] == 1


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


def test_apply_passive_effects_mah_strike(mahanian_state):
    mahanian_state.unlocked_techs = ["mah_strike"]
    result = apply_passive_effects(mahanian_state, "asat_kinetic")
    assert result["nodes_destroyed_bonus"] == 1


def test_apply_passive_effects_rog_shock_free_strike(mahanian_state):
    mahanian_state.unlocked_techs = ["rog_shock"]
    mahanian_state.rog_shock_used = False
    result = apply_passive_effects(mahanian_state, "asat_kinetic")
    assert result["free_strike"] is True


def test_apply_passive_effects_rog_shock_already_used(mahanian_state):
    mahanian_state.unlocked_techs = ["rog_shock"]
    mahanian_state.rog_shock_used = True
    result = apply_passive_effects(mahanian_state, "asat_kinetic")
    assert result["free_strike"] is False


def test_apply_passive_effects_adversary_estimate_defaults(mahanian_state):
    result = apply_passive_effects(mahanian_state, "adversary_estimate")
    assert result["asat_deniable_visible"] is True
    assert result["leo_visibility_fraction"] == 1.0


def test_apply_passive_effects_gz_masking(mahanian_state):
    mahanian_state.unlocked_techs = ["gz_masking"]
    result = apply_passive_effects(mahanian_state, "adversary_estimate")
    assert result["asat_deniable_visible"] is False


def test_apply_passive_effects_gz_ghost(mahanian_state):
    mahanian_state.unlocked_techs = ["gz_ghost"]
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
    mahanian_state.unlocked_techs = ["gz_influence"]
    result = apply_passive_effects(mahanian_state, "gray_zone_loyalty")
    assert result["loyalty_reduction"] == pytest.approx(0.15)


def test_all_19_nodes_defined():
    assert len(TECH_NODES) == 19


def test_trunk_ids_constant():
    assert set(TRUNK_IDS) == {"trunk_launch", "trunk_capacity", "trunk_budget"}


def test_apply_passive_effects_jamming_radius(mahanian_state):
    result = apply_passive_effects(mahanian_state, "jamming_radius")
    assert result["extend_to_adjacent"] is False
    mahanian_state.unlocked_techs = ["gz_jamming"]
    result = apply_passive_effects(mahanian_state, "jamming_radius")
    assert result["extend_to_adjacent"] is True


def test_apply_passive_effects_rog_ascent_active(mahanian_state):
    result = apply_passive_effects(mahanian_state, "rog_ascent_active")
    assert result["same_turn_resolve"] is False
    mahanian_state.unlocked_techs = ["rog_ascent"]
    result = apply_passive_effects(mahanian_state, "rog_ascent_active")
    assert result["same_turn_resolve"] is True


def test_apply_passive_effects_unknown_context_raises(mahanian_state):
    with pytest.raises(ValueError, match="Unknown tech effect context"):
        apply_passive_effects(mahanian_state, "nonexistent_context")
