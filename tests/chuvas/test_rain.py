from datetime import date, datetime, timedelta, timezone

import pytest

from pages.chuvas.clients.open_meteo_forecast import parse_forecast
from pages.chuvas.domain.models import DailyRain, HourlyRain, Intensity, RainForecast
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


def hourly(day: date, values: list[float | None]) -> tuple[HourlyRain, ...]:
    """Horas de um dia começando à 0h; `values` pode ter menos de 24 itens."""
    return tuple(
        HourlyRain(moment=datetime(day.year, day.month, day.day, index), precipitation_mm=value)
        for index, value in enumerate(values)
    )


def with_hours(base: RainForecast, *hours: HourlyRain) -> RainForecast:
    return RainForecast(timezone=base.timezone, days=base.days, hours=hours)


@pytest.mark.parametrize(
    ("total_mm", "expected"),
    [(None, None), (0.0, False), (0.9, False), (1.0, True), (1.1, True)],
)
def test_rain_starts_at_one_millimetre_and_no_data_is_not_a_no(total_mm, expected):
    outlook = rain_outlook(forecast([total_mm, None, None, None, None, None, None]), TODAY)

    assert outlook.today.will_rain is expected


@pytest.mark.parametrize(
    ("peak", "intensity"),
    [
        (0.4, Intensity.FRACA),
        (2.4, Intensity.FRACA),
        (2.5, Intensity.MODERADA),  # limite inferior de cada faixa cai na faixa de cima
        (9.9, Intensity.MODERADA),
        (10.0, Intensity.FORTE),
        (49.9, Intensity.FORTE),
        (50.0, Intensity.MUITO_FORTE),
    ],
)
def test_intensity_comes_from_the_strongest_hour_not_the_daily_total(peak, intensity):
    base = forecast([max(peak, 5.0), None, None, None, None, None, None])
    hours = hourly(TODAY, [0.0, peak, 0.0])

    today = rain_outlook(with_hours(base, *hours), TODAY).today

    assert today.peak_mm_per_hour == peak
    assert today.peak_at == datetime(2026, 11, 10, 1)
    assert today.intensity is intensity


def test_heavy_daily_total_spread_over_the_day_is_not_strong_rain():
    base = forecast([30.0, None, None, None, None, None, None])
    hours = hourly(TODAY, [1.25] * 24)  # 30 mm em 24 h

    today = rain_outlook(with_hours(base, *hours), TODAY).today

    assert today.will_rain is True
    assert today.intensity is Intensity.FRACA


def test_no_hourly_data_means_rain_without_intensity():
    today = rain_outlook(forecast([4.0, None, None, None, None, None, None]), TODAY).today

    assert today.will_rain is True
    assert today.peak_mm_per_hour is None
    assert today.intensity is None


def test_dry_day_has_no_intensity_even_with_hourly_data():
    base = forecast([0.5, None, None, None, None, None, None])

    today = rain_outlook(with_hours(base, *hourly(TODAY, [0.2, 0.3])), TODAY).today

    assert today.will_rain is False
    assert today.intensity is None


def test_peak_ignores_missing_hours_and_keeps_the_first_of_a_tie():
    base = forecast([6.0, None, None, None, None, None, None])
    hours = hourly(TODAY, [None, 3.0, 3.0, 1.0])

    today = rain_outlook(with_hours(base, *hours), TODAY).today

    assert today.peak_at == datetime(2026, 11, 10, 1)


def test_peak_is_only_taken_from_the_day_it_belongs_to():
    base = forecast([0.0, 6.0, None, None, None, None, None])
    hours = hourly(TODAY + timedelta(days=1), [20.0, 1.0])

    outlook = rain_outlook(with_hours(base, *hours), TODAY)

    assert outlook.today.peak_mm_per_hour is None  # o pico de amanhã não vale para hoje
    assert outlook.tomorrow.peak_mm_per_hour == 20.0
    assert outlook.tomorrow.intensity is Intensity.FORTE  # 20 mm/h


def test_week_counts_rainy_days_and_days_with_forecast_only():
    outlook = rain_outlook(forecast([5.0, 0.5, 2.0, None, 0.0, 1.0, 9.0]), TODAY)

    assert outlook.rainy_days == 4  # 5,0, 2,0, 1,0 e 9,0
    assert outlook.known_days == 6  # o dia sem previsão não conta
