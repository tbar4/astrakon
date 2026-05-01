# tests/test_action_space.py
import pytest
from pathlib import Path
from engine.action_space import ActionSpace
from scenarios.loader import load_scenario

SCENARIO = load_scenario(Path("scenarios/pacific_crossroads.yaml"))


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
