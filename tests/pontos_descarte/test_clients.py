import json
from pathlib import Path

import pytest

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.clients.nominatim import NominatimClient, parse_search_result
from pages.pontos_descarte.clients.osrm import parse_route, parse_table
from pages.pontos_descarte.clients.photon import PhotonClient, parse_feature
from pages.pontos_descarte.config import load_settings

FIXTURES = Path(__file__).parent / "fixtures"

def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

def test_parse_osrm_table_skips_the_origin_column():
    estimates = parse_table(load("osrm_table.json"), expected=2)
    assert [round(estimate.distance_m) for estimate in estimates] == [9932, 7781]
    assert [round(estimate.duration_s) for estimate in estimates] == [719, 551]


def test_parse_osrm_table_rejects_incomplete_answers():
    with pytest.raises(ServiceError):
        parse_table(load("osrm_table.json"), expected=3)


def test_parse_osrm_route_returns_geojson_path():
    route = parse_route(load("osrm_route.json"))
    assert route.distance_m == pytest.approx(9932.1)
    assert route.path[0] == (-34.844153, -7.09879)
    assert len(route.path) == 4


def test_parse_nominatim_search_builds_short_label():
    place = parse_search_result(load("nominatim_search.json")[0])
    assert place.label == "Rua das Trincheiras, Centro, João Pessoa"
    assert place.latitude == pytest.approx(-7.1249869)


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[dict] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params})
        return FakeResponse(self.payload)


def test_nominatim_adds_city_hint_and_respects_rate_limit():
    settings = load_settings()
    session = FakeSession(load("nominatim_search.json"))
    now = [100.0]
    sleeps: list[float] = []
    client = NominatimClient(
        session, settings.geocoding, timeout_seconds=5, clock=lambda: now[0], sleep=sleeps.append
    )

    client.search("Rua das Trincheiras")
    client.search("Intermares, Cabedelo")

    assert session.calls[0]["params"]["q"] == "Rua das Trincheiras, João Pessoa, PB"
    assert session.calls[1]["params"]["q"] == "Intermares, Cabedelo"
    assert session.calls[0]["params"]["bounded"] == 1
    assert sleeps == [pytest.approx(settings.geocoding.min_interval_seconds)]


def test_nominatim_returns_none_for_empty_results():
    client = NominatimClient(FakeSession([]), load_settings().geocoding, timeout_seconds=5, sleep=lambda s: None)
    assert client.search("lugar que não existe") is None
    assert client.search("   ") is None


def test_parse_photon_feature_builds_short_label():
    place = parse_feature(load("photon_search.json")["features"][0])
    assert place.label == "Estacionamento Manaíra Shopping, Rua Monsenhor Antônio Afonso, Parque Verde, Cabedelo"
    assert (place.latitude, place.longitude) == (-7.098928, -34.8467569)


def test_photon_restricts_to_the_search_area_and_handles_empty_results():
    settings = load_settings()
    session = FakeSession(load("photon_search.json"))
    PhotonClient(session, settings.geocoding, timeout_seconds=5).search("Manaíra Shopping")

    params = session.calls[0]["params"]
    west, north, east, south = settings.geocoding.viewbox
    assert session.calls[0]["url"] == f"{settings.geocoding.photon_url}/api/"
    assert params["bbox"] == f"{west},{south},{east},{north}"  # o Photon usa oeste, sul, leste, norte
    assert PhotonClient(FakeSession({"features": []}), settings.geocoding, 5).search("lugar nenhum") is None
    assert PhotonClient(FakeSession({}), settings.geocoding, 5).search("  ") is None
