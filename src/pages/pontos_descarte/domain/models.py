"""Modelos do recurso de pontos de descarte de eletroeletrônicos."""

from dataclasses import dataclass, field
from enum import StrEnum


class Category(StrEnum):
    """O que um ponto aceita, segundo a descrição da planilha."""

    BATTERIES = "pilhas_baterias"
    PHONES = "celulares_acessorios"
    CARTRIDGES = "cartuchos"
    SMALL = "pequeno_porte"
    MEDIUM = "medio_porte"
    LARGE = "grande_porte"
    UNSPECIFIED = "nao_especificado"


CATEGORY_LABELS: dict[Category, str] = {
    Category.BATTERIES: "Pilhas e baterias",
    Category.PHONES: "Celulares e acessórios",
    Category.CARTRIDGES: "Cartuchos de impressora",
    Category.SMALL: "Eletrônicos de pequeno porte",
    Category.MEDIUM: "Eletrônicos de médio porte",
    Category.LARGE: "Eletrônicos de grande porte",
    Category.UNSPECIFIED: "Eletroeletrônicos (categorias a confirmar)",
}


class MatchLevel(StrEnum):
    """Quanto um ponto atende ao que a pessoa quer descartar."""

    ACCEPTS = "aceita"  # a descrição do ponto cobre todos os itens pedidos
    POSSIBLE = "confirmar"  # o ponto recebe eletroeletrônicos, mas não detalha quais


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class DisposalPoint:
    """Um ponto de entrega voluntária (PEV) já limpo pelo `prepare`."""

    id: int
    name: str
    latitude: float
    longitude: float
    waste_description: str  # texto original de `tipo_descarte`
    categories: frozenset[Category]
    address: str | None = None  # rua e número
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    notes: str | None = None
    phone: str | None = None
    email: str | None = None
    whatsapp: str | None = None
    address_estimated: bool = False  # endereço completado pelo OpenStreetMap
    neighborhood_estimated: bool = False  # bairro completado pelo OpenStreetMap
    coordinates_status: str | None = None
    coordinates_check: str | None = None
    source: str | None = None

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(self.latitude, self.longitude)


@dataclass(frozen=True)
class GeocodedPlace:
    """Resultado de uma geocodificação (endereço ou bairro digitado pela pessoa)."""

    label: str
    latitude: float
    longitude: float

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(self.latitude, self.longitude)


@dataclass(frozen=True)
class LocationGroup:
    """Pontos que ficam no mesmo lugar (ex.: lojas do mesmo shopping) viram um marcador só."""

    id: str
    latitude: float
    longitude: float
    points: tuple[DisposalPoint, ...] = field(default_factory=tuple)

    @property
    def title(self) -> str:
        if len(self.points) == 1:
            return self.points[0].name
        return f"{len(self.points)} pontos neste local"


Ring = tuple[tuple[float, float], ...]  # (longitude, latitude), ordem do GeoJSON


@dataclass(frozen=True)
class CityBoundary:
    """Limite oficial do município, destacado no mapa."""

    name: str
    polygons: tuple[tuple[Ring, ...], ...]  # cada polígono: contorno externo e, se houver, buracos
