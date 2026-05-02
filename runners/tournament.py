# runners/tournament.py
"""TournamentRunner: round-robin Elo evaluation with coalition side-swap.

Algorithm
---------
For each pair of strategies (A vs B):
  - Run games_per_matchup // 2 games with A controlling blue coalition
  - Run games_per_matchup // 2 games with A controlling red coalition
  This gives a balanced games_per_matchup total.

Coalition winner is mapped to the controlling strategy to update win records.
Elo ratings use the Bradley-Terry update (K=32) starting from 1500.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import pyspiel

import engine.openspiel_env  # noqa: ensure game is registered
from engine.state import (
    Phase, GameStateSnapshot, FactionState, CoalitionState, InvestmentAllocation,
)
from runners.headless import HeadlessRunner, GameResult
from scenarios.loader import load_scenario

_ELO_K = 32
_ELO_INITIAL = 1500.0


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class GameRecord:
    """Outcome of one tournament game."""
    scenario_path: str
    strat_a: str
    strat_b: str
    strat_a_coalition: str           # which coalition strat_a controlled
    winner_strategy: str | None      # None = draw
    winner_coalition: str | None
    n_turns: int
    final_dominance: dict[str, float]


@dataclass
class TournamentResult:
    """Aggregated results from run_round_robin."""
    elo_ratings: dict[str, float]
    win_matrix: dict[str, dict[str, float]]        # win_matrix[a][b] = wins of a over b
    per_scenario_win_rates: dict[str, dict[str, float]]   # scenario → strategy → win rate [0..1]
    raw_results: list[GameRecord]
    wilson_ci: dict[str, tuple[float, float]] = field(default_factory=dict)  # strategy → (lo, hi)


# ---------------------------------------------------------------------------
# Bot construction helpers
# ---------------------------------------------------------------------------

def _build_snapshot(
    state: "engine.openspiel_env.AstrakonState",
    faction_idx: int,
) -> GameStateSnapshot:
    """Build a minimal GameStateSnapshot for the acting faction at faction_idx."""
    core = state._core
    fid = core.faction_order[faction_idx]
    fs = core.faction_states[fid]

    ally_states: dict[str, FactionState] = {}
    adversary_estimates: dict[str, dict] = {}
    coalition_states: dict[str, CoalitionState] = {}
    faction_names: dict[str, str] = {}

    for cid, coalition in core._scenario.coalitions.items():
        coalition_states[cid] = CoalitionState(coalition_id=cid, member_ids=coalition.member_ids)

    for other_fid, other_fs in core.faction_states.items():
        faction_names[other_fid] = other_fs.name
        if other_fid == fid:
            continue
        if other_fs.coalition_id == fs.coalition_id:
            ally_states[other_fid] = other_fs
        else:
            est = core._estimate_adversary_assets(fid, other_fid)
            adversary_estimates[other_fid] = est.model_dump()

    incoming_threats = [
        k for k in core.pending_kinetics
        if k.get("target_faction_id") == fid
    ]

    total_debris = sum(core.debris_fields.values())

    available_actions = [
        core._action_space._action_to_string(faction_idx, a) if hasattr(core._action_space, '_action_to_string')
        else str(a)
        for a in core.legal_actions(faction_idx)
    ]

    return GameStateSnapshot(
        turn=core.current_turn(),
        phase=core.current_phase(),
        faction_id=fid,
        faction_state=fs,
        ally_states=ally_states,
        adversary_estimates=adversary_estimates,
        coalition_states=coalition_states,
        available_actions=available_actions,
        coalition_dominance=dict(core.coalition_dominance),
        victory_threshold=core._victory_threshold,
        total_turns=core._total_turns,
        escalation_rung=core.escalation_rung,
        debris_fields=dict(core.debris_fields),
        debris_level=total_debris / max(len(core.debris_fields), 1),
        tension_level=core.escalation_rung / 5.0,
        incoming_threats=incoming_threats,
        faction_names=faction_names,
    )


def _decision_to_action_idx(decision, asp, legal_actions: list[int]) -> int:
    """Convert an agent Decision to a global action index.

    Falls back to the first legal action if no exact match is found.
    """
    # INVEST phase
    if decision.phase == Phase.INVEST and decision.investment is not None:
        inv = decision.investment
        best_idx = 0
        best_score = -1.0
        inv_fields = [
            "r_and_d", "constellation", "meo_deployment", "geo_deployment",
            "cislunar_deployment", "launch_capacity", "commercial",
            "influence_ops", "education", "covert", "diplomacy", "kinetic_weapons",
        ]
        inv_vec = [getattr(inv, f) for f in inv_fields]
        for idx in range(asp.INVEST_COUNT):
            if idx not in legal_actions:
                continue
            alloc, _ = asp.invest_portfolios[idx]
            port_vec = [getattr(alloc, f) for f in inv_fields]
            # cosine-like dot product similarity
            dot = sum(a * b for a, b in zip(inv_vec, port_vec))
            if dot > best_score:
                best_score = dot
                best_idx = idx
        return best_idx

    # OPERATIONS phase
    if decision.phase == Phase.OPERATIONS and decision.operations:
        op = decision.operations[0]
        action_type = op.action_type
        target_fid = op.target_faction
        mission = op.parameters.get("mission", "") if op.parameters else ""
        for local_idx, entry in enumerate(asp.ops_actions):
            global_idx = asp.OPS_OFFSET + local_idx
            if global_idx not in legal_actions:
                continue
            if entry["action_type"] != action_type:
                continue
            if entry.get("target_faction_id") != target_fid:
                continue
            if entry.get("mission", "") != mission:
                continue
            return global_idx
        # Fallback: find any legal OPS action with same action_type
        for local_idx, entry in enumerate(asp.ops_actions):
            global_idx = asp.OPS_OFFSET + local_idx
            if global_idx not in legal_actions:
                continue
            if entry["action_type"] == action_type:
                return global_idx

    # RESPONSE phase
    if decision.phase == Phase.RESPONSE and decision.response is not None:
        resp = decision.response
        escalate = resp.escalate
        retaliate = resp.retaliate
        target_fid = resp.target_faction
        for local_idx, entry in enumerate(asp.response_actions):
            global_idx = asp.RESPONSE_OFFSET + local_idx
            if global_idx not in legal_actions:
                continue
            if entry["escalate"] != escalate:
                continue
            if entry["retaliate"] != retaliate:
                continue
            if retaliate and entry.get("target_faction_id") != target_fid:
                continue
            return global_idx
        # Fallback: any legal RESPONSE action with matching escalate
        for local_idx, entry in enumerate(asp.response_actions):
            global_idx = asp.RESPONSE_OFFSET + local_idx
            if global_idx not in legal_actions:
                continue
            if entry["escalate"] == escalate:
                return global_idx

    # Last resort: first legal action
    if legal_actions:
        return legal_actions[0]
    raise ValueError("No legal actions available")


def _make_bot_for_faction(
    strategy_factory: Callable,
    faction_ids_controlled: list[str],
    asp,
) -> Callable:
    """Return a bot callable(state) -> action for one strategy controlling given factions.

    A single agent instance is shared across all controlled factions
    (initialized lazily on first call with the acting faction).
    """
    # One agent per faction_id to avoid state bleed between factions
    agents: dict[str, object] = {}

    def bot(state) -> int:
        core = state._core
        player = core.acting_faction_idx()
        fid = core.faction_order[player]

        if fid not in faction_ids_controlled:
            # Should not happen — caller should only set this bot for controlled indices
            legal = state.legal_actions(player)
            return legal[0] if legal else 0

        if fid not in agents:
            agent = strategy_factory()
            # Initialize agent with the faction object from the scenario
            faction_obj = next(
                f for f in core._scenario.factions if f.faction_id == fid
            )
            agent.initialize(faction_obj)
            agents[fid] = agent

        agent = agents[fid]
        snap = _build_snapshot(state, player)
        agent.receive_state(snap)
        decision = asyncio.run(agent.submit_decision(core.current_phase()))
        legal = state.legal_actions(player)
        return _decision_to_action_idx(decision, asp, legal)

    return bot


# ---------------------------------------------------------------------------
# Elo helpers
# ---------------------------------------------------------------------------

def _elo_update(
    ratings: dict[str, float],
    winner: str,
    loser: str,
) -> None:
    """Apply Bradley-Terry K=32 Elo update in-place."""
    ra = ratings[winner]
    rb = ratings[loser]
    ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
    ratings[winner] += _ELO_K * (1.0 - ea)
    ratings[loser] += _ELO_K * (0.0 - (1.0 - ea))


def _elo_draw(
    ratings: dict[str, float],
    strat_a: str,
    strat_b: str,
) -> None:
    """Apply half-credit draw update in-place."""
    ra = ratings[strat_a]
    rb = ratings[strat_b]
    ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
    ratings[strat_a] += _ELO_K * (0.5 - ea)
    ratings[strat_b] += _ELO_K * (0.5 - (1.0 - ea))


# ---------------------------------------------------------------------------
# TournamentRunner
# ---------------------------------------------------------------------------

class TournamentRunner:
    """Run round-robin tournaments between agent strategies."""

    def run_round_robin(
        self,
        agent_strategies: dict[str, Callable],
        scenario_paths: list[str],
        games_per_matchup: int = 4,
        n_workers: int = 1,
    ) -> TournamentResult:
        """Run a round-robin tournament.

        Parameters
        ----------
        agent_strategies:
            Mapping of strategy name → zero-argument factory that returns an
            AgentInterface instance (fresh instance per game).
        scenario_paths:
            List of scenario YAML paths. Each path runs games_per_matchup games.
        games_per_matchup:
            Total games per (strat_a, strat_b, scenario) triple.
            Must be even; half with strat_a as blue, half as red.
        n_workers:
            Number of parallel workers (currently sequential when 1).
        """
        strategy_names = list(agent_strategies.keys())
        elo_ratings: dict[str, float] = {s: _ELO_INITIAL for s in strategy_names}
        win_matrix: dict[str, dict[str, float]] = {
            s: {t: 0.0 for t in strategy_names} for s in strategy_names
        }
        per_scenario_win_rates: dict[str, dict[str, float]] = {}
        raw_results: list[GameRecord] = []

        # For 2 strategies, we treat (a, b) and (b, a) as the same matchup.
        # Produce all unordered pairs.
        pairs = [
            (strategy_names[i], strategy_names[j])
            for i in range(len(strategy_names))
            for j in range(i + 1, len(strategy_names))
        ]
        if not pairs:
            # Single strategy — nothing to compare
            return TournamentResult(
                elo_ratings=elo_ratings,
                win_matrix=win_matrix,
                per_scenario_win_rates=per_scenario_win_rates,
                raw_results=raw_results,
            )

        half = max(1, games_per_matchup // 2)

        for scenario_path in scenario_paths:
            game = pyspiel.load_game("astrakon", {"scenario_path": scenario_path})
            scenario = game._scenario
            asp = game._action_space

            # Build coalition lookup: coalition_id → list[faction_id]
            coalition_map: dict[str, list[str]] = {
                cid: list(col.member_ids)
                for cid, col in scenario.coalitions.items()
            }
            coalition_ids = list(coalition_map.keys())  # e.g. ["blue", "red"]
            if len(coalition_ids) < 2:
                raise ValueError(
                    f"Scenario {scenario_path} must have at least 2 coalitions"
                )

            faction_order = scenario.factions  # ordered list of Faction objects
            faction_id_list = [f.faction_id for f in faction_order]

            # Map faction_id → player index
            faction_to_idx: dict[str, int] = {
                fid: idx for idx, fid in enumerate(faction_id_list)
            }

            # scenario-level win tracking for win rates
            scenario_wins: dict[str, int] = {s: 0 for s in strategy_names}
            scenario_games: int = 0

            for strat_a, strat_b in pairs:
                factory_a = agent_strategies[strat_a]
                factory_b = agent_strategies[strat_b]

                # Run half games with strat_a=coalition_ids[0], strat_b=coalition_ids[1]
                # and half games with the sides swapped.
                for swap in range(2):
                    n_games = half
                    if swap == 0:
                        a_coalition = coalition_ids[0]
                        b_coalition = coalition_ids[1]
                    else:
                        a_coalition = coalition_ids[1]
                        b_coalition = coalition_ids[0]

                    a_fids = coalition_map[a_coalition]
                    b_fids = coalition_map[b_coalition]

                    for seed in range(n_games):
                        record = self._run_one(
                            game=game,
                            asp=asp,
                            strat_a=strat_a,
                            strat_b=strat_b,
                            factory_a=factory_a,
                            factory_b=factory_b,
                            a_fids=a_fids,
                            b_fids=b_fids,
                            a_coalition=a_coalition,
                            b_coalition=b_coalition,
                            faction_to_idx=faction_to_idx,
                            scenario_path=scenario_path,
                            seed=seed + swap * 1000,
                        )
                        raw_results.append(record)
                        scenario_games += 1

                        # Update win matrix and Elo
                        ws = record.winner_strategy
                        if ws is None:
                            # Draw
                            _elo_draw(elo_ratings, strat_a, strat_b)
                        elif ws == strat_a:
                            win_matrix[strat_a][strat_b] += 1.0
                            scenario_wins[strat_a] += 1
                            _elo_update(elo_ratings, strat_a, strat_b)
                        else:
                            win_matrix[strat_b][strat_a] += 1.0
                            scenario_wins[strat_b] += 1
                            _elo_update(elo_ratings, strat_b, strat_a)

            # Compute per-scenario win rates
            if scenario_games > 0:
                per_scenario_win_rates[scenario_path] = {
                    s: scenario_wins[s] / scenario_games
                    for s in strategy_names
                }

        # Wilson confidence intervals (requires scipy)
        wilson_ci: dict[str, tuple[float, float]] = {}
        try:
            from scipy.stats import proportion_confint  # type: ignore[import]
            total_games = len(raw_results)
            for s in strategy_names:
                n_wins = sum(
                    1 for r in raw_results if r.winner_strategy == s
                )
                lo, hi = proportion_confint(n_wins, total_games, method="wilson")
                wilson_ci[s] = (float(lo), float(hi))
        except Exception:
            pass

        result = TournamentResult(
            elo_ratings=elo_ratings,
            win_matrix=win_matrix,
            per_scenario_win_rates=per_scenario_win_rates,
            raw_results=raw_results,
            wilson_ci=wilson_ci,
        )

        self._save_results(result)
        return result

    def _run_one(
        self,
        game,
        asp,
        strat_a: str,
        strat_b: str,
        factory_a: Callable,
        factory_b: Callable,
        a_fids: list[str],
        b_fids: list[str],
        a_coalition: str,
        b_coalition: str,
        faction_to_idx: dict[str, int],
        scenario_path: str,
        seed: int,
    ) -> GameRecord:
        """Run a single game and return a GameRecord."""
        bot_a = _make_bot_for_faction(factory_a, a_fids, asp)
        bot_b = _make_bot_for_faction(factory_b, b_fids, asp)

        # Build bots list indexed by faction player index
        n_players = len(faction_to_idx)
        bots: list = [None] * n_players
        for fid in a_fids:
            idx = faction_to_idx[fid]
            bots[idx] = bot_a
        for fid in b_fids:
            idx = faction_to_idx[fid]
            bots[idx] = bot_b

        runner = HeadlessRunner()
        gr: GameResult = runner.run_game(game, bots=bots, seed=seed)

        winner_coalition = gr.winner_coalition
        if winner_coalition is None:
            winner_strategy = None
        elif winner_coalition == a_coalition:
            winner_strategy = strat_a
        elif winner_coalition == b_coalition:
            winner_strategy = strat_b
        else:
            winner_strategy = None  # unknown coalition — treat as draw

        return GameRecord(
            scenario_path=scenario_path,
            strat_a=strat_a,
            strat_b=strat_b,
            strat_a_coalition=a_coalition,
            winner_strategy=winner_strategy,
            winner_coalition=winner_coalition,
            n_turns=gr.n_turns,
            final_dominance=gr.final_dominance,
        )

    def _save_results(self, result: TournamentResult) -> None:
        """Persist results to results/tournament_{timestamp}.json."""
        try:
            os.makedirs("results", exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            path = f"results/tournament_{ts}.json"
            data = {
                "elo_ratings": result.elo_ratings,
                "win_matrix": result.win_matrix,
                "per_scenario_win_rates": result.per_scenario_win_rates,
                "wilson_ci": {k: list(v) for k, v in result.wilson_ci.items()},
                "raw_results": [
                    {
                        "scenario_path": r.scenario_path,
                        "strat_a": r.strat_a,
                        "strat_b": r.strat_b,
                        "strat_a_coalition": r.strat_a_coalition,
                        "winner_strategy": r.winner_strategy,
                        "winner_coalition": r.winner_coalition,
                        "n_turns": r.n_turns,
                        "final_dominance": r.final_dominance,
                    }
                    for r in result.raw_results
                ],
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # saving results is best-effort
