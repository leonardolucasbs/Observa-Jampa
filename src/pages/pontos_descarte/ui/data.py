"""Acesso da tela aos dados e serviços, com cache do Streamlit.

As consultas externas (geocodificação e rotas) ficam em cache para respeitar os limites
dos serviços públicos do OpenStreetMap e deixar a tela rápida ao mudar outros filtros.
"""

import streamlit as st

from pages.pontos_descarte.bootstrap import Container, build_container
from pages.pontos_descarte.domain.models import Coordinates, DisposalPoint, GeocodedPlace
from pages.pontos_descarte.services.routing_service import RouteResult
from pages.pontos_descarte.services.search_service import SearchResult, SearchService

ONE_DAY = 24 * 3600


@st.cache_resource
def get_container() -> Container:
    return build_container()


@st.cache_data(ttl=ONE_DAY, show_spinner=False)
def geocode(query: str) -> GeocodedPlace | None:
    """Erros de rede sobem como ServiceError e não ficam em cache."""
    return get_container().geocoder.search(query)


def search(waste: str, neighborhood: str, address: str) -> SearchResult:
    container = get_container()
    settings = container.settings.search
    service = SearchService(
        container.points,
        geocode=geocode,
        neighborhood_radius_m=settings.neighborhood_radius_km * 1000,
        address_radius_m=settings.address_radius_km * 1000,
    )
    return service.search(waste=waste, neighborhood=neighborhood, address=address)


def points_by_id() -> dict[int, DisposalPoint]:
    return {point.id: point for point in get_container().points}


@st.cache_data(ttl=3600, show_spinner=False)
def nearest_route(latitude: float, longitude: float, point_ids: tuple[int, ...], profile: str) -> RouteResult | None:
    points = points_by_id()
    candidates = [points[point_id] for point_id in point_ids if point_id in points]
    return get_container().routing_service.nearest(Coordinates(latitude, longitude), candidates, profile)


@st.cache_data(ttl=3600, show_spinner=False)
def route_to(latitude: float, longitude: float, point_id: int, profile: str) -> RouteResult | None:
    point = points_by_id().get(point_id)
    if point is None:
        return None
    return get_container().routing_service.route_to(Coordinates(latitude, longitude), point, profile)
