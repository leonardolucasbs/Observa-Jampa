import logging
from collections.abc import Sequence
from dataclasses import dataclass

from itinerario.clients.base import DataSourceClient, FetchWindow
from itinerario.domain.models import AirQualityReading, Location
from itinerario.repositories.air_quality_repository import AirQualityRepository
from itinerario.repositories.location_repository import LocationRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    source: str
    locations: int
    upserted: int
    forecast: int


class AirQualityIngestion:
    def __init__(
        self,
        client: DataSourceClient[AirQualityReading],
        location_repository: LocationRepository,
        measurement_repository: AirQualityRepository,
        locations: Sequence[Location],
    ) -> None:
        self._client = client
        self._location_repository = location_repository
        self._measurement_repository = measurement_repository
        self._locations = tuple(locations)

    def run(self, window: FetchWindow) -> IngestionResult:
        location_ids = self._location_repository.sync(self._locations)
        readings = self._client.fetch(self._locations, window)
        upserted = self._measurement_repository.upsert(readings, location_ids)
        result = IngestionResult(
            source=self._client.source_name,
            locations=len(self._locations),
            upserted=upserted,
            forecast=sum(reading.is_forecast for reading in readings),
        )
        logger.info(
            "Coleta %s concluída: %d registros gravados (%d de previsão) em %d localizações",
            result.source,
            result.upserted,
            result.forecast,
            result.locations,
        )
        return result
