import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FEATURE_DIR = Path(__file__).resolve().parent 

@dataclass(frozen=True)
class LocationConfig:
    name: str
    latitude: float
    longitude: float
    ibge_code: str


@dataclass(frozen=True)
class HttpConfig:
    timeout_seconds: float
    retries: int
    backoff_factor: float
    user_agent: str


@dataclass(frozen=True)
class ForecastConfig:
    base_url: str
    forecast_days: int
    refresh_seconds: int
    max_stale_seconds: int
    retry_after_failure_seconds: int


@dataclass(frozen=True)
class AlertsConfig:
    base_url: str
    alert_page_url: str
    source_timezone: str
    refresh_seconds: int
    max_stale_seconds: int
    retry_after_failure_seconds: int


@dataclass(frozen=True)
class UiConfig:
    rerun_seconds: int


@dataclass(frozen=True)
class TextsConfig:
    rain_disclaimer: str
    alerts_disclaimer: str
    attribution: str


@dataclass(frozen=True)
class Settings:
    log_level: str
    timezone: str
    location: LocationConfig
    http: HttpConfig
    forecast: ForecastConfig
    alerts: AlertsConfig
    ui: UiConfig
    texts: TextsConfig


def load_settings(config_path: Path | None = None) -> Settings:
    with (config_path or FEATURE_DIR / "config.toml").open("rb") as file:
        raw = tomllib.load(file)
    return build_settings(raw)


def build_settings(raw: dict[str, Any]) -> Settings:
    return Settings(
        log_level=raw.get("log_level", "INFO"),
        timezone=raw["timezone"],
        location=LocationConfig(**{**raw["location"], "ibge_code": str(raw["location"]["ibge_code"])}),
        http=HttpConfig(**raw["http"]),
        forecast=ForecastConfig(**raw["forecast"]),
        alerts=AlertsConfig(**raw["alerts"]),
        ui=UiConfig(**raw["ui"]),
        texts=TextsConfig(**raw["texts"]),
    )
