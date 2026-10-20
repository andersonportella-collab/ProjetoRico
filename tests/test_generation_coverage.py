from itertools import combinations
from math import comb
from random import Random

import pytest

from loterias.config import LOTTERIES
from loterias.coverage import certify_coverage, complete_closure, optimize_portfolio
from loterias.generation import generate_uniform, make_tickets, uniform_games, unrank_combination


def test_unranking_matches_exhaustive_small_spaces():
    for n in range(1, 10):
        pool = tuple(range(1, n + 1))
        for k in range(1, n + 1):
            assert [unrank_combination(pool, k, r) for r in range(comb(n, k))] == list(
                combinations(pool, k)
            )


@pytest.mark.parametrize("key", list(LOTTERIES))
def test_uniform_portfolio_is_unique_valid_and_reproducible(key):
    cfg = LOTTERIES[key]
    a = generate_uniform(cfg, cfg.draw_size, 200, 42)
    assert a == generate_uniform(cfg, cfg.draw_size, 200, 42)
    assert a != generate_uniform(cfg, cfg.draw_size, 200, 43)
    assert len({t.numbers for t in a}) == 200
    assert all(len(t.numbers) == cfg.draw_size and len(set(t.numbers)) == cfg.draw_size for t in a)
    assert all(min(t.numbers) >= 1 and max(t.numbers) <= cfg.population for t in a)


def test_large_space_is_sampled_without_enumerating_combinations():
    result = uniform_games(range(1, 61), 20, 200, Random(10))
    assert len(set(result)) == 200


def test_complete_is_not_truncated_at_500():
    games = complete_closure(range(1, 13), 6)
    assert len(games) == 924
    assert len(set(games)) == 924
    assert certify_coverage(range(1, 13), games, 6, 6).guaranteed


def test_complete_work_limit_rejects_before_enumeration(monkeypatch):
    def forbidden(*args):
        raise AssertionError("Não deveria enumerar este espaço.")

    monkeypatch.setattr("loterias.coverage.combinations", forbidden)
    with pytest.raises(ValueError, match="supera o limite"):
        complete_closure(range(1, 28), 15)


def test_number_coverage_does_not_imply_prize_guarantee():
    pool = tuple(range(1, 19))
    games = [pool[:6], pool[6:12], pool[12:]]
    report = certify_coverage(pool, games, 6, 4)
    assert set.union(*map(set, games)) == set(pool)
    assert report.exact and not report.guaranteed
    assert report.worst_hits == 2
    assert report.counterexample is not None
    assert max(len(set(report.counterexample) & set(g)) for g in games) < 4


def test_certificate_matches_independent_brute_force():
    pool = tuple(range(1, 10))
    games = uniform_games(pool, 6, 8, Random(20))
    outcomes = list(combinations(pool, 6))
    counts = [max(len(set(o) & set(g)) for g in games) for o in outcomes]
    report = certify_coverage(pool, games, 6, 4)
    assert report.evaluated == len(outcomes)
    assert report.covered == sum(hit >= 4 for hit in counts)
    assert report.worst_hits == min(counts)
    assert report.guaranteed == (min(counts) >= 4)


def test_certificate_limits_never_turn_into_sampled_guarantees():
    report = certify_coverage(range(1, 61), [range(1, 7)], 6, 4)
    assert not report.exact and not report.guaranteed
    assert report.conditional_probability is None and report.evaluated == 0


def test_duplicate_tickets_cannot_fake_complete_certificate():
    games = [tuple(range(1, 7))] * 7
    report = certify_coverage(range(1, 8), games, 6, 6)
    assert not report.guaranteed and report.covered == 1


@pytest.mark.parametrize("method", ["greedy", "genetic"])
def test_optimizer_is_unique_reproducible_and_preserves_baseline(method):
    args = (tuple(range(1, 12)), 6, 10, 6, 4, 42)
    result = optimize_portfolio(*args, method=method, generations=5, population=12)
    assert result == optimize_portfolio(*args, method=method, generations=5, population=12)
    assert len(set(result.games)) == 10
    assert result.training_covered >= result.baseline_training_covered
    assert len(result.baseline) == len(result.games)
    assert all(set(g) <= set(range(1, 12)) for g in result.games)


@pytest.mark.parametrize("key", list(LOTTERIES))
def test_optimizer_all_lotteries(key):
    cfg = LOTTERIES[key]
    pool = tuple(range(1, cfg.draw_size + 4))
    result = optimize_portfolio(pool, cfg.draw_size, 5, cfg.draw_size, cfg.min_prize, 1)
    assert len(set(result.games)) == 5
    assert certify_coverage(pool, result.games, cfg.draw_size, cfg.min_prize).exact


def test_invalid_month_and_duplicate_tickets_rejected():
    cfg = LOTTERIES["diadesorte"]
    with pytest.raises(ValueError):
        generate_uniform(cfg, 7, 5, 42, 13)
    with pytest.raises(ValueError):
        make_tickets([range(1, 8)] * 2, cfg, 42)


def test_impossible_partial_count_rejected():
    with pytest.raises(ValueError):
        uniform_games(range(1, 8), 6, 8, Random(0))


def test_held_out_validation_separate_from_training_and_exhaustive_certificate():
    result = optimize_portfolio(range(1, 15), 6, 10, 6, 4, 42, scenarios=64)
    assert not result.training_exact and result.validation_outcomes == 512
    assert 0 <= result.validation_covered <= 512
    assert 0 <= result.baseline_validation_covered <= 512
    exact = certify_coverage(range(1, 15), result.games, 6, 4)
    assert exact.evaluated == 3003


def test_no_held_out_sample_when_training_is_exhaustive():
    result = optimize_portfolio(range(1, 9), 6, 5, 6, 4, 42)
    assert result.training_exact and result.validation_outcomes == 0
