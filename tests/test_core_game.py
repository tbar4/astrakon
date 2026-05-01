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
