"""Interface: python -m streamlit run loterias_web.py."""

import logging
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from math import comb
from random import Random
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from loterias.config import LOTTERIES, MAX_COMPLETE_TICKETS, MONTHS, PRICE_CHECKED_ON
from loterias.coverage import certify_coverage, complete_closure, optimize_portfolio
from loterias.data import load_history
from loterias.export import csv_bytes, excel_bytes, metadata_bytes, tickets_table
from loterias.generation import generate_uniform, heuristic_games, make_tickets, uniform_games
from loterias.probability import (
    affordable_count,
    exact_hits_probability,
    jackpot_probability,
    ticket_price,
    validate_numbers,
)
from loterias.statistics import ScoreWeights, calculate_stats, stats_table

logging.basicConfig(level=logging.INFO)


@st.cache_data(ttl=900, show_spinner=False)
def cached_history(lottery: str):
    return load_history(lottery)


@st.cache_data(show_spinner=False)
def cached_stats(draws, lottery: str):
    # Os dados participam da chave: mudar o histórico invalida as estatísticas.
    return calculate_stats(draws, LOTTERIES[lottery])


def money(value):
    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def probability_text(probability):
    if not probability:
        return "0%"
    return f"{float(probability) * 100:.8f}% (1 em {1 / float(probability):,.2f})"


def show_history(cfg):
    st.write(
        "Frequência, ausências e coocorrências descrevem o período observado. Não são previsões."
    )
    if st.button("Carregar / atualizar histórico", key=f"history_load_{cfg.key}"):
        try:
            cached_history.clear(cfg.key)
            with st.spinner("Validando histórico e conferindo o último concurso na CAIXA..."):
                st.session_state[f"history_{cfg.key}"] = cached_history(cfg.key)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    history = st.session_state.get(f"history_{cfg.key}")
    if history is None:
        st.info(
            "Carregue os dados para consultar as estatísticas. A geração uniforme funciona sem histórico."
        )
        return
    for notice in history.warnings:
        st.warning(notice)
    first, last = history.draws[0], history.draws[-1]
    a, b, c = st.columns(3)
    a.metric("Concursos disponíveis", len(history.draws))
    b.metric("Último concurso na base", last.contest)
    c.metric("Referência oficial", history.official_latest or "Não verificada")
    st.caption(
        f"Fonte: {history.source}. Período: concursos {first.contest} a {last.contest}. "
        f"Última data disponível: {last.draw_date or 'não informada'}. "
        f"Consulta: {history.fetched_at}. Use o botão para atualizar."
    )
    if history.verified_latest:
        st.success(
            "Último concurso conferido com a CAIXA na consulta indicada. O restante do espelho não foi integralmente auditado."
        )
    else:
        st.warning("Atualidade do histórico não confirmada.")
    stats = cached_stats(history.draws, cfg.key)
    frame = stats_table(stats)
    freq, delay, trend, cooc = st.tabs(
        ["Frequência", "Ausências", "Variação recente", "Coocorrências"]
    )
    with freq:
        st.bar_chart(frame.set_index("Dezena")["Presença (%)"])
        st.caption(
            f"Referência uniforme por concurso: {100 * cfg.draw_size / cfg.population:.2f}% por dezena."
        )
    with delay:
        st.bar_chart(frame.set_index("Dezena")["Ausências consecutivas"])
        st.caption(
            "Quando a dezena nunca aparece no período, o atraso é apenas um limite inferior. Não significa que ela esteja mais propensa a sair."
        )
    with trend:
        st.bar_chart(frame.set_index("Dezena")["Variação recente (p.p.)"])
        st.caption(
            f"Últimos {stats.window} concursos versus todo o período. Variação descritiva em pontos percentuais, sem teste de significância."
        )
    with cooc:
        pairs = sorted(stats.cooccurrence.items(), key=lambda item: (-item[1], item[0]))[:20]
        st.dataframe(
            pd.DataFrame([{"Par": f"{a:02d} + {b:02d}", "Ocorrências": n} for (a, b), n in pairs]),
            hide_index=True,
        )
    st.dataframe(frame, hide_index=True)


