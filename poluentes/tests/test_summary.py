from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import Engine

from itinerario.domain.aqi import EPA_BANDS, UNKNOWN_BAND, band_lower_bound, band_severity, scale_position
from itinerario.domain.guidance import BAND_GUIDANCE, UNKNOWN_GUIDANCE, guidance_for
from itinerario.repositories.air_quality_repository import AirQualityRepository
from itinerario.repositories.location_repository import LocationRepository
from itinerario.services.aggregations import daily_median
from itinerario.services.air_quality_service import AirQualityService
from tests.conftest import JOAO_PESSOA, make_reading

NOW = datetime(2026, 10, 30, 12, 30)


def at(hour: int) -> datetime:
    return datetime(2026, 10, 30, hour)


def test_every_band_has_plain_language_text() -> None:
    assert {band.label for band in EPA_BANDS} == set(BAND_GUIDANCE)
    assert guidance_for(UNKNOWN_BAND.label) is UNKNOWN_GUIDANCE


@pytest.mark.parametrize(
    ("value", "position"),
    [(0, 0.0), (50, 1 / 6), (75, 1.5 / 6), (101, 2 / 6 + 1 / 300), (500, 1.0), (900, 1.0), (None, None)],
)
def test_scale_position_gives_each_band_the_same_width(value: int | None, position: float | None) -> None:
    assert scale_position(value) == (None if position is None else pytest.approx(position))


def test_band_severity_and_lower_bound() -> None:
    assert [band_severity(band) for band in EPA_BANDS] == list(range(6))
    assert band_severity(UNKNOWN_BAND) == -1
    assert [band_lower_bound(band) for band in EPA_BANDS] == [0, 51, 101, 151, 201, 301]


def test_daily_median_breaks_ties_upward_and_skips_missing_hours() -> None:
    frame = pd.DataFrame(
        {
            "measured_at": pd.to_datetime(
                ["2026-10-29 08:00", "2026-10-29 09:00", "2026-10-29 10:00", "2026-10-29 11:00", "2026-10-29 12:00",
                 "2026-10-30 08:00", "2026-10-30 09:00", "2026-10-31 08:00"]
            ),
            "severity": [0, 0, 0, 5, None, 0, 2, None],
        }
    )

    daily = daily_median(frame, "severity")

    assert daily["median"].tolist()[:2] == [0, 2]
    assert pd.isna(daily["median"].iloc[2])
    assert daily["hours"].tolist() == [4, 2, 0]


@pytest.fixture
def service(engine: Engine) -> AirQualityService:
    ids = LocationRepository(engine).sync([JOAO_PESSOA])
    repository = AirQualityRepository(engine)
    repository.upsert(
        [
            make_reading(measured_at=datetime(2026, 10, 28, 9), us_aqi=40, pm2_5=20.0),
            make_reading(measured_at=datetime(2026, 10, 28, 15), us_aqi=120, pm2_5=18.0),
            make_reading(measured_at=datetime(2026, 10, 30, 11), us_aqi=45, pm2_5=8.0),
            make_reading(measured_at=at(12), us_aqi=48, pm2_5=9.0),
            make_reading(measured_at=at(13), us_aqi=160, is_forecast=True),
        ],
        ids,
    )
    return AirQualityService(repository, clock=lambda: NOW)


def test_daily_aqi_uses_median_band_of_observed_hours(service: AirQualityService) -> None:
    daily = service.daily_aqi("joao-pessoa", days=3)

    assert list(daily.index) == list(pd.to_datetime(["2026-10-28", "2026-10-29", "2026-10-30"]))
    assert daily["band_label"].tolist() == ["Ruim p/ sensíveis", "Sem dado", "Boa"]
    assert daily["band_color"].iloc[1] == UNKNOWN_BAND.color
    assert daily["hours"].tolist() == [2, 0, 2]
