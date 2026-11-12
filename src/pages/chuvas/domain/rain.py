"""Acumulados de chuva prevista para hoje, amanhã e os próximos 7 dias, e o que eles significam para a pessoa.

Os períodos são definidos por datas locais de João Pessoa, não pela posição dos valores na resposta:
uma previsão consultada ontem continua servindo para hoje, mas o último dia da semana fica sem dado.

Veredito e intensidade:
- Vai chover quando o total previsto do dia chega a RAIN_THRESHOLD_MM. Abaixo disso é garoa ou nada.
- A intensidade vem do pico em uma hora (mm/h), que é o que define se a chuva é forte, não o total do dia:
  o mesmo total de 30 mm pode cair em 24 h leves ou em 2 h fortes.
"""

from dataclasses import replace
from datetime import date, timedelta

from pages.chuvas.domain.models import DailyRain, HourlyRain, Intensity, RainForecast, RainOutlook, RainTotal

WEEK_DAYS = 7
RAIN_THRESHOLD_MM = 1.0
# Limite inferior de cada faixa, do mais forte para o mais fraco (mm em uma hora).
INTENSITY_FLOORS = (
    (50.0, Intensity.MUITO_FORTE),
    (10.0, Intensity.FORTE),
    (2.5, Intensity.MODERADA),
    (0.0, Intensity.FRACA),
)


def rain_outlook(forecast: RainForecast, today: date) -> RainOutlook:
    by_day = {entry.day: entry for entry in forecast.days}
    week_days = [today + timedelta(days=offset) for offset in range(WEEK_DAYS)]
    week_values = [by_day[day].precipitation_mm for day in week_days if day in by_day]
    return RainOutlook(
        today=_single_day(by_day, forecast.hours, today),
        tomorrow=_single_day(by_day, forecast.hours, today + timedelta(days=1)),
        week=total_for(by_day, week_days),
        daily=tuple(by_day[day] for day in week_days if day in by_day),
        rainy_days=sum(1 for value in week_values if is_rainy(value)),
        known_days=sum(1 for value in week_values if value is not None),
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


def is_rainy(precipitation_mm: float | None) -> bool | None:
    """True se o total previsto chega ao limiar; None quando não há previsão (nunca False por falta de dado)."""
    return None if precipitation_mm is None else precipitation_mm >= RAIN_THRESHOLD_MM


def intensity_for(peak_mm_per_hour: float) -> Intensity:
    for floor, intensity in INTENSITY_FLOORS:
        if peak_mm_per_hour >= floor:
            return intensity
    return Intensity.FRACA


def _single_day(by_day: dict[date, DailyRain], hours: tuple[HourlyRain, ...], day: date) -> RainTotal:
    entry = by_day.get(day)
    total = total_for(by_day, [day])
    peak = _peak(hours, day)
    will_rain = is_rainy(total.precipitation_mm)
    intensity = None
    if will_rain and peak is not None:
        intensity = intensity_for(peak.precipitation_mm)
    return replace(
        total,
        probability_max_pct=entry.probability_max_pct if entry else None,
        will_rain=will_rain,
        peak_mm_per_hour=peak.precipitation_mm if peak else None,
        peak_at=peak.moment if peak else None,
        intensity=intensity,
    )


def _peak(hours: tuple[HourlyRain, ...], day: date) -> HourlyRain | None:
    """Hora com mais chuva prevista no dia. Empate: a primeira. Horas sem valor não contam."""
    candidates = [hour for hour in hours if hour.moment.date() == day and hour.precipitation_mm is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda hour: hour.precipitation_mm)  # max devolve o primeiro empatado
