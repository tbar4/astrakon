# runners/headless.py
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Callable
import pyspiel


@dataclass
class GameResult:
    winner_coalition: str | None
    returns: list[float]
    final_dominance: dict[str, float]
    action_history: list[tuple[int, int]] = field(default_factory=list)
    n_turns: int = 0


class HeadlessRunner:
    def run_game(
        self,
        game: pyspiel.Game,
        bots: list | None = None,
        seed: int = 0,
    ) -> GameResult:
        """Run a single game to terminal. bots[i] is callable(state)->action, or None for random."""
        random.seed(seed)
        state = game.new_initial_state()
        history: list[tuple[int, int]] = []

        while not state.is_terminal():
            player = state.current_player()
            legal = state.legal_actions(player)
            if bots and bots[player] is not None:
                action = bots[player](state)
            else:
                action = random.choice(legal)
            history.append((player, action))
            state.apply_action(action)

        core = state._core
        return GameResult(
            winner_coalition=core._winner_coalition,
            returns=state.returns(),
            final_dominance=dict(core.coalition_dominance),
            action_history=history,
            n_turns=core.current_turn() - 1,
        )

    def run_parallel(
        self,
        game_params: dict,
        bots_factory: Callable[[], list] | None = None,
        n_games: int = 10,
        n_workers: int = 4,
    ) -> list[GameResult]:
        """Run n_games in parallel using multiprocessing."""
        import engine.openspiel_env  # noqa: ensure registration in each worker
        import multiprocessing as mp
        args = [(game_params, bots_factory, i) for i in range(n_games)]
        with mp.Pool(processes=n_workers) as pool:
            results = pool.starmap(_run_one_game, args)
        return results


def _run_one_game(game_params: dict, bots_factory, seed: int) -> GameResult:
    import engine.openspiel_env  # noqa: register on worker import
    game = __import__("pyspiel").load_game("astrakon", game_params)
    bots = bots_factory() if bots_factory else None
    return HeadlessRunner().run_game(game, bots=bots, seed=seed)
