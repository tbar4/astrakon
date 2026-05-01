from __future__ import annotations
import asyncio
import random
from pathlib import Path
from typing import Optional

import pyspiel

from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, Recommendation, GameStateSnapshot,
    InvestmentAllocation, OperationalAction, ResponseDecision,
)


class _RuleBasedEvaluator:
    """Lightweight evaluator for ISMCTSBot.

    evaluator.prior(state)    → [(action, prob), ...]  uniform over legal actions
    evaluator.evaluate(state) → list[float]            random rollout returns
    """

    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.Random()

    def prior(self, state: pyspiel.State) -> list[tuple[int, float]]:
        """Return uniform prior over legal actions."""
        legal = state.legal_actions()
        if not legal:
            return []
        n = len(legal)
        return [(a, 1.0 / n) for a in legal]

    def evaluate(self, state: pyspiel.State) -> list[float]:
        """Random rollout to terminal; return per-player returns."""
        import copy as _copy
        s = state.clone()
        while not s.is_terminal():
            legal = s.legal_actions()
            if not legal:
                break
            action = self._rng.choice(legal)
            s.apply_action(action)
        return s.returns()


class ISMCTSAgent(AgentInterface):
    """IS-MCTS agent using OpenSpiel's ISMCTSBot.

    Runs one search per turn during INVEST phase, caching the OPS and RESPONSE
    actions from the highest-value simulation paths. Subsequent phase calls
    return the cached values without running a second search.

    Phase caching strategy:
    - INVEST call: load the OpenSpiel game, advance state to our INVEST turn,
      run ISMCTSBot to pick the best INVEST action, then advance state through
      all factions' INVEST+OPS decisions to reach our OPS turn, run a second
      quick search for OPS, then similarly reach our RESPONSE turn and cache
      the RESPONSE action. Returns the INVEST Decision.
    - OPERATIONS call: if cached, build and return Decision from cache.
    - RESPONSE call: if cached, build and return Decision from cache.
    """

    def __init__(self, n_simulations: int = 800, rollout_policy: str = "rule_based"):
        super().__init__()
        self.n_simulations = n_simulations
        self.rollout_policy = rollout_policy
        self._cached_ops_action: Optional[int] = None
        self._cached_response_action: Optional[int] = None
        self._cached_invest_action: Optional[int] = None
        self._scenario_path: Optional[str] = None

    def initialize(self, faction) -> None:
        super().initialize(faction)
        self._archetype = getattr(faction, "archetype", "mahanian")

    def receive_state(self, snapshot: GameStateSnapshot) -> None:
        super().receive_state(snapshot)
        self._cached_ops_action = None
        self._cached_response_action = None
        self._cached_invest_action = None

    async def submit_decision(self, phase: Phase) -> Decision:
        """Return a Decision for the requested phase.

        On INVEST: runs IS-MCTS search once, caches ops+response actions,
        returns INVEST Decision.
        On OPS/RESPONSE: returns cached actions without new search (or falls
        back to search if cache is empty due to out-of-order calls).
        """
        if phase == Phase.INVEST:
            # Run search in a thread to avoid blocking the event loop.
            result = await asyncio.to_thread(self._run_full_turn_search)
            invest_idx, ops_idx, response_idx = result
            self._cached_invest_action = invest_idx
            self._cached_ops_action = ops_idx
            self._cached_response_action = response_idx
            return self._action_idx_to_decision(Phase.INVEST, invest_idx)

        if phase == Phase.OPERATIONS:
            ops_idx = self._cached_ops_action
            if ops_idx is None:
                # Fallback: run rule-based (avoids blocking; safe since it's sync)
                return await self._rule_fallback(phase)
            return self._action_idx_to_decision(Phase.OPERATIONS, ops_idx)

        # Phase.RESPONSE
        resp_idx = self._cached_response_action
        if resp_idx is None:
            return await self._rule_fallback(phase)
        return self._action_idx_to_decision(Phase.RESPONSE, resp_idx)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_game_and_state(self):
        """Load pyspiel game and return (game, initial_state)."""
        import engine.openspiel_env  # noqa: F401  — triggers astrakon game registration
        scenario_path = self._scenario_path or "scenarios/pacific_crossroads.yaml"
        game = pyspiel.load_game("astrakon", {"scenario_path": scenario_path})
        state = game.new_initial_state()
        return game, state

    def _make_bot(self, game, n_simulations: int | None = None):
        """Construct ISMCTSBot with _RuleBasedEvaluator and a deterministic resampler.

        Because Astrakon is a deterministic game (no chance nodes), sampling from
        the information state is equivalent to cloning the current world state.
        We inject a resampler callback that does exactly that.
        """
        from open_spiel.python.algorithms.ismcts import ISMCTSBot
        evaluator = _RuleBasedEvaluator()
        sims = n_simulations if n_simulations is not None else self.n_simulations
        bot = ISMCTSBot(
            game=game,
            evaluator=evaluator,
            uct_c=1.5,
            max_simulations=sims,
        )
        # Resampler: in a deterministic game, the world state equals the info state.
        bot.set_resampler(lambda state, player: state.clone())
        return bot

    def _faction_idx(self, state) -> int:
        """Return our faction's player index from the game state."""
        core = state._core
        try:
            return core.faction_order.index(self.faction_id)
        except ValueError:
            return 0

    def _run_full_turn_search(self) -> tuple[int, int, int]:
        """Synchronous: run IS-MCTS for all three phases in one shot.

        Returns (invest_action_idx, ops_action_idx, response_action_idx).
        All indices are globally-indexed (i.e. ops_idx >= OPS_OFFSET).
        """
        game, state = self._get_game_and_state()
        bot = self._make_bot(game)
        asp = state._core._action_space
        my_idx = self._faction_idx(state)

        # ── INVEST phase ──────────────────────────────────────────────
        # Advance past earlier factions' INVEST actions to reach our slot.
        state = self._advance_to_our_turn(state, Phase.INVEST, my_idx)
        invest_action = self._bot_step(bot, state)
        # Record invest and advance all factions through INVEST.
        state = self._advance_through_phase(state, Phase.INVEST, my_idx, invest_action)

        # ── OPS phase ─────────────────────────────────────────────────
        bot.reset()
        state = self._advance_to_our_turn(state, Phase.OPERATIONS, my_idx)
        ops_action = self._bot_step(bot, state)
        state = self._advance_through_phase(state, Phase.OPERATIONS, my_idx, ops_action)

        # ── RESPONSE phase ────────────────────────────────────────────
        bot.reset()
        state = self._advance_to_our_turn(state, Phase.RESPONSE, my_idx)
        response_action = self._bot_step(bot, state)

        return invest_action, ops_action, response_action

    def _bot_step(self, bot, state) -> int:
        """Run ISMCTSBot.step() and return the chosen action index."""
        _, action = bot.step_with_policy(state)
        return int(action)

    def _advance_to_our_turn(self, state, phase: Phase, my_idx: int):
        """Apply random legal actions for other factions until it is our turn in `phase`."""
        while True:
            core = state._core
            if core.current_phase() != phase:
                # Wrong phase — something unexpected; return as-is to avoid infinite loop
                break
            if core.acting_faction_idx() == my_idx:
                break
            # Apply a random legal action for the current (other) faction
            legal = state.legal_actions()
            if not legal:
                break
            state.apply_action(legal[0])
        return state

    def _advance_through_phase(self, state, phase: Phase, my_idx: int, our_action: int):
        """Apply our action and then advance other factions until the phase ends."""
        # Apply our action (we are currently the acting faction)
        state.apply_action(our_action)
        # Now advance remaining factions in this phase
        while not state.is_terminal():
            core = state._core
            if core.current_phase() != phase:
                break  # phase has advanced
            legal = state.legal_actions()
            if not legal:
                break
            state.apply_action(legal[0])
        return state

    def _action_idx_to_decision(self, phase: Phase, action_idx: int) -> Decision:
        """Convert a globally-indexed action integer to a Decision object."""
        # We need the action space. Load it cheaply from the game.
        # Use a cached reference if available to avoid repeated game loads.
        asp = self._get_action_space()

        if phase == Phase.INVEST:
            alloc, _name = asp.invest_portfolios[action_idx]
            return Decision(
                phase=Phase.INVEST,
                faction_id=self.faction_id,
                investment=alloc.model_copy(),
            )

        if phase == Phase.OPERATIONS:
            entry = asp.ops_action_from_index(action_idx)
            op = OperationalAction(
                action_type=entry["action_type"],
                target_faction=entry.get("target_faction_id"),
                parameters={"mission": entry["mission"]} if entry.get("mission") else {},
            )
            return Decision(
                phase=Phase.OPERATIONS,
                faction_id=self.faction_id,
                operations=[op],
            )

        # Phase.RESPONSE
        entry = asp.response_action_from_index(action_idx)
        resp = ResponseDecision(
            escalate=entry.get("escalate", False),
            retaliate=entry.get("retaliate", False),
            target_faction=entry.get("target_faction_id"),
        )
        return Decision(
            phase=Phase.RESPONSE,
            faction_id=self.faction_id,
            response=resp,
        )

    def _get_action_space(self):
        """Return the ActionSpace for the scenario (cached after first load)."""
        if not hasattr(self, "_action_space_cache") or self._action_space_cache is None:
            from scenarios.loader import load_scenario
            from engine.action_space import ActionSpace
            scenario_path = self._scenario_path or "scenarios/pacific_crossroads.yaml"
            scenario = load_scenario(Path(scenario_path))
            self._action_space_cache = ActionSpace(scenario)
        return self._action_space_cache

    async def _rule_fallback(self, phase: Phase) -> Decision:
        """Fallback to rule-based agent when cache is missing."""
        from agents.rule_based import MahanianAgent, GrayZoneAgent
        archetype = getattr(self, "_archetype", "mahanian")
        cls = GrayZoneAgent if archetype == "gray_zone" else MahanianAgent
        agent = cls()
        agent.faction_id = self.faction_id
        if self._last_snapshot:
            agent.receive_state(self._last_snapshot)
        return await agent.submit_decision(phase)

    async def get_recommendation(self, phase: Phase) -> Optional[Recommendation]:
        return None  # Implemented in Task 4
