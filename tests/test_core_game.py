# tests/test_core_game.py
import pytest
import copy
from pathlib import Path
from engine.core_game import CoreGame
from engine.action_space import ActionSpace
from engine.state import Phase
from scenarios.loader import load_scenario

SCENARIO = load_scenario(Path("scenarios/pacific_crossroads.yaml"))


def make_game() -> CoreGame:
    return CoreGame(SCENARIO)


def test_constructor_creates_faction_states():
    g = make_game()
    assert set(g.faction_states.keys()) == {"ussf", "nexus_corp", "pla_ssf", "russia_vks"}


def test_constructor_initial_turn():
    g = make_game()
    assert g.current_turn() == 1
    assert g.current_phase() == Phase.INVEST
    assert g.acting_faction_idx() == 0


def test_constructor_starting_assets():
    g = make_game()
    fs = g.faction_states["ussf"]
    assert fs.assets.leo_nodes == 30
    assert fs.assets.geo_nodes == 6


def test_constructor_coalition_dominance():
    g = make_game()
    dom = g.coalition_dominance
    assert "blue" in dom and "red" in dom
    total = sum(dom.values())
    assert abs(total - 1.0) < 0.01


def test_is_terminal_false_at_start():
    g = make_game()
    assert not g.is_terminal()


def test_legal_actions_invest_phase():
    g = make_game()
    actions = g.legal_actions(0)
    assert len(actions) == 100  # all INVEST portfolios legal at start
    assert all(0 <= a < 100 for a in actions)


def test_apply_action_wrong_faction_raises():
    g = make_game()
    with pytest.raises(ValueError, match="faction_idx"):
        g.apply_action(1, 0)  # faction[0] is acting, not faction[1]


def test_apply_invest_advances_faction():
    g = make_game()
    assert g.acting_faction_idx() == 0
    g.apply_action(0, 0)  # faction[0] submits invest action 0
    assert g.acting_faction_idx() == 1
    assert g.current_phase() == Phase.INVEST


def test_invest_phase_advances_to_ops():
    g = make_game()
    for i in range(4):
        g.apply_action(i, 0)  # all 4 factions submit same invest action
    assert g.current_phase() == Phase.OPERATIONS
    assert g.acting_faction_idx() == 0


def test_legal_actions_ops_phase():
    g = make_game()
    for i in range(4):
        g.apply_action(i, 0)
    actions = g.legal_actions(0)
    assert all(a >= 100 for a in actions)  # OPS range starts at 100


def _full_turn(g: CoreGame, invest_idx: int = 0, ops_idx: int = None, resp_idx: int = 0) -> None:
    """Submit one complete turn for all factions."""
    for i in range(4):
        g.apply_action(i, invest_idx)
    if ops_idx is None:
        ops_idx = g._action_space.OPS_OFFSET
    for i in range(4):
        g.apply_action(i, ops_idx)
    for i in range(4):
        g.apply_action(i, resp_idx + g._action_space.RESPONSE_OFFSET)


def test_investment_increases_assets():
    g = make_game()
    _full_turn(g, invest_idx=0)
    assert g.current_turn() == 2
    total_leo = sum(g.faction_states[fid].assets.leo_nodes for fid in g.faction_order)
    total_meo = sum(g.faction_states[fid].assets.meo_nodes for fid in g.faction_order)
    assert total_leo + total_meo > sum(
        SCENARIO.factions[i].starting_assets.leo_nodes + SCENARIO.factions[i].starting_assets.meo_nodes
        for i in range(4)
    )


def test_pending_kinetics_resolve_next_turn():
    g = make_game()
    _full_turn(g, invest_idx=0)
    g.pending_kinetics.append({
        "attacker_id": "pla_ssf",
        "target_faction_id": "ussf",
        "shell": "leo",
        "power": 3,
    })
    ussf_leo_before = g.faction_states["ussf"].assets.leo_nodes
    _full_turn(g, invest_idx=0)
    ussf_leo_after = g.faction_states["ussf"].assets.leo_nodes
    assert ussf_leo_after <= ussf_leo_before


def test_turn_advances_to_total():
    g = make_game()
    for _ in range(14):
        _full_turn(g, invest_idx=0)
    assert g.is_terminal()
