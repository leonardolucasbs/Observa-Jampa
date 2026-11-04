from dataclasses import dataclass

from pages.pontos_descarte.clients.http import build_session
from pages.pontos_descarte.clients.nominatim import NominatimClient
from pages.pontos_descarte.clients.osrm import OsrmClient
from pages.pontos_descarte.config import Settings, load_settings
from pages.pontos_descarte.domain.models import CityBoundary, DisposalPoint
from pages.pontos_descarte.repositories.boundary_repository import BoundaryRepository
from pages.pontos_descarte.repositories.points_repository import PointsRepository
from pages.pontos_descarte.services.routing_service import RoutingService


@dataclass(frozen=True)
class Container:
    settings: Settings
    points: tuple[DisposalPoint, ...]
    city_boundary: CityBoundary | None
    geocoder: NominatimClient
    routing_service: RoutingService


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or load_settings()
    session = build_session(settings.http)
    repository = PointsRepository(settings.data.points)
    return Container(
        settings=settings,
        points=repository.all() if repository.exists() else (),
        city_boundary=BoundaryRepository(settings.data.city_boundary, settings.boundary.name).load(),
        geocoder=NominatimClient(session, settings.geocoding, settings.http.timeout_seconds),
        routing_service=RoutingService(
            OsrmClient(session, settings.routing, settings.http.timeout_seconds),
            candidates=settings.routing.candidates,
        ),
    )
