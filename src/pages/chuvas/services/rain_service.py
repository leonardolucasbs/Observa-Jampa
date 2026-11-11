from zoneinfo import ZoneInfo

from pages.chuvas.domain.models import RainForecast, RainOutlook
from pages.chuvas.domain.rain import rain_outlook
from pages.chuvas.services.cache import CachedSource, Clock, Snapshot


class RainService:
    def __init__(self, source: CachedSource[RainForecast], clock: Clock, timezone: str) -> None:
        self._source = source
        self._clock = clock
        self._zone = ZoneInfo(timezone)

    def outlook(self) -> Snapshot[RainOutlook]:
        """Hoje, amanhã e 7 dias pela data atual de João Pessoa, mesmo quando a previsão veio do cache.
        Levanta SourceUnavailable se a fonte falhou e não há previsão recente."""
        snapshot = self._source.get()
        today = self._clock().astimezone(self._zone).date()
        return snapshot.with_value(rain_outlook(snapshot.value, today))
