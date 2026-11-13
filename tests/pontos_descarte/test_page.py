"""Integridade dos dados versionados e fumaça da página (sem rede: nenhum filtro aciona serviços externos)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from pages.pontos_descarte.config import load_settings
from pages.pontos_descarte.repositories.points_repository import PointsRepository

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


def test_page_renders_and_filters_without_errors():
    app = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not app.exception
    assert app.title[0].value == "Pontos de descarte de eletroeletrônicos"

    app.text_input(key="filter_waste").input("pilhas").run()
    app.text_input(key="filter_neighborhood").input("manaira").run()
    assert not app.exception
    assert any("Pilhas e baterias" in caption.value for caption in app.caption)
    assert any("Manaíra" in caption.value for caption in app.caption)


def test_app_opens_on_the_landing_page():
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert app.title[0].value == "Observa Jampa"
