"""Bairros e endereços: nomes canônicos e correspondência aproximada por texto."""

import re
from collections.abc import Iterable

from pages.pontos_descarte.domain.models import DisposalPoint
from pages.pontos_descarte.domain.text import (
    ADDRESS_ABBREVIATIONS,
    COMMON_STOPWORDS,
    normalize,
    phrase_score,
    tokenize,
)

# Bairros oficiais de João Pessoa e alguns da região metropolitana que aparecem nos dados.
# Servem para padronizar a grafia (a planilha mistura "MANAIRA", "MANAÍRA" e "Manaíra").
KNOWN_NEIGHBORHOODS: tuple[str, ...] = (
    "Aeroclube", "Água Fria", "Altiplano Cabo Branco", "Alto do Céu", "Alto do Mateus", "Anatólia",
    "Bairro das Indústrias", "Bairro dos Estados", "Bairro dos Ipês", "Bairro dos Novais", "Bancários",
    "Barra de Gramame", "Bessa", "Brisamar", "Cabo Branco", "Castelo Branco", "Centro", "Costa do Sol",
    "Costa e Silva", "Cristo Redentor", "Cruz das Armas", "Cuiá", "Distrito Industrial", "Ernâni Sátiro",
    "Ernesto Geisel", "Expedicionários", "Funcionários", "Gramame", "Grotão", "Ilha do Bispo", "Jaguaribe",
    "Jardim Cidade Universitária", "Jardim Luna", "Jardim Oceania", "Jardim São Paulo", "Jardim Veneza",
    "João Agripino", "João Paulo II", "José Américo", "Manaíra", "Mandacaru", "Mangabeira", "Mata do Buraquinho",
    "Miramar", "Mumbaba", "Muçumagro", "Oitizeiro", "Padre Zé", "Paratibe", "Pedro Gondim", "Penha",
    "Planalto da Boa Esperança", "Ponta do Seixas", "Portal do Sol", "Roger", "São José", "Tambauzinho", "Tambaú",
    "Tambiá", "Torre", "Treze de Maio", "Trincheiras", "Valentina de Figueiredo", "Varadouro", "Varjão",
    # Região metropolitana
    "Intermares", "Camboinha", "Ponta de Campina", "Poço", "Várzea Nova",
)

NEIGHBORHOOD_ALIASES: dict[str, str] = {
    "estados": "Bairro dos Estados",
    "ipes": "Bairro dos Ipês",
    "novais": "Bairro dos Novais",
    "industrias": "Bairro das Indústrias",
    "altiplano": "Altiplano Cabo Branco",
    "jardim c universitaria": "Jardim Cidade Universitária",
    "jardim cid universitaria": "Jardim Cidade Universitária",
    "cidade universitaria": "Jardim Cidade Universitária",
    "valentina": "Valentina de Figueiredo",
}

NEIGHBORHOOD_STOPWORDS = COMMON_STOPWORDS | {"bairro"}

# Palavras que não eliminam um endereço se não baterem (a pessoa pode errar "rua" x "avenida").
OPTIONAL_ADDRESS_WORDS = frozenset(
    {"rua", "avenida", "travessa", "rodovia", "praca", "alameda", "loja", "sala", "quiosque", "sn", "s", "n", "br"}
)

_ROMAN_SUFFIX = re.compile(r"\s+(i{1,3}|iv|v|vi{1,3})$")
_PARTICLES = frozenset({"de", "da", "do", "das", "dos", "e"})
_KEEP_UPPER = frozenset({"pb", "br", "sn", "ii", "iii", "iv", "vi", "vii", "viii"})


def _key(name: str) -> str:
    return " ".join(tokenize(name, stopwords=(), abbreviations={"jd": "jardim"}))


_CANONICAL_BY_KEY: dict[str, str] = {_key(name): name for name in KNOWN_NEIGHBORHOODS} | NEIGHBORHOOD_ALIASES


def canonical_neighborhood(raw: str | None, *, fuzzy: bool = False) -> str | None:
    """Padroniza o nome de um bairro: "MANGABEIRA I" → "Mangabeira", "JD OCEANIA" → "Jardim Oceania".

    Com `fuzzy`, também corrige nomes abreviados ou com erro de digitação, desde que apontem para um
    único bairro conhecido: "CRISTO" → "Cristo Redentor", "PADDRE ZE" → "Padre Zé".
    """
    if not raw or not normalize(raw):
        return None
    key = _key(raw)
    if key in _CANONICAL_BY_KEY:
        return _CANONICAL_BY_KEY[key]
    without_roman = _ROMAN_SUFFIX.sub("", key)
    if without_roman in _CANONICAL_BY_KEY:
        return _CANONICAL_BY_KEY[without_roman]
    if fuzzy and (closest := _closest_known_neighborhood(raw)):
        return closest
    return smart_title(raw)


FUZZY_NEIGHBORHOOD_MIN_SCORE = 0.85


def _closest_known_neighborhood(raw: str) -> str | None:
    query = neighborhood_tokens(raw)
    if not query:
        return None
    scores = {name: phrase_score(query, neighborhood_tokens(name)) for name in KNOWN_NEIGHBORHOODS}
    best = max(scores.values())
    winners = [name for name, score in scores.items() if score == best]
    return winners[0] if best >= FUZZY_NEIGHBORHOOD_MIN_SCORE and len(winners) == 1 else None


def smart_title(text: str) -> str:
    """Título em português sem estragar siglas curtas: "RUA DAS FLORES, S/N" → "Rua das Flores, S/N"."""
    result = []
    for index, word in enumerate(text.strip().split()):
        lower = word.lower()
        if index > 0 and lower in _PARTICLES:
            result.append(lower)
        elif any(char.isdigit() for char in word):
            result.append(word)  # "4619-A", "T-236"
        elif "/" in word or normalize(word) in _KEEP_UPPER:
            result.append(word.upper())
        else:
            result.append(lower[:1].upper() + lower[1:])
    return " ".join(result)


def neighborhood_tokens(name: str) -> list[str]:
    return tokenize(name, stopwords=NEIGHBORHOOD_STOPWORDS, abbreviations=ADDRESS_ABBREVIATIONS)


def match_neighborhoods(query: str, names: Iterable[str]) -> dict[str, float]:
    """Bairros dos dados que correspondem ao texto digitado, com a nota de cada um.

    Se algum bairro bate exatamente, só os exatos ficam: "tambau" traz Tambaú, não Tambauzinho.
    Já "jardim" traz todos os "Jardim ...".
    """
    query_tokens = neighborhood_tokens(query)
    if not query_tokens:
        return {}
    scores = {name: phrase_score(query_tokens, neighborhood_tokens(name)) for name in set(names)}
    scores = {name: score for name, score in scores.items() if score > 0}
    exact = {name: score for name, score in scores.items() if score >= 1.0}
    return exact or scores


def address_tokens(point: DisposalPoint) -> list[str]:
    text = " ".join(
        part
        for part in (point.name, point.address, point.neighborhood, point.city, point.state, point.postal_code)
        if part
    )
    return tokenize(text, abbreviations=ADDRESS_ABBREVIATIONS)


def address_score(query: str, point: DisposalPoint) -> float:
    """Quanto o endereço (ou nome) do ponto corresponde ao texto digitado; 0 = não corresponde."""
    query_tokens = tokenize(query, abbreviations=ADDRESS_ABBREVIATIONS)
    if not query_tokens:
        return 0.0
    return phrase_score(query_tokens, address_tokens(point), optional=OPTIONAL_ADDRESS_WORDS)