def save_result(key, cfg, tickets, price, seed, method, *, report=None, extra=None):
    metadata = {
        "modalidade": cfg.label,
        "método": method,
        "semente": seed,
        "gerado_em": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "quantidade": len(tickets),
        "preço_base": str(price),
        "preços_conferidos_em": PRICE_CHECKED_ON,
        "fonte_regras": cfg.rules_url,
        "hipótese_probabilidades": "Sorteios uniformes e independentes.",
        "garantia": "Somente quando comprovada; condicionada a todas as dezenas sorteadas estarem no pool.",
    }
    if report:
        metadata["certificado"] = asdict(report)
        metadata["garantia_comprovada"] = report.guaranteed
    metadata.update(extra or {})
    st.session_state[key] = {
        "tickets": tickets,
        "table": tickets_table(tickets, cfg, price),
        "metadata": metadata,
        "price": price,
        "report": report,
    }


def show_result(key, cfg):
    result = st.session_state.get(key)
    if result is None:
        return
    tickets, table, metadata = result["tickets"], result["table"], result["metadata"]
    st.write(f"**Carteira gerada: {len(tickets)} jogos.**")
    total = sum((ticket_price(cfg, len(t.numbers), result["price"]) for t in tickets), Decimal("0"))
    probability, unique = jackpot_probability(cfg, [t.numbers for t in tickets])
    a, b = st.columns(2)
    a.metric("Custo dos jogos gerados", money(total))
    b.metric(
        "Combinações simples distintas", f"{unique:,}" if unique is not None else "Não enumeradas"
    )
    if probability is not None:
        st.write(
            f"Probabilidade de ao menos um acerto máximo das dezenas: **{probability_text(probability)}**."
        )
    else:
        st.info(
            "A união das combinações excede o limite de cálculo. Não foi estimada uma probabilidade exata para esta carteira."
        )
    if cfg.key == "diadesorte":
        st.caption(
            "A probabilidade acima considera somente as dezenas. O Mês da Sorte é uma premiação separada; cada mês tem probabilidade 1/12 no modelo uniforme."
        )
    report = result["report"]
    if report:
        if report.guaranteed:
            st.success(
                f"Garantia comprovada de pelo menos {report.threshold} acertos em algum jogo, "
                f"SE todas as {cfg.draw_size} dezenas sorteadas estiverem no pool. "
                f"Mínimo de acertos comprovado: {report.worst_hits}."
            )
        elif report.exact:
            st.warning(
                f"Não há garantia de {report.threshold} acertos. Pior resultado dentro do pool: {report.worst_hits} acertos."
            )
            st.write(
                "Resultado possível sem atingir a meta:",
                " ".join(f"{n:02d}" for n in report.counterexample),
            )
        else:
            st.warning(report.reason)
        if report.conditional_probability is not None:
            st.write(
                f"Cobertura exata de resultados com pelo menos {report.threshold} acertos: "
                f"{report.covered:,}/{report.total_outcomes:,} "
                f"({100 * float(report.conditional_probability):.2f}%), condicionada ao pool."
            )
        if report.distribution:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Melhor acerto entre os jogos": hits,
                            "Resultados possíveis no pool": count,
                        }
                        for hits, count in sorted(report.distribution.items())
                    ]
                ),
                hide_index=True,
            )
    if "treinamento" in metadata:
        st.caption(metadata["treinamento"])
        st.write(metadata["comparação_referência"])
        if "validação_separada" in metadata:
            st.write(metadata["validação_separada"])
        baseline = metadata["certificado_referência_aleatória"]
        if report.exact and baseline["exact"]:
            st.write(
                f"Comparação exata em todos os {report.total_outcomes:,} resultados do pool: "
                f"carteira gerada cobre {report.covered:,}; referência aleatória cobre {baseline['covered']:,}. "
                "Esta comparação é específica destas carteiras e deste pool."
            )
    st.dataframe(table, hide_index=True)
    st.caption(
        f"Semente: {metadata['semente']}. Método: {metadata['método']}. Gerado em {metadata['gerado_em']}."
    )
    a, b, c = st.columns(3)
    a.download_button(
        "Baixar CSV", csv_bytes(table), f"{cfg.key}_jogos.csv", "text/csv", key=f"{key}_csv"
    )
    b.download_button(
        "Baixar Excel", excel_bytes(table, metadata), f"{cfg.key}_jogos.xlsx", key=f"{key}_xlsx"
    )
    c.download_button(
        "Baixar informações",
        metadata_bytes(metadata),
        f"{cfg.key}_informacoes.json",
        "application/json",
        key=f"{key}_json",
    )
    st.caption(
        "Os resultados permanecem disponíveis ao alterar controles ou baixar arquivos. Gere novamente para aplicar novas configurações."
    )


