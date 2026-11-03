from datetime import datetime

from sqlalchemy import Engine

from pages.poluentes.domain.models import Location
from pages.poluentes.repositories.air_quality_repository import AirQualityRepository
from pages.poluentes.repositories.location_repository import LocationRepository
from tests.poluentes.conftest import JOAO_PESSOA, RECIFE, make_reading


def test_upsert_inserts_new_rows(engine: Engine) -> None:
    ids = LocationRepository(engine).sync([JOAO_PESSOA, RECIFE])
    repository = AirQualityRepository(engine)

    repository.upsert([make_reading("joao-pessoa"), make_reading("recife")], ids)

    assert repository.count() == 2


def test_upsert_updates_existing_row_instead_of_duplicating(engine: Engine) -> None:
    ids = LocationRepository(engine).sync([JOAO_PESSOA])
    repository = AirQualityRepository(engine)
    hour = datetime(2026, 10, 30, 12)
    repository.upsert([make_reading(measured_at=hour, pm2_5=10.0, is_forecast=True, fetched_at=datetime(2026, 10, 30, 6))], ids)

    revised_fetch = datetime(2026, 10, 30, 18)
    repository.upsert([make_reading(measured_at=hour, pm2_5=14.5, is_forecast=False, fetched_at=revised_fetch)], ids)

    rows = repository.find_between(datetime(2026, 10, 30), datetime(2026, 10, 31))
    assert repository.count() == 1
    assert rows.loc[0, "pm2_5"] == 14.5
    assert not rows.loc[0, "is_forecast"]
    assert rows.loc[0, "fetched_at"] == revised_fetch


def test_location_sync_is_idempotent_and_updates_name(engine: Engine) -> None:
    repository = LocationRepository(engine)
    first = repository.sync([JOAO_PESSOA])

    second = repository.sync([Location("joao-pessoa", "JP", -7.1, -34.8)])

    assert first == second


def test_find_latest_until_ignores_future_rows(engine: Engine) -> None:
    ids = LocationRepository(engine).sync([JOAO_PESSOA])
    repository = AirQualityRepository(engine)
    repository.upsert(
        [
            make_reading(measured_at=datetime(2026, 10, 30, 11), us_aqi=40),
            make_reading(measured_at=datetime(2026, 10, 30, 12), us_aqi=55),
            make_reading(measured_at=datetime(2026, 10, 30, 13), us_aqi=99, is_forecast=True),
        ],
        ids,
    )

    latest = repository.find_latest_until(datetime(2026, 10, 30, 12, 30))

    assert len(latest) == 1
    assert latest.loc[0, "us_aqi"] == 55
