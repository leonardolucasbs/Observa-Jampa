"""Client dos avisos meteorológicos do INMET (https://apiprevmet3.inmet.gov.br/avisos/ativos).

O endpoint não tem documentação pública. Formato validado em 10/11/2026:

    {"hoje": [aviso, ...], "futuro": [aviso, ...]}

Cada aviso traz `id`, `id_aviso` e `id_sequencia` (versões do mesmo aviso), `descricao` (fenômeno),
`severidade` e `aviso_cor`, `inicio` e `fim` ("AAAA-MM-DD HH:MM", horário de Brasília, conferido
com o `onset`/`expires` do CAP do mesmo aviso), `encerrado`, `geocodes` (códigos IBGE separados por
vírgula), `municipios` ("Nome - UF (código),..."), `mesorregioes`, `estados`, `riscos` e `instrucoes`
(listas de textos). O mesmo aviso pode aparecer nas duas listas.
"""

import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from pages.chuvas.clients.http import SourceError, get_json
from pages.chuvas.config import AlertsConfig
from pages.chuvas.domain.models import AlertFeed, WeatherAlert

logger = logging.getLogger(__name__)

SOURCE = "INMET"
BUCKETS = ("hoje", "futuro")
MUNICIPALITY = re.compile(r"\s*(?P<name>[^,()]+?)\s+-\s+[A-Z]{2}\s+\((?P<code>\d{7})\)")
COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
IBGE_CODE = re.compile(r"\d{7}")


class InmetAlertsClient:
    def __init__(self, session: requests.Session, config: AlertsConfig, timeout_seconds: float) -> None:
        self._session = session
        self._config = config
        self._timeout = timeout_seconds

    def fetch(self) -> AlertFeed:
        logger.info("Consultando os avisos meteorológicos do INMET")
        payload = get_json(self._session, self._config.base_url, None, self._timeout, SOURCE)
        try:
            return parse_alerts(payload, ZoneInfo(self._config.source_timezone), self._config.alert_page_url)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:  # formato que o parser não previu
            logger.exception("Resposta do INMET em formato inesperado")
            raise SourceError("Formato inesperado do INMET") from exc


def parse_alerts(payload: Any, source_zone: ZoneInfo, page_url: str) -> AlertFeed:
    """Lê as duas listas. Sem elas a resposta é recusada: "nenhum aviso" só vale com a lista em mãos."""
    if not isinstance(payload, dict) or not all(isinstance(payload.get(bucket), list) for bucket in BUCKETS):
        raise SourceError("Formato inesperado do INMET: faltam as listas 'hoje' e 'futuro'")
    alerts: list[WeatherAlert] = []
    unreadable = 0
    for item in (item for bucket in BUCKETS for item in payload[bucket]):
        alert = _parse_alert(item, source_zone, page_url)
        if alert is None:
            unreadable += 1
        else:
            alerts.append(alert)
    if unreadable:
        logger.warning("%d avisos do INMET não puderam ser lidos", unreadable)
    return AlertFeed(alerts=tuple(alerts), unreadable=unreadable)


def _parse_alert(item: Any, zone: ZoneInfo, page_url: str) -> WeatherAlert | None:
    if not isinstance(item, dict) or item.get("id") in (None, ""):
        return None
    alert_id = str(item["id"])
    municipalities = _municipalities(item.get("municipios"))
    geocodes = set(IBGE_CODE.findall(_text(item.get("geocodes")) or ""))
    geocodes.update(code for _, code in municipalities)
    return WeatherAlert(
        id=alert_id,
        event=_text(item.get("descricao")),
        severity=_text(item.get("severidade")),
        color=_color(item.get("aviso_cor")),
        starts_at=_moment(item.get("inicio"), item.get("data_inicio"), item.get("hora_inicio"), zone),
        ends_at=_moment(item.get("fim"), item.get("data_fim"), item.get("hora_fim"), zone),
        closed=item.get("encerrado") is True,
        geocodes=frozenset(geocodes),
        municipalities=tuple(name for name, _ in municipalities),
        regions=_split(item.get("mesorregioes")),
        states=_split(item.get("estados")),
        risks=_texts(item.get("riscos")),
        instructions=_texts(item.get("instrucoes")),
        url=page_url.format(id=quote(alert_id, safe="")),
        notice_id=_text(item.get("id_aviso")),
        sequence=_int(item.get("id_sequencia")),
    )


def _moment(combined: Any, raw_date: Any, raw_time: Any, zone: ZoneInfo) -> datetime | None:
    """`inicio`/`fim` ("2026-11-10 00:01"); na falta deles, `data_inicio` (só a data vale) + `hora_inicio`."""
    text = _text(combined)
    if text is None and _text(raw_date) and _text(raw_time):
        text = f"{_text(raw_date)[:10]} {_text(raw_time)}"
    if text is None:
        return None
    try:
        return datetime.strptime(text[:16], "%Y-%m-%d %H:%M").replace(tzinfo=zone)
    except ValueError:
        return None


def _municipalities(raw: Any) -> list[tuple[str, str]]:
    return [(match["name"], match["code"]) for match in MUNICIPALITY.finditer(_text(raw) or "")]


def _split(raw: Any) -> tuple[str, ...]:
    return tuple(part.strip() for part in (_text(raw) or "").split(",") if part.strip())


def _texts(raw: Any) -> tuple[str, ...]:
    values = raw if isinstance(raw, list) else [raw]
    return tuple(text for text in (_text(value) for value in values) if text)


def _text(raw: Any) -> str | None:
    """Texto ou número da fonte; listas, objetos e booleanos não viram texto."""
    if isinstance(raw, bool) or not isinstance(raw, str | int):
        return None
    text = str(raw).strip()
    return text or None


def _color(raw: Any) -> str | None:
    text = _text(raw)
    return text if text and COLOR.fullmatch(text) else None


def _int(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
