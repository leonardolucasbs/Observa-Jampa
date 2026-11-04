import json
import logging
from pathlib import Path
from typing import Any

from pages.pontos_descarte.domain.models import CityBoundary, Ring

logger = logging.getLogger(__name__)


class BoundaryRepository:
    """Lê o limite do município gravado pelo `prepare` (GeoJSON do IBGE)."""

    def __init__(self, path: Path, name: str) -> None:
        self._path = path
        self._name = name

    def load(self) -> CityBoundary | None:
        """None se o arquivo faltar ou estiver inválido: o mapa abre sem o destaque da cidade."""
        if not self._path.exists():
            logger.warning("Limite do município não encontrado em %s", self._path)
            return None
        try:
            return boundary_from_geojson(json.loads(self._path.read_text(encoding="utf-8")), self._name)
        except (ValueError, KeyError, TypeError):
            logger.warning("Limite do município inválido em %s", self._path, exc_info=True)
            return None


def boundary_from_geojson(data: dict[str, Any], name: str) -> CityBoundary:
    polygons = []
    for feature in data["features"]:
        geometry = feature["geometry"]
        if geometry["type"] == "Polygon":
            polygons.append(_polygon(geometry["coordinates"]))
        elif geometry["type"] == "MultiPolygon":
            polygons.extend(_polygon(polygon) for polygon in geometry["coordinates"])
        else:
            raise ValueError(f"Geometria inesperada no limite do município: {geometry['type']}")
    if not polygons:
        raise ValueError("Limite do município sem polígonos")
    return CityBoundary(name=name, polygons=tuple(polygons))


def _polygon(rings: list[list[list[float]]]) -> tuple[Ring, ...]:
    return tuple(tuple((float(lon), float(lat)) for lon, lat, *_ in ring) for ring in rings)
