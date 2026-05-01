# tests/test_scenario_loader.py
import pytest
from pathlib import Path
from scenarios.loader import load_scenario, Scenario


def test_load_pacific_crossroads():
    path = Path("scenarios/pacific_crossroads.yaml")
    scenario = load_scenario(path)
    assert scenario.name == "Pacific Crossroads"
    assert scenario.turns == 14
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


def test_faction_has_checkpoint_path_field():
    from scenarios.loader import Faction
    f = Faction(
        faction_id="x", name="X", archetype="mahanian",
        agent_type="alphazero", budget_per_turn=100,
        checkpoint_path="training/checkpoints/test.pt",
    )
    assert f.checkpoint_path == "training/checkpoints/test.pt"


def test_checkpoint_path_optional_default_none():
    from scenarios.loader import Faction
    f = Faction(
        faction_id="x", name="X", archetype="mahanian",
        agent_type="rule_based", budget_per_turn=100,
    )
    assert f.checkpoint_path is None
