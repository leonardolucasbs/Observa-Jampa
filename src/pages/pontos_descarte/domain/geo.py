"""Cálculos geográficos simples: distância, agrupamento de pontos e enquadramento do mapa."""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from pages.pontos_descarte.domain.models import Coordinates, DisposalPoint, LocationGroup

EARTH_RADIUS_M = 6_371_000.0
WORLD_SIZE_PX = 512  # largura do mundo no zoom 0 no deck.gl/Mapbox (blocos de 512 px)


def haversine_m(origin: Coordinates, destination: Coordinates) -> float:
    """Distância em linha reta, em metros."""
    lat1, lat2 = math.radians(origin.latitude), math.radians(destination.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(destination.longitude - origin.longitude)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def circle_bounds(center: Coordinates, radius_m: float) -> list[Coordinates]:
    """Os quatro extremos (norte, sul, leste, oeste) de um círculo, para enquadrá-lo inteiro no mapa."""
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    dlon = dlat / math.cos(math.radians(center.latitude))
    return [
        Coordinates(center.latitude + dlat, center.longitude),
        Coordinates(center.latitude - dlat, center.longitude),
        Coordinates(center.latitude, center.longitude + dlon),
        Coordinates(center.latitude, center.longitude - dlon),
    ]


def closest_points(origin: Coordinates, points: Iterable[DisposalPoint], limit: int) -> list[DisposalPoint]:
    """Os `limit` pontos mais próximos em linha reta (pré-seleção antes de consultar rotas)."""
    return sorted(points, key=lambda point: haversine_m(origin, point.coordinates))[:limit]


def group_by_location(points: Iterable[DisposalPoint], radius_m: float = 60.0) -> list[LocationGroup]:
    """Junta pontos do mesmo lugar num marcador só, para que nenhum fique escondido sob outro.

    Ex.: os coletores de três programas diferentes dentro do mesmo supermercado.
    """
    groups: list[list[DisposalPoint]] = []
    for point in sorted(points, key=lambda point: point.id):
        for members in groups:
            if haversine_m(members[0].coordinates, point.coordinates) <= radius_m:
                members.append(point)
                break
        else:
            groups.append([point])
    return [
        LocationGroup(
            id="-".join(str(point.id) for point in members),
            latitude=sum(point.latitude for point in members) / len(members),
            longitude=sum(point.longitude for point in members) / len(members),
            points=tuple(members),
        )
        for members in groups
    ]


@dataclass(frozen=True)
class MapView:
    latitude: float
    longitude: float
    zoom: float


def fit_view(
    coordinates: Sequence[Coordinates],
    *,
    default: MapView,
    width_px: int = 800,
    height_px: int = 560,
    max_zoom: float = 15.5,
    padding: float = 1.25,
) -> MapView:
    """Centro e zoom que enquadram todas as coordenadas (projeção Web Mercator)."""
    if not coordinates:
        return default
    lats = [coordinate.latitude for coordinate in coordinates]
    lons = [coordinate.longitude for coordinate in coordinates]
    center = MapView(latitude=(min(lats) + max(lats)) / 2, longitude=(min(lons) + max(lons)) / 2, zoom=max_zoom)
    lon_span = (max(lons) - min(lons)) * padding
    lat_span = (_mercator_y(max(lats)) - _mercator_y(min(lats))) * padding
    zooms = [max_zoom]
    if lon_span > 0:
        zooms.append(math.log2(width_px * 360 / (WORLD_SIZE_PX * lon_span)))
    if lat_span > 0:
        zooms.append(math.log2(height_px * 2 * math.pi / (WORLD_SIZE_PX * lat_span)))
    return MapView(latitude=center.latitude, longitude=center.longitude, zoom=round(max(min(zooms), 3.0), 2))


def _mercator_y(latitude: float) -> float:
    radians = math.radians(latitude)
    return math.log(math.tan(math.pi / 4 + radians / 2))
