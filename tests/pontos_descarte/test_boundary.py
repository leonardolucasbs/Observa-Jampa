import json
from pathlib import Path

import pytest

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.clients.ibge import validate_boundary
from pages.pontos_descarte.config import load_settings
from pages.pontos_descarte.repositories.boundary_repository import BoundaryRepository, boundary_from_geojson

FIXTURE = Path(__file__).parent / "fixtures" / "ibge_malha.json"


def ibge_answer() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_ibge_answer_is_accepted_and_parsed():
    boundary = boundary_from_geojson(validate_boundary(ibge_answer()), "João Pessoa")
    assert boundary.name == "João Pessoa"
    assert len(boundary.polygons) == 1
    outer = boundary.polygons[0][0]
    assert outer[0] == outer[-1]  # anel fechado
    assert all(-35.0 < lon < -34.7 and -7.3 < lat < -7.0 for lon, lat in outer)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"type": "FeatureCollection", "features": []},
        {"features": [{"geometry": {"type": "Point", "coordinates": [-34.9, -7.1]}}]},
        ["não é GeoJSON"],
    ],
)
def test_unexpected_ibge_answers_are_rejected(payload):
    with pytest.raises(ServiceError):
        validate_boundary(payload)


def test_multipolygon_keeps_every_part():
    square = [[[0, 0], [1, 0], [1, 1], [0, 0]]]
    data = {"features": [{"geometry": {"type": "MultiPolygon", "coordinates": [square, square]}}]}
    assert len(boundary_from_geojson(data, "Ilha").polygons) == 2


def test_missing_or_broken_file_means_no_highlight(tmp_path):
    assert BoundaryRepository(tmp_path / "nao_existe.geojson", "João Pessoa").load() is None
    broken = tmp_path / "quebrado.geojson"
    broken.write_text("{", encoding="utf-8")
    assert BoundaryRepository(broken, "João Pessoa").load() is None


def test_committed_boundary_covers_the_points_of_joao_pessoa():
    settings = load_settings()
    boundary = BoundaryRepository(settings.data.city_boundary, settings.boundary.name).load()
    assert boundary is not None
    lons = [lon for polygon in boundary.polygons for ring in polygon for lon, _ in ring]
    lats = [lat for polygon in boundary.polygons for ring in polygon for _, lat in ring]
    points = json.loads(settings.data.points.read_text(encoding="utf-8"))
    for point in points:
        if point["city"] == "João Pessoa":
            assert min(lons) <= point["longitude"] <= max(lons), point["name"]
            assert min(lats) <= point["latitude"] <= max(lats), point["name"]
