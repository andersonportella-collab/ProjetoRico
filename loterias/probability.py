"""Probabilidades exatas sob sorteios uniformes e independentes."""

import re
from decimal import Decimal
from fractions import Fraction
from itertools import combinations
from math import comb, sqrt

from .config import MAX_EXPANDED_COMBINATIONS, Lottery


def integer(value, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name}: informe um número inteiro.")
    if not re.fullmatch(r"[+-]?\d+", str(value).strip()):
        raise ValueError(f"{name}: informe um número inteiro.")
    return int(value)


def validate_numbers(numbers, population: int, minimum: int, maximum: int) -> tuple[int, ...]:
    result = tuple(sorted(integer(x, "Dezena") for x in numbers))
    if not minimum <= len(result) <= maximum:
        raise ValueError(f"Informe entre {minimum} e {maximum} dezenas.")
    if len(set(result)) != len(result):
        raise ValueError("Há dezenas repetidas no mesmo conjunto.")
    if any(x < 1 or x > population for x in result):
        raise ValueError(f"As dezenas devem estar entre 1 e {population}.")
    return result


def ticket_price(lottery: Lottery, size: int, base_price: Decimal | None = None) -> Decimal:
    size = integer(size, "Quantidade de dezenas")
    if not lottery.draw_size <= size <= lottery.max_ticket:
        raise ValueError("Quantidade de dezenas fora dos limites da modalidade.")
    price = lottery.base_price if base_price is None else Decimal(str(base_price))
    if not price.is_finite() or price <= 0:
        raise ValueError("Preço deve ser positivo e finito.")
    if price != price.quantize(Decimal("0.01")):
        raise ValueError("Preço deve ter no máximo duas casas decimais.")
    return price * comb(size, lottery.draw_size)


def affordable_count(budget: Decimal, unit_price: Decimal) -> int:
    budget, unit_price = Decimal(str(budget)), Decimal(str(unit_price))
    if not budget.is_finite() or budget < 0 or not unit_price.is_finite() or unit_price <= 0:
        raise ValueError("Orçamento não negativo e preço positivo devem ser finitos.")
    return int(budget // unit_price)


def exact_hits_probability(lottery: Lottery, ticket_size: int, hits: int) -> Fraction:
    ticket_price(lottery, ticket_size)  # valida tamanho
    hits = integer(hits, "Acertos")
    d, n = lottery.draw_size, lottery.population
    if not 0 <= hits <= d or d - hits > n - ticket_size:
        return Fraction(0)
    return Fraction(comb(ticket_size, hits) * comb(n - ticket_size, d - hits), comb(n, d))


def sum_reference(population: int, size: int) -> tuple[float, float]:
    if not 1 <= size <= population:
        raise ValueError("Tamanho inválido.")
    return size * (population + 1) / 2, sqrt(size * (population - size) * (population + 1) / 12)


def jackpot_probability(lottery: Lottery, games) -> tuple[Fraction | None, int | None]:
    """Conta a UNIÃO das apostas simples; não soma probabilidades sobrepostas.

    Dia de Sorte: apenas os acertos das dezenas, sem o prêmio independente do mês.
    None significa que a expansão ultrapassaria o limite de trabalho.
    """
    validated = [
        validate_numbers(g, lottery.population, lottery.draw_size, lottery.max_ticket)
        for g in games
    ]
    if sum(comb(len(g), lottery.draw_size) for g in validated) > MAX_EXPANDED_COMBINATIONS:
        return None, None
    covered = {c for g in validated for c in combinations(g, lottery.draw_size)}
    return Fraction(len(covered), comb(lottery.population, lottery.draw_size)), len(covered)
