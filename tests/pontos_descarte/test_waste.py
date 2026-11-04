import pytest

from pages.pontos_descarte.domain.models import Category, MatchLevel
from pages.pontos_descarte.domain.waste import categories_from_description, interpret_waste_query, match_level
from tests.pontos_descarte.conftest import (
    ALL_SIZES,
    BATTERIES,
    PHONES_AND_BATTERIES,
    SMALL_AND_MEDIUM,
    UNSPECIFIED,
    make_point,
)


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        (PHONES_AND_BATTERIES, {Category.PHONES, Category.BATTERIES}),
        (SMALL_AND_MEDIUM, {Category.SMALL, Category.MEDIUM}),
        (ALL_SIZES, {Category.SMALL, Category.MEDIUM, Category.LARGE}),
        (BATTERIES, {Category.BATTERIES}),
        ("Pilhas e Cartuchos", {Category.BATTERIES, Category.CARTRIDGES}),
        (UNSPECIFIED, {Category.UNSPECIFIED}),
        (None, {Category.UNSPECIFIED}),
    ],
)
def test_categories_from_description(description, expected):
    assert categories_from_description(description) == frozenset(expected)


@pytest.mark.parametrize(
    ("query", "label"),
    [
        ("pilhas", "Pilhas e baterias"),
        ("quero descartar umas baterias velhas", "Pilhas e baterias"),
        ("bateira", "Pilhas e baterias"),  # erro de digitação
        ("celular velho", "Celular e acessórios"),
        ("fone de ouvido", "Celular e acessórios"),
        ("notebook", "Eletrônico de pequeno porte"),
        ("TV", "Eletrônico de médio porte"),
        ("micro-ondas", "Eletrônico de médio porte"),
        ("geladeira", "Eletrodoméstico de grande porte"),
        ("máquina de lavar", "Eletrodoméstico de grande porte"),
        ("cartucho de impressora", "Cartuchos e toners"),
    ],
)
def test_interpret_waste_query_understands_everyday_words(query, label):
    interpretation = interpret_waste_query(query)
    assert [item.label for item in interpretation.items] == [label]


def test_interpret_prefers_longer_terms():
    labels = [item.label for item in interpret_waste_query("forno elétrico").items]
    assert labels == ["Eletrônico de médio porte"]


def test_interpret_multiple_items():
    labels = {item.label for item in interpret_waste_query("celular e pilhas").items}
    assert labels == {"Celular e acessórios", "Pilhas e baterias"}


def test_interpret_generic_and_unknown_queries():
    generic = interpret_waste_query("lixo eletrônico")
    assert generic.generic and not generic.items

    unknown = interpret_waste_query("abacaxi")
    assert unknown.uses_text_fallback
    assert unknown.unknown_words == ("abacaxi",)

    assert interpret_waste_query("   ").is_empty


def test_match_level_accepts_only_when_every_item_is_covered():
    vivo = make_point(1, description=PHONES_AND_BATTERIES)
    magalu = make_point(2, description=SMALL_AND_MEDIUM)
    drogasil = make_point(3, description=UNSPECIFIED)

    phone = interpret_waste_query("celular")
    assert match_level(vivo, phone) == MatchLevel.ACCEPTS
    assert match_level(magalu, phone) == MatchLevel.ACCEPTS  # celular é eletrônico de pequeno porte
    assert match_level(drogasil, phone) == MatchLevel.POSSIBLE

    fridge = interpret_waste_query("geladeira")
    assert match_level(vivo, fridge) is None
    assert match_level(magalu, fridge) is None

    both = interpret_waste_query("notebook e pilhas")
    assert match_level(vivo, both) is None  # aceita pilhas, mas não notebook
    assert match_level(magalu, both) is None


def test_match_level_without_query_or_with_generic_query_accepts_everyone():
    point = make_point(1, description=BATTERIES)
    assert match_level(point, interpret_waste_query("")) == MatchLevel.ACCEPTS
    assert match_level(point, interpret_waste_query("eletrônicos")) == MatchLevel.ACCEPTS


def test_match_level_falls_back_to_description_and_notes_text():
    with_notes = make_point(1, description=PHONES_AND_BATTERIES, notes="Outros produtos mediante agendamento.")
    without_notes = make_point(2, description=PHONES_AND_BATTERIES)
    query = interpret_waste_query("agendamento")
    assert match_level(with_notes, query) == MatchLevel.ACCEPTS
    assert match_level(without_notes, query) is None
