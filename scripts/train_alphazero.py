#!/usr/bin/env python3
"""AlphaZero self-play training CLI for Astrakon.

Usage:
    python scripts/train_alphazero.py \
        --scenario scenarios/pacific_crossroads.yaml \
        --iterations 1000 \
        --games-per-iter 10 \
        --train-steps-per-iter 100 \
        --n-simulations 400 \
        --checkpoint-dir training/checkpoints/ \
        --resume training/checkpoints/pacific_crossroads_step_0010000.pt
"""
import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="AlphaZero self-play training for Astrakon")
    parser.add_argument("--scenario", default="scenarios/pacific_crossroads.yaml")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--games-per-iter", type=int, default=10)
    parser.add_argument("--train-steps-per-iter", type=int, default=100)
    parser.add_argument("--self-play-workers", type=int, default=8)
    parser.add_argument("--n-simulations", type=int, default=400)
    parser.add_argument("--checkpoint-dir", default="training/checkpoints/")
    parser.add_argument("--resume", default=None)
    parser.add_argument("--buffer-size", type=int, default=500_000)
    args = parser.parse_args()

    print("Verifying CoreGame throughput...")
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/benchmark_coregame.py", "--n-sims", "20",
         "--scenario", args.scenario],
        capture_output=True, text=True
    )
    print(result.stdout)
    if "NO-GO" in result.stdout:
        print("ERROR: CoreGame throughput insufficient. Implement __copy__ optimization first.")
        sys.exit(1)

    import engine.openspiel_env  # noqa
    import pyspiel
    from scenarios.loader import load_scenario
    from training.network import PolicyValueNetwork, load_network
    from training.replay_buffer import ReplayBuffer
    from training.trainer import AlphaZeroTrainer
    from training.self_play import SelfPlayRunner
    from training.league import LeagueTrainer
    from engine.action_space import ActionSpace

    scenario = load_scenario(Path(args.scenario))
    action_space = ActionSpace(scenario)

    game = pyspiel.load_game("astrakon", {"scenario_path": args.scenario})
    state = game.new_initial_state()
    input_dim = len(state.information_state_tensor(0))
    action_dim = action_space.TOTAL_ACTIONS

    print(f"Network dimensions: input_dim={input_dim}, action_dim={action_dim}")

    if args.resume:
        print(f"Resuming from {args.resume}")
        network = load_network(Path(args.resume))
    else:
        network = PolicyValueNetwork(input_dim=input_dim, action_dim=action_dim)

    buffer = ReplayBuffer(max_size=args.buffer_size)
    checkpoint_dir = Path(args.checkpoint_dir)

    trainer = AlphaZeroTrainer(
        network=network, buffer=buffer,
        lr=1e-3, checkpoint_dir=checkpoint_dir,
    )
    trainer._scenario_name = scenario.name.lower().replace(" ", "_")

    if args.resume:
        trainer.load_checkpoint(Path(args.resume))

    runner = SelfPlayRunner(
        network=network,
        game_params={"scenario_path": args.scenario},
        n_simulations=args.n_simulations,
    )

    league = LeagueTrainer(
        trainer=trainer, runner=runner,
        pool_size=15,
        games_per_iter=args.games_per_iter,
        train_steps_per_iter=args.train_steps_per_iter,
    )

    print(f"Starting training: {args.iterations} iterations, "
          f"{args.games_per_iter} games/iter, {args.train_steps_per_iter} steps/iter")
    print(f"Self-play workers: {args.self_play_workers}, simulations/decision: {args.n_simulations}")
    print()

    league.run(total_iterations=args.iterations)
    print("Training complete.")


if __name__ == "__main__":
    main()
