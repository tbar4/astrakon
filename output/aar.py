import asyncio
import json
import anthropic
from output.audit import AuditTrail

AAR_SYSTEM = """You are a senior military strategist writing an after-action review of a space wargame session. You will receive the complete game log — every decision, every crisis event, every strategic move.

Write a structured military AAR with these sections:
1. CAMPAIGN SUMMARY — outcome, winner, turns played
2. DECISIVE TURNING POINTS — specific turn/phase/decision citations that changed the campaign
3. STRATEGIC FAILURE ANALYSIS — what each losing faction did wrong and why
4. COALITION DYNAMICS — how alliances held or fractured, defection pressures
5. EMERGENT INSIGHTS — what the simulation revealed that wasn't predicted by initial doctrine
6. COMPARISON TO HISTORICAL ANALOGUES — connect outcomes to real spacepower theory (Dolman, Ziarnick, Carlson, Mahan)

Be analytical and specific. Cite exact turns and decisions. This report will be used as PME case study material."""


class AfterActionReportGenerator:
    def __init__(self, model: str = "claude-opus-4-7"):
        self._client = anthropic.Anthropic()
        self._model = model

    async def generate(self, audit: AuditTrail, scenario_name: str) -> str:
        game_log = await audit.get_full_game_log()
        log_text = json.dumps(game_log, indent=2)

        response = await asyncio.to_thread(
            self._client.messages.create,
            model=self._model,
            max_tokens=4096,
            system=AAR_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"SCENARIO: {scenario_name}\n\nGAME LOG:\n{log_text}"
            }],
        )
        return response.content[0].text
