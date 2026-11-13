"""Busca de endereços digitados no índice local de trechos de rua (CNEFE do IBGE, Censo 2022).

Entende o texto como o resto da página (sem acento, abreviações, erros de digitação) e também:

- títulos opcionais: "Rui Carneiro" acha "Avenida Senador Ruy Carneiro";
- grafias antigas: Ruy/Rui, Luiz/Luís, Mello/Melo;
- "rua" e "avenida" trocados: só ajudam a ordenar, não eliminam;
- iniciais que o IBGE abrevia: "Aurélio Moreira" acha "Aurelio M de Albuquerque";
- número da casa: escolhe o trecho da rua cuja faixa de números contém o número;
- CEP: centro dos endereços daquele CEP;
- bairro e cidade no texto restringem a busca. Se o bairro não bater, tenta só com a rua.
"""

import bisect
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from pages.pontos_descarte.domain.geo import haversine_m
from pages.pontos_descarte.domain.models import Coordinates, GeocodedPlace, GeocodePrecision, StreetSegment
from pages.pontos_descarte.domain.places import neighborhood_tokens
from pages.pontos_descarte.domain.text import (
    ADDRESS_ABBREVIATIONS,
    FUZZY_THRESHOLD,
    MIN_FUZZY_LENGTH,
    MIN_PREFIX_LENGTH,
    PREFIX_SCORE,
    phonetic,
    tokenize,
    word_similarity,
)

POSTAL_CODE = re.compile(r"\b(\d{5})-?(\d{3})\b")
INITIAL_SCORE = 0.85  # "moreira" contra a inicial "m" que o IBGE guardou
MAX_LENGTH_GAP = 2  # palavras com tamanhos muito diferentes nem são comparadas (economiza tempo)
COVERAGE_WEIGHT = 0.15  # prefere a rua cujo nome a pessoa escreveu inteiro (pesa mais que o tipo)
# Tipo e título digitados não eliminam ninguém, só ordenam. Trocar "rua" por "avenida" é comum, então
# a rua do outro tipo ainda aparece como opção; um título diferente ("Infante" x "Conselheiro") não.
TYPE_WEIGHT = 0.05
TITLE_WEIGHT = 0.1
AMBIGUITY_MARGIN = 0.06  # candidatos até essa distância da melhor nota entram em "Você quis dizer?"
SAME_PLACE_M = 500.0  # a mesma rua a menos disso é o mesmo lugar: não repete na lista

# Complementos que a pessoa pode escrever sem que eliminem a rua.
COMPLEMENT_WORDS = frozenset(
    {"s", "n", "sn", "numero", "casa", "apto", "apartamento", "ap", "bloco", "loja", "sala", "cep"}
)
# Valem para qualquer endereço do índice, como o nome da cidade.
STATE_WORDS = ("pb", "paraiba", "brasil")


def _tokens(text: str | None) -> list[str]:
    return [phonetic(word) for word in tokenize(text, abbreviations=ADDRESS_ABBREVIATIONS)]


@dataclass
class _Street:
    """Uma rua dentro de um bairro: a unidade que a busca compara e devolve."""

    street: str
    city: str
    neighborhood: str | None
    core: frozenset[str]  # palavras do nome ("ruy", "carneiro")
    optional: frozenset[str]  # tipo e título ("avenida", "senador")
    tokens: frozenset[str]  # nome + tipo + título + bairro + cidade
    segments: tuple[StreetSegment, ...]
    addresses: int
    middle: StreetSegment  # trecho mais próximo do centro: onde fica "a rua" quando não há número

    def locate(self, number: int | None) -> tuple[StreetSegment, GeocodePrecision]:
        if number is not None:
            numbered = [segment for segment in self.segments if segment.number_max > 0]
            inside = [segment for segment in numbered if segment.contains(number)]
            if inside:
                return min(inside, key=lambda s: (s.number_max - s.number_min, s.latitude)), GeocodePrecision.ADDRESS
            if numbered:
                return min(numbered, key=lambda s: (s.gap_to(number), s.latitude)), GeocodePrecision.STREET
        return self.middle, GeocodePrecision.STREET


