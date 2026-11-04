"""Busca de pontos pelos três filtros: tipo de descarte, bairro e endereço.

Cada filtro tenta primeiro entender o texto pelos próprios dados (vocabulário de itens, nomes de
bairros, endereços). Se o bairro ou endereço digitado não aparece em nenhum ponto ("Bancários",
"Rua das Trincheiras"), ele é localizado no mapa e entram os pontos num raio em volta.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.domain.geo import haversine_m
from pages.pontos_descarte.domain.models import DisposalPoint, GeocodedPlace, MatchLevel
from pages.pontos_descarte.domain.places import address_score, match_neighborhoods
from pages.pontos_descarte.domain.waste import WasteInterpretation, interpret_waste_query, match_level

logger = logging.getLogger(__name__)

Geocoder = Callable[[str], GeocodedPlace | None]


class PlaceStrategy(StrEnum):
    TEXT = "texto"  # o texto bateu com bairros/endereços dos próprios pontos
    NEARBY = "proximidade"  # o lugar foi localizado no mapa; entram os pontos do raio
    NOT_FOUND = "nao_encontrado"
    UNAVAILABLE = "indisponivel"  # o serviço de geocodificação falhou; o filtro é ignorado


@dataclass(frozen=True)
class PlaceInterpretation:
    """O que entendemos do campo de bairro ou de endereço."""

    query: str
    strategy: PlaceStrategy
    matched_names: tuple[str, ...] = ()  # bairros reconhecidos (bairro por texto)
    reference: GeocodedPlace | None = None  # lugar localizado no mapa (proximidade)
    radius_m: float | None = None


@dataclass(frozen=True)
class PointMatch:
    point: DisposalPoint
    level: MatchLevel
    distance_to_reference_m: float | None = None


@dataclass(frozen=True)
class SearchResult:
    matches: tuple[PointMatch, ...]
    waste: WasteInterpretation
    neighborhood: PlaceInterpretation | None
    address: PlaceInterpretation | None
    total_points: int

    @property
    def points(self) -> tuple[DisposalPoint, ...]:
        return tuple(match.point for match in self.matches)

    @property
    def references(self) -> tuple[PlaceInterpretation, ...]:
        """Lugares localizados no mapa, para desenhar o raio de busca."""
        return tuple(place for place in (self.neighborhood, self.address) if place and place.reference)


@dataclass(frozen=True)
class _PlaceFilter:
    interpretation: PlaceInterpretation
    accepts: Callable[[DisposalPoint], bool]

    def distance_m(self, point: DisposalPoint) -> float | None:
        reference = self.interpretation.reference
        return haversine_m(reference.coordinates, point.coordinates) if reference else None


class SearchService:
    def __init__(
        self,
        points: Sequence[DisposalPoint],
        geocode: Geocoder,
        neighborhood_radius_m: float,
        address_radius_m: float,
    ) -> None:
        self._points = tuple(points)
        self._geocode = geocode
        self._neighborhood_radius_m = neighborhood_radius_m
        self._address_radius_m = address_radius_m

    def search(self, waste: str = "", neighborhood: str = "", address: str = "") -> SearchResult:
        waste_interpretation = interpret_waste_query(waste)
        neighborhood_filter = self._neighborhood_filter(neighborhood)
        address_filter = self._address_filter(address)
        place_filters = [place_filter for place_filter in (neighborhood_filter, address_filter) if place_filter]

        matches: list[PointMatch] = []
        for point in self._points:
            level = match_level(point, waste_interpretation)
            if level is None or not all(place_filter.accepts(point) for place_filter in place_filters):
                continue
            distances = [d for d in (f.distance_m(point) for f in place_filters) if d is not None]
            matches.append(PointMatch(point, level, min(distances) if distances else None))

        matches.sort(key=self._ranking(address, address_filter))
        return SearchResult(
            matches=tuple(matches),
            waste=waste_interpretation,
            neighborhood=neighborhood_filter.interpretation if neighborhood_filter else None,
            address=address_filter.interpretation if address_filter else None,
            total_points=len(self._points),
        )

    def _neighborhood_filter(self, query: str) -> _PlaceFilter | None:
        if not query.strip():
            return None
        names = {point.neighborhood for point in self._points if point.neighborhood}
        matched = match_neighborhoods(query, names)
        if not matched:
            return self._nearby_filter(query, self._neighborhood_radius_m)
        interpretation = PlaceInterpretation(query, PlaceStrategy.TEXT, matched_names=tuple(sorted(matched)))
        return _PlaceFilter(interpretation, lambda point: point.neighborhood in matched)

    def _address_filter(self, query: str) -> _PlaceFilter | None:
        if not query.strip():
            return None
        if not any(address_score(query, point) > 0 for point in self._points):
            return self._nearby_filter(query, self._address_radius_m)
        return _PlaceFilter(
            PlaceInterpretation(query, PlaceStrategy.TEXT), lambda point: address_score(query, point) > 0
        )

    def _nearby_filter(self, query: str, radius_m: float) -> _PlaceFilter:
        try:
            place = self._geocode(query)
        except ServiceError as exc:
            logger.warning("Geocodificação de %r falhou: %s", query, exc)
            return _PlaceFilter(PlaceInterpretation(query, PlaceStrategy.UNAVAILABLE), lambda point: True)
        if place is None:
            return _PlaceFilter(PlaceInterpretation(query, PlaceStrategy.NOT_FOUND), lambda point: False)
        interpretation = PlaceInterpretation(query, PlaceStrategy.NEARBY, reference=place, radius_m=radius_m)
        return _PlaceFilter(
            interpretation, lambda point: haversine_m(place.coordinates, point.coordinates) <= radius_m
        )

    @staticmethod
    def _ranking(address_query: str, address_filter: _PlaceFilter | None) -> Callable[[PointMatch], tuple]:
        """Primeiro quem aceita com certeza, depois o endereço mais parecido, depois o mais perto."""
        rank_by_address = address_filter is not None and address_filter.interpretation.strategy == PlaceStrategy.TEXT

        def key(match: PointMatch) -> tuple:
            certainty = 0 if match.level == MatchLevel.ACCEPTS else 1
            relevance = -address_score(address_query, match.point) if rank_by_address else 0.0
            distance = match.distance_to_reference_m or 0.0
            return certainty, relevance, distance, match.point.name

        return key
