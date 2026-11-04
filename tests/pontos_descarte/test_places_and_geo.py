import pytest

from pages.pontos_descarte.domain.geo import MapView, closest_points, fit_view, group_by_location, haversine_m
from pages.pontos_descarte.domain.models import Coordinates
from pages.pontos_descarte.domain.places import (
    address_score,
    canonical_neighborhood,
    match_neighborhoods,
    smart_title,
)
from tests.pontos_descarte.conftest import make_point


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("MANAIRA", "Manaíra"),
        ("Manaíra", "Manaíra"),
        ("MANGABEIRA I", "Mangabeira"),
        ("JD OCEANIA", "Jardim Oceania"),
        ("JD C UNIVERSITÁRIA", "Jardim Cidade Universitária"),
        ("ESTADOS", "Bairro dos Estados"),
        ("João Paulo II", "João Paulo II"),
        ("CASTELO BRANCO III", "Castelo Branco"),
        ("BAIRRO NOVO DA SILVA", "Bairro Novo da Silva"),  # fora da lista: só ajusta maiúsculas
        ("", None),
        (None, None),
    ],
)
def test_canonical_neighborhood(raw, expected):
    assert canonical_neighborhood(raw) == expected


def test_smart_title_keeps_codes_and_numbers():
    assert smart_title("RUA HENRIQUE VIEIRA, S/N") == "Rua Henrique Vieira, S/N"
    assert smart_title("AVENIDA HILTON SOUTO MAIOR, 4619-A, LOJA T-236 E T237") == (
        "Avenida Hilton Souto Maior, 4619-A, Loja T-236 e T237"
    )


def test_match_neighborhoods_is_tolerant_and_prefers_exact_matches():
    names = ["Manaíra", "Tambaú", "Tambauzinho", "Jardim Oceania", "Jardim São Paulo", "Mangabeira"]
    assert set(match_neighborhoods("manaira", names)) == {"Manaíra"}
    assert set(match_neighborhoods("bairro mangabeia", names)) == {"Mangabeira"}
    assert set(match_neighborhoods("tambau", names)) == {"Tambaú"}  # não traz Tambauzinho
    assert set(match_neighborhoods("jardim", names)) == {"Jardim Oceania", "Jardim São Paulo"}
    assert match_neighborhoods("bancarios", names) == {}


def test_address_score_understands_abbreviations_name_and_postal_code():
    point = make_point(
        1,
        name="PEV GM&C - DROGASIL - TAMBAUZINHO",
        address="Av. Presidente Epitácio Pessoa, 2346",
        neighborhood="Tambauzinho",
    )
    assert address_score("avenida epitacio pessoa", point) > 0
    assert address_score("rua epitacio 2346", point) > address_score("rua epitacio 1", point) > 0
    assert address_score("drogasil", point) > 0
    assert address_score("rua das trincheiras", point) == 0


def test_haversine_known_distance():
    # Ponta do Seixas → centro de João Pessoa: cerca de 8,5 km
    distance = haversine_m(Coordinates(-7.1550, -34.7951), Coordinates(-7.1195, -34.8631))
    assert 8_000 < distance < 9_000


def test_closest_points_orders_by_straight_line_distance():
    near = make_point(1, latitude=-7.120, longitude=-34.860)
    far = make_point(2, latitude=-7.200, longitude=-34.900)
    middle = make_point(3, latitude=-7.140, longitude=-34.860)
    assert [p.id for p in closest_points(Coordinates(-7.12, -34.86), [far, near, middle], limit=2)] == [1, 3]


def test_group_by_location_merges_points_a_few_meters_apart():
    store_a = make_point(1, latitude=-7.1467674, longitude=-34.8494649)
    store_b = make_point(2, latitude=-7.1467711, longitude=-34.8493151)  # ~17 m
    elsewhere = make_point(3, latitude=-7.1652, longitude=-34.8321)
    groups = group_by_location([store_b, elsewhere, store_a])
    assert sorted(len(group.points) for group in groups) == [1, 2]
    shared = next(group for group in groups if len(group.points) == 2)
    assert shared.id == "1-2"
    assert shared.title == "2 pontos neste local"


def test_fit_view_zooms_in_on_close_points_and_out_on_spread_points():
    default = MapView(-7.12, -34.87, 11)
    assert fit_view([], default=default) == default
    close = fit_view([Coordinates(-7.120, -34.860), Coordinates(-7.121, -34.861)], default=default)
    spread = fit_view([Coordinates(-7.03, -34.83), Coordinates(-7.17, -34.98)], default=default)
    assert close.zoom > spread.zoom
    assert spread.latitude == pytest.approx(-7.10)
    assert fit_view([Coordinates(-7.12, -34.86)], default=default, max_zoom=15.5).zoom == 15.5
