"""Histórico validado, reconciliação com a CAIXA e fallback identificado."""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import pairwise
from unicodedata import normalize
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import LOTTERIES, MONTHS
from .probability import integer, validate_numbers

logger = logging.getLogger(__name__)
OFFICIAL = "https://servicebus2.caixa.gov.br/portaldeloterias/api"
MIRROR = "https://raw.githubusercontent.com/maickon/free-apiloterias/master/database"
LEGACY = "https://raw.githubusercontent.com/guilhermeasn/loteria.json/master/data"


@dataclass(frozen=True)
class Draw:
    contest: int
    numbers: tuple[int, ...]
    draw_date: date | None = None
    month: int | None = None


@dataclass(frozen=True)
class History:
    draws: tuple[Draw, ...]
    source: str
    fetched_at: str
    official_latest: int | None
    verified_latest: bool
    warnings: tuple[str, ...]

    @property
    def last_contest(self):
        return self.draws[-1].contest

    @property
    def complete(self):
        return self.draws[0].contest == 1 and len(self.draws) == self.last_contest


def _text(value):
    return normalize("NFKD", str(value)).encode("ascii", "ignore").decode().strip().casefold()


def parse_month(value) -> int:
    for i, name in enumerate(MONTHS, 1):
        if _text(value) == _text(name) or str(value).strip() == str(i):
            return i
    raise ValueError("Mês da Sorte inválido.")


def parse_draw(record: dict, lottery: str) -> Draw:
    cfg = LOTTERIES[lottery]
    if not isinstance(record, dict):
        raise ValueError("Concurso deve ser um objeto JSON.")
    if record.get("tipoJogo", cfg.api_type) != cfg.api_type:
        raise ValueError("Modalidade divergente na resposta.")
    contest = integer(record.get("numero"), "Concurso")
    if contest < 1:
        raise ValueError("Concurso deve ser positivo.")
    values = record.get("listaDezenas")
    if not isinstance(values, list):
        raise ValueError("Lista de dezenas ausente.")
    numbers = validate_numbers(values, cfg.population, cfg.draw_size, cfg.draw_size)
    raw_date = record.get("dataApuracao")
    draw_date = datetime.strptime(raw_date, "%d/%m/%Y").date() if raw_date else None
    month = parse_month(record.get("nomeTimeCoracaoMesSorte")) if lottery == "diadesorte" else None
    return Draw(contest, numbers, draw_date, month)


def parse_history(raw, lottery: str) -> tuple[Draw, ...]:
    if isinstance(raw, list):
        draws = [parse_draw(record, lottery) for record in raw]
    elif isinstance(raw, dict):
        draws = []
        cfg = LOTTERIES[lottery]
        for contest, values in raw.items():
            if not isinstance(values, list) or len(values) != cfg.draw_size + (
                lottery == "diadesorte"
            ):
                raise ValueError(f"Concurso {contest}: tamanho inválido.")
            record = {"numero": contest, "listaDezenas": values[: cfg.draw_size]}
            if lottery == "diadesorte":
                record["nomeTimeCoracaoMesSorte"] = values[-1]
            draws.append(parse_draw(record, lottery))
    else:
        raise ValueError("Formato de histórico não reconhecido.")
    if not draws:
        raise ValueError("Histórico vazio.")
    draws.sort(key=lambda d: d.contest)
    if len({d.contest for d in draws}) != len(draws):
        raise ValueError("Concursos duplicados no histórico.")
    if any(b.contest != a.contest + 1 for a, b in pairwise(draws)):
        raise ValueError("Histórico contém lacunas entre concursos.")
    dated = [d.draw_date for d in draws if d.draw_date]
    if dated != sorted(dated):
        raise ValueError("Datas fora da ordem dos concursos.")
    return tuple(draws)


def get_json(url: str):
    """HTTPS com timeout, retries limitados e teto de download de 30 MB."""
    retry = Retry(total=2, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504))
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        with session.get(url, timeout=(5, 15), stream=True) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 30_000_000:
                    raise ValueError("Histórico excede o limite de download de 30 MB.")
                chunks.append(chunk)
            import json

            return json.loads(b"".join(chunks))


