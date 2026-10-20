"""Otimização de cobertura e certificados condicionais, nunca previsão."""

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from math import comb
from random import Random

from .config import (
    MAX_COMPLETE_TICKETS,
    MAX_COVERAGE_OPERATIONS,
    MAX_COVERAGE_OUTCOMES,
    MAX_OPTIMIZATION_OPERATIONS,
)
from .generation import uniform_games
from .probability import integer, validate_numbers


@dataclass(frozen=True)
class CoverageReport:
    exact: bool
    total_outcomes: int
    evaluated: int
    threshold: int
    covered: int | None
    worst_hits: int | None
    counterexample: tuple[int, ...] | None
    distribution: dict[int, int]
    reason: str = ""

    @property
    def guaranteed(self) -> bool:
        return self.exact and self.worst_hits is not None and self.worst_hits >= self.threshold

    @property
    def conditional_probability(self) -> Fraction | None:
        return Fraction(self.covered, self.evaluated) if self.exact and self.evaluated else None


@dataclass(frozen=True)
class OptimizationResult:
    games: tuple[tuple[int, ...], ...]
    baseline: tuple[tuple[int, ...], ...]
    training_outcomes: int
    training_exact: bool
    training_covered: int
    baseline_training_covered: int
    seed: int
    method: str
    validation_outcomes: int
    validation_covered: int
    baseline_validation_covered: int


def _pool(pool):
    return validate_numbers(pool, 60, 1, 60)


def _validated(pool, size, count=None):
    pool = _pool(pool)
    size = integer(size, "Dezenas por jogo")
    if not 1 <= size <= len(pool):
        raise ValueError("Tamanho de jogo inválido para o pool.")
    if count is not None:
        count = integer(count, "Quantidade")
        if not 1 <= count <= min(comb(len(pool), size), MAX_COMPLETE_TICKETS):
            raise ValueError("Quantidade fora do limite ou superior às combinações disponíveis.")
    return pool


def complete_closure(pool, size: int) -> list[tuple[int, ...]]:
    size = integer(size, "Dezenas por jogo")
    pool = _validated(pool, size)
    total = comb(len(pool), size)
    if total > MAX_COMPLETE_TICKETS:
        raise ValueError(
            f"Fechamento exige {total:,} jogos e supera o limite de {MAX_COMPLETE_TICKETS:,}. "
            "Reduza o pool ou escolha parcial. Nenhum fechamento completo será truncado."
        )
    return list(combinations(pool, size))


def _mask(game):
    return sum(1 << (n - 1) for n in game)


def certify_coverage(pool, games, draw_size: int, threshold: int) -> CoverageReport:
    """Prova condicional a TODAS as dezenas sorteadas pertencerem ao pool.

    Se o trabalho exceder os limites, devolve explicitamente 'não certificado'.
    A presença individual das dezenas não participa do critério de garantia.
    """
    pool = _pool(pool)
    draw_size, threshold = integer(draw_size, "Dezenas sorteadas"), integer(threshold, "Meta")
    if not 1 <= threshold <= draw_size <= len(pool):
        raise ValueError("Faixa de acertos ou quantidade sorteada inválida.")
    games = [validate_numbers(g, 60, draw_size, len(pool)) for g in games]
    if not games or any(not set(g).issubset(pool) for g in games):
        raise ValueError("Jogos devem ser não vazios e estar contidos no pool.")
    unique = set(games)
    total = comb(len(pool), draw_size)
    # Prova por construção: todas as combinações de um tamanho k >= d estão presentes.
    lengths = {len(g) for g in unique}
    if len(lengths) == 1 and len(unique) == comb(len(pool), len(games[0])):
        return CoverageReport(
            True,
            total,
            total,
            threshold,
            total,
            draw_size,
            None,
            {draw_size: total},
            "Cobertura completa demonstrada por construção.",
        )
    if total > MAX_COVERAGE_OUTCOMES or total * len(unique) > MAX_COVERAGE_OPERATIONS:
        return CoverageReport(
            False,
            total,
            0,
            threshold,
            None,
            None,
            None,
            {},
            "Certificação exaustiva excede o limite de trabalho. Nenhuma garantia foi comprovada.",
        )
    masks = [_mask(g) for g in unique]
    distribution, witness, minimum = Counter(), None, draw_size
    for outcome in combinations(pool, draw_size):
        mask = _mask(outcome)
        best = max((mask & game).bit_count() for game in masks)
        distribution[best] += 1
        minimum = min(minimum, best)
        if best < threshold and witness is None:
            witness = outcome
    covered = sum(n for hits, n in distribution.items() if hits >= threshold)
    return CoverageReport(
        True, total, total, threshold, covered, minimum, witness, dict(distribution)
    )


