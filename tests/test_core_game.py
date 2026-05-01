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
