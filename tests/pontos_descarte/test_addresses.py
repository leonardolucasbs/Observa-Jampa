import pytest

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.domain.addresses import AddressIndex
from pages.pontos_descarte.domain.models import GeocodedPlace, GeocodePrecision, StreetSegment
from pages.pontos_descarte.services.geocoding_service import GeocodingService
from tests.pontos_descarte.conftest import FakeGeocoder


def segment(
    street_type: str,
    name: str,
    neighborhood: str,
    numbers: tuple[int, int],
    latitude: float,
    longitude: float,
    *,
    title: str | None = None,
    city: str = "João Pessoa",
    postal_code: str | None = None,
    addresses: int = 10,
) -> StreetSegment:
    return StreetSegment(
        city=city,
        street_type=street_type,
        title=title,
        name=name,
        neighborhood=neighborhood,
        postal_code=postal_code,
        number_min=numbers[0],
        number_max=numbers[1],
        latitude=latitude,
        longitude=longitude,
        addresses=addresses,
    )


SEGMENTS = [
    segment("Avenida", "Ruy Carneiro", "Miramar", (100, 198), -7.1180, -34.8420, title="Senador"),
    segment("Avenida", "Ruy Carneiro", "Miramar", (200, 398), -7.1182, -34.8409, title="Senador"),
    segment("Avenida", "Ruy Carneiro", "Manaíra", (1000, 1500), -7.1126, -34.8294, title="Senador"),
    segment("Rua", "Silvino Lopes", "Tambaú", (1, 500), -7.1167, -34.8288),
    segment("Avenida", "Silvino Lopes", "Tambaú", (1, 300), -7.1160, -34.8286, addresses=3),
    segment("Rua", "das Trincheiras", "Jaguaribe", (300, 600), -7.1287, -34.8838),
    segment("Rua", "das Trincheiras", "Centro", (1, 298), -7.1249, -34.8845, addresses=30),
    segment("Rua", "Aurelio M de Albuquerque", "Jardim Cidade Universitária", (200, 260), -7.1560, -34.8423,
            title="Desembargador"),
    segment("Avenida", "Epitacio Pessoa", "Bairro dos Estados", (921, 1037), -7.1196, -34.8618, title="Presidente"),
    segment("Avenida", "Epitacio Pessoa", "Tambauzinho", (2700, 2800), -7.1197, -34.8464, title="Presidente"),
    segment("Rua", "Sao Jose", "Treze de Maio", (1, 400), -7.1126, -34.8659),
    segment("Rua", "Sao Jose", "Renascer", (1, 400), -7.0773, -34.8531, city="Cabedelo", addresses=50),
    segment("Avenida", "Brasil", "Cristo Redentor", (1, 900), -7.1493, -34.8831),
    segment("Rua", "Brasilia", "Grotão", (1, 900), -7.1900, -34.8852),
    segment("Rua", "Joao Pessoa", "Centro", (1, 900), -6.9751, -34.8369, title="Presidente", city="Cabedelo"),
    segment("Avenida", "Joao Mauricio", "Manaíra", (1, 2000), -7.1035, -34.8305, postal_code="58038-000"),
]


@pytest.fixture
def index() -> AddressIndex:
    return AddressIndex(SEGMENTS, primary_city="João Pessoa")


def labels(places: list[GeocodedPlace]) -> list[str]:
    return [place.label for place in places]


def test_finds_street_without_title_with_old_spelling_and_house_number(index):
    places = index.search("Av. Rui Carneiro, 300, Miramar")
    assert labels(places) == ["Avenida Senador Ruy Carneiro, 300, Miramar, João Pessoa"]
    assert places[0].precision == GeocodePrecision.ADDRESS
    assert (places[0].latitude, places[0].longitude) == (-7.1182, -34.8409)  # o trecho 200–398


def test_typo_finds_street_and_offers_the_other_street_type(index):
    places = index.search("Rua Silvino Lope")
    assert labels(places) == ["Rua Silvino Lopes, Tambaú, João Pessoa", "Avenida Silvino Lopes, Tambaú, João Pessoa"]
    assert places[0].precision == GeocodePrecision.STREET


def test_house_number_picks_the_segment_of_a_long_avenue(index):
    places = index.search("Av. Epitácio Pessoa, 2737")
    assert labels(places) == ["Avenida Presidente Epitacio Pessoa, 2737, Tambauzinho, João Pessoa"]
    assert (places[0].latitude, places[0].longitude) == (-7.1197, -34.8464)


