from __future__ import annotations
import random
import numpy as np
import torch
from dataclasses import dataclass
from torch import Tensor
import pyspiel
import engine.openspiel_env  # noqa: register game type
from training.network import PolicyValueNetwork


@dataclass
class TrainingExample:
    """A single (state, MCTS policy, outcome) tuple collected during self-play.

    Attributes:
        info_state: Flat float tensor encoding the information state for the
            acting player at this step (length == game info_state_tensor dim).
        mcts_policy: Probability distribution over all actions produced by
            the network-guided MCTS policy (length == num_distinct_actions).
        game_return: Terminal return for the acting player: +1.0 win, -1.0
            loss, 0.0 draw.
    """

    info_state: Tensor
    mcts_policy: Tensor
    game_return: float


class SelfPlayRunner:
    """Generates self-play games using a network-guided policy.

    For each game step the runner calls ``_run_mcts_policy`` which uses the
    policy head of ``network`` to produce visit-count estimates over legal
    actions without running full tree search.  This is a "network-policy"
    approximation: visit counts are proportional to the policy network
    probabilities, re-normalised over legal actions.

    Args:
        network: Shared ``PolicyValueNetwork`` used to score actions.
        game_params: Keyword parameters forwarded to ``pyspiel.load_game``.
        n_simulations: Controls how many simulated visits to distribute.
            Lower values speed up tests; higher values produce sharper policies.
    """

    def __init__(
        self,
        network: PolicyValueNetwork,
        game_params: dict,
        n_simulations: int = 400,
    ):
        self.network = network
        self.game_params = game_params
        self.n_simulations = n_simulations

    def generate_game(self, seed: int) -> list[TrainingExample]:
        """Play one complete game and return a ``TrainingExample`` per step.

        Seeds all random number generators with ``seed`` for full
        reproducibility.  The game terminal returns are looked up after the
        game ends and back-filled into every example.

        Args:
            seed: Integer seed for ``random``, ``numpy``, and ``torch``.

        Returns:
            List of ``TrainingExample`` objects, one per decision step.
        """
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

        game = pyspiel.load_game("astrakon", self.game_params)
        state = game.new_initial_state()
        raw: list[dict] = []

        while not state.is_terminal():
            player = state.current_player()
            legal = state.legal_actions(player)

            info_tensor = torch.tensor(
                state.information_state_tensor(player), dtype=torch.float32
            )

            mcts_policy = self._run_mcts_policy(state, legal)

            raw.append({
                "player_idx": player,
                "info_state": info_tensor,
                "mcts_policy": mcts_policy,
            })

            # Sample action from the MCTS policy (legal actions only)
            probs = mcts_policy.numpy()
            legal_probs = np.array([probs[a] for a in legal])
            legal_probs = legal_probs / legal_probs.sum()
            local_idx = int(np.random.choice(len(legal), p=legal_probs))
            action = legal[local_idx]
            state.apply_action(action)

        returns = state.returns()

        examples = []
        for entry in raw:
            player_idx = entry["player_idx"]
            game_return = returns[player_idx] if player_idx < len(returns) else 0.0
            examples.append(TrainingExample(
                info_state=entry["info_state"],
                mcts_policy=entry["mcts_policy"],
                game_return=float(game_return),
            ))

        return examples

    def _run_mcts_policy(self, state, legal: list[int]) -> Tensor:
        """Compute a network-guided policy over all actions.

        Runs the policy head of ``self.network`` on the current state and
        distributes ``n_simulations`` virtual visit counts proportionally to
        the softmax probabilities, restricted to legal actions.  The result is
        normalised to sum to 1.0.

        Args:
            state: Current ``AstrakonState`` from which to read the info tensor.
            legal: List of legal action indices for the current player.

        Returns:
            A float tensor of shape ``(action_dim,)`` that sums to 1.0.
        """
        action_dim = self.network.action_dim
        visit_counts = torch.zeros(action_dim)

        if not legal:
            return visit_counts

        if self.n_simulations == 0:
            for a in legal:
                visit_counts[a] = 1.0
            return visit_counts / visit_counts.sum()

        info_tensor = torch.tensor(
            state.information_state_tensor(state.current_player()),
            dtype=torch.float32,
        ).unsqueeze(0)

        legal_mask = torch.zeros(action_dim, dtype=torch.bool)
        for a in legal:
            legal_mask[a] = True

        self.network.eval()
        with torch.no_grad():
            logits, _ = self.network(info_tensor, legal_mask=legal_mask.unsqueeze(0))

        probs = torch.softmax(logits[0], dim=-1)
        for a in legal:
            visit_counts[a] = max(1.0, float(self.n_simulations) * float(probs[a]))

        return visit_counts / visit_counts.sum()

    def generate_batch(self, n_games: int, n_workers: int = 8) -> list[TrainingExample]:
        """Generate multiple self-play games in parallel using ``spawn`` workers.

        The network is shared via ``share_memory()`` so worker processes read
        weights without copying.

        Args:
            n_games: Number of games to generate.
            n_workers: Number of parallel worker processes.

        Returns:
            Flat list of ``TrainingExample`` objects from all games.
        """
        self.network.share_memory()
        import torch.multiprocessing as mp
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=n_workers) as pool:
            args = [
                (self.network, self.game_params, self.n_simulations, i)
                for i in range(n_games)
            ]
            results = pool.starmap(_worker_generate_game, args)
        return [ex for game_examples in results for ex in game_examples]


def _worker_generate_game(
    network: PolicyValueNetwork,
    game_params: dict,
    n_simulations: int,
    seed: int,
) -> list[TrainingExample]:
    """Top-level function used by ``generate_batch`` worker processes.

    Must be importable at the module level (not a closure) so ``spawn``
    multiprocessing can pickle it.
    """
    import engine.openspiel_env  # noqa: re-register in the worker process
    runner = SelfPlayRunner(
        network=network,
        game_params=game_params,
        n_simulations=n_simulations,
    )
    return runner.generate_game(seed=seed)
