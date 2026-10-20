# Analisador de Loterias

Aplicativo Streamlit para **Mega-Sena, Lotofácil e Dia de Sorte**, com análise
histórica descritiva, geração de carteiras únicas, orçamento e verificação de
cobertura de fechamentos.

**Não prevê sorteios.** Sob sorteios uniformes e independentes, qualquer
combinação simples específica tem a mesma probabilidade. Frequência, atraso e
coocorrência históricos não demonstram vantagem preditiva por si mesmos.

## Executar

Requer **Python 3.12 ou superior**. O ambiente reproduzível e a integração
contínua usam Python 3.12.

```bash
git clone https://github.com/andersonportella-collab/ProjetoRico.git
cd ProjetoRico
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m streamlit run loterias_web.py
```

No Windows, ative com `.venv\Scripts\activate`. O arquivo `requirements.lock.txt`
fixa as dependências diretas e transitivas do ambiente validado, inclusive os
instrumentos de testes. `requirements.txt` fixa somente as dependências diretas
de execução, para instalação mais enxuta, sem travar as transitivas.

No Streamlit Cloud, selecione Python 3.12 e `loterias_web.py` como entrada.
O tema está em `.streamlit/config.toml`.

## Configuração recomendada para a Mega-Sena

- Método **Aleatório uniforme**, disponível sem carregar dados.
- Seis dezenas por jogo para facilitar o controle da carteira.
- Quantidade limitada ao orçamento; cada jogo simples custa R$ 6,00 na tabela
  conferida em 20/10/2026. O preço-base pode ser atualizado na barra lateral.
- Todos os jogos da carteira são distintos. A semente reproduz a mesma geração
  no mesmo ambiente e com os mesmos parâmetros. Altere-a para outra carteira.

Uma aposta de sete dezenas custa o mesmo que sete apostas simples e contém sete
combinações simples distintas. Para a sena, ambas as alternativas têm a mesma
probabilidade se as sete apostas simples também forem distintas. A distribuição
dos prêmios menores depende da composição dos jogos.

## Modos de geração

### Aleatório uniforme

Amostra índices de combinações uniformemente, sem reposição. A conversão dos
índices para dezenas evita enumerar o espaço combinatório e impede jogos iguais.
No Dia de Sorte, o mês é escolhido uma vez por jogo, ou fixado pelo usuário,
e permanece igual na tela, no CSV e no Excel.

### Heurístico descritivo

Modo experimental de preferência, que amostra candidatos uniformes e os ordena
por frequência, atraso, variação recente, paridade, consecutivos, amplitude,
soma e coocorrência. **Não existe alegação de maior chance de ganhar.**

Todos os pesos são explícitos, inicialmente zero. Zerar todos produz score zero,
sem penalizações ocultas. A referência de soma é ajustada ao número de dezenas
do bilhete, usando amostragem sem reposição, e não a média de sorteios de um
tamanho diferente. O histórico usado é identificado nas informações exportadas.

## Fechamentos e otimização de carteira

O pool pode ser informado ou amostrado uniformemente; não é escolhido por uma
alegação de previsão. No parcial, estão disponíveis:

- seleção aleatória uniforme;
- seleção gulosa pelo ganho de cobertura;
- algoritmo genético com elitismo e mutação, cuja função objetivo é a cobertura
  de resultados com pelo menos a meta de acertos escolhida.

O AG otimiza **a carteira**, não o score histórico de uma dezena ou de um pool.
A quantidade e o custo da carteira de referência aleatória são os mesmos da
carteira otimizada. A referência faz parte das soluções candidatas; o resultado
não piora seu score de treinamento. Isso **não** garante superioridade na
validação, ótimo global ou vantagem em um sorteio futuro.

O treinamento utiliza até 512 resultados possíveis e até 400 jogos candidatos
por padrão, amostrados sem reposição. A validação usa até 512 resultados que não
participaram da seleção. Quando o treinamento já é exaustivo, não há amostra de
validação restante. Esses escores são distinguidos do certificado exato.

### O que significa uma garantia

Para um pool P, sorteio D de tamanho d e jogos J, uma garantia de r acertos exige:

```text
para todo D contido em P, com |D| = d:
    existe J na carteira com |D ∩ J| >= r
```

Portanto, a garantia é **condicionada a todas as dezenas sorteadas estarem no
pool**. Não significa ganho garantido em qualquer concurso. O prêmio do mês do
Dia de Sorte é separado e não integra a garantia das dezenas.

O aplicativo verifica exaustivamente os resultados possíveis ou demonstra a
cobertura completa por construção. Quando a verificação exaustiva supera os
limites de trabalho, mostra **não certificado**, sem transformar uma amostra em
garantia. Se a meta falhar na verificação exata, mostra um contraexemplo.

Representar todas as dezenas individualmente nos jogos **não é uma prova de
premiação**. A presença individual e a cobertura de resultados são conceitos
distintos.

### Limites de trabalho

Definidos em `loterias/config.py`, antes de alocar combinações:

| Operação | Limite |
|---|---:|
| Fechamento completo | 20.000 jogos |
| Parcial otimizado | 200 jogos |
| Certificação exaustiva | 20.000 resultados e 5 milhões de comparações |
| União de combinações simples para probabilidade | 200.000 expansões |
| Treinamento do otimizador | 20 milhões de operações estimadas |

