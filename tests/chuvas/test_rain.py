from datetime import date, datetime, timedelta, timezone

import pytest

from pages.chuvas.clients.open_meteo_forecast import parse_forecast
from pages.chuvas.domain.models import DailyRain, RainForecast
from pages.chuvas.domain.rain import rain_outlook
from pages.chuvas.services.cache import CachedSource
from pages.chuvas.services.rain_service import RainService
from tests.chuvas.conftest import FakeClock

TIMEZONE = "America/Fortaleza"
TODAY = date(2026, 11, 10)


def forecast(values: list[float | None], first_day: date = TODAY) -> RainForecast:
    return RainForecast(
        timezone=TIMEZONE,
        days=tuple(
            DailyRain(first_day + timedelta(days=index), value, probability_max_pct=50)
            for index, value in enumerate(values)
        ),
    )


def test_real_response_totals_for_today_tomorrow_and_seven_days(forecast_payload):
    outlook = rain_outlook(parse_forecast(forecast_payload, TIMEZONE), TODAY)

    assert outlook.today.precipitation_mm == 4.0
    assert outlook.tomorrow.precipitation_mm == 5.3
    # 4,0 + 5,3 + 4,4 + 2,3 + 2,8 + 0,2 + 2,2 = 21,2 (arredondado: sem resíduo de ponto flutuante)
    assert outlook.week.precipitation_mm == 21.2
    assert (outlook.week.start, outlook.week.end, outlook.week.days) == (TODAY, date(2026, 11, 16), 7)
    assert outlook.week.complete
    assert outlook.today.probability_max_pct == 86
    assert outlook.week.probability_max_pct is None  # probabilidade não se soma nem se agrega na semana


def test_seven_day_total_counts_each_day_once_and_ignores_days_outside_the_window():
    eight_days = forecast([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 100.0])  # o 8º dia fica fora

    week = rain_outlook(eight_days, TODAY).week

    assert week.precipitation_mm == 28.0
    assert week.end == date(2026, 11, 16)


def test_zero_rain_is_a_value_and_missing_rain_is_not():
    outlook = rain_outlook(forecast([0.0, None, 0.0, 0.0, 0.0, 0.0, 0.0]), TODAY)

    assert outlook.today.precipitation_mm == 0.0
    assert outlook.today.complete
    assert outlook.tomorrow.precipitation_mm is None
    assert not outlook.tomorrow.complete
    assert outlook.week.precipitation_mm == 0.0
    assert outlook.week.missing_days == (date(2026, 11, 11),)
    assert not outlook.week.complete


def test_no_forecast_at_all_gives_no_total():
    outlook = rain_outlook(forecast([None] * 7), TODAY)

    assert outlook.week.precipitation_mm is None
    assert len(outlook.week.missing_days) == 7


def test_forecast_from_yesterday_still_serves_today_but_the_week_is_partial():
    """Previsão do cache consultada ontem: os dias são achados pela data, não pela posição."""
    yesterday_forecast = forecast([9.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0], first_day=TODAY - timedelta(days=1))

    outlook = rain_outlook(yesterday_forecast, TODAY)

    assert outlook.today.precipitation_mm == 1.0
    assert outlook.tomorrow.precipitation_mm == 2.0
    assert outlook.week.precipitation_mm == 21.0  # 1 + 2 + 3 + 4 + 5 + 6, sem o 9 de ontem
    assert outlook.week.missing_days == (date(2026, 11, 16),)


@pytest.mark.parametrize(
    ("instant", "expected_today"),
    [
        # 01:30 UTC de 11/11 ainda é 22:30 de 10/11 em João Pessoa (UTC−3)
        (datetime(2026, 11, 11, 1, 30, tzinfo=timezone.utc), date(2026, 11, 10)),
        # 03:00 UTC de 11/11 é meia-noite em João Pessoa: já é o dia 11
        (datetime(2026, 11, 11, 3, 0, tzinfo=timezone.utc), date(2026, 11, 11)),
    ],
)
def test_today_follows_joao_pessoa_timezone_not_utc(forecast_payload, instant, expected_today):
    parsed = parse_forecast(forecast_payload, TIMEZONE)
    source = CachedSource(lambda: parsed, ttl_seconds=60, max_stale_seconds=60, retry_after_seconds=60,
                          clock=FakeClock(instant), name="teste")

    outlook = RainService(source, FakeClock(instant), TIMEZONE).outlook().value

    assert outlook.today.start == expected_today
    assert outlook.tomorrow.start == expected_today + timedelta(days=1)
    assert outlook.week.start == expected_today