def show_generation(cfg, price):
    method = st.selectbox(
        "Método de geração",
        ["Aleatório uniforme", "Heurístico descritivo"],
        key=f"gen_method_{cfg.key}",
    )
    weights = ScoreWeights()
    if method == "Heurístico descritivo":
        st.warning(
            "Preferências históricas não demonstram vantagem no próximo sorteio. Todos os pesos são explícitos; zero desativa o componente."
        )
        labels = {
            "frequency": "Frequência",
            "delay": "Atraso",
            "trend": "Variação recente",
            "parity": "Equilíbrio de paridade",
            "sequence": "Evitar consecutivos",
            "dispersion": "Amplitude",
            "sum": "Proximidade da soma esperada",
            "cooccurrence": "Coocorrências",
        }
        with st.expander("Pesos de preferência descritiva"):
            weights = ScoreWeights(
                **{
                    name: st.slider(label, 0.0, 3.0, 0.0, 0.1, key=f"weight_{cfg.key}_{name}")
                    for name, label in labels.items()
                }
            )
    a, b, c = st.columns(3)
    size = a.number_input(
        "Dezenas por jogo", cfg.draw_size, cfg.max_ticket, cfg.draw_size, key=f"gen_size_{cfg.key}"
    )
    count = b.number_input("Quantidade desejada", 1, 200, 5, key=f"gen_count_{cfg.key}")
    seed = c.number_input("Semente", 0, 2**32 - 1, 42, key=f"gen_seed_{cfg.key}")
    budget = st.number_input(
        "Orçamento máximo (R$)", min_value=0.0, value=120.0, step=6.0, key=f"gen_budget_{cfg.key}"
    )
    month = None
    if cfg.key == "diadesorte":
        month = st.selectbox(
            "Mês da Sorte",
            [None, *range(1, 13)],
            format_func=lambda m: "Aleatório por jogo" if m is None else MONTHS[m - 1],
            key="gen_month",
        )
    unit = ticket_price(cfg, size, price)
    actual = min(count, affordable_count(Decimal(str(budget)), unit), comb(cfg.population, size))
    st.write(
        f"Preço por jogo: **{money(unit)}**. Cabem **{actual} jogos**, total **{money(unit * actual)}**."
    )
    if actual < count:
        st.info("A quantidade será limitada pelo orçamento e pelas combinações disponíveis.")
    if st.button("Gerar carteira", type="primary", key=f"gen_submit_{cfg.key}"):
        if actual == 0:
            st.error("Orçamento insuficiente para um jogo desta configuração.")
        else:
            try:
                if method == "Aleatório uniforme":
                    tickets = generate_uniform(cfg, size, actual, seed, month)
                    extra = {}
                else:
                    history = st.session_state.get(f"history_{cfg.key}")
                    if history is None:
                        raise ValueError(
                            "Carregue o histórico na aba de análise antes de usar a heurística."
                        )
                    stats = cached_stats(history.draws, cfg.key)
                    tickets = heuristic_games(cfg, size, actual, seed, stats, weights)
                    if month is not None:
                        tickets = make_tickets([t.numbers for t in tickets], cfg, seed, month)
                    extra = {
                        "pesos_descritivos": asdict(weights),
                        "último_concurso_base": history.last_contest,
                        "atualidade_base_verificada": history.verified_latest,
                    }
                    if history.warnings or not history.verified_latest:
                        st.warning(
                            "A heurística está usando uma base com ressalvas. Consulte os avisos na análise."
                        )
                save_result(f"generation_{cfg.key}", cfg, tickets, price, seed, method, extra=extra)
            except ValueError as exc:
                st.error(str(exc))
    show_result(f"generation_{cfg.key}", cfg)


