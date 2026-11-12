from datetime import date, datetime

import pytest
import requests

from pages.chuvas.clients.http import SourceError
from pages.chuvas.clients.open_meteo_forecast import OpenMeteoForecastClient, parse_forecast
from tests.chuvas.conftest import FakeResponse, FakeSession

TIMEZONE = "America/Fortaleza"


def client(settings, session) -> OpenMeteoForecastClient:
    return OpenMeteoForecastClient(session, settings.forecast, settings.location, settings.timezone, timeout_seconds=5)


def test_parses_the_real_response_one_entry_per_local_date(forecast_payload):
    forecast = parse_forecast(forecast_payload, TIMEZONE)

    assert [entry.day for entry in forecast.days] == [date(2026, 11, day) for day in range(10, 17)]
    assert [entry.precipitation_mm for entry in forecast.days] == forecast_payload["daily"]["precipitation_sum"]
    assert forecast.days[0].probability_max_pct == forecast_payload["daily"]["precipitation_probability_max"][0]
    assert not any(entry.from_hourly for entry in forecast.days)


def test_daily_sum_matches_the_hourly_values_of_the_real_response(forecast_payload):
    """Confere a premissa do fallback horário: na resposta real, o total diário é a soma das 24 horas."""
    del forecast_payload["daily"]["precipitation_sum"]

    forecast = parse_forecast(forecast_payload, TIMEZONE)

    assert all(entry.from_hourly for entry in forecast.days)
    assert [entry.precipitation_mm for entry in forecast.days] == [4.0, 5.3, 4.4, 2.3, 2.8, 0.2, 2.2]


def test_zero_is_kept_and_null_stays_missing(forecast_payload):
    forecast_payload["daily"]["precipitation_sum"][1] = 0.0
    forecast_payload["daily"]["precipitation_sum"][2] = None
    forecast_payload["daily"]["precipitation_probability_max"][2] = None
    forecast_payload["hourly"]["precipitation"][48] = None  # 12/11 também sem uma hora: sem fallback

    days = parse_forecast(forecast_payload, TIMEZONE).days

    assert days[1].precipitation_mm == 0.0
    assert days[2].precipitation_mm is None
    assert days[2].probability_max_pct is None


def test_missing_daily_value_falls_back_to_complete_hourly_day(forecast_payload):
    forecast_payload["daily"]["precipitation_sum"][0] = None

    first = parse_forecast(forecast_payload, TIMEZONE).days[0]

    assert first.precipitation_mm == 4.0
    assert first.from_hourly


@pytest.mark.parametrize("bad_value", ["3.8", -1.0, True, float("nan"), {"mm": 3}])
def test_invalid_values_become_missing_not_zero(forecast_payload, bad_value):
    forecast_payload["daily"]["precipitation_sum"][3] = bad_value
    forecast_payload["hourly"]["precipitation"][72] = None  # impede o fallback para 13/11

    assert parse_forecast(forecast_payload, TIMEZONE).days[3].precipitation_mm is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop("daily"),
        lambda payload: payload["daily"].pop("time"),
        lambda payload: payload["daily"].update(time=[]),
        lambda payload: payload["daily"].update(time=["10/11/2026"] * 7),
        lambda payload: payload["daily"]["precipitation_sum"].pop(),  # série desalinhada das datas
        lambda payload: payload["daily"]["time"].__setitem__(1, payload["daily"]["time"][0]),  # data repetida
        lambda payload: payload.update(timezone="GMT"),
    ],
    ids=["sem daily", "sem time", "time vazio", "data inválida", "série desalinhada", "data repetida", "outro fuso"],
)
def test_rejects_responses_that_cannot_be_trusted(forecast_payload, mutate):
    mutate(forecast_payload)
    with pytest.raises(SourceError):
        parse_forecast(forecast_payload, TIMEZONE)


def test_rejects_api_error_payload():
    with pytest.raises(SourceError, match="Invalid timezone"):
        parse_forecast({"error": True, "reason": "Invalid timezone"}, TIMEZONE)


def test_client_requests_daily_totals_in_joao_pessoa_timezone(settings, forecast_payload):
    session = FakeSession(FakeResponse(forecast_payload))

    forecast = client(settings, session).fetch()

    params = session.calls[0]["params"]
    assert params["timezone"] == "America/Fortaleza"
    assert params["daily"] == "precipitation_sum,precipitation_probability_max"
    assert params["forecast_days"] == 7
    assert (params["latitude"], params["longitude"]) == (-7.1195, -34.845)
    assert len(forecast.days) == 7


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (requests.Timeout("lento"), "não respondeu em 5 s"),
        (requests.ConnectionError("sem rede"), "Sem conexão com Open-Meteo"),
        (FakeResponse({"error": True, "reason": "Server overloaded"}, status_code=503), "HTTP 503: Server overloaded"),
        (FakeResponse(text="<html>erro</html>", status_code=502), "HTTP 502"),
        (FakeResponse(text="<html>ok?</html>"), "não é JSON"),
    ],
)
def test_client_turns_network_and_http_failures_into_source_error(settings, outcome, message):
    with pytest.raises(SourceError, match=message):
        client(settings, FakeSession(outcome)).fetch()


def test_rate_limit_carries_retry_after(settings):
    session = FakeSession(FakeResponse({"error": True, "reason": "limit"}, status_code=429, headers={"Retry-After": "600"}))

    with pytest.raises(SourceError) as error:
        client(settings, session).fetch()

    assert "429" in str(error.value)
    assert error.value.retry_after_seconds == 600


def test_unexpected_shape_becomes_source_error(settings, forecast_payload):
    forecast_payload["hourly"] = {"time": [1, 2], "precipitation": [0, 0]}  # horas que não são datas
    forecast_payload["daily"]["precipitation_sum"] = [None] * 7
    forecast = client(settings, FakeSession(FakeResponse(forecast_payload))).fetch()
    assert all(entry.precipitation_mm is None for entry in forecast.days)

    with pytest.raises(SourceError):
        client(settings, FakeSession(FakeResponse(["não", "é", "objeto"]))).fetch()


def test_parses_hour_by_hour_values_of_the_real_response(forecast_payload):
    forecast = parse_forecast(forecast_payload, TIMEZONE)

    assert len(forecast.hours) == 168
    assert forecast.hours[0].moment == datetime(2026, 11, 10, 0, 0)
    assert forecast.hours[0].precipitation_mm == 0.2
