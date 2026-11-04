"""Rota da pessoa até o ponto de descarte mais próximo (pelas ruas, não em linha reta)."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.clients.osrm import RouteGeometry, TravelEstimate
from pages.pontos_descarte.domain.geo import closest_points, haversine_m
from pages.pontos_descarte.domain.models import Coordinates, DisposalPoint

logger = logging.getLogger(__name__)


class Router(Protocol):
    def table(
        self, profile: str, origin: Coordinates, destinations: Sequence[Coordinates]
    ) -> list[TravelEstimate | None]: ...

    def route(self, profile: str, origin: Coordinates, destination: Coordinates) -> RouteGeometry: ...


@dataclass(frozen=True)
class RouteResult:
    point: DisposalPoint
    profile: str
    distance_m: float
    duration_s: float | None
    path: tuple[tuple[float, float], ...]  # (longitude, latitude)
    straight_line: bool = False  # o serviço de rotas falhou: distância e traço em linha reta
    error: str | None = None


class RoutingService:
    def __init__(self, router: Router, candidates: int) -> None:
        self._router = router
        self._candidates = candidates

    def nearest(self, origin: Coordinates, points: Sequence[DisposalPoint], profile: str) -> RouteResult | None:
        """Rota até o ponto com o menor percurso pelas ruas.

        Os `candidates` pontos mais próximos em linha reta são comparados numa única consulta
        à matriz de distâncias do OSRM; só o vencedor tem a rota completa calculada.
        """
        if not points:
            return None
        shortlist = closest_points(origin, points, self._candidates)
        target = shortlist[0]
        try:
            estimates = self._router.table(profile, origin, [point.coordinates for point in shortlist])
            reachable = [(estimate, point) for estimate, point in zip(estimates, shortlist, strict=True) if estimate]
            if reachable:
                target = min(reachable, key=lambda item: (item[0].distance_m, item[0].duration_s))[1]
        except ServiceError as exc:
            logger.warning("Matriz de distâncias indisponível, usando a linha reta: %s", exc)
        return self.route_to(origin, target, profile)

    def route_to(self, origin: Coordinates, point: DisposalPoint, profile: str) -> RouteResult:
        try:
            geometry = self._router.route(profile, origin, point.coordinates)
        except ServiceError as exc:
            logger.warning("Rota até o ponto %s indisponível: %s", point.id, exc)
            return RouteResult(
                point=point,
                profile=profile,
                distance_m=haversine_m(origin, point.coordinates),
                duration_s=None,
                path=((origin.longitude, origin.latitude), (point.longitude, point.latitude)),
                straight_line=True,
                error=str(exc),
            )
        return RouteResult(
            point=point,
            profile=profile,
            distance_m=geometry.distance_m,
            duration_s=geometry.duration_s,
            path=geometry.path,
        )
