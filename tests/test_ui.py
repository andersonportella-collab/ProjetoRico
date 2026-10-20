"""Regressões de interação com Streamlit AppTest, sem rede."""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from loterias.data import Draw, History


@pytest.fixture
def app():
    return AppTest.from_file(
        Path(__file__).resolve().parents[1] / "loterias_web.py", default_timeout=20
    ).run()


def assert_ok(app):
    assert not app.exception, [e.message for e in app.exception]


def test_app_opens_offline_and_generates_without_history(app):
    assert_ok(app)
    app.button(key="gen_submit_megasena").click().run()
    assert_ok(app)
    table = app.session_state["generation_megasena"]["table"].copy()
    assert len(table) == 5 and table["Custo (R$)"].sum() == 30
    # Reexecução causada por controles/download não apaga nem gera outra carteira.
    app.number_input(key="gen_seed_megasena").set_value(99).run()
    assert_ok(app)
    assert app.session_state["generation_megasena"]["table"].equals(table)


def test_multiple_ticket_price_and_budget_limit_in_ui(app):
    app.number_input(key="gen_size_megasena").set_value(7).run()
    app.number_input(key="gen_count_megasena").set_value(20).run()
    app.button(key="gen_submit_megasena").click().run()
    assert_ok(app)
    table = app.session_state["generation_megasena"]["table"]
    assert len(table) == 2 and table["Custo (R$)"].sum() == 84


def test_budget_insufficient_shows_error_without_crashing(app):
    app.number_input(key="gen_budget_megasena").set_value(0.0).run()
    app.button(key="gen_submit_megasena").click().run()
    assert_ok(app)
    assert any("Orçamento insuficiente" in e.value for e in app.error)


def test_closure_changes_controls_immediately_and_never_silently_truncates(app):
    app.selectbox(key="fc_mode_megasena").set_value("Completo").run()
    app.number_input(key="fc_pool_size_megasena").set_value(12).run()
    app.number_input(key="fc_budget_megasena").set_value(5544.0).run()
    app.button(key="fc_submit_megasena").click().run(timeout=20)
    assert_ok(app)
    result = app.session_state["closure_megasena"]
    assert len(result["table"]) == 924
    assert result["report"].guaranteed
    assert result["table"]["Custo (R$)"].sum() == 5544


@pytest.mark.parametrize("method", ["Cobertura gulosa", "AG de cobertura", "Aleatório uniforme"])
def test_partial_methods_and_certificates(app, method):
    app.selectbox(key="fc_algorithm_megasena").set_value(method).run()
    app.button(key="fc_submit_megasena").click().run(timeout=20)
    assert_ok(app)
    result = app.session_state["closure_megasena"]
    assert len(result["tickets"]) == 20
    assert result["report"].exact


def test_day_of_luck_month_is_persisted_in_display_and_export(app):
    app.sidebar.radio[0].set_value("diadesorte").run()
    app.selectbox(key="gen_month").set_value(3).run()
    app.button(key="gen_submit_diadesorte").click().run()
    assert_ok(app)
    result = app.session_state["generation_diadesorte"]
    assert all(t.month == 3 for t in result["tickets"])
    assert set(result["table"]["Mês da Sorte"]) == {"Março"}
    app.run()
    assert app.session_state["generation_diadesorte"]["tickets"] == result["tickets"]


def test_heuristic_requires_history_but_uniform_does_not(app):
    app.selectbox(key="gen_method_megasena").set_value("Heurístico descritivo").run()
    app.button(key="gen_submit_megasena").click().run()
    assert_ok(app)
    assert any("Carregue o histórico" in e.value for e in app.error)


def test_cached_stats_change_when_history_changes(app):
    def history(numbers):
        return History((Draw(1, numbers, date(2026, 10, 18)),), "Teste", "Teste", 1, True, ())

    app.session_state["history_megasena"] = history((1, 2, 3, 4, 5, 6))
    app.run()
    assert_ok(app)
    first = app.dataframe[1].value  # tabela completa de frequências
    assert first.loc[first.Dezena == 1, "Frequência"].iloc[0] == 1
    app.session_state["history_megasena"] = history((7, 8, 9, 10, 11, 12))
    app.run()
    assert_ok(app)
    second = app.dataframe[1].value
    assert second.loc[second.Dezena == 1, "Frequência"].iloc[0] == 0


def test_switching_lotteries_and_dynamic_pool_sizes(app):
    for key, size in [("lotofacil", 20), ("diadesorte", 15), ("megasena", 20)]:
        app.sidebar.radio[0].set_value(key).run()
        app.number_input(key=f"fc_size_{key}").set_value(size).run()
        assert_ok(app)
        app.button(key=f"gen_submit_{key}").click().run()
        assert_ok(app)
