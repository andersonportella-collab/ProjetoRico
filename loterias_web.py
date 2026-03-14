"""
╔══════════════════════════════════════════════════════════════╗
║      ANALISADOR INTELIGENTE DE LOTERIAS — Interface Web     ║
║      Mega-Sena | Lotofácil | Dia de Sorte                   ║
╚══════════════════════════════════════════════════════════════╝
Execute com:  streamlit run loterias_web.py
Dependências: pip install streamlit pandas numpy requests openpyxl
"""

import io
import random
import itertools
import warnings
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🎲 Analisador de Loterias",
    page_icon="🍀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS customizado
st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 2rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center;
}
.main-header h1 { color: #FFD700; font-size: 2.2rem; margin: 0; }
.main-header p  { color: #a0c4ff; margin: 0.3rem 0 0; font-size: 1rem; }
.metric-card {
    background: #1e293b; border: 1px solid #334155; border-radius: 10px;
    padding: 1rem; text-align: center;
}
.metric-card .val { font-size: 1.8rem; font-weight: bold; color: #FFD700; }
.metric-card .lbl { font-size: 0.8rem; color: #94a3b8; margin-top: 0.2rem; }
.numero-badge {
    display: inline-block; background: #1d4ed8; color: #fff;
    border-radius: 50%; width: 40px; height: 40px; line-height: 40px;
    text-align: center; font-weight: bold; font-size: 1rem; margin: 3px;
}
.numero-badge.quente { background: #b91c1c; }
.numero-badge.frio   { background: #0369a1; }
.jogo-box {
    background: #0f172a; border: 1px solid #1e40af; border-radius: 10px;
    padding: 0.8rem 1.2rem; margin: 0.5rem 0;
    display: flex; align-items: center; gap: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────
# Fonte: github.com/guilhermeasn/loteria.json — atualizado diariamente
URLS_JSON = {
    "megasena":  "https://raw.githubusercontent.com/guilhermeasn/loteria.json/master/data/megasena.json",
    "lotofacil": "https://raw.githubusercontent.com/guilhermeasn/loteria.json/master/data/lotofacil.json",
    "diadesorte":"https://raw.githubusercontent.com/guilhermeasn/loteria.json/master/data/diadesorte.json",
}

CONFIG = {
    "megasena":  {"min_dez": 6,  "max_dez": 15, "max_n": 60, "label": "Mega-Sena",   "emoji": "🟢", "cor": "#16a34a"},
    "lotofacil": {"min_dez": 15, "max_dez": 20, "max_n": 25, "label": "Lotofácil",   "emoji": "🔵", "cor": "#2563eb"},
    "diadesorte":{"min_dez": 7,  "max_dez": 14, "max_n": 31, "label": "Dia de Sorte","emoji": "🟡", "cor": "#ca8a04"},
}

NOMES_MESES = {
    1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",
    5:"Maio",6:"Junho",7:"Julho",8:"Agosto",
    9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"
}

PESOS_DEFAULT = {
    "freq": 1.0, "atraso": 0.08, "paridade": 10.0,
    "sequencia": 12.0, "dispersao": 1.2, "soma": 0.5, "quadrante": 8.0,
}

# ─────────────────────────────────────────────────────────────
# CARREGAMENTO DE DADOS
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def carregar_dados(loteria: str) -> pd.DataFrame:
    """
    Baixa os resultados históricos do repositório JSON (GitHub).
    Formato real: {"1": ["41","05",...], "2": [...], ...}
    Para diadesorte, o último elemento de cada lista é o mês (ex: "Fevereiro").
    Cache de 1 hora via st.cache_data.
    """
    url = URLS_JSON[loteria]
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()  # dict[str, list[str]]

    n_bolas = CONFIG[loteria]["min_dez"]  # número fixo de dezenas por sorteio

    registros = []
    for concurso_str, valores in raw.items():
        if not isinstance(valores, list) or len(valores) == 0:
            continue
        rec = {"concurso": int(concurso_str)}

        if loteria == "diadesorte":
            # último elemento é o mês (string), os demais são dezenas numéricas
            nums = []
            mes  = ""
            for v in valores:
                try:
                    nums.append(int(v))
                except (ValueError, TypeError):
                    mes = str(v)
            for i, n in enumerate(nums, 1):
                rec[f"Bola{i}"] = n
            rec["mes_sorte"] = mes
        else:
            for i, v in enumerate(valores[:n_bolas], 1):
                rec[f"Bola{i}"] = int(v)

        registros.append(rec)

    df = pd.DataFrame(registros).sort_values("concurso").reset_index(drop=True)
    return df


def get_bola_cols(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c.startswith("Bola")]

# ─────────────────────────────────────────────────────────────
# ANÁLISE ESTATÍSTICA
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def calcular_stats(_df: pd.DataFrame, loteria: str) -> dict:
    bola_cols = get_bola_cols(_df)
    max_n = CONFIG[loteria]["max_n"]
    total = len(_df)

    todos = _df[bola_cols].values.flatten()
    todos = todos[~np.isnan(todos.astype(float))].astype(int)
    freq_raw = Counter(todos)
    freq = {n: freq_raw.get(n, 0) for n in range(1, max_n + 1)}

    # Atraso
    atraso = {}
    for n in range(1, max_n + 1):
        mask = (_df[bola_cols] == n).any(axis=1)
        idx  = _df[mask].index
        atraso[n] = total - idx.max() - 1 if len(idx) > 0 else total

    # Tendência (últimos 30 vs. histórico)
    rec = _df.tail(30)[bola_cols].values.flatten().astype(int)
    freq_rec = Counter(rec)
    tendencia = {
        n: (freq_rec.get(n, 0) / 30) - (freq.get(n, 0) / total)
        for n in range(1, max_n + 1)
    }

    # Quadrante
    q = max_n // 4
    quadrante = {n: min((n - 1) // q, 3) for n in range(1, max_n + 1)}

    # Soma
    somas = _df[bola_cols].sum(axis=1)
    soma_media, soma_std = float(somas.mean()), float(somas.std())

    # Paridade histórica
    pares_hist = [sum(1 for v in row if v % 2 == 0) for row in _df[bola_cols].values]
    razao_par = np.mean(pares_hist) / len(bola_cols)

    # Co-ocorrências
    cooc = Counter()
    for _, row in _df[bola_cols].iterrows():
        nums = sorted(row.dropna().astype(int).tolist())
        for par in itertools.combinations(nums, 2):
            cooc[par] += 1

    return {
        "freq": freq, "atraso": atraso, "tendencia": tendencia,
        "quadrante": quadrante, "soma_media": soma_media, "soma_std": soma_std,
        "razao_par": float(razao_par),
        "quentes": sorted(range(1, max_n+1), key=lambda n: freq[n], reverse=True)[:15],
        "frios":   sorted(range(1, max_n+1), key=lambda n: atraso[n], reverse=True)[:15],
        "top_cooc": dict(cooc.most_common(50)),
        "total": total, "max_n": max_n,
    }

# ─────────────────────────────────────────────────────────────
# FITNESS
# ─────────────────────────────────────────────────────────────
def fitness(jogo, stats, pesos, loteria):
    freq, atraso, tendencia = stats["freq"], stats["atraso"], stats["tendencia"]
    top_cooc, soma_med, soma_std = stats["top_cooc"], stats["soma_media"], stats["soma_std"]
    max_n, total = stats["max_n"], stats["total"]
    n = len(jogo)
    score = 0.0

    score += sum(freq.get(x, 0) for x in jogo) / total * pesos["freq"] * 100
    score += sum(np.log1p(atraso.get(x, 0)) for x in jogo) * pesos["atraso"]
    score += sum(tendencia.get(x, 0) for x in jogo) * 30

    pares = sum(1 for x in jogo if x % 2 == 0)
    alvo_par = round(n * stats["razao_par"])
    score -= abs(pares - alvo_par) * pesos["paridade"]

    seq = 1
    for i in range(1, n):
        if jogo[i] == jogo[i-1] + 1:
            seq += 1
            if seq > 3:
                score -= pesos["sequencia"]
        else:
            seq = 1

    quads = Counter(stats["quadrante"].get(x, 0) for x in jogo)
    score -= np.std([quads.get(q, 0) for q in range(4)]) * pesos["quadrante"]

    soma = sum(jogo)
    z = abs(soma - soma_med) / (soma_std + 1e-9)
    score -= z * pesos["soma"] * 10

    for par in itertools.combinations(jogo, 2):
        p = (min(par), max(par))
        if p in top_cooc:
            score += np.log1p(top_cooc[p]) * 0.1

    if loteria == "lotofacil" and not (170 <= soma <= 230):
        score -= 40
    if loteria == "megasena" and max(jogo) - min(jogo) < 30:
        score -= 35
    if loteria == "diadesorte":
        if sum(1 for x in jogo if x <= 10) > 4:
            score -= 20

    return score

# ─────────────────────────────────────────────────────────────
# GERAÇÃO DE JOGOS
# ─────────────────────────────────────────────────────────────
def gerar_jogo_base(dezenas, stats):
    max_n = stats["max_n"]
    pool = list(range(1, max_n + 1))
    quentes = set(stats["quentes"])
    frios   = set(stats["frios"])
    tend_pos = set(sorted(stats["tendencia"], key=stats["tendencia"].get, reverse=True)[:10])
    pesos_pool = []
    for n in pool:
        p = 1.0
        if n in quentes:   p += 1.5
        if n in frios:     p += 0.8
        if n in tend_pos:  p += 1.2
        pesos_pool.append(p)
    total_p = sum(pesos_pool)
    probs = [p / total_p for p in pesos_pool]
    escolhidos = set()
    while len(escolhidos) < dezenas:
        escolhidos.add(np.random.choice(pool, p=probs))
    return sorted(escolhidos)


def _reparar(individuo: list, tamanho: int, max_n: int) -> list:
    """Garante que o indivíduo tenha exatamente `tamanho` dezenas únicas em [1, max_n]."""
    s = sorted(set(int(x) for x in individuo if 1 <= int(x) <= max_n))
    while len(s) < tamanho:
        novo = random.randint(1, max_n)
        if novo not in s:
            s.append(novo)
    return sorted(s[:tamanho])


def algoritmo_genetico(stats, dezenas, loteria, pesos,
                       geracoes=80, pop_size=200, progress_cb=None):
    max_n = stats["max_n"]
    populacao = [gerar_jogo_base(dezenas, stats) for _ in range(pop_size)]
    melhor_score = -1e18
    melhor_jogo  = populacao[0]
    sem_melhora  = 0
    n_elite = max(2, int(pop_size * 0.15))

    for g in range(geracoes):
        if progress_cb:
            progress_cb(g / geracoes)
        scores = [fitness(j, stats, pesos, loteria) for j in populacao]
        ordem  = sorted(range(pop_size), key=lambda i: scores[i], reverse=True)
        elite  = [populacao[i] for i in ordem[:n_elite]]

        if scores[ordem[0]] > melhor_score:
            melhor_score = scores[ordem[0]]
            melhor_jogo  = populacao[ordem[0]]
            sem_melhora  = 0
        else:
            sem_melhora += 1

        if sem_melhora >= 20:
            break

        nova = elite[:]
        taxa_mut = 0.10 + 0.05 * (sem_melhora / 10)

        while len(nova) < pop_size:
            def torneio():
                cands = random.sample(list(zip(populacao, scores)), 4)
                return max(cands, key=lambda x: x[1])[0]
            p1, p2 = torneio(), torneio()
            corte = random.randint(1, dezenas - 1)
            filho = _reparar(p1[:corte] + p2[corte:], dezenas, max_n)
            if random.random() < taxa_mut:
                # Substitui uma dezena aleatória — usa lista temporária para evitar colisão
                substituir = random.randint(0, dezenas - 1)
                candidato  = random.randint(1, max_n)
                temp = [x for i, x in enumerate(filho) if i != substituir] + [candidato]
                filho = _reparar(temp, dezenas, max_n)
            nova.append(filho)
        populacao = nova

    return melhor_jogo, melhor_score


def sugerir_mes(df):
    if "mes_sorte" not in df.columns:
        return random.randint(1, 12)
    meses = df["mes_sorte"].dropna().str.upper().str.strip()
    mapa = {"JANEIRO":1,"FEVEREIRO":2,"MARÇO":3,"ABRIL":4,
            "MAIO":5,"JUNHO":6,"JULHO":7,"AGOSTO":8,
            "SETEMBRO":9,"OUTUBRO":10,"NOVEMBRO":11,"DEZEMBRO":12}
    nums = meses.map(mapa).dropna().astype(int)
    freq_m = Counter(nums)
    total = len(nums)
    atraso_m = {}
    for m in range(1, 13):
        idx = nums[nums == m].index
        atraso_m[m] = total - idx.max() - 1 if len(idx) > 0 else total
    max_f = max(freq_m.values(), default=1)
    max_a = max(atraso_m.values(), default=1)
    score = {m: (freq_m.get(m,0)/max_f)*0.4 + (atraso_m.get(m,0)/max_a)*0.6 for m in range(1,13)}
    top3 = sorted(score, key=score.get, reverse=True)[:3]
    return random.choice(top3)

# ─────────────────────────────────────────────────────────────
# COMPONENTES VISUAIS
# ─────────────────────────────────────────────────────────────
def badge(n, classe=""):
    return f'<span class="numero-badge {classe}">{n:02d}</span>'


def exibir_numeros_html(numeros, stats):
    quentes = set(stats["quentes"][:10])
    frios   = set(stats["frios"][:10])
    html = ""
    for n in numeros:
        if n in quentes:
            html += badge(n, "quente")
        elif n in frios:
            html += badge(n, "frio")
        else:
            html += badge(n)
    return html

# ─────────────────────────────────────────────────────────────
# PÁGINA DE ANÁLISE ESTATÍSTICA
# ─────────────────────────────────────────────────────────────
def pagina_analise(loteria, df, stats):
    cfg   = CONFIG[loteria]
    max_n = cfg["max_n"]
    total = stats["total"]

    st.markdown(f"### 📊 Análise Histórica — {cfg['label']} ({total} sorteios)")

    # Métricas topo
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        num_mais_freq = max(stats["freq"], key=stats["freq"].get)
        st.markdown(f'<div class="metric-card"><div class="val">{num_mais_freq:02d}</div><div class="lbl">Nº mais frequente</div></div>', unsafe_allow_html=True)
    with c2:
        num_mais_atr = max(stats["atraso"], key=stats["atraso"].get)
        st.markdown(f'<div class="metric-card"><div class="val">{num_mais_atr:02d}</div><div class="lbl">Maior atraso atual</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="val">{stats["soma_media"]:.0f}</div><div class="lbl">Soma média/jogo</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="val">{stats["razao_par"]*100:.0f}%</div><div class="lbl">Média de pares/jogo</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["🔥 Frequência", "⏱ Atraso", "📈 Tendência", "🤝 Co-ocorrências"])

    # TAB 1 — Frequência
    with tab1:
        freq_df = pd.DataFrame(
            [(n, stats["freq"][n], stats["freq"][n]/total*100)
             for n in range(1, max_n + 1)],
            columns=["Número", "Frequência", "% do total"]
        ).sort_values("Frequência", ascending=False)

        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.bar_chart(freq_df.set_index("Número")["Frequência"], height=300)
        with col_b:
            st.dataframe(freq_df.head(15), use_container_width=True, hide_index=True)

        st.markdown("**🔥 Top 10 mais sorteados:**")
        html = "".join(badge(n, "quente") for n in stats["quentes"][:10])
        st.markdown(html, unsafe_allow_html=True)

    # TAB 2 — Atraso
    with tab2:
        atr_df = pd.DataFrame(
            [(n, stats["atraso"][n]) for n in range(1, max_n + 1)],
            columns=["Número", "Atraso (sorteios)"]
        ).sort_values("Atraso (sorteios)", ascending=False)

        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.bar_chart(atr_df.set_index("Número")["Atraso (sorteios)"], height=300)
        with col_b:
            st.dataframe(atr_df.head(15), use_container_width=True, hide_index=True)

        st.markdown("**❄️ Top 10 com maior atraso:**")
        html = "".join(badge(n, "frio") for n in stats["frios"][:10])
        st.markdown(html, unsafe_allow_html=True)

    # TAB 3 — Tendência
    with tab3:
        tend_df = pd.DataFrame(
            [(n, stats["tendencia"][n]*100) for n in range(1, max_n + 1)],
            columns=["Número", "Tendência (%)"]
        ).sort_values("Tendência (%)", ascending=False)

        st.caption("Positivo = apareceu mais nos últimos 30 sorteios que no histórico geral")
        st.bar_chart(tend_df.set_index("Número")["Tendência (%)"], height=300)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**📈 Aquecendo (top 5):**")
            for _, row in tend_df.head(5).iterrows():
                st.write(f"  `{int(row['Número']):02d}` → +{row['Tendência (%)']:.2f}%")
        with col_b:
            st.markdown("**📉 Esfriando (top 5):**")
            for _, row in tend_df.tail(5).iterrows():
                st.write(f"  `{int(row['Número']):02d}` → {row['Tendência (%)']:.2f}%")

    # TAB 4 — Co-ocorrências
    with tab4:
        cooc_df = pd.DataFrame(
            [(f"{a:02d} + {b:02d}", v) for (a, b), v in list(stats["top_cooc"].items())[:20]],
            columns=["Par", "Aparições juntos"]
        )
        col_a, col_b = st.columns([1, 2])
        with col_a:
            st.dataframe(cooc_df, use_container_width=True, hide_index=True)
        with col_b:
            st.bar_chart(cooc_df.set_index("Par"), height=350)


# ─────────────────────────────────────────────────────────────
# SEÇÃO — FECHAMENTO MATEMÁTICO
# ─────────────────────────────────────────────────────────────

def calcular_combinacoes(n: int, k: int) -> int:
    """C(n, k) sem overflow."""
    if k > n:
        return 0
    from math import comb
    return comb(n, k)


def gerar_pool_otimizado(stats: dict, tamanho_pool: int, dezenas_jogo: int,
                          loteria: str, pesos: dict,
                          geracoes: int = 100, pop_size: int = 300) -> list:
    """
    Usa o AG para encontrar um conjunto (pool) de `tamanho_pool` dezenas
    que maximize a cobertura estatística quando fechado em jogos de `dezenas_jogo`.
    Critério extra: maximiza a soma dos fitness de todas as combinações do pool.
    """
    max_n = stats["max_n"]

    # Cada indivíduo é um pool de tamanho_pool dezenas
    populacao = [
        sorted(random.sample(range(1, max_n + 1), tamanho_pool))
        for _ in range(pop_size)
    ]

    def fitness_pool(pool):
        # Avalia a média do fitness de uma amostra de combinações do pool
        combos = list(itertools.combinations(pool, dezenas_jogo))
        if len(combos) > 50:
            combos = random.sample(combos, 50)
        return np.mean([fitness(list(c), stats, pesos, loteria) for c in combos])

    melhor_score = -1e18
    melhor_pool  = populacao[0]
    sem_melhora  = 0
    n_elite = max(2, int(pop_size * 0.15))

    for _ in range(geracoes):
        scores = [fitness_pool(p) for p in populacao]
        ordem  = sorted(range(pop_size), key=lambda i: scores[i], reverse=True)
        elite  = [populacao[i] for i in ordem[:n_elite]]

        if scores[ordem[0]] > melhor_score:
            melhor_score = scores[ordem[0]]
            melhor_pool  = populacao[ordem[0]]
            sem_melhora  = 0
        else:
            sem_melhora += 1

        if sem_melhora >= 15:
            break

        nova = elite[:]
        while len(nova) < pop_size:
            p1 = random.choice(elite)
            p2 = random.choice(elite)
            corte = random.randint(1, tamanho_pool - 1)
            filho = _reparar(p1[:corte] + p2[corte:], tamanho_pool, max_n)
            if random.random() < 0.15:
                substituir = random.randint(0, tamanho_pool - 1)
                candidato  = random.randint(1, max_n)
                temp = [x for i, x in enumerate(filho) if i != substituir] + [candidato]
                filho = _reparar(temp, tamanho_pool, max_n)
            nova.append(filho)
        populacao = nova

    return melhor_pool


def gerar_fechamento_completo(pool: list, dezenas_jogo: int,
                               stats: dict, pesos: dict, loteria: str,
                               limite: int = 500) -> list:
    """
    Gera todas as combinações C(pool, dezenas_jogo), ordena por score,
    e retorna no máximo `limite` jogos (os melhores).
    """
    todas = list(itertools.combinations(pool, dezenas_jogo))
    scored = [(list(c), fitness(list(c), stats, pesos, loteria)) for c in todas]
    scored.sort(key=lambda x: -x[1])
    return scored[:limite]


def gerar_fechamento_parcial(pool: list, dezenas_jogo: int,
                              stats: dict, pesos: dict, loteria: str,
                              n_jogos: int, df_orig=None) -> list:
    """
    Fechamento parcial: seleciona `n_jogos` combinações do pool que maximizam
    cobertura (máx. diversidade entre si) + score estatístico.
    Garante que todo número do pool aparece ao menos uma vez.
    """
    todas_combos = list(itertools.combinations(pool, dezenas_jogo))
    if len(todas_combos) <= n_jogos:
        combos_scored = [(list(c), fitness(list(c), stats, pesos, loteria)) for c in todas_combos]
        combos_scored.sort(key=lambda x: -x[1])
        return combos_scored

    # Fase 1: cobertura — garante que todo número do pool apareça ao menos 1x
    selecionados  = []
    cobertura_num = {n: 0 for n in pool}
    restantes     = list(todas_combos)
    random.shuffle(restantes)

    while any(v == 0 for v in cobertura_num.values()) and restantes:
        # Escolhe a combo que cobre o número mais descoberto
        descobertos = {n for n, v in cobertura_num.items() if v == 0}
        melhor = max(restantes, key=lambda c: len(set(c) & descobertos))
        selecionados.append(melhor)
        for n in melhor:
            cobertura_num[n] = cobertura_num.get(n, 0) + 1
        restantes.remove(melhor)

    # Fase 2: preenche até n_jogos com os de maior score entre os restantes
    restantes_scored = [(c, fitness(list(c), stats, pesos, loteria)) for c in restantes]
    restantes_scored.sort(key=lambda x: -x[1])
    for c, sc in restantes_scored:
        if len(selecionados) >= n_jogos:
            break
        selecionados.append(c)

    # Calcula scores finais
    resultado = [(list(c), fitness(list(c), stats, pesos, loteria)) for c in selecionados[:n_jogos]]
    resultado.sort(key=lambda x: -x[1])
    return resultado


def pagina_fechamento(loteria, df, stats):
    cfg = CONFIG[loteria]
    max_n   = cfg["max_n"]
    dez_min = cfg["min_dez"]
    dez_max = cfg["max_dez"]

    st.markdown(f"### 🔐 Fechamento Matemático — {cfg['label']}")
    st.info(
        "**O que é fechamento?** Você escolhe um *pool* de N dezenas (ex: 10 números). "
        "O sistema gera todas ou as melhores combinações desse pool em jogos de tamanho menor, "
        "garantindo que se as bolas sorteadas estiverem no seu pool, você tem um prêmio garantido. "
        "Ideal para acumulados onde vale a pena investir mais.",
        icon="💡"
    )

    with st.form("form_fechamento"):
        col1, col2, col3 = st.columns(3)
        with col1:
            dezenas_jogo = st.number_input(
                f"Dezenas por jogo ({dez_min}–{dez_max})",
                dez_min, dez_max, dez_min
            )
        with col2:
            pool_min = dezenas_jogo + 1
            pool_max = min(dezenas_jogo + 12, max_n)
            tamanho_pool = st.number_input(
                f"Tamanho do pool ({pool_min}–{pool_max})",
                pool_min, pool_max,
                min(dezenas_jogo + 3, pool_max)
            )
        with col3:
            tipo_fechamento = st.selectbox(
                "Tipo de fechamento",
                ["Parcial (N melhores jogos)", "Completo (todas as combinações)"]
            )

        n_jogos_parcial = 20
        if "Parcial" in tipo_fechamento:
            n_jogos_parcial = st.number_input(
                "Quantidade de jogos no fechamento parcial", 5, 200, 20
            )

        with st.expander("⚙️ Configurações do AG do Pool"):
            col_a, col_b = st.columns(2)
            with col_a:
                ger_pool = st.slider("Gerações AG pool", 20, 200, 80)
                pop_pool = st.slider("Pop. AG pool", 50, 400, 200)
            with col_b:
                st.markdown("**Pesos do Fitness**")
                p_freq  = st.slider("Frequência",  0.0, 3.0, 1.0, 0.1, key="fc_freq")
                p_atr   = st.slider("Atraso",      0.0, 0.5, 0.08, 0.01, key="fc_atr")
                p_par   = st.slider("Paridade",    0.0, 20.0, 10.0, 0.5, key="fc_par")
                p_seq   = st.slider("Sequência",   0.0, 30.0, 12.0, 1.0, key="fc_seq")
                p_soma  = st.slider("Soma",        0.0, 2.0, 0.5, 0.1, key="fc_soma")
                p_quad  = st.slider("Quadrante",   0.0, 20.0, 8.0, 0.5, key="fc_quad")

        submitted = st.form_submit_button("🔐 Gerar Fechamento", use_container_width=True, type="primary")

    if submitted:
        pesos = {
            "freq": p_freq, "atraso": p_atr, "paridade": p_par,
            "sequencia": p_seq, "dispersao": PESOS_DEFAULT["dispersao"],
            "soma": p_soma, "quadrante": p_quad,
        }

        n_combos = calcular_combinacoes(tamanho_pool, dezenas_jogo)

        # Aviso de custo
        custo_unit = {"megasena": 5.00, "lotofacil": 3.00, "diadesorte": 1.50}
        preco = custo_unit.get(loteria, 5.0)
        n_jogos_exibir = n_combos if "Completo" in tipo_fechamento else n_jogos_parcial
        custo_total = n_jogos_exibir * preco

        col_i1, col_i2, col_i3 = st.columns(3)
        col_i1.metric("Combinações totais", f"C({tamanho_pool},{dezenas_jogo}) = {n_combos:,}")
        col_i2.metric("Jogos no fechamento", f"{n_jogos_exibir:,}")
        col_i3.metric("Custo estimado", f"R$ {custo_total:,.2f}")

        if "Completo" in tipo_fechamento and n_combos > 500:
            st.warning(
                f"⚠️ Fechamento completo geraria {n_combos:,} jogos (custo ~R$ {n_combos*preco:,.2f}). "
                "Limitando a 500 jogos de maior score. Use fechamento **Parcial** para controlar quantidade.",
                icon="⚠️"
            )

        # Geração do pool via AG
        with st.spinner(f"Otimizando pool de {tamanho_pool} dezenas com AG..."):
            pool = gerar_pool_otimizado(
                stats, tamanho_pool, dezenas_jogo, loteria, pesos,
                geracoes=ger_pool, pop_size=pop_pool
            )

        st.markdown("---")
        st.markdown("#### 🎯 Pool Otimizado pelo AG")
        html_pool = exibir_numeros_html(pool, stats)
        st.markdown(
            f'<div class="jogo-box" style="flex-wrap:wrap">'
            f'<strong style="color:#94a3b8;margin-right:8px">Pool ({tamanho_pool} dezenas):</strong>'
            f'{html_pool}</div>',
            unsafe_allow_html=True
        )
        st.caption("🔴 quente  🔵 frio  ⚪ neutro")

        # Geração do fechamento
        with st.spinner("Gerando jogos do fechamento..."):
            if "Completo" in tipo_fechamento:
                fechamento = gerar_fechamento_completo(
                    pool, dezenas_jogo, stats, pesos, loteria, limite=500
                )
            else:
                fechamento = gerar_fechamento_parcial(
                    pool, dezenas_jogo, stats, pesos, loteria, n_jogos_parcial, df
                )

        st.markdown("---")
        st.markdown(f"#### 🎟️ Jogos do Fechamento ({len(fechamento)} jogos)")

        # Estatísticas de cobertura
        cobertura = {n: 0 for n in pool}
        for jogo, _ in fechamento:
            for n in jogo:
                if n in cobertura:
                    cobertura[n] += 1

        scores_fech = [sc for _, sc in fechamento]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score médio",   f"{np.mean(scores_fech):.1f}")
        c2.metric("Melhor score",  f"{max(scores_fech):.1f}")
        c3.metric("Cobertura",     f"{sum(1 for v in cobertura.values() if v>0)}/{tamanho_pool} números")
        c4.metric("Jogos gerados", str(len(fechamento)))

        # Cobertura por número
        with st.expander("📊 Ver cobertura de cada número do pool"):
            cob_df = pd.DataFrame(
                [(n, cobertura[n]) for n in pool],
                columns=["Número", "Aparições nos jogos"]
            )
            st.dataframe(cob_df, use_container_width=True, hide_index=True)

        # Lista de jogos
        st.caption("🔴 quente  🔵 frio  ⚪ neutro")
        for idx, (jogo, sc) in enumerate(fechamento, 1):
            html_nums = exibir_numeros_html(jogo, stats)
            mes_html  = ""
            if loteria == "diadesorte":
                mes = sugerir_mes(df)
                mes_html = f' &nbsp;&nbsp; 🍀 <strong>{NOMES_MESES[mes]}</strong>'
            soma = sum(jogo)
            st.markdown(
                f'<div class="jogo-box">'
                f'<strong style="color:#94a3b8;min-width:60px">#{idx:03d}</strong>'
                f'{html_nums}{mes_html}'
                f'&nbsp;&nbsp;<span style="color:#64748b;font-size:0.85rem">soma={soma} | score={sc:.1f}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Exportação
        st.markdown("---")
        st.markdown("### 💾 Exportar Fechamento")
        rows = []
        for idx, (jogo, sc) in enumerate(fechamento, 1):
            row = {"Jogo": idx, "Score": round(sc, 2)}
            for i, n in enumerate(jogo, 1):
                row[f"N{i:02d}"] = n
            row["Soma"] = sum(jogo)
            if loteria == "diadesorte":
                row["Mês da Sorte"] = NOMES_MESES[sugerir_mes(df)]
            rows.append(row)

        # Adiciona linha de resumo do pool
        pool_row = {"Jogo": "POOL", "Score": "—"}
        for i, n in enumerate(pool, 1):
            pool_row[f"N{i:02d}"] = n
        pool_row["Soma"] = sum(pool)
        rows.insert(0, pool_row)

        df_exp = pd.DataFrame(rows)
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            csv_b = df_exp.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                "📥 Baixar CSV", csv_b,
                f"fechamento_{loteria}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv", use_container_width=True
            )
        with col_e2:
            buf = io.BytesIO()
            df_exp.to_excel(buf, index=False, engine="openpyxl")
            st.download_button(
                "📥 Baixar Excel", buf.getvalue(),
                f"fechamento_{loteria}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                use_container_width=True
            )
        st.dataframe(df_exp.head(20), use_container_width=True, hide_index=True)
        if len(df_exp) > 20:
            st.caption(f"Mostrando 20 de {len(df_exp)} jogos. Baixe o arquivo para ver todos.")


# ─────────────────────────────────────────────────────────────
# PÁGINA DE GERAÇÃO DE JOGOS
# ─────────────────────────────────────────────────────────────
def pagina_geracao(loteria, df, stats):
    cfg = CONFIG[loteria]

    st.markdown(f"### 🎯 Gerar Jogos — {cfg['label']}")

    with st.form("form_geracao"):
        col1, col2, col3 = st.columns(3)
        with col1:
            qtd_jogos = st.number_input("Quantidade de jogos", 1, 50, 5)
        with col2:
            dezenas = st.number_input(
                f"Dezenas por jogo ({cfg['min_dez']}–{cfg['max_dez']})",
                cfg["min_dez"], cfg["max_dez"], cfg["min_dez"]
            )
        with col3:
            usar_ag = st.selectbox("Método", ["Algoritmo Genético", "Heurístico (rápido)"])

        if usar_ag == "Algoritmo Genético":
            with st.expander("⚙️ Configurações do AG"):
                col_a, col_b = st.columns(2)
                with col_a:
                    geracoes = st.slider("Gerações", 20, 300, 80)
                    pop_size = st.slider("Tamanho da população", 50, 500, 200)
                with col_b:
                    st.markdown("**Pesos do Fitness**")
                    p_freq  = st.slider("Frequência",  0.0, 3.0, 1.0, 0.1)
                    p_atr   = st.slider("Atraso",      0.0, 0.5, 0.08, 0.01)
                    p_par   = st.slider("Paridade",    0.0, 20.0, 10.0, 0.5)
                    p_seq   = st.slider("Sequência",   0.0, 30.0, 12.0, 1.0)
                    p_soma  = st.slider("Soma",        0.0, 2.0, 0.5, 0.1)
                    p_quad  = st.slider("Quadrante",   0.0, 20.0, 8.0, 0.5)
        else:
            geracoes = pop_size = 0
            p_freq = p_atr = p_par = p_seq = p_soma = p_quad = 0

        submitted = st.form_submit_button("🚀 Gerar Jogos", use_container_width=True, type="primary")

    if submitted:
        pesos = {
            "freq": p_freq, "atraso": p_atr, "paridade": p_par,
            "sequencia": p_seq, "dispersao": PESOS_DEFAULT["dispersao"],
            "soma": p_soma, "quadrante": p_quad,
        }

        resultados = []
        progress = st.progress(0, text="Gerando jogos...")

        for i in range(qtd_jogos):
            progress.progress((i) / qtd_jogos, text=f"Gerando jogo {i+1}/{qtd_jogos}...")

            if usar_ag == "Algoritmo Genético":
                jogo, sc = algoritmo_genetico(
                    stats, dezenas, loteria, pesos, geracoes, pop_size
                )
            else:
                jogo = gerar_jogo_base(dezenas, stats)
                sc = fitness(jogo, stats, PESOS_DEFAULT, loteria)

            info = {"jogo": i + 1, "numeros": jogo, "score": round(sc, 2)}
            if loteria == "diadesorte":
                mes = sugerir_mes(df)
                info["mes_num"] = mes
                info["mes_nome"] = NOMES_MESES[mes]
            resultados.append(info)

        progress.progress(1.0, text="✅ Concluído!")

        # Exibição
        st.markdown("---")
        st.markdown("### 🎟️ Jogos Gerados")
        scores = [r["score"] for r in resultados]
        c1, c2, c3 = st.columns(3)
        c1.metric("Score Médio",  f"{np.mean(scores):.1f}")
        c2.metric("Melhor Score", f"{max(scores):.1f}")
        c3.metric("Pior Score",   f"{min(scores):.1f}")
        st.caption("🔴 vermelho = número quente  |  🔵 azul = número frio  |  ⚪ branco = neutro")

        for r in resultados:
            html_nums = exibir_numeros_html(r["numeros"], stats)
            extras = ""
            if loteria == "diadesorte":
                extras = f' &nbsp;&nbsp; 🍀 <strong>{r["mes_nome"]}</strong>'
            soma = sum(r["numeros"])
            st.markdown(
                f'<div class="jogo-box">'
                f'<strong style="color:#94a3b8;min-width:60px">Jogo {r["jogo"]:02d}</strong>'
                f'{html_nums}{extras}'
                f'&nbsp;&nbsp;<span style="color:#64748b;font-size:0.85rem">soma={soma} | score={r["score"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Exportação
        st.markdown("---")
        st.markdown("### 💾 Exportar")
        rows = []
        for r in resultados:
            row = {"Jogo": r["jogo"], "Score": r["score"]}
            for i, n in enumerate(r["numeros"], 1):
                row[f"N{i:02d}"] = n
            if loteria == "diadesorte":
                row["Mês da Sorte"] = r["mes_nome"]
            row["Soma"] = sum(r["numeros"])
            rows.append(row)
        df_exp = pd.DataFrame(rows)

        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv_bytes = df_exp.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button("📥 Baixar CSV", csv_bytes,
                               f"{loteria}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                               "text/csv", use_container_width=True)
        with col_exp2:
            buf = io.BytesIO()
            df_exp.to_excel(buf, index=False, engine="openpyxl")
            st.download_button("📥 Baixar Excel", buf.getvalue(),
                               f"{loteria}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                               use_container_width=True)

        st.dataframe(df_exp, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────
# APP PRINCIPAL
# ─────────────────────────────────────────────────────────────
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🎲 Analisador Inteligente de Loterias</h1>
        <p>Mega-Sena · Lotofácil · Dia de Sorte &nbsp;|&nbsp; Dados oficiais da Caixa Econômica Federal</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar — seleção de loteria
    with st.sidebar:
        st.markdown("## 🎯 Configuração")
        loteria = st.radio(
            "Selecione a loteria",
            ["megasena", "lotofacil", "diadesorte"],
            format_func=lambda x: f"{CONFIG[x]['emoji']} {CONFIG[x]['label']}",
        )

        st.markdown("---")
        if st.button("🔄 Atualizar dados da Caixa", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache limpo! Recarregue a página.")

        st.markdown("---")
        st.markdown("**Sobre os dados:**")
        st.caption("Fonte: repositório `guilhermeasn/loteria.json` no GitHub, atualizado diariamente via GitHub Actions com dados oficiais da Caixa.")
        st.markdown("---")
        st.caption("⚠️ Este programa é apenas para fins analíticos e de entretenimento. Loterias são jogos de azar; nenhum sistema garante ganho.")

    # Carregamento com spinner
    cfg = CONFIG[loteria]
    with st.spinner(f"Carregando histórico da {cfg['label']}..."):
        try:
            df = carregar_dados(loteria)
            stats = calcular_stats(df, loteria)
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            st.info("Verifique sua conexão com a internet e tente novamente.")
            return

    st.success(f"✅ {stats['total']} sorteios carregados para a {cfg['label']}")

    # Abas principais
    aba_analise, aba_geracao, aba_fechamento = st.tabs([
        "📊 Análise Estatística", "🎯 Gerar Jogos", "🔐 Fechamento Matemático"
    ])

    with aba_analise:
        pagina_analise(loteria, df, stats)

    with aba_geracao:
        pagina_geracao(loteria, df, stats)

    with aba_fechamento:
        pagina_fechamento(loteria, df, stats)


if __name__ == "__main__":
    main()