class _Vocabulary:
    """Todas as palavras do índice, para achar rápido as parecidas com uma palavra digitada."""

    def __init__(self, words: Iterable[str]) -> None:
        self._all = frozenset(words)
        self._sorted = sorted(self._all)
        self._by_first_letter: dict[str, list[str]] = defaultdict(list)
        for word in self._sorted:
            self._by_first_letter[word[0]].append(word)

    def similar(self, word: str) -> dict[str, float]:
        """Palavras do índice parecidas com `word`, com a nota de cada uma.

        Erros na primeira letra não são cobertos: comparar só com quem começa igual é o que
        deixa a busca rápida.
        """
        found: dict[str, float] = {}
        if word in self._all:
            found[word] = 1.0
        if len(word) >= MIN_PREFIX_LENGTH:
            position = bisect.bisect_left(self._sorted, word)
            while position < len(self._sorted) and self._sorted[position].startswith(word):
                found.setdefault(self._sorted[position], PREFIX_SCORE)
                position += 1
        if len(word) >= MIN_FUZZY_LENGTH:
            for candidate in self._by_first_letter.get(word[0], ()):
                if candidate not in found and abs(len(candidate) - len(word)) <= MAX_LENGTH_GAP:
                    score = word_similarity(word, candidate)
                    if score >= FUZZY_THRESHOLD:
                        found[candidate] = score
        if len(word) > 1 and word[0] in self._all:
            found.setdefault(word[0], INITIAL_SCORE)
        return found


@dataclass(frozen=True)
class _Query:
    required: tuple[str, ...]  # toda palavra precisa aparecer na rua, no bairro ou na cidade
    soft: tuple[str, ...]  # tipo, título e complementos: só ajudam a ordenar
    digits: tuple[str, ...]  # número da casa ou parte do nome ("Rua 13 de Maio")
    # Palavras que precisam bater com o nome da rua: as do primeiro trecho entre vírgulas, já que
    # o resto costuma ser bairro e cidade ("Rua Brasil, 100, João Pessoa" não é a "Rua João Pessoa").
    street_words: frozenset[str]


_LETTER = re.compile(r"[^\W\d_]")


