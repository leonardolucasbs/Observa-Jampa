import logging
import math
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import requests

from pages.chuvas.clients.http import SourceError, get_json
from pages.chuvas.config import ForecastConfig, LocationConfig
from pages.chuvas.domain.models import DailyRain, HourlyRain, RainForecast

logger = logging.getLogger(__name__)

SOURCE = "Open-Meteo"
DAILY_VARIABLES = ("precipitation_sum", "precipitation_probability_max")
HOURLY_VARIABLES = ("precipitation",)
HOURS_PER_DAY = 24


class OpenMeteoForecastClient:
    def __init__(
        self,
        session: requests.Session,
        config: ForecastConfig,
        location: LocationConfig,
        timezone: str,
        timeout_seconds: float,
    ) -> None:
        self._session = session
        self._config = config
        self._location = location
        self._timezone = timezone
        self._timeout = timeout_seconds

    def fetch(self) -> RainForecast:
        params = {
            "latitude": self._location.latitude,
            "longitude": self._location.longitude,
            "daily": ",".join(DAILY_VARIABLES),
            "hourly": ",".join(HOURLY_VARIABLES),
            "forecast_days": self._config.forecast_days,
            "timezone": self._timezone,
        }
        logger.info("Consultando a previsão de chuva na Open-Meteo")
        payload = get_json(self._session, self._config.base_url, params, self._timeout, SOURCE)
        try:
            return parse_forecast(payload, self._timezone)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:  # formato que o parser não previu
            logger.exception("Resposta da Open-Meteo em formato inesperado")
            raise SourceError("Formato inesperado da Open-Meteo") from exc


def parse_forecast(payload: Any, expected_timezone: str) -> RainForecast:
    if not isinstance(payload, dict):
        raise SourceError("Formato inesperado da Open-Meteo: a resposta não é um objeto")
    if payload.get("error"):
        raise SourceError(f"A Open-Meteo recusou a consulta: {payload.get('reason', 'sem detalhe')}")
    if payload.get("timezone") != expected_timezone:
        # As datas diárias são do fuso pedido; em outro fuso "hoje" e "amanhã" ficariam errados.
        raise SourceError(f"A Open-Meteo respondeu no fuso {payload.get('timezone')!r}, não em {expected_timezone}")

    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise SourceError("Formato inesperado da Open-Meteo: falta o bloco 'daily'")
    days = _dates(daily.get("time"))
    totals = _series(daily, "precipitation_sum", len(days))
    probabilities = _series(daily, "precipitation_probability_max", len(days))
    hours = _hourly_entries(payload.get("hourly"))
    hourly_totals = _hourly_totals(hours)

    entries = []
    for index, day in enumerate(days):
        total = _non_negative(totals[index])
        from_hourly = total is None and day in hourly_totals
        if from_hourly:
            total = hourly_totals[day]
        probability = _non_negative(probabilities[index])
        entries.append(
            DailyRain(
                day=day,
                precipitation_mm=total,
                probability_max_pct=None if probability is None else round(probability),
                from_hourly=from_hourly,
            )
        )
    return RainForecast(timezone=expected_timezone, days=tuple(entries), hours=tuple(hours))


def _dates(raw: Any) -> list[date]:
    if not isinstance(raw, list) or not raw:
        raise SourceError("Formato inesperado da Open-Meteo: 'daily.time' ausente ou vazio")
    try:
        days = [date.fromisoformat(value) for value in raw]
    except (TypeError, ValueError) as exc:
        raise SourceError("Formato inesperado da Open-Meteo: data inválida em 'daily.time'") from exc
    if len(set(days)) != len(days):
        raise SourceError("A Open-Meteo repetiu datas em 'daily.time'")
    return days


def _series(block: dict[str, Any], name: str, length: int) -> list[Any]:
    """Série ausente vira lista de None; série com tamanho diferente das datas não dá para alinhar."""
    values = block.get(name)
    if values is None:
        logger.warning("A Open-Meteo não trouxe '%s'", name)
        return [None] * length
    if not isinstance(values, list) or len(values) != length:
        raise SourceError(f"Formato inesperado da Open-Meteo: '{name}' não acompanha as datas")
    return values


def _hourly_entries(hourly: Any) -> list[HourlyRain]:
    """Previsão hora a hora. Horário ou série inválidos descartam tudo: não dá para alinhar as horas."""
    if not isinstance(hourly, dict):
        return []
    times, values = hourly.get("time"), hourly.get("precipitation")
    if not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values):
        return []
    entries = []
    for raw_time, value in zip(times, values, strict=True):
        try:
            moment = datetime.fromisoformat(raw_time)
        except (TypeError, ValueError):
            return []
        entries.append(HourlyRain(moment=moment, precipitation_mm=_non_negative(value)))
    return entries


def _hourly_totals(hours: list[HourlyRain]) -> dict[date, float]:
    """Soma horária por data local, só para os dias com as 24 horas preenchidas."""
    by_day: dict[date, list[float | None]] = defaultdict(list)
    for hour in hours:
        by_day[hour.moment.date()].append(hour.precipitation_mm)
    return {
        day: round(sum(values), 1)
        for day, values in by_day.items()
        if len(values) == HOURS_PER_DAY and all(value is not None for value in values)
    }


def _non_negative(value: Any) -> float | None:
    """Número finito e não negativo; qualquer outra coisa é dado ausente (nunca zero)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return float(value)
