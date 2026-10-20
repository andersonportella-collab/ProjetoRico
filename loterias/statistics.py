"""Estatística descritiva. Estes indicadores não são previsões."""

from collections import Counter
from dataclasses import dataclass, fields
from itertools import combinations, pairwise
from math import isfinite, log1p

import numpy as np
import pandas as pd

from .config import Lottery
from .data import Draw
from .probability import sum_reference, validate_numbers


@dataclass(frozen=True)
class DescriptiveStats:
    lottery: Lottery
    total: int
    frequency: dict[int, int]
    delay: dict[int, int]
    recent_delta: dict[int, float]
    cooccurrence: dict[tuple[int, int], int]
    window: int


def calculate_stats(
    draws: tuple[Draw, ...], lottery: Lottery, window: int = 30
) -> DescriptiveStats:
    if not draws or window < 1:
        raise ValueError("Histórico e janela devem ser não vazios.")
    draws = tuple(sorted(draws, key=lambda d: d.contest))
    if any(b.contest != a.contest + 1 for a, b in pairwise(draws)):
        raise ValueError("As estatísticas exigem concursos consecutivos, sem duplicações.")
    for draw in draws:
        validate_numbers(draw.numbers, lottery.population, lottery.draw_size, lottery.draw_size)
    total, window = len(draws), min(window, len(draws))
    freq, recent, cooc = Counter(), Counter(), Counter()
    last = {}
    for index, draw in enumerate(draws):
        freq.update(draw.numbers)
        cooc.update(combinations(draw.numbers, 2))
        last.update({number: index for number in draw.numbers})
    for draw in draws[-window:]:
        recent.update(draw.numbers)
    numbers = range(1, lottery.population + 1)
    return DescriptiveStats(
        lottery,
        total,
        {n: freq[n] for n in numbers},
        {n: total - last[n] - 1 if n in last else total for n in numbers},
        {n: recent[n] / window - freq[n] / total for n in numbers},
        dict(cooc),
        window,
    )


def stats_table(stats: DescriptiveStats) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Dezena": n,
                "Frequência": stats.frequency[n],
                "Presença (%)": 100 * stats.frequency[n] / stats.total,
                "Ausências consecutivas": stats.delay[n],
                "Atraso é limite inferior": stats.frequency[n] == 0,
                "Variação recente (p.p.)": 100 * stats.recent_delta[n],
            }
            for n in range(1, stats.lottery.population + 1)
        ]
    )


@dataclass(frozen=True)
class ScoreWeights:
    frequency: float = 0.0
    delay: float = 0.0
    trend: float = 0.0
    parity: float = 0.0
    sequence: float = 0.0
    dispersion: float = 0.0
    sum: float = 0.0
    cooccurrence: float = 0.0

    def __post_init__(self):
        if any(
            not isfinite(getattr(self, f.name)) or getattr(self, f.name) < 0 for f in fields(self)
        ):
            raise ValueError("Pesos devem ser finitos e não negativos.")


def descriptive_score(game, stats: DescriptiveStats, weights: ScoreWeights) -> float:
    """Preferência descritiva, sem penalidades ou pesos implícitos."""
    cfg = stats.lottery
    game = validate_numbers(game, cfg.population, cfg.draw_size, cfg.max_ticket)
    k, expected = len(game), cfg.draw_size / cfg.population
    mean, std = sum_reference(cfg.population, k)
    even = sum(n % 2 == 0 for n in game)
    pair_frequency = np.mean(
        [stats.cooccurrence.get(pair, 0) / stats.total for pair in combinations(game, 2)]
    )
    components = {
        "frequency": np.mean([stats.frequency[n] / stats.total for n in game]) / expected,
        "delay": np.mean([log1p(stats.delay[n]) for n in game]) / log1p(stats.total),
        "trend": np.mean([stats.recent_delta[n] for n in game]) / expected,
        "parity": -abs(even - k * (cfg.population // 2) / cfg.population) / k,
        "sequence": -sum(b == a + 1 for a, b in pairwise(game)) / (k - 1),
        "dispersion": (game[-1] - game[0]) / (cfg.population - 1),
        "sum": -abs(sum(game) - mean) / (std or 1),
        "cooccurrence": pair_frequency
        / (cfg.draw_size * (cfg.draw_size - 1) / (cfg.population * (cfg.population - 1))),
    }
    return float(sum(getattr(weights, key) * value for key, value in components.items()))
