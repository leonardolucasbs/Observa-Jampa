"""Normalização e comparação aproximada de textos em português.

É a base das buscas "semânticas": ignora acentos, maiúsculas, pontuação, abreviações comuns
e pequenos erros de digitação, para que "av epitacio" encontre "AV. PRESIDENTE EPITÁCIO PESSOA".
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping

FUZZY_THRESHOLD = 0.8  # semelhança mínima entre duas palavras para considerá-las iguais
PREFIX_SCORE = 0.9  # nota de quem digitou só o começo da palavra ("epit" → "epitacio")
MIN_PREFIX_LENGTH = 4
MIN_FUZZY_LENGTH = 4  # palavras curtas ("tv", "pc", "rua") só batem exatamente

COMMON_STOPWORDS = frozenset(
    {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "um", "uma",
     "ao", "aos", "com", "para", "pra", "pro", "por", "perto", "proximo", "proxima", "ou"}
)

ADDRESS_ABBREVIATIONS: Mapping[str, str] = {
    "av": "avenida",
    "avd": "avenida",
    "r": "rua",
    "rod": "rodovia",
    "trav": "travessa",
    "tv": "travessa",
    "pc": "praca",
    "pca": "praca",
    "al": "alameda",
    "jd": "jardim",
    "jdm": "jardim",
    "pq": "parque",
    "cj": "conjunto",
    "conj": "conjunto",
    "res": "residencial",
    "pres": "presidente",
    "gov": "governador",
    "sen": "senador",
    "dep": "deputado",
    "min": "ministro",
    "dr": "doutor",
    "dra": "doutora",
    "prof": "professor",
    "eng": "engenheiro",
    "des": "desembargador",
    "pe": "padre",
    "cel": "coronel",
    "gal": "general",
    "alm": "almirante",
    "sta": "santa",
    "sto": "santo",
    "sr": "senhor",
    "sra": "senhora",
    "nsa": "nossa",
    "jp": "joao pessoa",
    "jpa": "joao pessoa",
}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize(text: str | None) -> str:
    """Minúsculas, sem acento e sem pontuação: "Manaíra-Shopping!" → "manaira shopping"."""
    if not text:
        return ""
    return _NON_ALNUM.sub(" ", strip_accents(text).lower()).strip()


def tokenize(
    text: str | None,
    *,
    stopwords: Iterable[str] = COMMON_STOPWORDS,
    abbreviations: Mapping[str, str] | None = None,
    singular: bool = False,
) -> list[str]:
    """Quebra o texto em palavras normalizadas, expandindo abreviações e tirando palavras vazias."""
    stop = frozenset(stopwords)
    tokens: list[str] = []
    for word in normalize(text).split():
        expanded = abbreviations.get(word, word) if abbreviations else word
        for part in expanded.split():
            if part in stop:
                continue
            tokens.append(singularize(part) if singular else part)
    return tokens


def singularize(word: str) -> str:
    """Plural → singular, só o suficiente para comparar ("carregadores" → "carregador")."""
    if len(word) <= 3 or word.isdigit():
        return word
    for suffix, replacement in (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("eis", "el"), ("res", "r"), ("zes", "z")):
        if word.endswith(suffix):
            return word[: -len(suffix)] + replacement
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


_DOUBLE_LETTERS = re.compile(r"([a-z])\1+")


def phonetic(word: str) -> str:
    """Iguala grafias antigas e variações comuns em nomes de rua, para comparar.

    "ruy" → "rui", "luiz" → "luis", "mello" → "melo", "athayde" → "ataide", "wagner" → "vagner".
    Também absorve erros como "jarrdim". Recebe palavras já normalizadas por `normalize`.
    """
    word = word.replace("ph", "f").replace("th", "t").replace("y", "i").replace("w", "v")
    word = _DOUBLE_LETTERS.sub(r"\1", word)
    if len(word) > 3 and word.endswith("z"):
        word = word[:-1] + "s"
    return word


def word_similarity(query: str, candidate: str) -> float:
    """Semelhança entre duas palavras já normalizadas, de 0 a 1.

    Usa distância de edição com transposição: "bateira" fica a 1 edição de "bateria"
    e a 2 de "batedeira", então a correção vai para a palavra certa.
    """
    if query == candidate:
        return 1.0
    if query.isdigit() or candidate.isdigit():
        return 0.0
    if len(query) >= MIN_PREFIX_LENGTH and candidate.startswith(query):
        return PREFIX_SCORE
    if min(len(query), len(candidate)) < MIN_FUZZY_LENGTH:
        return 0.0
    return 1.0 - edit_distance(query, candidate) / max(len(query), len(candidate))


def edit_distance(first: str, second: str) -> int:
    """Distância de Damerau-Levenshtein (variante OSA): inserção, remoção, troca e transposição."""
    before_previous: list[int] = []
    previous = list(range(len(second) + 1))
    for i in range(1, len(first) + 1):
        current = [i] + [0] * len(second)
        for j in range(1, len(second) + 1):
            cost = 0 if first[i - 1] == second[j - 1] else 1
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost)
            if i > 1 and j > 1 and first[i - 1] == second[j - 2] and first[i - 2] == second[j - 1]:
                current[j] = min(current[j], before_previous[j - 2] + 1)
        before_previous, previous = previous, current
    return previous[-1]


def best_similarity(query: str, candidates: Iterable[str]) -> float:
    return max((word_similarity(query, candidate) for candidate in candidates), default=0.0)


def phrase_score(
    query_tokens: list[str],
    candidate_tokens: list[str],
    *,
    optional: frozenset[str] = frozenset(),
    threshold: float = FUZZY_THRESHOLD,
) -> float:
    """Quanto as palavras da busca aparecem no candidato (0 se alguma palavra obrigatória falta).

    Números e palavras de `optional` (ex.: "rua", "avenida") não eliminam ninguém: só ajudam a ordenar,
    assim "rua epitacio pessoa 2346" ainda encontra "Av. Presidente Epitácio Pessoa, 2346".
    Se a busca só tem números (um CEP, por exemplo), todos precisam aparecer.
    """
    required = [token for token in query_tokens if not token.isdigit() and token not in optional]
    extras = [token for token in query_tokens if token.isdigit() or token in optional]
    if not required:
        return 1.0 if extras and all(token in candidate_tokens for token in extras) else 0.0
    scores = [best_similarity(word, candidate_tokens) for word in required]
    if min(scores) < threshold:
        return 0.0
    score = sum(scores) / len(scores)
    if extras:
        score += 0.05 * sum(token in candidate_tokens for token in extras) / len(extras)
    return score
