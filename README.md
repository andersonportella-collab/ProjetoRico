# 🎲 Analisador Inteligente de Loterias

Aplicativo web para análise estatística e geração otimizada de jogos para **Mega-Sena**, **Lotofácil** e **Dia de Sorte**, com suporte a fechamento matemático.

Desenvolvido em Python com Streamlit. Os dados históricos são obtidos automaticamente do repositório público [`guilhermeasn/loteria.json`](https://github.com/guilhermeasn/loteria.json), atualizado diariamente com resultados oficiais da Caixa Econômica Federal.

---

## Funcionalidades

### 📊 Análise Estatística
- Frequência histórica de cada número com gráfico de barras interativo
- Atraso atual (sorteios desde a última aparição)
- Tendência recente: compara os últimos 30 sorteios contra o histórico completo
- Pares co-ocorrentes: os 20 pares de números que mais saíram juntos

### 🎯 Geração de Jogos
- **Algoritmo Genético** com elitismo, seleção por torneio e mutação adaptativa
- **Função fitness multi-critério**: frequência, atraso, tendência recente, paridade par/ímpar, sequências, cobertura de quadrantes, soma histórica e co-ocorrências
- Modo heurístico rápido para geração sem AG
- Pesos do fitness configuráveis via sliders
- Sugestão de **Mês da Sorte** baseada em frequência e atraso por mês (Dia de Sorte)
- Exportação em CSV e Excel

### 🔐 Fechamento Matemático
- AG otimiza um **pool de N dezenas** avaliando a qualidade média das suas combinações
- **Fechamento completo**: gera todas as C(pool, dezenas) combinações ordenadas por score
- **Fechamento parcial**: seleciona K jogos garantindo cobertura completa do pool + máximo score
- Exibe custo estimado antes de gerar
- Tabela de cobertura por número do pool
- Exportação com pool destacado na primeira linha

---

## Estrutura do repositório

```
loterias/
├── loterias_web.py          # Aplicativo principal (arquivo único)
├── requirements.txt         # Dependências Python
├── .streamlit/
│   └── config.toml          # Tema e configurações do Streamlit
├── .gitignore
└── README.md
```

---

## Instalação local

### Pré-requisitos
- Python 3.10 ou superior
- pip

### Passos

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/SEU_REPO.git
cd SEU_REPO

# 2. (Opcional) Crie um ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Execute o app
streamlit run loterias_web.py
```

O navegador abre automaticamente em `http://localhost:8501`.

---

## Deploy no Streamlit Cloud

### Passo 1 — Suba o repositório no GitHub

O repositório pode ser **privado**. O Streamlit Cloud aceita repositórios privados em todos os planos (incluindo o gratuito, via conexão OAuth com o GitHub).

```bash
git init
git add .
git commit -m "primeiro commit"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

### Passo 2 — Conecte ao Streamlit Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com sua conta GitHub
2. Clique em **"New app"**
3. Selecione:
   - **Repository**: `SEU_USUARIO/SEU_REPO`
   - **Branch**: `main`
   - **Main file path**: `loterias_web.py`
4. Clique em **"Deploy!"**

O Streamlit Cloud instala as dependências do `requirements.txt` automaticamente e publica a URL pública do app.

### Passo 3 — Atualizações futuras

Basta fazer push para a branch `main` — o Streamlit Cloud detecta automaticamente e faz redeploy.

```bash
git add loterias_web.py
git commit -m "melhoria: descrição da mudança"
git push
```

---

## Dependências

| Biblioteca  | Versão mínima | Finalidade                              |
|-------------|---------------|-----------------------------------------|
| streamlit   | 1.32.0        | Interface web                           |
| pandas      | 2.0.0         | Manipulação dos dados históricos        |
| numpy       | 1.26.0        | Cálculos estatísticos e AG              |
| requests    | 2.31.0        | Download dos resultados históricos      |
| openpyxl    | 3.1.0         | Exportação para Excel (.xlsx)           |

Todas as outras bibliotecas usadas (`io`, `random`, `itertools`, `math`, `warnings`, `collections`, `datetime`) fazem parte da biblioteca padrão do Python — não requerem instalação.

---

## Fonte dos dados

Os resultados históricos são obtidos do repositório público:

> **guilhermeasn/loteria.json** — https://github.com/guilhermeasn/loteria.json

Os dados são atualizados automaticamente todos os dias via GitHub Actions com os resultados oficiais da Caixa Econômica Federal. O app faz cache local por 1 hora para evitar requisições desnecessárias.

---

## Aviso legal

Este aplicativo é desenvolvido exclusivamente para fins **analíticos e de entretenimento**. Loterias são jogos de azar regulados pela Caixa Econômica Federal. Nenhum método estatístico ou algorítmico garante ganho em jogos de azar. Jogue com responsabilidade.

---

## Referências técnicas

- Algoritmo Genético com elitismo e mutação adaptativa
- Função fitness multi-critério baseada em análise de séries históricas
- Fechamento matemático com garantia de cobertura mínima do pool
- Análise de co-ocorrências por pares via `itertools.combinations`
- Tendência recente: comparação de distribuição nos últimos 30 sorteios vs. histórico completo
