from datetime import datetime

import pytest

from pages.poluentes.clients.base import DataSourceError
from pages.poluentes.clients.open_meteo_air_quality import parse_air_quality_response
from tests.poluentes.conftest import JOAO_PESSOA, RECIFE

FETCHED_AT = datetime(2026, 10, 30, 12, 25)


def test_parses_one_block_per_location_in_request_order(multi_location_payload: list[dict]) -> None:
    readings = parse_air_quality_response(multi_location_payload, [JOAO_PESSOA, RECIFE], FETCHED_AT)

    assert len(readings) == 48
    assert {r.location_slug for r in readings[:24]} == {"joao-pessoa"}
    assert {r.location_slug for r in readings[24:]} == {"recife"}


def test_maps_values_and_types_from_real_payload(multi_location_payload: list[dict]) -> None:
    readings = parse_air_quality_response(multi_location_payload, [JOAO_PESSOA, RECIFE], FETCHED_AT)
    noon = next(r for r in readings if r.location_slug == "joao-pessoa" and r.measured_at.hour == 12)
    hourly = multi_location_payload[0]["hourly"]

    assert noon.measured_at == datetime(2026, 10, 30, 12)
    assert noon.us_aqi == hourly["us_aqi"][12]
    assert isinstance(noon.us_aqi, int)
    assert noon.pm2_5 == pytest.approx(hourly["pm2_5"][12])
    assert noon.dominant_pollutant == "pm2_5"
    assert noon.fetched_at == FETCHED_AT


def test_marks_hours_after_fetch_hour_as_forecast(multi_location_payload: list[dict]) -> None:
    readings = parse_air_quality_response(multi_location_payload, [JOAO_PESSOA, RECIFE], FETCHED_AT)
    jp = [r for r in readings if r.location_slug == "joao-pessoa"]

    assert [r.measured_at.hour for r in jp if r.is_forecast] == list(range(13, 24))
    assert not next(r for r in jp if r.measured_at.hour == 12).is_forecast


def test_accepts_single_object_for_single_location(multi_location_payload: list[dict]) -> None:
    readings = parse_air_quality_response(multi_location_payload[0], [JOAO_PESSOA], FETCHED_AT)

    assert len(readings) == 24


def test_null_values_become_none() -> None:
    payload = {"hourly": {"time": ["2026-10-30T00:00"], "us_aqi": [None], "pm2_5": [None]}}

    reading = parse_air_quality_response(payload, [JOAO_PESSOA], FETCHED_AT)[0]

    assert reading.us_aqi is None
    assert reading.pm2_5 is None
    assert reading.dust is None
    assert reading.dominant_pollutant is None


def test_rejects_block_count_mismatch(multi_location_payload: list[dict]) -> None:
    with pytest.raises(DataSourceError):
        parse_air_quality_response(multi_location_payload, [JOAO_PESSOA], FETCHED_AT)


def test_rejects_block_without_hourly_time() -> None:
    with pytest.raises(DataSourceError):
        parse_air_quality_response({"hourly": {}}, [JOAO_PESSOA], FETCHED_AT)
