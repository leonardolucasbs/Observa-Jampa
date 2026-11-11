from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from pages.chuvas.clients.http import build_session
from pages.chuvas.clients.inmet_alerts import InmetAlertsClient
from pages.chuvas.clients.open_meteo_forecast import OpenMeteoForecastClient
from pages.chuvas.config import Settings, load_settings
from pages.chuvas.services.alerts_service import AlertsService
from pages.chuvas.services.cache import CachedSource, Clock
from pages.chuvas.services.rain_service import RainService


@dataclass(frozen=True)
class Container:
    settings: Settings
    clock: Clock
    rain_service: RainService
    alerts_service: AlertsService


def local_clock(timezone: str) -> Clock:
    zone = ZoneInfo(timezone)

    def now() -> datetime:
        return datetime.now(zone).replace(microsecond=0)

    return now


def build_container(settings: Settings | None = None, clock: Clock | None = None) -> Container:
    settings = settings or load_settings()
    clock = clock or local_clock(settings.timezone)
    timeout = settings.http.timeout_seconds
    forecast_client = OpenMeteoForecastClient(
        build_session(settings.http), settings.forecast, settings.location, settings.timezone, timeout
    )
    alerts_client = InmetAlertsClient(build_session(settings.http), settings.alerts, timeout)
    forecast_source = CachedSource(
        forecast_client.fetch,
        ttl_seconds=settings.forecast.refresh_seconds,
        max_stale_seconds=settings.forecast.max_stale_seconds,
        retry_after_seconds=settings.forecast.retry_after_failure_seconds,
        clock=clock,
        name="Open-Meteo",
    )
    alerts_source = CachedSource(
        alerts_client.fetch,
        ttl_seconds=settings.alerts.refresh_seconds,
        max_stale_seconds=settings.alerts.max_stale_seconds,
        retry_after_seconds=settings.alerts.retry_after_failure_seconds,
        clock=clock,
        name="INMET",
    )
    return Container(
        settings=settings,
        clock=clock,
        rain_service=RainService(forecast_source, clock, settings.timezone),
        alerts_service=AlertsService(alerts_source, settings.location.ibge_code, clock),
    )