class AddressIndex:
    def __init__(self, segments: Iterable[StreetSegment], primary_city: str | None = None) -> None:
        """`primary_city` desempata nomes repetidos em outras cidades ("Avenida Brasil")."""
        self._primary_city = primary_city
        grouped: dict[tuple, list[StreetSegment]] = defaultdict(list)
        for segment in segments:
            key = (segment.city, segment.street_type, segment.title, segment.name, segment.neighborhood)
            grouped[key].append(segment)

        self._streets: list[_Street] = []
        self._postings: dict[str, set[int]] = defaultdict(set)
        self._by_postal_code: dict[str, list[StreetSegment]] = defaultdict(list)
        types: set[str] = set()
        titles: set[str] = set()
        places: set[str] = set(STATE_WORDS)
        for (city, street_type, title, name, neighborhood), members in sorted(grouped.items(), key=_sort_key):
            core = frozenset(_tokens(name))
            if not core:
                continue
            type_words, title_words = _tokens(street_type), _tokens(title)
            types.update(type_words)
            titles.update(title_words)
            place = [phonetic(word) for word in neighborhood_tokens(neighborhood or "")] + _tokens(city)
            places.update(place)
            street = _Street(
                street=members[0].street,
                city=city,
                neighborhood=neighborhood,
                core=core,
                optional=frozenset(type_words + title_words),
                tokens=core | frozenset(type_words + title_words + place) | frozenset(STATE_WORDS),
                segments=tuple(members),
                addresses=sum(segment.addresses for segment in members),
                middle=_middle(members),
            )
            for word in street.tokens:
                self._postings[word].add(len(self._streets))
            self._streets.append(street)
            for segment in members:
                if segment.postal_code:
                    self._by_postal_code[segment.postal_code].append(segment)

        self._types_and_titles = frozenset(types | titles)
        self._soft = self._types_and_titles | COMPLEMENT_WORDS
        self._titles = frozenset(titles)
        self._places = frozenset(places)
        self._vocabulary = _Vocabulary(self._postings)

    def __len__(self) -> int:
        return len(self._streets)

    def search(self, query: str, limit: int = 5) -> list[GeocodedPlace]:
        """Lugares que correspondem ao texto, do mais provável ao menos. Lista vazia se nada bater."""
        text = query.strip()
        if not text or not self._streets:
            return []
        postal_code = POSTAL_CODE.search(text)
        if postal_code:
            place = self._postal_code(f"{postal_code[1]}-{postal_code[2]}")
            if place:
                return [place]
            text = text[: postal_code.start()] + text[postal_code.end():]

        parsed = self._parse(text)
        scored = self._match(parsed)
        parts = [part for part in text.split(",") if _LETTER.search(part)]
        if not scored and len(parts) > 1:
            # "Rua X, 100, Bairro Y": o bairro pode estar registrado com outro nome. Tenta só a rua.
            street_only = self._parse(parts[0])
            scored = self._match(
                _Query(street_only.required, street_only.soft, parsed.digits, street_only.street_words)
            )
        return self._resolve(scored, limit)

    def _parse(self, text: str) -> _Query:
        words = _tokens(text)
        digits = tuple(word for word in words if word.isdigit())
        required, soft = self._classify(word for word in words if not word.isdigit())
        parts = [part for part in text.split(",") if _LETTER.search(part)]
        street_words = frozenset(required)
        if len(parts) > 1:
            first_required, _ = self._classify(word for word in _tokens(parts[0]) if not word.isdigit())
            street_words = frozenset(first_required) or street_words
        return _Query(required, soft, digits, street_words)

    def _classify(self, words: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Separa as palavras obrigatórias das que só ajudam a ordenar (tipo, título, complemento)."""
        words = list(words)
        required = tuple(word for word in words if word not in self._soft)
        soft = tuple(word for word in words if word in self._soft)
        if not required:
            # "Rua Senador": o título é o próprio nome que a pessoa procura.
            required = tuple(word for word in soft if word in self._titles)
            soft = tuple(word for word in soft if word not in self._titles)
        return required, soft

    def _match(self, query: _Query) -> list[tuple[float, _Street, _Query]]:
        if not query.required:
            return []
        if not query.soft and all(word in self._places for word in query.required):
            # Só o nome de um bairro ou cidade ("Bancários", "Intermares, Cabedelo"): quem localiza o
            # bairro inteiro é o OpenStreetMap, não uma rua qualquer que tenha esse nome.
            return []
        similar_by_word = []
        candidates: set[int] | None = None
        for word in query.required:
            similar = self._vocabulary.similar(word)
            ids = set().union(*(self._postings[candidate] for candidate in similar))
            candidates = ids if candidates is None else candidates & ids
            if not candidates:
                return []
            similar_by_word.append(similar)

        typed_titles = [word for word in query.soft if word in self._titles]
        typed_types = [word for word in query.soft if word in self._types_and_titles and word not in self._titles]
        scored = []
        for street_id in candidates or ():
            street = self._streets[street_id]
            best_scores = []
            covered: set[str] = set()
            street_hit = False
            for word, similar in zip(query.required, similar_by_word, strict=True):
                in_name = [candidate for candidate in street.core if candidate in similar]
                covered.update(in_name)
                # Uma inicial solta ("M") não basta para dizer que é esta rua.
                street_hit = street_hit or (word in query.street_words and any(len(c) > 1 for c in in_name))
                if word in query.street_words:
                    # A nota vem só das palavras do nome. Contra o nome primeiro: "brasil" bate com o
                    # estado em todo endereço, mas em "Avenida Brasília" só bate pela metade.
                    best_scores.append(max((similar[c] for c in in_name), default=0.0)
                                       or max(similar.get(c, 0.0) for c in street.tokens))
            if not street_hit:
                continue  # só bateu com bairro, cidade ou uma inicial: não é esta rua
            covered.update(word for word in street.core if word in query.soft or word in query.digits)
            score = (
                sum(best_scores) / len(best_scores)
                + COVERAGE_WEIGHT * len(covered) / len(street.core)
                + TYPE_WEIGHT * _share(typed_types, street)
                + TITLE_WEIGHT * _share(typed_titles, street)
            )
            scored.append((score, street, query))
        return scored

    def _resolve(self, scored: list[tuple[float, _Street, _Query]], limit: int) -> list[GeocodedPlace]:
        if not scored:
            return []
        best = max(score for score, _, _ in scored)
        located = []
        for score, street, query in scored:
            if score < best - AMBIGUITY_MARGIN:
                continue
            number = next((int(word) for word in query.digits if word not in street.core and len(word) <= 5), None)
            segment, precision = street.locate(number)
            located.append((score, precision, street, segment, number))
        # Entre opções com notas parecidas: primeiro as que têm o número digitado (é a pista mais forte),
        # depois as da cidade principal. Com número, a faixa mais estreita é a mais confiável; sem número,
        # vale a rua com mais endereços.
        located.sort(
            key=lambda item: (
                item[1] != GeocodePrecision.ADDRESS,
                item[2].city != self._primary_city,
                -round(item[0], 6),
                item[3].number_max - item[3].number_min if item[1] == GeocodePrecision.ADDRESS else 0,
                -item[2].addresses,
                item[2].street,
                item[2].neighborhood or "",
            )
        )
        if located[0][1] == GeocodePrecision.ADDRESS:
            # Alguma rua tem o número digitado: as que não têm deixam de ser opções.
            located = [item for item in located if item[1] == GeocodePrecision.ADDRESS]

        places: list[GeocodedPlace] = []
        kept: list[tuple[str, str, Coordinates]] = []
        for _, precision, street, segment, number in located:
            same_street = (street.street, street.city)
            if any((name, city) == same_street and haversine_m(where, segment.coordinates) < SAME_PLACE_M
                   for name, city, where in kept):
                continue
            kept.append((*same_street, segment.coordinates))
            places.append(_place(street, segment, precision, number))
            if len(places) >= limit:
                break
        return places

    def _postal_code(self, postal_code: str) -> GeocodedPlace | None:
        segments = self._by_postal_code.get(postal_code)
        if not segments:
            return None
        center = _middle(segments)
        streets = {segment.street for segment in segments}
        neighborhoods: Counter[str] = Counter()
        for segment in segments:
            if segment.neighborhood:
                neighborhoods[segment.neighborhood] += segment.addresses
        neighborhood = neighborhoods.most_common(1)[0][0] if neighborhoods else None
        main = streets.pop() if len(streets) == 1 else f"CEP {postal_code}"
        parts = [main, neighborhood, center.city]
        label = ", ".join(part for part in parts if part)
        if not label.startswith("CEP"):
            label += f" (CEP {postal_code})"
        return GeocodedPlace(label, center.latitude, center.longitude, GeocodePrecision.POSTAL_CODE)


def _share(typed: Sequence[str], street: _Street) -> float:
    """Fração das palavras digitadas (tipo ou título) que a rua tem; 0 se nenhuma foi digitada."""
    if not typed:
        return 0.0
    return sum(word in street.optional or word in street.core for word in typed) / len(typed)


def _sort_key(item: tuple[tuple, list[StreetSegment]]) -> tuple:
    return tuple(part or "" for part in item[0])


def _middle(segments: Sequence[StreetSegment]) -> StreetSegment:
    """O trecho mais perto do centro (ponderado pelo número de endereços): fica sempre sobre a rua."""
    total = sum(segment.addresses for segment in segments) or 1
    center = Coordinates(
        sum(segment.latitude * segment.addresses for segment in segments) / total,
        sum(segment.longitude * segment.addresses for segment in segments) / total,
    )
    return min(segments, key=lambda segment: (haversine_m(center, segment.coordinates), segment.number_min))


def _place(street: _Street, segment: StreetSegment, precision: GeocodePrecision, number: int | None) -> GeocodedPlace:
    name = f"{street.street}, {number}" if precision == GeocodePrecision.ADDRESS else street.street
    label = ", ".join(part for part in (name, street.neighborhood, street.city) if part)
    return GeocodedPlace(label, segment.latitude, segment.longitude, precision)
