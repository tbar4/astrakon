# tests/test_combat_events.py
import pytest
from engine.state import CombatEvent
from api.models import GameState


def test_combat_event_instantiates():
    ev = CombatEvent(
        turn=1,
        attacker_id="ussf",
        target_faction_id="pla_ssf",
        shell="leo",
        event_type="kinetic",
        nodes_destroyed=3,
        detail="USSF destroys 3 PLA_SSF nodes in LEO",
    )
    assert ev.nodes_destroyed == 3
    assert ev.shell == "leo"
    d = ev.model_dump()
    assert d["event_type"] == "kinetic"


def test_game_state_has_combat_events_field():
    from engine.state import FactionState, CoalitionState, Phase, FactionAssets
    fs = FactionState(
        faction_id="ussf", name="USSF", budget_per_turn=10, current_budget=10,
        assets=FactionAssets(), coalition_id="usa", coalition_loyalty=1.0, archetype="mahanian"
    )
    state = GameState(
        session_id="s1", scenario_id="test", scenario_name="Test", turn=1, total_turns=5,
        current_phase=Phase.INVEST, faction_states={"ussf": fs},
        coalition_states={}, human_faction_id="ussf",
    )
    assert state.combat_events == []
