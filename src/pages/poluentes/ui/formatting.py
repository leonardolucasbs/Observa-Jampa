from datetime import datetime, timedelta


def format_moment(moment: datetime) -> str:
    return f"{moment:%d/%m/%Y} às {moment:%H:%M}"


def format_age(age: timedelta) -> str:
    minutes = int(age.total_seconds() // 60)
    if minutes < 1:
        return "há menos de 1 min"
    if minutes < 60:
        return f"há {minutes} min"
    hours, rest = divmod(minutes, 60)
    if hours < 48:
        return f"há {hours} h {rest:02d} min"
    return f"há {hours // 24} dias"


def format_interval(seconds: float) -> str:
    minutes = round(seconds / 60)
    return f"{minutes} min" if minutes < 60 else f"{minutes // 60} h"
