"""Integridade dos dados versionados e fumaça da página (sem rede: os filtros usados só consultam dados locais)."""

from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

from pages.pontos_descarte.config import load_settings
from pages.pontos_descarte.domain.addresses import AddressIndex
from pages.pontos_descarte.domain.models import GeocodePrecision
from pages.pontos_descarte.repositories.address_repository import AddressRepository
from pages.pontos_descarte.repositories.points_repository import PointsRepository
from pages.pontos_descarte.ui import data

SRC = Path(__file__).resolve().parents[2] / "src"
PAGE = str(SRC / "pages" / "pontos_descarte" / "page.py")
APP = str(SRC / "app.py")


def test_committed_points_are_valid():
    points = PointsRepository(load_settings().data.points).all()
    assert len(points) == len({point.id for point in points}) >= 60
    for point in points:
        assert -7.35 < point.latitude < -6.9 and -35.1 < point.longitude < -34.7, point.id
        assert point.categories, point.id
        assert point.city, point.id


def test_committed_address_index_is_valid():
    settings = load_settings()
    repository = AddressRepository(settings.data.addresses)
    segments = repository.load()
    assert len(segments) > 30_000
    assert {segment.city for segment in segments} == set(settings.addresses.cities)
    for segment in segments:
        assert -7.6 < segment.latitude < -6.8 and -35.3 < segment.longitude < -34.7, segment
        assert segment.number_min <= segment.number_max
    assert "CNEFE" in repository.metadata()["fonte"]

    # Ruas que o OpenStreetMap não encontra (sem nome no mapa ou com outra grafia) estão no índice.
    index = AddressIndex(segments, primary_city="João Pessoa")
    for query, expected in [
        ("Rua Anita Garibaldi, 198, Paratibe", "Rua Anita Garibaldi, 198, Paratibe"),
        ("Av. Rui Carneiro, 300, Miramar", "Avenida Senador Ruy Carneiro, 300, Miramar"),
    ]:
        place = index.search(query)[0]
        assert place.label.startswith(expected) and place.precision == GeocodePrecision.ADDRESS


def test_page_renders_and_filters_without_errors():
    app = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not app.exception
    assert app.title[0].value == "Pontos de descarte de eletroeletrônicos"

    app.text_input(key="filter_waste").input("pilhas").run()
    app.text_input(key="filter_neighborhood").input("manaira").run()
    assert not app.exception
    assert any("Pilhas e baterias" in caption.value for caption in app.caption)
    assert any("Manaíra" in caption.value for caption in app.caption)


def test_typed_origin_uses_best_match_and_offers_the_others():
    """Origem digitada: usa o lugar mais provável na hora e lista os outros com o mesmo nome.

    A rota é substituída por um dublê para o teste não acessar a rede.
    """
    with mock.patch.object(data, "nearest_route", return_value=None), mock.patch.object(data, "route_to"):
        app = AppTest.from_file(PAGE, default_timeout=60).run()
        next(g for g in app.button_group if g.key == "origin_source").set_value("Digitar endereço").run()
        next(t for t in app.text_input if t.label == "Seu endereço").input("Rua São José")
        next(b for b in app.button if b.label == "Buscar endereço").click().run()
        assert not app.exception
        assert any("Saindo de:** Rua Sao Jose, Treze de Maio, João Pessoa" in m.value for m in app.markdown)

        choice = next(s for s in app.selectbox if s.key == "route_origin_choice")
        assert len(choice.options) > 1
        choice.set_value(1).run()
        assert any(f"Saindo de:** {choice.options[1]}" in m.value for m in app.markdown)
        assert any("posição aproximada" in c.value.lower() for c in app.caption)


def test_app_opens_on_the_landing_page():
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert app.title[0].value == "Observa Jampa"
