"""Client do Nominatim (geocodificação do OpenStreetMap).

Política de uso: no máximo 1 requisição por segundo e User-Agent identificando o app.
https://operations.osmfoundation.org/policies/nominatim/
"""

import threading
import time
from collections.abc import Callable
from typing import Any

import requests

from pages.pontos_descarte.clients.http import get_json
from pages.pontos_descarte.config import GeocodingConfig
from pages.pontos_descarte.domain.models import GeocodedPlace
from pages.pontos_descarte.domain.text import normalize

NEIGHBORHOOD_KEYS = ("suburb", "quarter", "neighbourhood")
CITY_KEYS = ("city", "town", "municipality", "village")
# Se a pessoa já citou uma cidade da região, não acrescentamos "João Pessoa" à busca.
METRO_CITIES = ("joao pessoa", "cabedelo", "bayeux", "santa rita", "conde", "lucena")


class NominatimClient:
    def __init__(
        self,
        session: requests.Session,
        config: GeocodingConfig,
        timeout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._session = session
        self._config = config
        self._timeout = timeout_seconds
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_request = float("-inf")

    def search(self, query: str) -> GeocodedPlace | None:
        """Localiza um endereço ou bairro digitado, dentro da região de João Pessoa."""
        text = query.strip()
        if not text:
            return None
        if not any(city in normalize(text) for city in METRO_CITIES):
            text = f"{text}, {self._config.city_hint}"
        west, north, east, south = self._config.viewbox
        payload = self._get(
            "/search",
            {
                "q": text,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": 1,
                "countrycodes": "br",
                "viewbox": f"{west},{north},{east},{south}",
                "bounded": 1,
                "accept-language": "pt-BR",
            },
        )
        if not isinstance(payload, list) or not payload:
            return None
        return parse_search_result(payload[0])

    def reverse(self, latitude: float, longitude: float) -> dict[str, str]:
        """Endereço (rua, bairro, cidade...) de uma coordenada. Dicionário vazio se não achar."""
        payload = self._get(
            "/reverse",
            {
                "lat": f"{latitude:.7f}",
                "lon": f"{longitude:.7f}",
                "format": "jsonv2",
                "zoom": 18,
                "addressdetails": 1,
                "accept-language": "pt-BR",
            },
        )
        if not isinstance(payload, dict):
            return {}
        return payload.get("address") or {}

    def _get(self, path: str, params: dict[str, Any]) -> object:
        with self._lock:
            wait = self._last_request + self._config.min_interval_seconds - self._clock()
            if wait > 0:
                self._sleep(wait)
            try:
                return get_json(self._session, f"{self._config.base_url}{path}", params, self._timeout)
            finally:
                self._last_request = self._clock()


def parse_search_result(entry: dict[str, Any]) -> GeocodedPlace:
    """Monta um rótulo curto ("Rua X, 10, Bairro, Cidade") em vez do display_name completo."""
    address = entry.get("address") or {}
    road = address.get("road")
    if road and address.get("house_number"):
        road = f"{road}, {address['house_number']}"
    parts: list[str] = []
    for part in (entry.get("name"), road, first_of(address, NEIGHBORHOOD_KEYS), first_of(address, CITY_KEYS)):
        if part and part not in parts:
            parts.append(part)
    label = ", ".join(parts) or (entry.get("display_name") or "").split(",")[0]
    return GeocodedPlace(label=label, latitude=float(entry["lat"]), longitude=float(entry["lon"]))


def first_of(address: dict[str, str], keys: tuple[str, ...]) -> str | None:
    return next((address[key] for key in keys if address.get(key)), None)
