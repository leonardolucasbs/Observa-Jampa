import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

import requests

from itinerario.clients.base import DataSourceClient, DataSourceError, FetchWindow
from itinerario.clock import Clock
from itinerario.config import AirQualityConfig
from itinerario.domain.aqi import dominant_pollutant
from itinerario.domain.models import POLLUTANTS, AirQualityReading, Location

logger = logging.getLogger(__name__)

INDEX_VARIABLES: tuple[str, ...] = ("us_aqi", "european_aqi")
US_AQI_SUB_INDEX: dict[str, str] = {
    "us_aqi_pm2_5": "pm2_5",
    "us_aqi_pm10": "pm10",
    "us_aqi_nitrogen_dioxide": "nitrogen_dioxide",
    "us_aqi_ozone": "ozone",
    "us_aqi_carbon_monoxide": "carbon_monoxide",
    "us_aqi_sulphur_dioxide": "sulphur_dioxide",
}
HOURLY_VARIABLES: tuple[str, ...] = INDEX_VARIABLES + POLLUTANTS + tuple(US_AQI_SUB_INDEX)


class OpenMeteoAirQualityClient(DataSourceClient[AirQualityReading]):
    def __init__(
        self,
        session: requests.Session,
        config: AirQualityConfig,
        timezone: str,
        timeout_seconds: float,
        clock: Clock,
    ) -> None:
        self._session = session
        self._config = config
        self._timezone = timezone
        self._timeout = timeout_seconds
        self._clock = clock

    @property
    def source_name(self) -> str:
        return "open-meteo-air-quality"

    def fetch(self, locations: Sequence[Location], window: FetchWindow) -> list[AirQualityReading]:
        if not locations:
            return []
        params = self._build_params(locations, window)
        logger.info(
            "Consultando Open-Meteo: %d localizações, past_days=%d, forecast_days=%d",
            len(locations),
            window.past_days,
            window.forecast_days,
        )
        payload = self._get_json(params)
        return parse_air_quality_response(payload, locations, fetched_at=self._clock())

    def _build_params(self, locations: Sequence[Location], window: FetchWindow) -> dict[str, str | int]:
        return {
            "latitude": ",".join(str(location.latitude) for location in locations),
            "longitude": ",".join(str(location.longitude) for location in locations),
            "hourly": ",".join(HOURLY_VARIABLES),
            "timezone": self._timezone,
            "past_days": window.past_days,
            "forecast_days": window.forecast_days,
        }

    def _get_json(self, params: dict[str, str | int]) -> Any:
        try:
            response = self._session.get(self._config.base_url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            raise DataSourceError(f"Falha de rede ao consultar Open-Meteo: {exc}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise DataSourceError(f"Resposta não-JSON da Open-Meteo (HTTP {response.status_code})") from exc
        if not response.ok or (isinstance(payload, dict) and payload.get("error")):
            reason = payload.get("reason", "sem detalhe") if isinstance(payload, dict) else "sem detalhe"
            raise DataSourceError(f"Open-Meteo recusou a requisição (HTTP {response.status_code}): {reason}")
        return payload


def parse_air_quality_response(
    payload: Any,
    locations: Sequence[Location],
    fetched_at: datetime,
) -> list[AirQualityReading]:
    blocks = payload if isinstance(payload, list) else [payload]
    if len(blocks) != len(locations):
        raise DataSourceError(
            f"Open-Meteo devolveu {len(blocks)} blocos para {len(locations)} localizações"
        )
    current_hour = fetched_at.replace(minute=0, second=0, microsecond=0)
    readings: list[AirQualityReading] = []
    for location, block in zip(locations, blocks, strict=True):
        readings.extend(_parse_block(location.slug, block, fetched_at, current_hour))
    return readings


def _parse_block(
    slug: str,
    block: dict[str, Any],
    fetched_at: datetime,
    current_hour: datetime,
) -> list[AirQualityReading]:
    hourly = block.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise DataSourceError(f"Bloco sem 'hourly.time' para {slug}")
    times: list[str] = hourly["time"]
    readings: list[AirQualityReading] = []
    for index, raw_time in enumerate(times):
        measured_at = datetime.fromisoformat(raw_time)
        value = _value_reader(hourly, index)
        sub_indices = {pollutant: value(variable) for variable, pollutant in US_AQI_SUB_INDEX.items()}
        readings.append(
            AirQualityReading(
                location_slug=slug,
                measured_at=measured_at,
                us_aqi=_to_int(value("us_aqi")),
                european_aqi=_to_int(value("european_aqi")),
                pm2_5=value("pm2_5"),
                pm10=value("pm10"),
                nitrogen_dioxide=value("nitrogen_dioxide"),
                ozone=value("ozone"),
                carbon_monoxide=value("carbon_monoxide"),
                sulphur_dioxide=value("sulphur_dioxide"),
                dust=value("dust"),
                dominant_pollutant=dominant_pollutant(sub_indices),
                is_forecast=measured_at > current_hour,
                fetched_at=fetched_at,
            )
        )
    return readings


def _value_reader(hourly: dict[str, Any], index: int) -> Callable[[str], float | None]:
    def read(variable: str) -> float | None:
        series = hourly.get(variable)
        if not series or index >= len(series) or series[index] is None:
            return None
        return float(series[index])

    return read


def _to_int(value: float | None) -> int | None:
    return None if value is None else int(round(value))
