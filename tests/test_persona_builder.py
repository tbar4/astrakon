# tests/test_persona_builder.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from personas.builder import PersonaBuilder, load_archetype


def test_load_mahanian_archetype():
    persona = load_archetype("mahanian")
    assert persona["persona"]["name"] == "The Mahanian"
    assert "system_prompt_context" in persona["persona"]
    assert "doctrine_narrative" in persona["persona"]


def test_load_iron_napoleon_archetype():
    persona = load_archetype("iron_napoleon")
    assert persona["persona"]["escalation_tolerance"] >= 0.8


def test_invalid_archetype_raises():
    with pytest.raises(ValueError, match="Unknown archetype"):
        load_archetype("nonexistent_archetype")


def test_persona_builder_natural_language(tmp_path):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        type="tool_use",
        name="create_persona",
        input={
            "name": "Iron Napoleon",
            "decision_style": "decisive_aggressive",
            "escalation_tolerance": 0.90,
            "coalition_loyalty": 0.30,
            "doctrine_narrative": "Concentrates force at decisive points.",
            "system_prompt_context": "You are Iron Napoleon...",
            "investment_bias": {
                "r_and_d": 0.20, "constellation": 0.05,
                "covert": 0.50, "diplomacy": 0.00,
                "launch_capacity": 0.05, "commercial": 0.00,
                "influence_ops": 0.10, "education": 0.10,
            }
        }
    )]
    with patch("personas.builder.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        builder = PersonaBuilder()
        yaml_str = builder.build_from_description(
            "Napoleon as a modern Space Force general — decisive kinetic action",
            save_to=tmp_path / "iron_napoleon.yaml"
        )
    assert "Iron Napoleon" in yaml_str
    assert (tmp_path / "iron_napoleon.yaml").exists()
