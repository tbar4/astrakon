# tests/test_openspiel_env.py
import pytest
import pyspiel
import engine.openspiel_env  # triggers registration on import
from engine.state import Phase


def test_game_loads():
    game = pyspiel.load_game("astrakon", {"scenario_path": "scenarios/pacific_crossroads.yaml"})
    assert game is not None


def test_num_players():
    game = pyspiel.load_game("astrakon", {"scenario_path": "scenarios/pacific_crossroads.yaml"})
    assert game.num_players() == 4


def test_num_distinct_actions():
    game = pyspiel.load_game("astrakon", {"scenario_path": "scenarios/pacific_crossroads.yaml"})
    assert game.num_distinct_actions() > 100


def test_new_initial_state():
    game = pyspiel.load_game("astrakon", {"scenario_path": "scenarios/pacific_crossroads.yaml"})
    state = game.new_initial_state()
    assert state is not None
    assert not state.is_terminal()


def _make_state():
    game = pyspiel.load_game("astrakon", {"scenario_path": "scenarios/pacific_crossroads.yaml"})
    return game.new_initial_state()


def test_current_player_not_simultaneous():
    state = _make_state()
    assert state.current_player() >= 0


def test_legal_actions_nonempty():
    state = _make_state()
    p = state.current_player()
    actions = state.legal_actions(p)
    assert len(actions) > 0


def test_apply_action_advances_player():
    state = _make_state()
    p0 = state.current_player()
    actions = state.legal_actions(p0)
    state.apply_action(actions[0])
    p1 = state.current_player()
    assert p1 == p0 + 1


def test_terminal_returns_length():
    state = _make_state()
    while not state.is_terminal():
        p = state.current_player()
        actions = state.legal_actions(p)
        state.apply_action(actions[0])
    assert len(state.returns()) == 4


def test_information_state_string_differs_by_player():
    state = _make_state()
    is0 = state.information_state_string(0)
    is1 = state.information_state_string(1)
    assert is0 != is1


def test_serialize_deserialize_round_trip():
    game = pyspiel.load_game("astrakon", {"scenario_path": "scenarios/pacific_crossroads.yaml"})
    state = game.new_initial_state()
    for _ in range(8):
        if state.is_terminal():
            break
        p = state.current_player()
        state.apply_action(state.legal_actions(p)[0])
    serialized = state.serialize()
    state2 = game.new_initial_state()
    state2.deserialize(serialized)
    assert state2.current_player() == state.current_player()
    assert state2.information_state_string(0) == state.information_state_string(0)


def test_pyspiel_random_sim_compliance():
    """Run OpenSpiel's built-in random simulation compliance suite.

    pyspiel.test_game does not exist in this version; random_sim_test is the
    equivalent C++ compliance harness (basic_tests.cc).  It verifies:
      - clone == replay determinism
      - serialize/deserialize round-trip
      - legal_actions / apply_action consistency
    """
    game = pyspiel.load_game("astrakon", {"scenario_path": "scenarios/pacific_crossroads.yaml"})
    pyspiel.random_sim_test(game, num_sims=3, serialize=True, verbose=False, mask_test=False)
