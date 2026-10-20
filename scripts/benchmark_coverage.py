"""Execute: python -m scripts.benchmark_coverage. Não acessa a rede."""

import json

from loterias.coverage import certify_coverage, optimize_portfolio


def main():
    results = []
    for method in ("greedy", "genetic"):
        for seed in range(5):
            result = optimize_portfolio(range(1, 13), 6, 10, 6, 5, seed, method=method)
            exact = certify_coverage(range(1, 13), result.games, 6, 5)
            baseline = certify_coverage(range(1, 13), result.baseline, 6, 5)
            results.append(
                {
                    "method": method,
                    "seed": seed,
                    "games": 10,
                    "pool": 12,
                    "target": 5,
                    "total_outcomes": exact.total_outcomes,
                    "optimized_covered_exact": exact.covered,
                    "baseline_covered_exact": baseline.covered,
                    "training_covered": result.training_covered,
                    "validation_outcomes": result.validation_outcomes,
                    "validation_covered": result.validation_covered,
                    "baseline_validation_covered": result.baseline_validation_covered,
                    "conditional_guarantee": exact.guaranteed,
                }
            )
    print(
        json.dumps(
            {
                "note": "Comparação específica de carteiras, condicionada ao pool; não prevê sorteios.",
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
