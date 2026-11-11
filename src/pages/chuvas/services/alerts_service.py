from pages.chuvas.domain.alerts import alerts_for_city
from pages.chuvas.domain.models import AlertFeed, CityAlerts
from pages.chuvas.services.cache import CachedSource, Clock, Snapshot


class AlertsService:
    def __init__(self, source: CachedSource[AlertFeed], ibge_code: str, clock: Clock) -> None:
        self._source = source
        self._ibge_code = ibge_code
        self._clock = clock

    def for_city(self) -> Snapshot[CityAlerts]:
        """A situação de cada aviso é calculada agora, não na hora da consulta: um aviso do cache
        que já terminou sai da lista. Levanta SourceUnavailable se a fonte falhou e não há lista recente."""
        snapshot = self._source.get()
        return snapshot.with_value(alerts_for_city(snapshot.value, self._ibge_code, self._clock()))
