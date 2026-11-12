from datetime import date, datetime, timedelta

WEEKDAYS = ("seg.", "ter.", "qua.", "qui.", "sex.", "sáb.", "dom.")

def format_mm(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}".replace(".", ",") + " mm"


def format_mm_per_hour(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + " mm/h"


def format_hour(moment: datetime) -> str:
    return f"{moment:%H}h"


def format_day(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day:%d/%m}"


def format_days(days: tuple[date, ...]) -> str:
    return ", ".join(f"{day:%d/%m}" for day in days)


def format_period(start: date, end: date) -> str:
    return format_day(start) if start == end else f"{format_day(start)} a {format_day(end)}"


def format_moment(moment: datetime | None) -> str:
    return "não informado" if moment is None else f"{moment:%d/%m/%Y} às {moment:%H:%M}"


def format_age(age: timedelta) -> str:
    minutes = int(age.total_seconds() // 60)
    if minutes < 1:
        return "há menos de 1 min"
    if minutes < 60:
        return f"há {minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"há {hours} h {rest:02d} min"


def format_interval(seconds: int) -> str:
    minutes = round(seconds / 60)
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h"