Um completo que exceder o limite é recusado, **nunca truncado**. Um completo com
custo acima do orçamento também é recusado. Um parcial pode ter a quantidade
reduzida para respeitar o orçamento, com aviso antes da geração.

## Probabilidades e custos

Para população N, sorteio de d dezenas, bilhete de k dezenas e preço-base p:

```text
custo = p × C(k, d)
P(exatamente h dezenas sorteadas no bilhete) = C(k,h) × C(N-k,d-h) / C(N,d)
P(acerto máximo da carteira) = |união das combinações simples| / C(N,d)
```

A união desconta sobreposições entre apostas múltiplas. O aplicativo não soma
probabilidades de eventos sobrepostos. Se a expansão exceder o limite, não
publica uma aproximação como exata. Frações e `Decimal` são usados no núcleo;
conversões para ponto flutuante são feitas apenas para exibição/exportação.

Preços-base e limites conferidos em **20/10/2026**:

| Modalidade | Dezenas por bilhete | Preço simples |
|---|---:|---:|
| Mega-Sena | 6–20 | R$ 6,00 |
| Lotofácil | 15–20 | R$ 3,50 |
| Dia de Sorte | 7–15 | R$ 2,50 |

Fontes para conferir e atualizar:
[Mega-Sena](https://loterias.caixa.gov.br/Paginas/mega-sena.aspx),
[Lotofácil](https://loterias.caixa.gov.br/Paginas/Lotofacil.aspx),
[Dia de Sorte](https://loterias.caixa.gov.br/Paginas/Dia-de-Sorte.aspx).
Preços não são atualizados automaticamente; a data de conferência e o preço
personalizado da sessão aparecem nas informações da carteira.

## Fontes e qualidade dos dados

O carregamento é solicitado na aba de análise, sem bloquear a geração uniforme:

1. Consulta o último resultado no [serviço da CAIXA](https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena).
2. Obtém a base do espelho público
   [free-apiloterias](https://github.com/maickon/free-apiloterias), com fallback
   para [loteria.json](https://github.com/guilhermeasn/loteria.json).
3. Compara o último concurso com a CAIXA e busca concursos faltantes na fonte
   oficial, com no máximo quatro requisições simultâneas.
4. Se a lacuna exigir mais de 100 atualizações, consulta somente a janela dos
   últimos 100 concursos. A interface identifica o histórico como parcial.

Esses endpoints externos podem mudar ou ficar indisponíveis. O carregador valida
dezenas, unicidade, limites, modalidade, concursos, datas e continuidade. Não
descarta silenciosamente registros inválidos. Em falhas, usa apenas uma sequência
válida e identifica a base defasada ou a atualidade não verificada. Não apresenta
o histórico inteiro de um espelho como integralmente auditado pela CAIXA.

O cache de estatísticas inclui os dados na chave. As ausências de uma dezena
nunca observada na janela são identificadas como limite inferior. A variação
recente usa a janela efetiva se houver menos de 30 concursos. Nenhum gráfico
atribui significância estatística ou capacidade preditiva a essas diferenças.

## Organização

```text
loterias_web.py           Interface e estado da sessão
loterias/config.py       Regras, preços e limites de trabalho
loterias/data.py         Validação, fontes e atualização
loterias/statistics.py   Descrição e preferências explícitas
loterias/probability.py  Combinatória, custos e probabilidades
loterias/generation.py   Carteiras e aleatoriedade reproduzível
loterias/coverage.py     Fechamentos, AG e certificados
loterias/export.py       CSV, Excel e informações em JSON
tests/                   Núcleo, falhas de fontes e Streamlit AppTest
scripts/                 Comparação reproduzível de cobertura
```

## Validar alterações

```bash
python -m pip install -r requirements.lock.txt
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m scripts.benchmark_coverage
```

Os testes são offline, com fontes simuladas, e incluem preços, normalização da
distribuição hipergeométrica, união de apostas sobrepostas, unicidade, sementes,
contraexemplos de falsas garantias, limites antes da enumeração, fallback,
cache e persistência de resultados/exportação. O benchmark compara carteiras
com dez jogos, pool de 12 dezenas e meta de cinco acertos para cinco sementes,
com avaliação exata dos 924 resultados possíveis. É uma comparação específica
condicionada ao pool, não evidência de previsão de loteria.

O workflow `.github/workflows/ci.yml` executa as verificações em push e pull
request. Para atualizar dependências, resolva em ambiente virtual limpo e revise
o novo `pip freeze` antes de substituir `requirements.lock.txt`.

## Migração da versão anterior

- O método padrão passou a ser uniforme e funciona sem rede.
- O AG de pool por score histórico foi substituído por otimização de cobertura
  da carteira; os pesos descritivos continuam disponíveis em modo separado.
- A interface deixou de associar “quente”, “frio” ou “score” a maior probabilidade.
- Os resultados e exportações persistem durante as reexecuções da sessão.
- O completo não é mais cortado em 500 jogos.
- O tema foi movido para o caminho reconhecido pelo Streamlit.

Aplicativo para análise e entretenimento. A única garantia combinatória exibida
é a que foi demonstrada, sob sua condição explícita de inclusão no pool.
