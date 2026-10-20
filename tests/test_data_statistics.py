from datetime import date

import pytest
import requests

from loterias.config import LOTTERIES
from loterias.data import (
    LEGACY,
    MIRROR,
    OFFICIAL,
    Draw,
    load_history,
    parse_draw,
    parse_history,
    parse_month,
)
from loterias.statistics import ScoreWeights, calculate_stats, descriptive_score


def record(contest=1, numbers=None, day="18/10/2026", **kwargs):
    return {
        "numero": contest,
        "listaDezenas": numbers or ["01", "02", "03", "04", "05", "06"],
        "dataApuracao": day,
        "tipoJogo": "MEGA_SENA",
        **kwargs,
    }


def fake_fetch(routes):
    def fetch(url):
        value = routes.get(url, requests.ConnectionError("Indisponível no teste"))
        if isinstance(value, Exception):
            raise value
        return value

    return fetch


def test_parse_official_month_and_numbers():
    raw = record(
        numbers=["01", "02", "03", "04", "05", "06", "31"],
        tipoJogo="DIA_DE_SORTE",
        nomeTimeCoracaoMesSorte="Março",
    )
    d = parse_draw(raw, "diadesorte")
    assert d.month == 3 and d.draw_date == date(2026, 10, 18)
    assert parse_month("MARCO") == 3 and parse_month("12") == 12


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {},
        {"1": ["1", "1", "2", "3", "4", "5"]},
        {"1": ["1", "2", "3"]},
        [record(), record()],
        [record(1), record(3)],
    ],
)
def test_invalid_history_is_rejected_instead_of_silently_skipping(raw):
    with pytest.raises(ValueError):
        parse_history(raw, "megasena")


def test_official_incremental_update():
    routes = {
        f"{OFFICIAL}/megasena": record(3),
        f"{MIRROR}/megasena/_todos.json": [record(1, day="15/10/2026")],
        f"{OFFICIAL}/megasena/2": record(2, day="16/10/2026"),
    }
    h = load_history("megasena", fake_fetch(routes), today=date(2026, 10, 20))
    assert [d.contest for d in h.draws] == [1, 2, 3]
    assert h.verified_latest and h.complete and h.official_latest == 3


def test_official_overrides_conflicting_latest_mirror():
    routes = {
        f"{OFFICIAL}/megasena": record(1),
        f"{MIRROR}/megasena/_todos.json": [record(1, numbers=[2, 3, 4, 5, 6, 7])],
    }
    h = load_history("megasena", fake_fetch(routes), today=date(2026, 10, 20))
    assert h.draws[-1].numbers == (1, 2, 3, 4, 5, 6)
    assert any("divergia" in warning for warning in h.warnings)


def test_large_gap_loads_bounded_contiguous_official_window():
    routes = {
        f"{OFFICIAL}/megasena": record(100),
        f"{MIRROR}/megasena/_todos.json": [record(1, day="01/01/2026")],
        f"{OFFICIAL}/megasena/98": record(98, day="16/10/2026"),
        f"{OFFICIAL}/megasena/99": record(99, day="17/10/2026"),
    }
    h = load_history("megasena", fake_fetch(routes), max_refresh=3, today=date(2026, 10, 20))
    assert [d.contest for d in h.draws] == [98, 99, 100]
    assert not h.complete and h.verified_latest


def test_update_failure_keeps_old_contiguous_base_and_warns():
    routes = {
        f"{OFFICIAL}/megasena": record(3),
        f"{MIRROR}/megasena/_todos.json": [record(1, day="01/01/2026")],
    }
    h = load_history("megasena", fake_fetch(routes), today=date(2026, 10, 20))
    assert h.last_contest == 1 and not h.verified_latest
    assert any("2 concursos" in warning for warning in h.warnings)


def test_official_failure_fallback_does_not_claim_freshness():
    routes = {f"{LEGACY}/megasena.json": {"1": ["01", "02", "03", "04", "05", "06"]}}
    h = load_history("megasena", fake_fetch(routes), today=date(2026, 10, 20))
    assert h.last_contest == 1 and not h.verified_latest and h.official_latest is None
    assert any("não verificada" in warning for warning in h.warnings)
    assert any("não informa datas" in warning for warning in h.warnings)


def test_all_providers_fail_explicitly():
    with pytest.raises(ValueError, match="Nenhuma fonte"):
        load_history("megasena", fake_fetch({}))


def test_future_data_not_accepted():
    routes = {
        f"{OFFICIAL}/megasena": record(1, day="01/01/2099"),
        f"{MIRROR}/megasena/_todos.json": [record(1, day="01/01/2099")],
    }
    with pytest.raises(ValueError):
        load_history("megasena", fake_fetch(routes), today=date(2026, 10, 20))


def test_short_history_trend_and_delay_are_correct():
    cfg = LOTTERIES["megasena"]
    draws = (Draw(10, (1, 2, 3, 4, 5, 6)), Draw(11, (1, 2, 3, 7, 8, 9)))
    stats = calculate_stats(draws, cfg)
    assert stats.window == 2 and all(v == 0 for v in stats.recent_delta.values())
    assert stats.delay[1] == 0 and stats.delay[4] == 1 and stats.delay[60] == 2


def test_zero_weights_really_disable_every_component():
    cfg = LOTTERIES["megasena"]
    stats = calculate_stats((Draw(1, (1, 2, 3, 4, 5, 6)),), cfg)
    for game in [(1, 2, 3, 4, 5, 6), (1, 11, 21, 31, 41, 51), tuple(range(1, 21))]:
        assert descriptive_score(game, stats, ScoreWeights()) == 0


def test_multiple_ticket_sum_reference_not_six_number_history():
    cfg = LOTTERIES["megasena"]
    stats = calculate_stats((Draw(1, (1, 2, 3, 4, 5, 6)),), cfg)
    centered = (10, 15, 20, 25, 30, 31, 36, 41, 46, 51)  # soma 305
    assert descriptive_score(centered, stats, ScoreWeights(sum=1)) == 0
