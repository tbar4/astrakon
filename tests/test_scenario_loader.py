# tests/test_scenario_loader.py
import pytest
from pathlib import Path
from scenarios.loader import load_scenario, Scenario


def test_load_pacific_crossroads():
    path = Path("scenarios/pacific_crossroads.yaml")
    scenario = load_scenario(path)
    assert scenario.name == "Pacific Crossroads"
    assert scenario.turns == 10
    assert len(scenario.factions) >= 2
    assert len(scenario.coalitions) >= 1


def test_coalition_members_reference_valid_factions():
    path = Path("scenarios/pacific_crossroads.yaml")
    scenario = load_scenario(path)
    faction_ids = {f.faction_id for f in scenario.factions}
    for coalition in scenario.coalitions.values():
        for member in coalition.member_ids:
            assert member in faction_ids, f"Coalition member {member} not in factions"


def test_faction_budget_positive():
    path = Path("scenarios/pacific_crossroads.yaml")
    scenario = load_scenario(path)
    for faction in scenario.factions:
        assert faction.budget_per_turn > 0
