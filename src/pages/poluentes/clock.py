from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

Clock = Callable[[], datetime]


def local_clock(timezone: str) -> Clock:
    zone = ZoneInfo(timezone)

    def now() -> datetime:
        return datetime.now(zone).replace(tzinfo=None, microsecond=0)

    return now
