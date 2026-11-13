"""Client do Photon (geocodificação do OpenStreetMap feita pela Komoot).

É a última tentativa da busca de endereços: tolera erros de digitação que o Nominatim não aceita.
O servidor público é para uso moderado; a página só o consulta quando o índice do IBGE e o
Nominatim não acharam nada, e guarda as respostas em cache.
https://photon.komoot.io
"""

from typing import Any

import requests

from pages.pontos_descarte.clients.http import get_json
from pages.pontos_descarte.config import GeocodingConfig
from pages.pontos_descarte.domain.models import GeocodedPlace


class PhotonClient:
    def __init__(self, session: requests.Session, config: GeocodingConfig, timeout_seconds: float) -> None:
        self._session = session
        self._config = config
        self._timeout = timeout_seconds

    def search(self, query: str) -> GeocodedPlace | None:
        """Localiza um endereço ou lugar digitado, dentro da área de busca de João Pessoa."""
        text = query.strip()
        if not text:
            return None
        west, north, east, south = self._config.viewbox
        payload = get_json(
            self._session,
            f"{self._config.photon_url}/api/",
            {
                "q": text,
                "limit": 1,
                "lat": (north + south) / 2,  # prefere resultados perto do centro da área
                "lon": (west + east) / 2,
                "bbox": f"{west},{south},{east},{north}",
            },
            self._timeout,
        )
        features = payload.get("features") if isinstance(payload, dict) else None
        if not features:
            return None
        return parse_feature(features[0])


def parse_feature(feature: dict[str, Any]) -> GeocodedPlace:
    """Monta um rótulo curto ("Lugar, Rua X, 10, Bairro, Cidade"), como o do Nominatim."""
    properties = feature.get("properties") or {}
    longitude, latitude = feature["geometry"]["coordinates"][:2]
    street = properties.get("street")
    if street and properties.get("housenumber"):
        street = f"{street}, {properties['housenumber']}"
    parts: list[str] = []
    district = properties.get("district") or properties.get("locality")
    for part in (properties.get("name"), street, district, properties.get("city")):
        if part and part not in parts:
            parts.append(part)
    label = ", ".join(parts) or "Local encontrado no mapa"
    return GeocodedPlace(label=label, latitude=float(latitude), longitude=float(longitude))
