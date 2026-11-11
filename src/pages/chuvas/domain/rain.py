"""Acumulados de chuva prevista para hoje, amanhã e os próximos 7 dias.

Os períodos são definidos por datas locais de João Pessoa, não pela posição dos valores na resposta:
uma previsão consultada ontem continua servindo para hoje, mas o último dia da semana fica sem dado.
"""

from dataclasses import replace
from datetime import date, timedelta

from pages.chuvas.domain.models import DailyRain, RainForecast, RainOutlook, RainTotal

WEEK_DAYS = 7


def rain_outlook(forecast: RainForecast, today: date) -> RainOutlook:
    by_day = {entry.day: entry for entry in forecast.days}
    week_days = [today + timedelta(days=offset) for offset in range(WEEK_DAYS)]
    return RainOutlook(
        today=_single_day(by_day, today),
        tomorrow=_single_day(by_day, today + timedelta(days=1)),
        week=total_for(by_day, week_days),
        daily=tuple(by_day[day] for day in week_days if day in by_day),
    )


def total_for(by_day: dict[date, DailyRain], days: list[date]) -> RainTotal:
    """Soma os dias com previsão; os dias sem previsão ficam listados em `missing_days`, não viram zero."""
    values = [by_day[day].precipitation_mm for day in days if day in by_day]
    known = [value for value in values if value is not None]
    missing = tuple(day for day in days if day not in by_day or by_day[day].precipitation_mm is None)
    return RainTotal(
        start=days[0],
        end=days[-1],
        precipitation_mm=round(sum(known), 1) if known else None,
        missing_days=missing,
        from_hourly=any(by_day[day].from_hourly for day in days if day in by_day),
    )


def _single_day(by_day: dict[date, DailyRain], day: date) -> RainTotal:
    entry = by_day.get(day)
    return replace(total_for(by_day, [day]), probability_max_pct=entry.probability_max_pct if entry else None)
