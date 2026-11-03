from dataclasses import dataclass

from sqlalchemy import Engine

from pages.poluentes.clients.http import build_session
from pages.poluentes.clients.open_meteo_air_quality import OpenMeteoAirQualityClient
from pages.poluentes.clock import local_clock
from pages.poluentes.config import Settings, load_settings
from pages.poluentes.etl.pipeline import AirQualityIngestion
from pages.poluentes.repositories.air_quality_repository import AirQualityRepository
from pages.poluentes.repositories.database import create_db_engine
from pages.poluentes.repositories.location_repository import LocationRepository
from pages.poluentes.services.air_quality_service import AirQualityService


@dataclass(frozen=True)
class Container:
    settings: Settings
    engine: Engine
    air_quality_ingestion: AirQualityIngestion
    air_quality_service: AirQualityService


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or load_settings()
    clock = local_clock(settings.timezone)
    engine = create_db_engine(settings.database_path)
    measurement_repository = AirQualityRepository(engine)
    client = OpenMeteoAirQualityClient(
        session=build_session(settings.http),
        config=settings.air_quality,
        timezone=settings.timezone,
        timeout_seconds=settings.http.timeout_seconds,
        clock=clock,
    )
    return Container(
        settings=settings,
        engine=engine,
        air_quality_ingestion=AirQualityIngestion(
            client=client,
            location_repository=LocationRepository(engine),
            measurement_repository=measurement_repository,
            locations=settings.locations,
        ),
        air_quality_service=AirQualityService(measurement_repository, clock),
    )
