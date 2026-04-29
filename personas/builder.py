import io
from pathlib import Path
from ruamel.yaml import YAML
import anthropic

ARCHETYPES_DIR = Path(__file__).parent / "archetypes"

KNOWN_ARCHETYPES = [
    "mahanian", "iron_napoleon", "gray_zone",
    "commercial_broker", "patient_dragon", "rogue_accelerationist"
]

CREATE_PERSONA_TOOL = {
    "name": "create_persona",
    "description": "Create a structured persona YAML from a natural language description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name":                   {"type": "string"},
            "decision_style":         {"type": "string"},
            "escalation_tolerance":   {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "coalition_loyalty":      {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "doctrine_narrative":     {"type": "string"},
            "system_prompt_context":  {"type": "string"},
            "investment_bias": {
                "type": "object",
                "properties": {
                    "r_and_d": {"type": "number"}, "constellation": {"type": "number"},
                    "launch_capacity": {"type": "number"}, "commercial": {"type": "number"},
                    "influence_ops": {"type": "number"}, "education": {"type": "number"},
                    "covert": {"type": "number"}, "diplomacy": {"type": "number"},
                },
            },
        },
        "required": [
            "name", "decision_style", "escalation_tolerance", "coalition_loyalty",
            "doctrine_narrative", "system_prompt_context", "investment_bias"
        ],
    },
}

BUILDER_SYSTEM = """You are a space wargame persona designer. Given a natural language description of a strategic commander, create a structured persona for use as an AI agent in a space strategy simulation.

Extract: name, decision style, escalation tolerance (0=dovish, 1=hawkish), coalition loyalty (0=purely self-interested, 1=fully loyal), doctrine narrative, system prompt context for the AI agent, and investment bias fractions that sum to 1.0.

Be creative and true to the described character. The system_prompt_context should speak directly to the AI agent in second person, telling it how to think and decide."""


def load_archetype(name: str) -> dict:
    if name not in KNOWN_ARCHETYPES:
        raise ValueError(f"Unknown archetype: '{name}'. Known: {KNOWN_ARCHETYPES}")
    yaml = YAML()
    path = ARCHETYPES_DIR / f"{name}.yaml"
    return yaml.load(path)


class PersonaBuilder:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic()
        self._model = model

    def build_from_description(
        self, description: str, save_to: Path | None = None
    ) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=BUILDER_SYSTEM,
            messages=[{"role": "user", "content": description}],
            tools=[CREATE_PERSONA_TOOL],
            tool_choice={"type": "any"},
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            raise RuntimeError("Persona builder: Claude did not return a tool call.")

        inp = tool_use.input
        persona_data = {
            "persona": {
                "name":                  inp["name"],
                "decision_style":        inp["decision_style"],
                "escalation_tolerance":  inp["escalation_tolerance"],
                "coalition_loyalty":     inp["coalition_loyalty"],
                "doctrine_narrative":    inp["doctrine_narrative"],
                "system_prompt_context": inp["system_prompt_context"],
                "investment_bias":       inp["investment_bias"],
            }
        }
        yaml = YAML()
        buf = io.StringIO()
        yaml.dump(persona_data, buf)
        yaml_str = buf.getvalue()

        if save_to is not None:
            save_to.parent.mkdir(parents=True, exist_ok=True)
            yaml.dump(persona_data, Path(save_to))

        return yaml_str
