from decimal import Decimal
from fractions import Fraction
from math import comb

import pytest

from loterias.config import LOTTERIES
from loterias.probability import (
    affordable_count,
    exact_hits_probability,
    integer,
    jackpot_probability,
    sum_reference,
    ticket_price,
    validate_numbers,
)


@pytest.mark.parametrize(
    "key,size,price",
    [
        ("megasena", 6, "6.00"),
        ("megasena", 7, "42.00"),
        ("megasena", 20, "232560.00"),
        ("lotofacil", 15, "3.50"),
        ("lotofacil", 16, "56.00"),
        ("diadesorte", 7, "2.50"),
        ("diadesorte", 15, "16087.50"),
    ],
)
def test_official_prices(key, size, price):
    assert ticket_price(LOTTERIES[key], size) == Decimal(price)


def test_custom_price_and_budget_use_decimal():
    assert ticket_price(LOTTERIES["megasena"], 7, Decimal("6.01")) == Decimal("42.07")
    assert affordable_count(Decimal("0.30"), Decimal("0.10")) == 3
    assert affordable_count(Decimal("41.99"), Decimal("42")) == 0


def test_hypergeometric_probabilities_sum_to_one():
    for cfg in LOTTERIES.values():
        for size in range(cfg.draw_size, cfg.max_ticket + 1):
            probabilities = [exact_hits_probability(cfg, size, h) for h in range(cfg.draw_size + 1)]
            assert sum(probabilities) == 1
            assert probabilities[-1] == Fraction(
                comb(size, cfg.draw_size), comb(cfg.population, cfg.draw_size)
            )


def test_mega_reference_probabilities():
    cfg = LOTTERIES["megasena"]
    assert exact_hits_probability(cfg, 6, 6) == Fraction(1, 50_063_860)
    assert exact_hits_probability(cfg, 7, 6) == Fraction(1, 7_151_980)
    assert exact_hits_probability(cfg, 6, 5) == Fraction(324, 50_063_860)
    assert exact_hits_probability(cfg, 6, 4) == Fraction(21_465, 50_063_860)


def test_overlapping_multiple_tickets_count_union_not_sum():
    cfg = LOTTERIES["megasena"]
    a, b = tuple(range(1, 8)), tuple(range(2, 9))
    probability, count = jackpot_probability(cfg, [a, b, a])
    # 7 + 7, com uma combinação simples em comum.
    assert count == 13
    assert probability == Fraction(13, 50_063_860)


def test_equal_budget_sena_equivalence():
    from itertools import combinations

    cfg = LOTTERIES["megasena"]
    assert jackpot_probability(cfg, [range(1, 8)]) == jackpot_probability(
        cfg, combinations(range(1, 8), 6)
    )


def test_work_limit_does_not_publish_approximate_exact_probability():
    probability, count = jackpot_probability(LOTTERIES["megasena"], [range(1, 21)] * 6)
    assert probability is None and count is None


def test_sum_reference_scales_with_ticket_size():
    assert sum_reference(60, 6) == pytest.approx((183, 40.5832477754))
    assert sum_reference(60, 10)[0] == 305
    assert sum_reference(25, 25) == (325, 0)


@pytest.mark.parametrize("value", [True, 1.2, "1.0", "abc", None, float("inf")])
def test_invalid_integer_input(value):
    with pytest.raises(ValueError):
        integer(value, "Teste")


def test_zero_padded_api_numbers_are_valid():
    assert validate_numbers(["01", "02", "03", "04", "05", "60"], 60, 6, 6) == (1, 2, 3, 4, 5, 60)


@pytest.mark.parametrize("numbers", [[1, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 61]])
def test_reject_invalid_game(numbers):
    with pytest.raises(ValueError):
        validate_numbers(numbers, 60, 6, 6)


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-1", "0", "6.001"])
def test_invalid_price(price):
    with pytest.raises(ValueError):
        ticket_price(LOTTERIES["megasena"], 6, Decimal(price))
