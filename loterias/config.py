"""Regras e preços parametrizados, com data e fonte de conferência."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Lottery:
    key: str
    label: str
    population: int
    draw_size: int
    max_ticket: int
    min_prize: int
    base_price: Decimal
    rules_url: str
    api_type: str


PRICE_CHECKED_ON = "2026-10-20"
LOTTERIES = {
    "megasena": Lottery(
        "megasena",
        "Mega-Sena",
        60,
        6,
        20,
        4,
        Decimal("6.00"),
        "https://loterias.caixa.gov.br/Paginas/mega-sena.aspx",
        "MEGA_SENA",
    ),
    "lotofacil": Lottery(
        "lotofacil",
        "Lotofácil",
        25,
        15,
        20,
        11,
        Decimal("3.50"),
        "https://loterias.caixa.gov.br/Paginas/Lotofacil.aspx",
        "LOTOFACIL",
    ),
    "diadesorte": Lottery(
        "diadesorte",
        "Dia de Sorte",
        31,
        7,
        15,
        4,
        Decimal("2.50"),
        "https://loterias.caixa.gov.br/Paginas/Dia-de-Sorte.aspx",
        "DIA_DE_SORTE",
    ),
}
MONTHS = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)

# Limites de trabalho, verificados ANTES de enumerar combinações.
MAX_COMPLETE_TICKETS = 20_000
MAX_COVERAGE_OUTCOMES = 20_000
MAX_COVERAGE_OPERATIONS = 5_000_000
MAX_EXPANDED_COMBINATIONS = 200_000
MAX_OPTIMIZATION_OPERATIONS = 20_000_000
