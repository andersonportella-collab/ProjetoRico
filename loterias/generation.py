"""Carteiras únicas e reproduzíveis, sem materializar o espaço combinatório."""

from dataclasses import dataclass
from math import comb
from random import Random

from .config import MAX_COMPLETE_TICKETS, Lottery
from .probability import integer, validate_numbers
from .statistics import ScoreWeights, descriptive_score


@dataclass(frozen=True)
class Ticket:
    numbers: tuple[int, ...]
    month: int | None = None


def unrank_combination(pool: tuple[int, ...], size: int, rank: int) -> tuple[int, ...]:
    """Combinação lexicográfica no índice rank, em O(len(pool) * size)."""
    if not 0 <= rank < comb(len(pool), size):
        raise ValueError("Índice de combinação inválido.")
    result, start = [], 0
    for remaining in range(size, 0, -1):
        for index in range(start, len(pool) - remaining + 1):
            block = comb(len(pool) - index - 1, remaining - 1)
            if rank < block:
                result.append(pool[index])
                start = index + 1
                break
            rank -= block
    return tuple(result)


def uniform_games(pool, size: int, count: int, rng: Random) -> list[tuple[int, ...]]:
    pool = tuple(sorted(pool))
    size, count = integer(size, "Dezenas"), integer(count, "Quantidade")
    if not pool or len(set(pool)) != len(pool) or not 1 <= size <= len(pool):
        raise ValueError("Pool ou tamanho de jogo inválido.")
    total = comb(len(pool), size)
    if not 1 <= count <= min(total, MAX_COMPLETE_TICKETS):
        raise ValueError(f"Quantidade deve estar entre 1 e {min(total, MAX_COMPLETE_TICKETS)}.")
    # Amostrar índices uniformes sem reposição também evita duplicação entre bilhetes.
    ranks = rng.sample(range(total), count)
    return [unrank_combination(pool, size, rank) for rank in ranks]


def generate_uniform(
    lottery: Lottery, size: int, count: int, seed: int, month: int | None = None
) -> list[Ticket]:
    if not lottery.draw_size <= size <= lottery.max_ticket:
        raise ValueError("Tamanho de aposta inválido.")
    if month is not None and not 1 <= month <= 12:
        raise ValueError("Mês inválido.")
    rng = Random(seed)
    games = uniform_games(range(1, lottery.population + 1), size, count, rng)
    return [
        Ticket(g, (month or rng.randint(1, 12)) if lottery.key == "diadesorte" else None)
        for g in games
    ]


def heuristic_games(
    lottery: Lottery, size: int, count: int, seed: int, stats, weights: ScoreWeights
) -> list[Ticket]:
    """Seleciona candidatos por preferência; não alega vantagem preditiva."""
    if not lottery.draw_size <= size <= lottery.max_ticket:
        raise ValueError("Tamanho de aposta inválido.")
    count = integer(count, "Quantidade")
    if not 1 <= count <= 200:
        raise ValueError("A heurística permite de 1 a 200 jogos.")
    candidates = min(comb(lottery.population, size), max(count, min(2000, count * 20)))
    rng = Random(seed)
    games = uniform_games(range(1, lottery.population + 1), size, candidates, rng)
    games.sort(key=lambda g: descriptive_score(g, stats, weights), reverse=True)
    return [
        Ticket(g, rng.randint(1, 12) if lottery.key == "diadesorte" else None)
        for g in games[:count]
    ]


def make_tickets(games, lottery: Lottery, seed: int, month: int | None = None) -> list[Ticket]:
    if month is not None and not 1 <= month <= 12:
        raise ValueError("Mês inválido.")
    rng = Random(seed)
    validated = [
        validate_numbers(g, lottery.population, lottery.draw_size, lottery.max_ticket)
        for g in games
    ]
    if len(validated) != len(set(validated)):
        raise ValueError("Carteira contém jogos repetidos.")
    return [
        Ticket(g, (month or rng.randint(1, 12)) if lottery.key == "diadesorte" else None)
        for g in validated
    ]
