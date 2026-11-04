import pytest

from pages.pontos_descarte.domain.text import (
    ADDRESS_ABBREVIATIONS,
    edit_distance,
    normalize,
    phrase_score,
    singularize,
    tokenize,
    word_similarity,
)


def test_normalize_removes_accents_case_and_punctuation():
    assert normalize("Manaíra-Shopping, Loja T-236!") == "manaira shopping loja t 236"
    assert normalize(None) == ""


def test_tokenize_expands_address_abbreviations_and_drops_stopwords():
    tokens = tokenize("Av. Pres. Epitácio Pessoa, 2346", abbreviations=ADDRESS_ABBREVIATIONS)
    assert tokens == ["avenida", "presidente", "epitacio", "pessoa", "2346"]
    assert tokenize("Jd. Cidade Universitária", abbreviations=ADDRESS_ABBREVIATIONS) == [
        "jardim", "cidade", "universitaria",
    ]


@pytest.mark.parametrize(
    ("plural", "singular"),
    [("pilhas", "pilha"), ("carregadores", "carregador"), ("televisões", "televisao"), ("tv", "tv"), ("2346", "2346")],
)
def test_singularize(plural, singular):
    assert singularize(normalize(plural)) == singular


def test_edit_distance_counts_transposition_as_one_edit():
    assert edit_distance("bateira", "bateria") == 1
    assert edit_distance("bateira", "batedeira") == 2
    assert edit_distance("", "abc") == 3


def test_word_similarity_tolerates_typos_but_not_different_words():
    assert word_similarity("mangabeia", "mangabeira") >= 0.8
    assert word_similarity("epit", "epitacio") == pytest.approx(0.9)  # começo da palavra
    assert word_similarity("tambau", "tambia") < 0.8  # bairros diferentes
    assert word_similarity("tv", "ti") == 0.0  # palavras curtas só batem exatamente
    assert word_similarity("805", "806") == 0.0


def test_phrase_score_requires_every_word_but_numbers_and_optional_words_only_rank():
    candidate = ["avenida", "presidente", "epitacio", "pessoa", "2346", "tambauzinho"]
    assert phrase_score(["epitacio", "pessoa"], candidate) > 0
    assert phrase_score(["epitacio", "trincheiras"], candidate) == 0
    with_number = phrase_score(["epitacio", "2346"], candidate)
    wrong_number = phrase_score(["epitacio", "9999"], candidate)
    assert with_number > wrong_number > 0
    assert phrase_score(["rua", "epitacio"], candidate, optional=frozenset({"rua"})) > 0


def test_phrase_score_with_only_numbers_matches_postal_code():
    assert phrase_score(["58038", "680"], ["cep", "58038", "680"]) == 1.0
    assert phrase_score(["58038", "999"], ["cep", "58038", "680"]) == 0.0
