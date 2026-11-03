import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine

from pages.poluentes.domain.models import AirQualityReading, Location
from pages.poluentes.repositories.database import create_db_engine

FIXTURES = Path(__file__).parent / "fixtures"

JOAO_PESSOA = Location("joao-pessoa", "João Pessoa", -7.115, -34.863)
RECIFE = Location("recife", "Recife", -8.05, -34.90)


@pytest.fixture
def multi_location_payload() -> list[dict[str, Any]]:
    return json.loads((FIXTURES / "open_meteo_multi.json").read_text(encoding="utf-8"))


@pytest.fixture
def engine() -> Engine:
    return create_db_engine("sqlite://")


def make_reading(
    slug: str = "joao-pessoa",
    measured_at: datetime = datetime(2026, 10, 30, 12),
    pm2_5: float | None = 10.0,
    us_aqi: int | None = 50,
    is_forecast: bool = False,
    fetched_at: datetime = datetime(2026, 10, 30, 13),
) -> AirQualityReading:
    return AirQualityReading(
        location_slug=slug,
        measured_at=measured_at,
        us_aqi=us_aqi,
        european_aqi=30,
        pm2_5=pm2_5,
        pm10=15.0,
        nitrogen_dioxide=2.0,
        ozone=40.0,
        carbon_monoxide=100.0,
        sulphur_dioxide=1.0,
        dust=0.5,
        dominant_pollutant="pm2_5",
        is_forecast=is_forecast,
        fetched_at=fetched_at,
    )
