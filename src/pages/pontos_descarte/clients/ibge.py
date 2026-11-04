"""Client da API de malhas territoriais do IBGE (limites oficiais dos municípios)."""

from typing import Any

import requests

from pages.pontos_descarte.clients.http import ServiceError, get_json
from pages.pontos_descarte.config import BoundaryConfig

GEOJSON_FORMAT = "application/vnd.geo+json"
POLYGON_TYPES = frozenset({"Polygon", "MultiPolygon"})


class IbgeClient:
    def __init__(self, session: requests.Session, config: BoundaryConfig, timeout_seconds: float) -> None:
        self._session = session
        self._config = config
        self._timeout = timeout_seconds

    def municipality_boundary(self) -> dict[str, Any]:
        """Limite do município configurado, em GeoJSON (FeatureCollection)."""
        payload = get_json(
            self._session,
            f"{self._config.base_url}/{self._config.ibge_code}",
            {"formato": GEOJSON_FORMAT, "qualidade": self._config.quality},
            self._timeout,
        )
        return validate_boundary(payload)


def validate_boundary(payload: object) -> dict[str, Any]:
    """Confere que a resposta é um FeatureCollection com pelo menos um polígono."""
    features = payload.get("features") if isinstance(payload, dict) else None
    if not features:
        raise ServiceError("O IBGE não devolveu o limite do município")
    if not all((feature.get("geometry") or {}).get("type") in POLYGON_TYPES for feature in features):
        raise ServiceError("O limite do município devolvido pelo IBGE não é um polígono")
    return payload
