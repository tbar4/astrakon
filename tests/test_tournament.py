import pytest
from runners.tournament import TournamentRunner, TournamentResult
from agents.rule_based import MahanianAgent, GrayZoneAgent


def make_mahanian():
    return MahanianAgent()


def make_grayzone():
    return GrayZoneAgent()


def test_tournament_result_has_elo():
    runner = TournamentRunner()
    result = runner.run_round_robin(
        agent_strategies={"mahanian": make_mahanian, "gray_zone": make_grayzone},
        scenario_paths=["scenarios/pacific_crossroads.yaml"],
        games_per_matchup=4,
        n_workers=1,
    )
    assert "mahanian" in result.elo_ratings
    assert "gray_zone" in result.elo_ratings
    for elo in result.elo_ratings.values():
        assert -float("inf") < elo < float("inf")


def test_coalition_swap_occurs():
    runner = TournamentRunner()
    result = runner.run_round_robin(
        agent_strategies={"a": make_mahanian, "b": make_grayzone},
        scenario_paths=["scenarios/pacific_crossroads.yaml"],
        games_per_matchup=4,
        n_workers=1,
    )
    assert len(result.raw_results) == 4


def test_per_scenario_win_rates_populated():
    runner = TournamentRunner()
    result = runner.run_round_robin(
        agent_strategies={"a": make_mahanian, "b": make_grayzone},
        scenario_paths=["scenarios/pacific_crossroads.yaml"],
        games_per_matchup=2,
        n_workers=1,
    )
    assert len(result.per_scenario_win_rates) > 0


def test_win_matrix_is_square():
    runner = TournamentRunner()
    result = runner.run_round_robin(
        agent_strategies={"a": make_mahanian, "b": make_grayzone},
        scenario_paths=["scenarios/pacific_crossroads.yaml"],
        games_per_matchup=2,
        n_workers=1,
    )
    strategies = list(result.win_matrix.keys())
    for s in strategies:
        assert set(result.win_matrix[s].keys()) == set(strategies)