def optimize_portfolio(
    pool,
    size: int,
    count: int,
    draw_size: int,
    threshold: int,
    seed: int,
    *,
    method: str = "greedy",
    generations: int = 30,
    population: int = 40,
    scenarios: int = 512,
    candidates: int = 400,
) -> OptimizationResult:
    """Maximiza cenários com >= threshold acertos; heurística sem ótimo global garantido.

    Cenários de treinamento são uniformes. O certificado posterior é independente
    do score de treinamento. O AG mantém a referência aleatória como incumbente.
    """
    size, count = integer(size, "Dezenas por jogo"), integer(count, "Quantidade")
    pool = _validated(pool, size, count)
    if not 1 <= threshold <= draw_size <= size:
        raise ValueError("Acertos e tamanho do sorteio devem ser compatíveis com o jogo.")
    if method not in {"greedy", "genetic"}:
        raise ValueError("Método desconhecido.")
    if not 1 <= count <= 200 or not 1 <= generations <= 100 or not 4 <= population <= 100:
        raise ValueError("Use até 200 jogos, 1–100 gerações e população 4–100.")
    if not 1 <= scenarios <= 2000 or not count <= candidates <= 2000:
        raise ValueError("Cenários ou candidatos fora do limite.")
    total_games, total_outcomes = comb(len(pool), size), comb(len(pool), draw_size)
    candidates, scenarios = min(candidates, total_games), min(scenarios, total_outcomes)
    operations = candidates * scenarios + population * generations * count
    if operations > MAX_OPTIMIZATION_OPERATIONS:
        raise ValueError("Otimização excede o limite de trabalho; reduza os parâmetros.")
    rng = Random(seed)
    candidate_games = uniform_games(pool, size, candidates, rng)
    outcomes = uniform_games(pool, draw_size, scenarios, rng)
    outcome_masks = [_mask(g) for g in outcomes]
    covered_masks = []
    for game in candidate_games:
        game_mask = _mask(game)
        covered_masks.append(
            sum(
                1 << i
                for i, outcome in enumerate(outcome_masks)
                if (game_mask & outcome).bit_count() >= threshold
            )
        )

    def score(individual):
        mask = 0
        for index in individual:
            mask |= covered_masks[index]
        return mask.bit_count()

    baseline = tuple(rng.sample(range(candidates), count))
    selected, remaining, covered = [], set(range(candidates)), 0
    for _ in range(count):
        chosen = max(sorted(remaining), key=lambda i: (covered_masks[i] & ~covered).bit_count())
        selected.append(chosen)
        remaining.remove(chosen)
        covered |= covered_masks[chosen]
    best = max([baseline, tuple(selected)], key=score)
    if method == "genetic":
        pop = [best, baseline] + [
            tuple(rng.sample(range(candidates), count)) for _ in range(population - 2)
        ]
        best_score, stagnant = score(best), 0
        for _ in range(generations):
            ranked = sorted(pop, key=score, reverse=True)
            if score(ranked[0]) > best_score:
                best, best_score, stagnant = ranked[0], score(ranked[0]), 0
            else:
                stagnant += 1
            if stagnant >= 12:
                break
            new = ranked[: max(2, population // 5)]
            while len(new) < population:
                a, b = rng.sample(ranked[: max(4, population // 2)], 2)
                union = sorted(set(a) | set(b))
                child = rng.sample(union, count)
                if count < candidates and rng.random() < 0.3:
                    replacement = rng.choice(sorted(set(range(candidates)) - set(child)))
                    child[rng.randrange(count)] = replacement
                new.append(tuple(sorted(child)))
            pop = new
        best = max([best, *pop], key=score)  # avalia a última geração também
    # Validação em cenários que NÃO participaram da seleção da carteira.
    # Quando o treinamento já é exaustivo, não há amostra restante.
    validation_size = min(512, total_outcomes - scenarios)
    training = set(outcomes)
    validation = set()
    validation_rng = Random(seed + 1_000_003)
    if validation_size and total_outcomes <= MAX_COVERAGE_OUTCOMES:
        remaining_outcomes = [g for g in combinations(pool, draw_size) if g not in training]
        validation = set(validation_rng.sample(remaining_outcomes, validation_size))
    elif validation_size:
        # O espaço é grande e o treinamento ocupa < 10% dele. Rejeição limitada.
        for _ in range(10):
            batch = uniform_games(pool, draw_size, min(1024, total_outcomes), validation_rng)
            validation.update(g for g in batch if g not in training)
            if len(validation) >= validation_size:
                validation = set(validation_rng.sample(sorted(validation), validation_size))
                break

    def held_out_score(individual):
        games = [_mask(candidate_games[i]) for i in individual]
        return sum(
            any((_mask(outcome) & game).bit_count() >= threshold for game in games)
            for outcome in validation
        )

    return OptimizationResult(
        tuple(candidate_games[i] for i in best),
        tuple(candidate_games[i] for i in baseline),
        scenarios,
        scenarios == total_outcomes,
        score(best),
        score(baseline),
        seed,
        method,
        len(validation),
        held_out_score(best),
        held_out_score(baseline),
    )
