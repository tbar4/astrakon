# tests/test_action_space.py
import pytest
from pathlib import Path
from engine.action_space import ActionSpace
from scenarios.loader import load_scenario

SCENARIO = load_scenario(Path("scenarios/pacific_crossroads.yaml"))


def test_archetype_portfolio_range_valid():
    space = ActionSpace(SCENARIO)
    for i in range(16):
        alloc, name = space.invest_portfolios[i]
        assert alloc.total() <= 1.001, f"slot {i} ({name}) sums to {alloc.total():.3f}"


def test_archetype_portfolio_names():
    space = ActionSpace(SCENARIO)
    names = [name for _, name in space.invest_portfolios[:16]]
    assert any("mahanian" in n for n in names)
    assert any("gray_zone" in n for n in names)
    assert any("rogue" in n for n in names)
    assert any("commercial" in n for n in names)


def test_invest_portfolio_total_count():
    space = ActionSpace(SCENARIO)
    assert len(space.invest_portfolios) == 100


def test_random_portfolios_reproducible():
    space1 = ActionSpace(SCENARIO)
    space2 = ActionSpace(SCENARIO)
    for i in range(20, 100):
        a1, n1 = space1.invest_portfolios[i]
        a2, n2 = space2.invest_portfolios[i]
        assert n1 == n2 == f"invest_slot_{i:03d}"
        assert abs(a1.total() - a2.total()) < 1e-9


def test_random_portfolios_sum_valid():
    space = ActionSpace(SCENARIO)
    for i in range(20, 100):
        alloc, _ = space.invest_portfolios[i]
        t = alloc.total()
        assert 0.45 <= t <= 1.001, f"slot {i} total {t:.4f} out of expected [0.45, 1.001]"


def test_extremal_portfolio_range_valid():
    space = ActionSpace(SCENARIO)
    for i in range(16, 20):
        alloc, name = space.invest_portfolios[i]
        assert alloc.total() <= 1.001, f"slot {i} ({name}) sums to {alloc.total():.3f}"


def test_extremal_portfolio_names():
    space = ActionSpace(SCENARIO)
    names = [name for _, name in space.invest_portfolios[16:20]]
    assert names == ["pure_orbital_leo", "pure_orbital_geo", "pure_kinetic", "pure_covert"]


def test_ops_actions_nonempty():
    space = ActionSpace(SCENARIO)
    assert len(space.ops_actions) > 0


def test_ops_indices_stable_across_instances():
    space1 = ActionSpace(SCENARIO)
    space2 = ActionSpace(SCENARIO)
    assert len(space1.ops_actions) == len(space2.ops_actions)
    for a1, a2 in zip(space1.ops_actions, space2.ops_actions):
        assert a1["action_type"] == a2["action_type"]
        assert a1.get("target_faction_id") == a2.get("target_faction_id")
        assert a1.get("mission") == a2.get("mission")


def test_ops_decode_round_trip():
    space = ActionSpace(SCENARIO)
    for idx, entry in enumerate(space.ops_actions):
        decoded = space.ops_action_from_index(idx + space.OPS_OFFSET)
        assert decoded["action_type"] == entry["action_type"]


def test_no_illegal_ops_combinations():
    space = ActionSpace(SCENARIO)
    for entry in space.ops_actions:
        action_type = entry["action_type"]
        mission = entry.get("mission", "")
        target = entry.get("target_faction_id")
        # coordinate + intercept is invalid
        assert not (action_type == "coordinate" and mission == "intercept")
        # signal requires a target
        assert not (action_type == "signal" and target is None)
        # alliance_move requires a target
        assert not (action_type == "alliance_move" and target is None)


def test_response_actions_nonempty():
    space = ActionSpace(SCENARIO)
    assert len(space.response_actions) >= 6


def test_response_decode_round_trip():
    space = ActionSpace(SCENARIO)
    for idx, entry in enumerate(space.response_actions):
        decoded = space.response_action_from_index(idx + space.RESPONSE_OFFSET)
        assert decoded["escalate"] == entry["escalate"]
        assert decoded["retaliate"] == entry["retaliate"]


def test_response_retaliate_requires_target():
    space = ActionSpace(SCENARIO)
    for entry in space.response_actions:
        if entry["retaliate"]:
            assert entry["target_faction_id"] is not None


def test_total_action_count():
    space = ActionSpace(SCENARIO)
    assert space.TOTAL_ACTIONS == space.INVEST_COUNT + space.OPS_COUNT + space.RESPONSE_COUNT
    assert space.TOTAL_ACTIONS > 100
