from dataclasses import dataclass

from pages.pontos_descarte.clients.http import build_session
from pages.pontos_descarte.clients.nominatim import NominatimClient
from pages.pontos_descarte.clients.osrm import OsrmClient
from pages.pontos_descarte.clients.photon import PhotonClient
from pages.pontos_descarte.config import Settings, load_settings
from pages.pontos_descarte.domain.addresses import AddressIndex
from pages.pontos_descarte.domain.models import CityBoundary, DisposalPoint
from pages.pontos_descarte.repositories.address_repository import AddressRepository
from pages.pontos_descarte.repositories.boundary_repository import BoundaryRepository
from pages.pontos_descarte.repositories.points_repository import PointsRepository
from pages.pontos_descarte.services.geocoding_service import GeocodingService
from pages.pontos_descarte.services.routing_service import RoutingService


@dataclass(frozen=True)
class Container:
    settings: Settings
    points: tuple[DisposalPoint, ...]
    city_boundary: CityBoundary | None
    geocoder: GeocodingService
    routing_service: RoutingService


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or load_settings()
    session = build_session(settings.http)
    repository = PointsRepository(settings.data.points)
    timeout = settings.http.timeout_seconds
    return Container(
        settings=settings,
        points=repository.all() if repository.exists() else (),
        city_boundary=BoundaryRepository(settings.data.city_boundary, settings.boundary.name).load(),
        geocoder=GeocodingService(
            AddressIndex(
                AddressRepository(settings.data.addresses).load(),
                primary_city=next(iter(settings.addresses.cities), None),
            ),
            fallbacks=(
                NominatimClient(session, settings.geocoding, timeout).search,
                PhotonClient(session, settings.geocoding, timeout).search,
            ),
            max_candidates=settings.addresses.max_candidates,
        ),
        routing_service=RoutingService(
            OsrmClient(session, settings.routing, timeout),
            candidates=settings.routing.candidates,
        ),
    )
