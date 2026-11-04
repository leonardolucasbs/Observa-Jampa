"""Tipos de descarte: o que cada ponto aceita e como interpretar o que a pessoa quer descartar.

A busca é semântica por vocabulário do domínio: "geladeira" é um eletrodoméstico de grande porte,
"fone de ouvido" é acessório de celular. Assim a pessoa escreve o objeto que tem em mãos, não a
categoria técnica da planilha.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from pages.pontos_descarte.domain.models import Category, DisposalPoint, MatchLevel
from pages.pontos_descarte.domain.text import (
    COMMON_STOPWORDS,
    FUZZY_THRESHOLD,
    normalize,
    phrase_score,
    tokenize,
    word_similarity,
)

WASTE_STOPWORDS = COMMON_STOPWORDS | {
    "quero", "queria", "gostaria", "preciso", "posso", "onde", "como", "descartar", "descarte", "jogar", "fora",
    "entregar", "levar", "reciclar", "reciclagem", "meu", "minha", "seu", "sua", "velho", "velha", "antigo",
    "antiga", "usado", "usada", "quebrado", "quebrada", "estragado", "estragada", "defeito", "lixo", "aparelho",
    "equipamento", "coisa", "tipo", "algum", "alguma", "isso", "esse", "essa", "uns", "umas",
}

WASTE_ABBREVIATIONS = {"cel": "celular", "note": "notebook", "tel": "telefone"}


@dataclass(frozen=True)
class WasteItem:
    """Um objeto (ou grupo de objetos) que a pessoa pode querer descartar."""

    label: str
    terms: tuple[str, ...]
    accepted_by: frozenset[Category]  # categorias de ponto que recebem este item


def _item(label: str, accepted_by: Iterable[Category], *terms: str) -> WasteItem:
    return WasteItem(label=label, terms=terms, accepted_by=frozenset(accepted_by))


WASTE_ITEMS: tuple[WasteItem, ...] = (
    _item("Pilhas e baterias", {Category.BATTERIES},
          "pilha", "bateria", "pilha recarregavel", "bateria de celular", "bateria de notebook", "bateria de relogio"),
    _item("Celular e acessórios", {Category.PHONES, Category.SMALL},
          "celular", "smartphone", "iphone", "telefone", "telefone sem fio", "telefonia", "carregador", "fone",
          "fone de ouvido", "headset", "cabo usb", "cabo", "power bank", "smartwatch", "relogio inteligente", "chip"),
    _item("Tablet", {Category.PHONES, Category.SMALL}, "tablet", "ipad"),
    _item("Cartuchos e toners", {Category.CARTRIDGES},
          "cartucho", "toner", "cartucho de impressora", "cartucho de tinta", "toner de impressora",
          "tinta de impressora"),
    _item("Eletrônico de pequeno porte", {Category.SMALL},
          "pequeno porte", "notebook", "laptop", "teclado", "mouse", "webcam", "roteador", "modem", "pendrive",
          "hd externo", "hd", "ssd", "placa", "controle remoto", "videogame", "console", "camera", "radio",
          "caixa de som", "som portatil", "secador", "secador de cabelo", "chapinha", "barbeador", "ferro de passar",
          "liquidificador", "batedeira", "mixer", "torradeira", "sanduicheira", "cafeteira", "chaleira eletrica",
          "espremedor", "processador de alimentos", "balanca", "calculadora", "brinquedo eletronico", "lanterna",
          "luminaria", "despertador", "relogio", "receptor", "decodificador", "tv box", "estabilizador", "nobreak",
          "filtro de linha", "adaptador", "fonte"),
    _item("Eletrônico de médio porte", {Category.MEDIUM},
          "medio porte", "televisao", "televisor", "tv", "tvs", "monitor", "computador", "pc", "cpu", "desktop",
          "gabinete", "impressora", "multifuncional", "scanner", "micro ondas", "microondas", "forno eletrico",
          "airfryer", "fritadeira eletrica", "aspirador", "aspirador de po", "ventilador", "climatizador",
          "aparelho de som", "micro system", "home theater", "dvd", "projetor", "purificador de agua", "bebedouro",
          "cooktop"),
    _item("Eletrodoméstico de grande porte", {Category.LARGE},
          "grande porte", "linha branca", "geladeira", "refrigerador", "freezer", "frigobar", "fogao",
          "maquina de lavar", "lavadora", "lava e seca", "tanquinho", "secadora", "lava loucas", "ar condicionado",
          "split", "forno", "adega"),
    _item("Eletrodomésticos em geral", {Category.SMALL, Category.MEDIUM, Category.LARGE},
          "eletrodomestico", "eletroportatil"),
)

# Termos que significam "qualquer eletroeletrônico": não restringem a busca.
GENERIC_TERMS: tuple[str, ...] = ("eletronico", "eletroeletronico", "eletrico", "residuo eletronico", "sucata")


def _term_tokens(text: str) -> tuple[str, ...]:
    return tuple(tokenize(text, stopwords=WASTE_STOPWORDS, abbreviations=WASTE_ABBREVIATIONS, singular=True))


# (item, palavras do termo). Item None = termo genérico.
_VOCABULARY: tuple[tuple[WasteItem | None, tuple[str, ...]], ...] = tuple(
    [(item, _term_tokens(term)) for item in WASTE_ITEMS for term in item.terms]
    + [(None, _term_tokens(term)) for term in GENERIC_TERMS]
)


@dataclass(frozen=True)
class WasteInterpretation:
    """O que entendemos do campo "O que você quer descartar?"."""

    query: str
    items: tuple[WasteItem, ...] = ()
    generic: bool = False  # a pessoa pediu "eletrônicos" em geral
    unknown_words: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not _term_tokens(self.query)

    @property
    def uses_text_fallback(self) -> bool:
        """Nada do vocabulário foi reconhecido: procura as palavras na descrição dos pontos."""
        return not self.is_empty and not self.items and not self.generic


def interpret_waste_query(query: str) -> WasteInterpretation:
    """Traduz texto livre ("celular velho e umas pilhas") em itens do vocabulário."""
    tokens = _term_tokens(query)
    if not tokens:
        return WasteInterpretation(query=query)

    candidates: list[tuple[int, float, WasteItem | None, frozenset[int]]] = []
    for item, term_tokens in _VOCABULARY:
        match = _match_term(term_tokens, tokens)
        if match:
            score, used = match
            candidates.append((len(used), score, item, used))

    # Termos mais longos e mais parecidos ganham ("forno eletrico" antes de "forno").
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1]), reverse=True)
    best_score_by_word: dict[int, float] = {}
    chosen: list[WasteItem] = []
    generic = False
    for _, score, item, used in candidates:
        already_explained = all(best_score_by_word.get(index, 0.0) >= score for index in used)
        if already_explained:
            continue
        for index in used:
            best_score_by_word[index] = max(best_score_by_word.get(index, 0.0), score)
        if item is None:
            generic = True
        elif item not in chosen:
            chosen.append(item)

    unknown = tuple(token for index, token in enumerate(tokens) if index not in best_score_by_word)
    return WasteInterpretation(query=query, items=tuple(chosen), generic=generic and not chosen, unknown_words=unknown)


def _match_term(term_tokens: tuple[str, ...], query_tokens: tuple[str, ...]) -> tuple[float, frozenset[int]] | None:
    """Todas as palavras do termo precisam aparecer (com tolerância) na busca."""
    if not term_tokens:
        return None
    used: set[int] = set()
    total = 0.0
    for term_token in term_tokens:
        scores = [(word_similarity(query_token, term_token), index) for index, query_token in enumerate(query_tokens)]
        best_score, best_index = max(scores)
        if best_score < FUZZY_THRESHOLD:
            return None
        used.add(best_index)
        total += best_score
    return total / len(term_tokens), frozenset(used)


def categories_from_description(description: str | None) -> frozenset[Category]:
    """Lê o `tipo_descarte` da planilha e devolve as categorias que o ponto aceita."""
    text = normalize(description)
    categories: set[Category] = set()
    if "pilha" in text or "bateria" in text:
        categories.add(Category.BATTERIES)
    if "celular" in text or "telefonia" in text or "carregador" in text:
        categories.add(Category.PHONES)
    if "cartucho" in text or "toner" in text:
        categories.add(Category.CARTRIDGES)
    if "pequeno" in text:
        categories.add(Category.SMALL)
    if "medio" in text:
        categories.add(Category.MEDIUM)
    if "grande" in text:
        categories.add(Category.LARGE)
    return frozenset(categories or {Category.UNSPECIFIED})


def match_level(point: DisposalPoint, interpretation: WasteInterpretation) -> MatchLevel | None:
    """Se o ponto serve para o que a pessoa quer descartar (None = não serve)."""
    if interpretation.is_empty or interpretation.generic:
        return MatchLevel.ACCEPTS
    if interpretation.items:
        if all(point.categories & item.accepted_by for item in interpretation.items):
            return MatchLevel.ACCEPTS
        if Category.UNSPECIFIED in point.categories:
            return MatchLevel.POSSIBLE
        return None
    description = tokenize(f"{point.waste_description} {point.notes or ''}", singular=True)
    return MatchLevel.ACCEPTS if phrase_score(list(_term_tokens(interpretation.query)), description) > 0 else None


EXAMPLES: tuple[str, ...] = ("pilhas", "celular", "carregador", "notebook", "TV", "impressora", "cartucho", "geladeira")
