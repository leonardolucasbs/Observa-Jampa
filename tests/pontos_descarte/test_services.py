from pages.pontos_descarte.domain.models import Coordinates, GeocodedPlace, MatchLevel
from pages.pontos_descarte.services.routing_service import RoutingService
from pages.pontos_descarte.services.search_service import PlaceStrategy, SearchService
from tests.pontos_descarte.conftest import FakeGeocoder, FakeRouter


def build_search(points, geocoder=None) -> SearchService:
    return SearchService(points, geocode=geocoder or FakeGeocoder(), neighborhood_radius_m=1500, address_radius_m=1000)


def ids(result) -> list[int]:
    return [match.point.id for match in result.matches]


def test_without_filters_returns_every_point(points):
    result = build_search(points).search()
    assert len(result.matches) == len(points) == result.total_points


def test_waste_filter_ranks_confirmed_points_before_unconfirmed(points):
    result = build_search(points).search(waste="celular")
    levels = [match.level for match in result.matches]
    assert set(ids(result)) == {1, 2, 3, 5, 6}  # Vivo, pequeno porte e os que não detalham
    assert levels == sorted(levels, key=lambda level: level != MatchLevel.ACCEPTS)
    assert {m.point.id for m in result.matches if m.level == MatchLevel.POSSIBLE} == {5, 6}


def test_neighborhood_filter_by_text_does_not_call_geocoder(points):
    geocoder = FakeGeocoder()
    result = build_search(points, geocoder).search(neighborhood="manaira")
    assert ids(result) == [1]
    assert result.neighborhood.strategy == PlaceStrategy.TEXT
    assert result.neighborhood.matched_names == ("Manaíra",)
    assert geocoder.queries == []


def test_unknown_neighborhood_is_located_on_the_map_and_filtered_by_radius(points):
    bancarios = GeocodedPlace("Bancários, João Pessoa", -7.1484, -34.8385)
    result = build_search(points, FakeGeocoder({"Bancários": bancarios})).search(neighborhood="Bancários")
    assert result.neighborhood.strategy == PlaceStrategy.NEARBY
    assert ids(result) == [4]  # Carrefour a ~1,2 km; a Central de Mangabeira fica a ~2 km
    assert result.matches[0].distance_to_reference_m < 1500
    assert result.references == (result.neighborhood,)


def test_place_not_found_returns_nothing_and_service_failure_ignores_the_filter(points):
    not_found = build_search(points, FakeGeocoder()).search(neighborhood="Atlântida")
    assert not_found.neighborhood.strategy == PlaceStrategy.NOT_FOUND
    assert not_found.matches == ()

    offline = build_search(points, FakeGeocoder(fail=True)).search(address="Rua Inexistente")
    assert offline.address.strategy == PlaceStrategy.UNAVAILABLE
    assert len(offline.matches) == len(points)


def test_address_filter_matches_text_and_ranks_by_similarity(points):
    result = build_search(points).search(address="av epitacio pessoa")
    assert ids(result) == [2]
    assert result.address.strategy == PlaceStrategy.TEXT


def test_filters_are_combined(points):
    result = build_search(points).search(waste="pilhas", neighborhood="jardim")
    # Jardim São Paulo aceita pilhas; Jardim Oceania recebe eletroeletrônicos sem detalhar → confirmar
    assert [(m.point.id, m.level) for m in result.matches] == [(4, MatchLevel.ACCEPTS), (6, MatchLevel.POSSIBLE)]
    result = build_search(points).search(waste="geladeira", neighborhood="jardim")
    assert [(m.point.id, m.level) for m in result.matches] == [(6, MatchLevel.POSSIBLE)]


def test_nearest_route_uses_road_distance_not_straight_line(points):
    origin = Coordinates(-7.12, -34.85)
    vivo, magalu = points[0], points[1]
    # O Magalu está mais perto em linha reta, mas o caminho pelas ruas dá uma volta enorme.
    router = FakeRouter(detour={(magalu.latitude, magalu.longitude): 20.0})
    route = RoutingService(router, candidates=5).nearest(origin, [vivo, magalu], profile="Carro")
    assert route.point.id == vivo.id
    assert router.table_calls == 1
    assert not route.straight_line
    assert route.distance_m == 1234.0


def test_nearest_route_falls_back_to_straight_line_when_service_is_down(points):
    route = RoutingService(FakeRouter(fail=True), candidates=3).nearest(Coordinates(-7.12, -34.85), points, "Carro")
    assert route.straight_line
    assert route.duration_s is None
    assert route.error
    assert len(route.path) == 2


def test_nearest_route_without_candidates_returns_none():
    assert RoutingService(FakeRouter(), candidates=3).nearest(Coordinates(-7.12, -34.85), [], "Carro") is None