def load_history(
    lottery: str, fetch=None, *, max_refresh: int = 100, today: date | None = None
) -> History:
    """Prioriza a CAIXA para atualização; espelhos servem como base histórica.

    O espelho não é tratado como fonte oficial nem como integralmente auditado.
    Falhas de sincronização devolvem a base antiga com avisos, sem inserir lacunas.
    """
    if lottery not in LOTTERIES or not 1 <= max_refresh <= 300:
        raise ValueError("Modalidade ou limite de atualização inválido.")
    fetch = fetch or get_json
    today = today or datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    notices, latest = [], None
    try:
        latest = parse_draw(fetch(f"{OFFICIAL}/{lottery}"), lottery)
        if latest.draw_date is None or latest.draw_date > today:
            raise ValueError("Data do último concurso oficial inválida.")
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning("Último concurso oficial indisponível: %s", exc)
        latest = None
        notices.append(
            "Não foi possível conferir o último concurso na CAIXA. Atualidade não verificada."
        )

    base, source = (), "CAIXA"
    for url, name in [
        (f"{MIRROR}/{lottery}/_todos.json", "free-apiloterias (espelho)"),
        (f"{LEGACY}/{lottery}.json", "loteria.json (espelho legado)"),
    ]:
        try:
            candidate = parse_history(fetch(url), lottery)
            if any(d.draw_date and d.draw_date > today for d in candidate):
                raise ValueError("Histórico contém data futura.")
            base = candidate
            source = name
            break
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.warning("Histórico indisponível em %s: %s", name, exc)

    verified = False
    if latest:
        if base and base[-1].contest > latest.contest:
            notices.append(
                "Espelho contém concursos posteriores à referência oficial; eles foram descartados."
            )
            base = tuple(d for d in base if d.contest <= latest.contest)
        original = base
        start = base[-1].contest + 1 if base else max(1, latest.contest - max_refresh + 1)
        if latest.contest - start + 1 > max_refresh:
            base = ()
            start = max(1, latest.contest - max_refresh + 1)
            notices.append(f"Atualização limitada aos últimos {max_refresh} concursos oficiais.")
        used_mirror = bool(base)
        try:

            def one(contest):
                draw = parse_draw(fetch(f"{OFFICIAL}/{lottery}/{contest}"), lottery)
                if draw.contest != contest or draw.draw_date is None or draw.draw_date > today:
                    raise ValueError("Concurso ou data divergente na atualização.")
                return draw

            with ThreadPoolExecutor(max_workers=4) as executor:
                added = list(executor.map(one, range(start, latest.contest)))
            if base and base[-1].contest == latest.contest:
                if base[-1].numbers != latest.numbers or base[-1].month != latest.month:
                    notices.append("Último concurso do espelho divergia da CAIXA e foi corrigido.")
                base = base[:-1]
            base = tuple(base) + tuple(added) + (latest,)
            if any(b.contest != a.contest + 1 for a, b in pairwise(base)):
                raise ValueError("Atualização produziria lacunas.")
            dates = [d.draw_date for d in base if d.draw_date]
            if dates != sorted(dates):
                raise ValueError("Datas da atualização fora de ordem.")
            verified = True
            source = f"{source} + conferência/atualização CAIXA" if used_mirror else "CAIXA"
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.warning("Sincronização incompleta: %s", exc)
            base = original or (latest,)
            verified = not original
            notices.append(
                "Sincronização incompleta. Exibindo apenas uma sequência sem lacunas; confira o último concurso exibido."
            )

    if not base:
        raise ValueError(
            "Nenhuma fonte retornou histórico válido. A geração uniforme continua disponível."
        )
    if latest and base[-1].contest < latest.contest:
        notices.append(f"Base defasada em {latest.contest - base[-1].contest} concursos.")
    last_date = base[-1].draw_date
    if last_date is None:
        notices.append("A fonte não informa datas; não é possível verificar a idade da base.")
    elif (today - last_date).days > 10:
        notices.append(
            f"Último sorteio da base ocorreu há {(today - last_date).days} dias. Base potencialmente defasada."
        )
    if base[0].contest != 1:
        notices.append("Histórico parcial: estatísticas se referem apenas ao período disponível.")
    return History(
        tuple(base),
        source,
        datetime.now(UTC).isoformat(),
        latest.contest if latest else None,
        verified,
        tuple(notices),
    )