def test_number_outside_every_segment_falls_back_to_the_nearest_one(index):
    places = index.search("Rua Silvino Lopes, 9000")
    assert places[0].label == "Rua Silvino Lopes, Tambaú, João Pessoa"  # sem o número, que não existe
    assert places[0].precision == GeocodePrecision.STREET


def test_neighborhood_restricts_and_unknown_neighborhood_is_ignored(index):
    assert labels(index.search("Rua das Trincheiras, Jaguaribe")) == ["Rua das Trincheiras, Jaguaribe, João Pessoa"]
    # O bairro digitado não bate com o do IBGE: busca só a rua, e o número 100 fica no trecho do Centro.
    assert labels(index.search("Rua das Trincheiras, 100, Bairro Inventado")) == [
        "Rua das Trincheiras, 100, Centro, João Pessoa",
    ]


def test_full_name_matches_the_initial_stored_by_ibge(index):
    places = index.search("Rua Desembargador Aurélio Moreira de Albuquerque, 230")
    assert labels(places) == [
        "Rua Desembargador Aurelio M de Albuquerque, 230, Jardim Cidade Universitária, João Pessoa"
    ]


def test_postal_code_returns_the_center_of_its_addresses(index):
    for query in ("58038-000", "CEP 58038000"):
        places = index.search(query)
        assert labels(places) == ["Avenida Joao Mauricio, Manaíra, João Pessoa (CEP 58038-000)"]
        assert places[0].precision == GeocodePrecision.POSTAL_CODE


def test_only_a_neighborhood_or_unknown_place_is_left_for_openstreetmap(index):
    assert index.search("Miramar") == []
    assert index.search("Tambaú, João Pessoa") == []
    assert index.search("Manaíra Shopping") == []
    assert index.search("   ") == []
    assert AddressIndex([]).search("Rua Silvino Lopes") == []


def test_city_name_after_a_comma_does_not_count_as_street_name(index):
    places = index.search("Rua Brasil, 100, João Pessoa - PB")
    assert places[0].label == "Avenida Brasil, 100, Cristo Redentor, João Pessoa"
    assert not any("Joao Pessoa" in label for label in labels(places))


def test_exact_name_beats_a_longer_name_with_the_same_prefix(index):
    assert labels(index.search("Avenida Brasil")) == ["Avenida Brasil, Cristo Redentor, João Pessoa"]


def test_same_name_in_two_cities_prefers_the_primary_city(index):
    assert labels(index.search("Rua São José")) == [
        "Rua Sao Jose, Treze de Maio, João Pessoa",
        "Rua Sao Jose, Renascer, Cabedelo",
    ]
    other = AddressIndex(SEGMENTS, primary_city="Cabedelo")
    assert other.search("Rua São José")[0].label == "Rua Sao Jose, Renascer, Cabedelo"


def test_limit_caps_the_number_of_candidates(index):
    assert len(index.search("Rua São José", limit=1)) == 1


# ---- sequência de fontes ----------------------------------------------------------------------

NOMINATIM_PLACE = GeocodedPlace("Manaíra Shopping, Manaíra, João Pessoa", -7.0989, -34.8447)
PHOTON_PLACE = GeocodedPlace("Estacionamento Manaíra Shopping, Cabedelo", -7.0989, -34.8467)


def test_local_index_answers_first_without_calling_external_services(index):
    nominatim, photon = FakeGeocoder(), FakeGeocoder()
    service = GeocodingService(index, fallbacks=(nominatim, photon))
    assert service.search("Rua Silvino Lopes, 100").precision == GeocodePrecision.ADDRESS
    assert nominatim.queries == [] and photon.queries == []


def test_falls_back_to_nominatim_then_photon(index):
    nominatim = FakeGeocoder({"Manaíra Shopping": NOMINATIM_PLACE})
    photon = FakeGeocoder({"Manaira Shoping": PHOTON_PLACE})
    service = GeocodingService(index, fallbacks=(nominatim, photon))

    assert service.candidates("Manaíra Shopping") == [NOMINATIM_PLACE]
    assert photon.queries == []
    assert service.candidates("Manaira Shoping") == [PHOTON_PLACE]
    assert nominatim.queries == ["Manaíra Shopping", "Manaira Shoping"]


def test_external_failure_only_surfaces_when_nobody_found_the_place(index):
    offline = FakeGeocoder(fail=True)
    assert GeocodingService(index, fallbacks=(offline, FakeGeocoder({"UFPB": PHOTON_PLACE}))).search("UFPB")
    with pytest.raises(ServiceError):
        GeocodingService(index, fallbacks=(offline, FakeGeocoder())).search("UFPB")
    assert GeocodingService(index, fallbacks=(FakeGeocoder(), FakeGeocoder())).search("UFPB") is None
