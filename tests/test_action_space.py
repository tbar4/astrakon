# tests/test_action_space.py
import pytest
from pathlib import Path
from engine.action_space import ActionSpace
from scenarios.loader import load_scenario

SCENARIO = load_scenario(Path("scenarios/pacific_crossroads.yaml"))


@pytest.mark.xfail(reason="slots 16-99 added in Task 3", strict=False)
def test_invest_portfolio_count():
    space = ActionSpace(SCENARIO)
    assert len(space.invest_portfolios) == 100


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
        assert alloc.total() <= 1.001, f"slot {i} sums to {alloc.total():.4f}"


def test_extremal_portfolio_names():
    space = ActionSpace(SCENARIO)
    names = [name for _, name in space.invest_portfolios[16:20]]
    assert names == ["pure_orbital_leo", "pure_orbital_geo", "pure_kinetic", "pure_covert"]