def show_closure(cfg, price):
    st.write(
        "Um fechamento organiza jogos dentro de um pool. A garantia, quando comprovada, exige que todas as dezenas sorteadas estejam nesse pool."
    )
    a, b = st.columns(2)
    size = a.number_input(
        "Dezenas por jogo no fechamento",
        cfg.draw_size,
        cfg.max_ticket,
        cfg.draw_size,
        key=f"fc_size_{cfg.key}",
    )
    seed = b.number_input("Semente do fechamento", 0, 2**32 - 1, 42, key=f"fc_seed_{cfg.key}")
    pool_mode = st.radio(
        "Escolha do pool",
        ["Aleatório uniforme", "Informar dezenas"],
        horizontal=True,
        key=f"fc_pool_mode_{cfg.key}",
    )
    try:
        if pool_mode == "Informar dezenas":
            text = st.text_input(
                "Dezenas separadas por espaços ou vírgulas", key=f"fc_pool_text_{cfg.key}"
            )
            pool = validate_numbers(
                text.replace(",", " ").split(), cfg.population, size, cfg.population
            )
        else:
            pool_size = st.number_input(
                "Tamanho do pool",
                size,
                min(cfg.population, size + 12),
                min(cfg.population, size + 3),
                key=f"fc_pool_size_{cfg.key}",
            )
            pool = tuple(sorted(Random(seed).sample(range(1, cfg.population + 1), pool_size)))
    except ValueError as exc:
        st.info(str(exc))
        show_result(f"closure_{cfg.key}", cfg)
        return
    st.write("Pool:", " ".join(f"{n:02d}" for n in pool))
    total = comb(len(pool), size)
    mode = st.selectbox("Tipo de fechamento", ["Parcial", "Completo"], key=f"fc_mode_{cfg.key}")
    count, method, generations, population = total, "Completo", 30, 40
    if mode == "Parcial":
        count = st.number_input(
            "Jogos no fechamento parcial",
            1,
            min(200, total),
            min(20, total),
            key=f"fc_count_{cfg.key}",
        )
        method = st.selectbox(
            "Seleção dos jogos",
            ["Cobertura gulosa", "AG de cobertura", "Aleatório uniforme"],
            key=f"fc_algorithm_{cfg.key}",
        )
        if method == "AG de cobertura":
            generations = st.slider("Gerações do AG", 1, 100, 30, key=f"fc_generations_{cfg.key}")
            population = st.slider("População do AG", 4, 100, 40, key=f"fc_population_{cfg.key}")
    threshold = st.selectbox(
        "Meta de acertos das dezenas",
        list(range(cfg.min_prize, cfg.draw_size + 1)),
        key=f"fc_threshold_{cfg.key}",
    )
    budget = st.number_input(
        "Orçamento do fechamento (R$)",
        min_value=0.0,
        value=120.0,
        step=6.0,
        key=f"fc_budget_{cfg.key}",
    )
    month = None
    if cfg.key == "diadesorte":
        month = st.selectbox(
            "Mês para o fechamento",
            [None, *range(1, 13)],
            format_func=lambda m: "Aleatório por jogo" if m is None else MONTHS[m - 1],
            key="fc_month",
        )
    unit = ticket_price(cfg, size, price)
    actual = (
        count if mode == "Completo" else min(count, affordable_count(Decimal(str(budget)), unit))
    )
    expected_cost = unit * actual
    st.write(
        f"Combinações do pool: **{total:,}**. Jogos a gerar: **{actual:,}**. Custo: **{money(expected_cost)}**."
    )
    if mode == "Parcial" and actual < count:
        st.info("Quantidade parcial reduzida para respeitar o orçamento.")
    if mode == "Completo" and total > MAX_COMPLETE_TICKETS:
        st.warning(
            f"Completo excede o limite de {MAX_COMPLETE_TICKETS:,} jogos. Reduza o pool ou use parcial."
        )
    if st.button("Gerar e verificar fechamento", type="primary", key=f"fc_submit_{cfg.key}"):
        try:
            if actual == 0 or expected_cost > Decimal(str(budget)):
                raise ValueError(
                    "Orçamento insuficiente. Fechamento completo não será reduzido automaticamente."
                )
            extra = {"pool": list(pool), "meta_acertos": threshold}
            with st.spinner("Gerando carteira e verificando cobertura..."):
                if mode == "Completo":
                    games = complete_closure(pool, size)
                elif method == "Aleatório uniforme":
                    games = uniform_games(pool, size, actual, Random(seed))
                else:
                    optimized = optimize_portfolio(
                        pool,
                        size,
                        actual,
                        cfg.draw_size,
                        threshold,
                        seed,
                        method="genetic" if method == "AG de cobertura" else "greedy",
                        generations=generations,
                        population=population,
                    )
                    games = optimized.games
                    label = (
                        "todos os cenários do pool"
                        if optimized.training_exact
                        else "uma amostra uniforme de cenários do pool"
                    )
                    extra["treinamento"] = (
                        f"Otimização sobre {optimized.training_outcomes} cenários ({label}). "
                        "O score de treinamento não é uma garantia nem uma validação fora da amostra."
                    )
                    extra["comparação_referência"] = (
                        f"Cenários cobertos no treinamento: {optimized.training_covered}; "
                        f"referência aleatória com os mesmos {actual} jogos: {optimized.baseline_training_covered}."
                    )
                    extra["certificado_referência_aleatória"] = asdict(
                        certify_coverage(pool, optimized.baseline, cfg.draw_size, threshold)
                    )
                    extra["parâmetros_otimização"] = {
                        "gerações": generations,
                        "população": population,
                        "cenários_treinamento": optimized.training_outcomes,
                        "candidatos_máximos": 400,
                    }
                    if optimized.validation_outcomes:
                        extra["validação_separada"] = (
                            f"Em {optimized.validation_outcomes} cenários que não participaram da seleção: "
                            f"carteira gerada cobre {optimized.validation_covered}; "
                            f"referência aleatória cobre {optimized.baseline_validation_covered}. "
                            "Resultado amostral condicionado ao pool, sem garantia de generalização."
                        )
                report = certify_coverage(pool, games, cfg.draw_size, threshold)
                tickets = make_tickets(games, cfg, seed, month)
                save_result(
                    f"closure_{cfg.key}",
                    cfg,
                    tickets,
                    price,
                    seed,
                    method,
                    report=report,
                    extra=extra,
                )
        except ValueError as exc:
            st.error(str(exc))
    show_result(f"closure_{cfg.key}", cfg)


