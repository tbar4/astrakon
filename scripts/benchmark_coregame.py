# scripts/benchmark_coregame.py
"""Measure CoreGame throughput. Must exceed 10 sim/sec to proceed with AlphaZero training."""
import time
import argparse
from pathlib import Path
from engine.core_game import CoreGame
from scenarios.loader import load_scenario


def run_one_simulation(core: CoreGame) -> None:
    clone = core.clone()
    while not clone.is_terminal():
        fidx = clone.acting_faction_idx()
        actions = clone.legal_actions(fidx)
        clone.apply_action(fidx, actions[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-sims", type=int, default=50)
    parser.add_argument("--scenario", default="scenarios/pacific_crossroads.yaml")
    args = parser.parse_args()

    scenario = load_scenario(Path(args.scenario))
    core = CoreGame(scenario)
    for turn_target in range(1, 7):
        while core.current_turn() == turn_target:
            fidx = core.acting_faction_idx()
            core.apply_action(fidx, core.legal_actions(fidx)[0])

    print(f"Benchmarking: {args.scenario}, turn {core.current_turn()}/{core._total_turns}")
    print(f"Running {args.n_sims} clone+rollout cycles...")
    start = time.perf_counter()
    for _ in range(args.n_sims):
        run_one_simulation(core)
    elapsed = time.perf_counter() - start

    sps = args.n_sims / elapsed
    print(f"\n  Total: {elapsed:.2f}s | {sps:.1f} sim/sec | {elapsed/args.n_sims*1000:.1f}ms/sim")
    if sps >= 10:
        print("GO: throughput >= 10 sim/sec")
    elif sps >= 5:
        print("CAUTION: throughput 5-10 sim/sec — add manual __copy__ optimization")
    else:
        print("NO-GO: throughput < 5 sim/sec — Cython required")


if __name__ == "__main__":
    main()
