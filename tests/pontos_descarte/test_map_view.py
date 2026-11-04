import json

import pytest

from pages.pontos_descarte.config import load_settings
from pages.pontos_descarte.domain.geo import circle_bounds, haversine_m
from pages.pontos_descarte.domain.models import CityBoundary, Coordinates, GeocodedPlace, MatchLevel
from pages.pontos_descarte.services.routing_service import RouteResult
from pages.pontos_descarte.services.search_service import PlaceInterpretation, PlaceStrategy, PointMatch
from pages.pontos_descarte.ui.map_view import build_deck


def deck_json(points, **overrides):
    matches = [PointMatch(point, MatchLevel.ACCEPTS) for point in points]
    options = {"origin": None, "route": None, "references": ()} | overrides
    deck, groups = build_deck(matches, config=load_settings().map, **options)
    return json.loads(deck.to_json()), groups


def test_units_reach_the_browser_as_literal_strings(points):
    """Regressão: "pixels" sem aspas virava a expressão "@@=pixels", o deck.gl ignorava a unidade
    e os marcadores eram desenhados com raios gigantes, cobrindo o mapa inteiro."""
    origin = GeocodedPlace("Você", -7.13, -34.88)
    route = RouteResult(points[0], "Carro", 1000.0, 120.0, ((-34.88, -7.13), (points[0].longitude, points[0].latitude)))
    reference = PlaceInterpretation(
        "Bancários", PlaceStrategy.NEARBY, reference=GeocodedPlace("Bancários", -7.148, -34.838), radius_m=1500
    )
    payload, _ = deck_json(points, origin=origin, route=route, references=(reference,))

    units = {
        (layer["id"], key): value
        for layer in payload["layers"]
        for key, value in layer.items()
        if key.endswith("Units")
    }
    assert units
    assert all(value in {"pixels", "meters"} for value in units.values()), units
    assert units[("pontos", "radiusUnits")] == "pixels"
    assert units[("raio_busca", "radiusUnits")] == "meters"
    assert units[("rota", "widthUnits")] == "pixels"


def test_markers_group_points_and_destination_is_clickable(points):
    route = RouteResult(points[0], "Carro", 1000.0, 120.0, ((-34.88, -7.13), (points[0].longitude, points[0].latitude)))
    payload, groups = deck_json(points, route=route)
    layer_ids = [layer["id"] for layer in payload["layers"]]
    assert {"pontos", "contagem", "rota", "destino"} <= set(layer_ids)
    assert f"destino-{points[0].id}" in groups


def test_view_fits_the_whole_search_circle(points):
    reference = PlaceInterpretation(
        "Bancários", PlaceStrategy.NEARBY, reference=GeocodedPlace("Bancários", -7.148, -34.838), radius_m=1500
    )
    with_circle, _ = deck_json(points[3:4], references=(reference,))
    without_circle, _ = deck_json(points[3:4])
    assert with_circle["initialViewState"]["zoom"] < without_circle["initialViewState"]["zoom"]


def test_circle_bounds_are_at_the_radius():
    center = Coordinates(-7.148, -34.838)
    for edge in circle_bounds(center, 1500):
        assert haversine_m(center, edge) == pytest.approx(1500, rel=0.01)


def test_all_points_fit_in_the_default_map(points):
    """Com o tamanho de mundo do deck.gl (512 px no zoom 0), toda a região cabe na largura do mapa."""
    payload, _ = deck_json(points)
    zoom = payload["initialViewState"]["zoom"]
    lon_span = max(p.longitude for p in points) - min(p.longitude for p in points)
    visible_degrees = 680 * 360 / (512 * 2**zoom)
    assert visible_degrees >= lon_span


CITY = CityBoundary(
    "João Pessoa",
    polygons=((((-34.97, -7.06), (-34.79, -7.06), (-34.79, -7.25), (-34.97, -7.25), (-34.97, -7.06)),),),
)


def test_city_is_painted_blue_at_twenty_percent_under_everything(points):
    payload, _ = deck_json(points, city=CITY)
    city_layer = payload["layers"][0]
    assert city_layer["id"] == "municipio"
    assert city_layer["@@type"] == "PolygonLayer"
    assert city_layer["getFillColor"] == [37, 99, 235, 51]  # 20% de 255
    assert city_layer.get("pickable") is False  # não rouba o clique dos marcadores
    assert city_layer["data"][0]["polygon"][0][0] == [-34.97, -7.06]


def test_map_without_city_file_still_renders(points):
    payload, _ = deck_json(points, city=None)
    assert "municipio" not in [layer["id"] for layer in payload["layers"]]


def test_basemap_is_the_gps_style_street_map(points):
    payload, _ = deck_json(points)
    assert "voyager" in payload["mapStyle"]


def test_markers_have_a_size_cap(points):
    """Mesmo que a unidade fosse mal interpretada, nenhum marcador passaria de alguns pixels."""
    origin = GeocodedPlace("Você", -7.13, -34.88)
    route = RouteResult(points[0], "Carro", 1000.0, 120.0, ((-34.88, -7.13), (points[0].longitude, points[0].latitude)))
    payload, _ = deck_json(points, origin=origin, route=route)
    scatter = [layer for layer in payload["layers"] if layer["@@type"] == "ScatterplotLayer"]
    assert {layer["id"] for layer in scatter} == {"pontos", "destino", "origem", "origem_halo"}
    assert all(layer["radiusMaxPixels"] <= 24 for layer in scatter)


def test_route_has_a_white_casing_below_the_line(points):
    route = RouteResult(points[0], "Carro", 1000.0, 120.0, ((-34.88, -7.13), (points[0].longitude, points[0].latitude)))
    payload, _ = deck_json(points, route=route)
    ids = [layer["id"] for layer in payload["layers"]]
    assert ids.index("rota_contorno") < ids.index("rota")