def main():
    st.set_page_config(page_title="Analisador de Loterias", page_icon="🍀", layout="wide")
    st.title("Analisador de Loterias")
    st.write("Análise descritiva, carteiras únicas e cobertura combinatória verificável.")
    st.caption(
        "Sob sorteios uniformes e independentes, o histórico não prevê o próximo resultado. Otimizar a cobertura não torna o pool escolhido mais provável."
    )
    with st.sidebar:
        key = st.radio("Loteria", list(LOTTERIES), format_func=lambda key: LOTTERIES[key].label)
        cfg = LOTTERIES[key]
        st.write(f"Preços conferidos em {PRICE_CHECKED_ON}.")
        st.link_button("Conferir regras e preços na CAIXA", cfg.rules_url)
        base = st.number_input(
            "Preço da aposta simples (R$)",
            min_value=0.01,
            value=float(cfg.base_price),
            step=0.01,
            key=f"price_{key}",
        )
        price = Decimal(str(base)).quantize(Decimal("0.01"))
        if price != cfg.base_price:
            st.info("Preço personalizado aplicado aos cálculos desta sessão.")
        st.caption(
            "A geração uniforme dispensa histórico. Use orçamento e semente para controlar a carteira."
        )
    analysis, generation, closure, probabilities = st.tabs(
        ["Análise histórica", "Gerar jogos", "Fechamento", "Probabilidades"]
    )
    with analysis:
        show_history(cfg)
    with generation:
        show_generation(cfg, price)
    with closure:
        show_closure(cfg, price)
    with probabilities:
        st.write(
            "Probabilidades teóricas de acertos das dezenas em um único bilhete. Custos usam o preço-base da sessão."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Dezenas": size,
                        "Apostas simples equivalentes": comb(size, cfg.draw_size),
                        "Custo (R$)": float(ticket_price(cfg, size, price)),
                        "Chance de acerto máximo": probability_text(
                            exact_hits_probability(cfg, size, cfg.draw_size)
                        ),
                    }
                    for size in range(cfg.draw_size, cfg.max_ticket + 1)
                ]
            ),
            hide_index=True,
        )
        st.write(
            "Para o acerto máximo das dezenas, o que conta é a união de combinações simples distintas. Bilhetes maiores não oferecem desconto de probabilidade por real apostado."
        )
        st.write(
            "A distribuição de prêmios menores depende da composição da carteira. Não somamos probabilidades de bilhetes sobrepostos."
        )
        if cfg.key == "diadesorte":
            st.write(
                "Mês da Sorte: 1/12 para cada mês, no modelo uniforme; tratado separadamente dos acertos das dezenas."
            )


if __name__ == "__main__":
    main()
