from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from runners.headless import GameResult


class EvaluationMetrics:
    @staticmethod
    def summarize(results: list[GameResult]) -> dict:
        n = len(results)
        if n == 0:
            return {}
        game_lengths = [r.n_turns for r in results]
        draws = sum(1 for r in results if r.winner_coalition is None)
        coalition_wins: dict[str, int] = {}
        for r in results:
            if r.winner_coalition:
                coalition_wins[r.winner_coalition] = coalition_wins.get(r.winner_coalition, 0) + 1

        return {
            "n_games": n,
            "mean_game_length": sum(game_lengths) / n,
            "min_game_length": min(game_lengths),
            "max_game_length": max(game_lengths),
            "draw_rate": draws / n,
            "coalition_win_rates": {c: w / n for c, w in coalition_wins.items()},
        }

    @staticmethod
    def write_game_record(
        result: GameResult,
        scenario: str,
        strategies: dict[str, str],
        output_dir: str = "results",
    ) -> str:
        os.makedirs(output_dir, exist_ok=True)
        record = {
            "game_id": str(uuid.uuid4()),
            "scenario": scenario,
            "strategies": strategies,
            "winner": result.winner_coalition,
            "n_turns": result.n_turns,
            "final_dominance": result.final_dominance,
            "returns": result.returns,
            "action_history": [
                {"player_idx": p, "action_idx": a}
                for p, a in result.action_history
            ],
        }
        path = Path(output_dir) / f"game_{record['game_id'][:8]}.json"
        with open(path, "w") as f:
            json.dump(record, f)
        return str(path)
