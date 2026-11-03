from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from itinerario.domain.models import Location

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class HttpConfig:
    timeout_seconds: float
    retries: int
    backoff_factor: float


@dataclass(frozen=True)
class AirQualityConfig:
    base_url: str
    collect_past_days: int
    forecast_days: int
    max_past_days: int


@dataclass(frozen=True)
class DashboardConfig:
    period_options: tuple[int, ...]
    cache_ttl_seconds: int
    attribution: str
    disclaimer: str
    plain_disclaimer: str


@dataclass(frozen=True)
class Settings:
    log_level: str
    timezone: str
    primary_location: str
    database_path: Path
    http: HttpConfig
    air_quality: AirQualityConfig
    who_guidelines_24h: dict[str, float]
    dashboard: DashboardConfig
    locations: tuple[Location, ...]


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    path = _resolve(config_path or Path(os.getenv("ITINERARIO_CONFIG", "config.toml")), PROJECT_ROOT)
    with path.open("rb") as file:
        raw = tomllib.load(file)
    return _build_settings(raw, base_dir=path.parent)


def _build_settings(raw: dict[str, Any], base_dir: Path) -> Settings:
    database_path = _resolve(Path(os.getenv("ITINERARIO_DB_PATH", raw["database"]["path"])), base_dir)
    locations = tuple(Location(**entry) for entry in raw["locations"])
    primary = raw["primary_location"]
    if primary not in {location.slug for location in locations}:
        raise ValueError(f"primary_location '{primary}' não está em [[locations]]")
    return Settings(
        log_level=os.getenv("ITINERARIO_LOG_LEVEL", raw.get("log_level", "INFO")),
        timezone=raw["timezone"],
        primary_location=primary,
        database_path=database_path,
        http=HttpConfig(**raw["http"]),
        air_quality=AirQualityConfig(**raw["air_quality"]),
        who_guidelines_24h={key: float(value) for key, value in raw["who_guidelines_24h"].items()},
        dashboard=DashboardConfig(
            period_options=tuple(raw["dashboard"]["period_options"]),
            cache_ttl_seconds=raw["dashboard"]["cache_ttl_seconds"],
            attribution=raw["dashboard"]["attribution"],
            disclaimer=raw["dashboard"]["disclaimer"],
            plain_disclaimer=raw["dashboard"]["plain_disclaimer"],
        ),
        locations=locations,
    )


def _resolve(path: Path, base_dir: Path) -> Path:
    return path if path.is_absolute() else (base_dir / path).resolve()
