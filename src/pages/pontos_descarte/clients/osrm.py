"""Client do OSRM (rotas sobre o mapa do OpenStreetMap).

Usa o servidor público do FOSSGIS (routing.openstreetmap.de), que tem perfis de carro, a pé e bicicleta.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import requests

from pages.pontos_descarte.clients.http import ServiceError, get_json
from pages.pontos_descarte.config import RoutingConfig
from pages.pontos_descarte.domain.models import Coordinates


@dataclass(frozen=True)
class TravelEstimate:
    distance_m: float
    duration_s: float


@dataclass(frozen=True)
class RouteGeometry:
    distance_m: float
    duration_s: float
    path: tuple[tuple[float, float], ...]  # (longitude, latitude), ordem do GeoJSON


class OsrmClient:
    def __init__(self, session: requests.Session, config: RoutingConfig, timeout_seconds: float) -> None:
        self._session = session
        self._config = config
        self._timeout = timeout_seconds

    def table(
        self, profile: str, origin: Coordinates, destinations: Sequence[Coordinates]
    ) -> list[TravelEstimate | None]:
        """Distância e tempo de viagem da origem até cada destino (None = sem caminho)."""
        coordinates = ";".join(_lon_lat(point) for point in (origin, *destinations))
        payload = self._get(
            f"/{self._service(profile)}/table/v1/driving/{coordinates}",
            {"sources": 0, "annotations": "duration,distance"},
        )
        return parse_table(payload, len(destinations))

    def route(self, profile: str, origin: Coordinates, destination: Coordinates) -> RouteGeometry:
        payload = self._get(
            f"/{self._service(profile)}/route/v1/driving/{_lon_lat(origin)};{_lon_lat(destination)}",
            {"overview": "full", "geometries": "geojson"},
        )
        return parse_route(payload)

    def _service(self, profile: str) -> str:
        try:
            return self._config.profiles[profile]
        except KeyError as exc:
            raise ServiceError(f"Meio de transporte desconhecido: {profile}") from exc

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = get_json(self._session, f"{self._config.base_url}{path}", params, self._timeout)
        if not isinstance(payload, dict) or payload.get("code") != "Ok":
            code = payload.get("code") if isinstance(payload, dict) else "resposta inválida"
            raise ServiceError(f"O serviço de rotas não encontrou um caminho ({code})")
        return payload


def parse_table(payload: dict[str, Any], expected: int) -> list[TravelEstimate | None]:
    distances = (payload.get("distances") or [[]])[0][1:]
    durations = (payload.get("durations") or [[]])[0][1:]
    if len(distances) != expected or len(durations) != expected:
        raise ServiceError("Resposta incompleta do serviço de rotas")
    return [
        TravelEstimate(distance, duration) if distance is not None and duration is not None else None
        for distance, duration in zip(distances, durations, strict=True)
    ]


def parse_route(payload: dict[str, Any]) -> RouteGeometry:
    routes = payload.get("routes") or []
    if not routes:
        raise ServiceError("O serviço de rotas não devolveu nenhuma rota")
    route = routes[0]
    path = tuple((float(lon), float(lat)) for lon, lat in route["geometry"]["coordinates"])
    return RouteGeometry(distance_m=float(route["distance"]), duration_s=float(route["duration"]), path=path)


def _lon_lat(point: Coordinates) -> str:
    return f"{point.longitude:.6f},{point.latitude:.6f}"
