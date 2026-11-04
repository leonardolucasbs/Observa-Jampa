from collections.abc import Sequence

import pytest

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.clients.osrm import RouteGeometry, TravelEstimate
from pages.pontos_descarte.domain.geo import haversine_m
from pages.pontos_descarte.domain.models import Coordinates, DisposalPoint, GeocodedPlace
from pages.pontos_descarte.domain.waste import categories_from_description

PHONES_AND_BATTERIES = "Entrega de celulares, carregadores, fones de ouvido, pilhas, baterias e produtos de telefonia"
SMALL_AND_MEDIUM = "Resíduos eletroeletrônicos de pequeno e médio porte"
ALL_SIZES = "Resíduos eletroeletrônicos de pequeno e médio E grande porte."
BATTERIES = "Pilhas e baterias (confirmar no local)"
UNSPECIFIED = "Resíduos eletroeletrônicos (confirmar categorias aceitas diretamente com o ponto)."


def make_point(
    point_id: int,
    *,
    name: str = "Ponto",
    latitude: float = -7.12,
    longitude: float = -34.86,
    description: str = UNSPECIFIED,
    address: str | None = None,
    neighborhood: str | None = None,
    city: str | None = "João Pessoa",
    notes: str | None = None,
) -> DisposalPoint:
    return DisposalPoint(
        id=point_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
        waste_description=description,
        categories=categories_from_description(description),
        address=address,
        neighborhood=neighborhood,
        city=city,
        state="PB",
        notes=notes,
    )


@pytest.fixture
def points() -> list[DisposalPoint]:
    return [
        make_point(1, name="PEV ABREE - LOJA VIVO MANAIRA SHOPPING", latitude=-7.0989, longitude=-34.8447,
                   description=PHONES_AND_BATTERIES, address="Rua Manoel Arruda Cavalcanti, 805", neighborhood="Manaíra"),
        make_point(2, name="PEV ABREE - MAGALU (EPITÁCIO)", latitude=-7.1214, longitude=-34.8465,
                   description=SMALL_AND_MEDIUM, address="Avenida Presidente Epitacio Pessoa, 2737",
                   neighborhood="Tambauzinho"),
        make_point(3, name="CENTRAL DE LOGÍSTICA REVERSA", latitude=-7.1652, longitude=-34.8321,
                   description=ALL_SIZES, address="Avenida Hilton Souto Maior, 4619-A", neighborhood="Mangabeira"),
        make_point(4, name="PEV Reciclus - Carrefour", latitude=-7.1468, longitude=-34.8494,
                   description=BATTERIES, neighborhood="Jardim São Paulo"),
        make_point(5, name="Drogasil - Tambaú", latitude=-7.1192, longitude=-34.8239,
                   description=UNSPECIFIED, address="Rua Nossa Senhora dos Navegantes, 950", neighborhood="Tambaú"),
        make_point(6, name="Drogasil - Jardim Oceania", latitude=-7.0839, longitude=-34.8388,
                   description=UNSPECIFIED, neighborhood="Jardim Oceania"),
    ]


class FakeGeocoder:
    def __init__(self, places: dict[str, GeocodedPlace] | None = None, fail: bool = False) -> None:
        self.places = places or {}
        self.fail = fail
        self.queries: list[str] = []

    def __call__(self, query: str) -> GeocodedPlace | None:
        self.queries.append(query)
        if self.fail:
            raise ServiceError("fora do ar")
        return self.places.get(query)


class FakeRouter:
    """Distância de rota = distância em linha reta × fator por destino (para simular ruas tortuosas)."""

    def __init__(self, detour: dict[tuple[float, float], float] | None = None, fail: bool = False) -> None:
        self.detour = detour or {}
        self.fail = fail
        self.table_calls = 0

    def table(
        self, profile: str, origin: Coordinates, destinations: Sequence[Coordinates]
    ) -> list[TravelEstimate | None]:
        self.table_calls += 1
        if self.fail:
            raise ServiceError("fora do ar")
        estimates = []
        for destination in destinations:
            factor = self.detour.get((destination.latitude, destination.longitude), 1.3)
            distance = haversine_m(origin, destination) * factor
            estimates.append(TravelEstimate(distance_m=distance, duration_s=distance / 10))
        return estimates

    def route(self, profile: str, origin: Coordinates, destination: Coordinates) -> RouteGeometry:
        if self.fail:
            raise ServiceError("fora do ar")
        path = ((origin.longitude, origin.latitude), (destination.longitude, destination.latitude))
        return RouteGeometry(distance_m=1234.0, duration_s=300.0, path=path)
