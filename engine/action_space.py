# engine/action_space.py
from __future__ import annotations
from engine.state import InvestmentAllocation, Phase
from scenarios.loader import Scenario


def _make_snap(urgency: str):
    """Return a minimal GameStateSnapshot for the given urgency level."""
    from engine.state import GameStateSnapshot, FactionState, FactionAssets
    my_col = "my_col"
    dom = {
        "ahead": 0.75,
        "normal": 0.50,
        "urgent": 0.60,
        "critical": 0.50,
    }[urgency]
    turns_left = {"ahead": 10, "normal": 10, "urgent": 4, "critical": 2}[urgency]
    fs = FactionState(
        faction_id="tmp", name="tmp", budget_per_turn=100, current_budget=100,
        assets=FactionAssets(), coalition_id=my_col,
    )
    return GameStateSnapshot(
        turn=14 - turns_left,
        phase=Phase.INVEST,
        faction_id="tmp",
        faction_state=fs,
        ally_states={},
        adversary_estimates={},
        coalition_states={},
        available_actions=[],
        coalition_dominance={my_col: dom},
        victory_threshold=0.68,
        total_turns=14,
    )


def _archetype_invest(archetype: str, urgency: str) -> InvestmentAllocation:
    from agents.rule_based import (
        MahanianAgent, GrayZoneAgent, RogueAccelerationistAgent, CommercialBrokerAgent,
    )
    cls = {
        "mahanian": MahanianAgent,
        "commercial_broker": CommercialBrokerAgent,
        "gray_zone": GrayZoneAgent,
        "rogue_accelerationist": RogueAccelerationistAgent,
    }[archetype]  # KeyError is fine — means _ARCHETYPES was misconfigured
    agent = cls()
    snap = _make_snap(urgency)
    return agent._invest(snap)


_ARCHETYPES = [
    "mahanian",
    "commercial_broker",
    "gray_zone",
    "rogue_accelerationist",
]
_URGENCIES = ["ahead", "normal", "urgent", "critical"]


class ActionSpace:
    def __init__(self, scenario: Scenario):
        self.faction_ids: list[str] = [f.faction_id for f in scenario.factions]
        self.faction_archetypes: dict[str, str] = {
            f.faction_id: f.archetype for f in scenario.factions
        }
        self.invest_portfolios: list[tuple[InvestmentAllocation, str]] = []
        self.INVEST_COUNT = 100
        self.INVEST_OFFSET = 0
        self._build_portfolios()
        self._build_ops()
        self._build_response()
        self.OPS_OFFSET = self.INVEST_COUNT
        self.OPS_COUNT = len(self.ops_actions)
        self.RESPONSE_OFFSET = self.OPS_OFFSET + self.OPS_COUNT
        self.RESPONSE_COUNT = len(self.response_actions)
        self.TOTAL_ACTIONS = self.INVEST_COUNT + self.OPS_COUNT + self.RESPONSE_COUNT

    def _build_portfolios(self) -> None:
        # Slots 0-15: 4 archetypes × 4 urgency stances
        for archetype in _ARCHETYPES:
            for urgency in _URGENCIES:
                alloc = _archetype_invest(archetype, urgency)
                name = f"{archetype}_{urgency}"
                self.invest_portfolios.append((alloc, name))
        # Slots 16-99 added in Task 3

    def invest_portfolio_name(self, idx: int) -> str:
        return self.invest_portfolios[idx][1]

    def _build_ops(self) -> None:
        self.ops_actions: list[dict] = []

    def _build_response(self) -> None:
        self.response_actions: list[dict] = []
