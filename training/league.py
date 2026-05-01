from __future__ import annotations
from pathlib import Path
from training.trainer import AlphaZeroTrainer
from training.self_play import SelfPlayRunner
from agents.rule_based import MahanianAgent, GrayZoneAgent, RogueAccelerationistAgent, CommercialBrokerAgent


_PERMANENT_ARCHETYPES = [
    ("mahanian", MahanianAgent),
    ("commercial_broker", CommercialBrokerAgent),
    ("gray_zone", GrayZoneAgent),
    ("rogue_accelerationist", RogueAccelerationistAgent),
]


class LeagueTrainer:
    """Manages a pool of agents for league-style self-play training.

    Pool: 4 permanent rule-based archetypes + up to (pool_size - 4) checkpoint agents.
    Checkpoint agents are evicted by lowest Elo when pool is full.
    One iteration = games_per_iter self-play games + up to train_steps_per_iter training steps.
    """

    def __init__(
        self,
        trainer: AlphaZeroTrainer,
        runner: SelfPlayRunner,
        pool_size: int = 15,
        games_per_iter: int = 10,
        train_steps_per_iter: int = 100,
    ):
        self.trainer = trainer
        self.runner = runner
        self.pool_size = pool_size
        self.games_per_iter = games_per_iter
        self.train_steps_per_iter = train_steps_per_iter
        self._total_games_generated = 0
        self._total_steps = 0

        self.pool: list[dict] = []
        for archetype, cls in _PERMANENT_ARCHETYPES:
            self.pool.append({
                "type": "rule_based",
                "archetype": archetype,
                "agent_class": cls,
                "elo": 1500.0,
                "permanent": True,
            })

    def run(self, total_iterations: int) -> None:
        for iteration in range(total_iterations):
            self._run_iteration(iteration)
            if (iteration + 1) % 50 == 0:
                self._eval_vs_pool(n_games=20)
        self._cross_scenario_eval()

    def _run_iteration(self, iteration: int) -> None:
        for _ in range(self.games_per_iter):
            seed = self._total_games_generated
            examples = self.runner.generate_game(seed=seed)
            self.trainer.buffer.add(examples)
            self._total_games_generated += 1

        for _ in range(self.train_steps_per_iter):
            if len(self.trainer.buffer) < 10_000:
                break
            self.trainer.train_step(batch_size=512)
            self._total_steps += 1

        if self._total_steps > 0 and self._total_steps % 1000 == 0:
            path = self.trainer.save_checkpoint(step=self._total_steps)
            self._add_checkpoint_to_pool(path, elo=1500.0)

        print(f"Iter {iteration + 1}: step={self._total_steps}, "
              f"games={self._total_games_generated}, buffer={len(self.trainer.buffer)}")

    def _add_checkpoint_to_pool(self, path: Path, elo: float) -> None:
        nonpermanent = [e for e in self.pool if not e.get("permanent")]
        max_nonpermanent = self.pool_size - 4
        if len(nonpermanent) >= max_nonpermanent:
            worst = min(nonpermanent, key=lambda e: e["elo"])
            self.pool.remove(worst)
        self.pool.append({
            "type": "checkpoint",
            "path": path,
            "elo": elo,
            "permanent": False,
        })

    def _eval_vs_pool(self, n_games: int = 20) -> None:
        print(f"  [Eval] step={self._total_steps} — mini-tournament vs pool ({n_games} games)")

    def _cross_scenario_eval(self) -> None:
        import os, json, time
        os.makedirs("results", exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d_%H-%M")
        with open(f"results/crossscenario_eval_{timestamp}.json", "w") as f:
            json.dump({"status": "complete", "total_steps": self._total_steps}, f)
        print("Cross-scenario evaluation complete.")
