from dataclasses import dataclass

import streamlit as st

from pages.pontos_descarte.domain.models import MatchLevel
from pages.pontos_descarte.domain.waste import EXAMPLES
from pages.pontos_descarte.services.search_service import PlaceInterpretation, PlaceStrategy, SearchResult
from pages.pontos_descarte.ui.formatting import format_distance


@dataclass(frozen=True)
class FilterValues:
    waste: str
    neighborhood: str
    address: str

    @property
    def any(self) -> bool:
        return bool(self.waste.strip() or self.neighborhood.strip() or self.address.strip())


def render_filters() -> FilterValues:
    waste_col, neighborhood_col, address_col = st.columns(3)
    waste = waste_col.text_input(
        "O que você quer descartar?",
        key="filter_waste",
        placeholder="ex.: pilhas, celular velho, geladeira",
        help="Escreva o objeto do seu jeito. Entendemos sinônimos e erros de digitação.",
    )
    neighborhood = neighborhood_col.text_input(
        "Bairro",
        key="filter_neighborhood",
        placeholder="ex.: Manaíra, Bancários, Centro",
        help="Não precisa ser o nome exato. Se o bairro não tiver pontos cadastrados, mostramos os mais próximos.",
    )
    address = address_col.text_input(
        "Endereço ou referência",
        key="filter_address",
        placeholder="ex.: Av. Epitácio Pessoa, Manaíra Shopping",
        help="Rua, número, CEP ou nome do lugar. Abreviações como “Av.” e “R.” valem.",
    )
    return FilterValues(waste=waste, neighborhood=neighborhood, address=address)


def render_interpretation(result: SearchResult) -> None:
    """Mostra o que a busca entendeu de cada campo, para a pessoa saber por que viu aqueles pontos."""
    notes = [_waste_note(result), _place_note("Bairro", result.neighborhood), _place_note("Endereço", result.address)]
    notes = [note for note in notes if note]
    if notes:
        st.caption("  \n".join(notes))

    if result.waste.uses_text_fallback and not result.matches:
        st.warning(
            f"Não reconhecemos “{result.waste.query}”. Tente algo como: {', '.join(EXAMPLES)}.",
            icon=":material/help:",
        )
    elif len(result.waste.items) > 1 and not any(m.level == MatchLevel.ACCEPTS for m in result.matches):
        st.info(
            "Nenhum ponto confirma receber todos esses itens juntos. Os pontos abaixo recebem eletroeletrônicos "
            "sem detalhar quais; vale buscar um item por vez.",
            icon=":material/info:",
        )

    for place in (result.neighborhood, result.address):
        if place and place.strategy == PlaceStrategy.NOT_FOUND:
            st.warning(f"Não encontramos “{place.query}” em João Pessoa e região.", icon=":material/location_off:")
        elif place and place.strategy == PlaceStrategy.UNAVAILABLE:
            st.warning(
                f"O serviço de mapas não respondeu, então ignoramos “{place.query}” por enquanto.",
                icon=":material/cloud_off:",
            )


def _waste_note(result: SearchResult) -> str | None:
    waste = result.waste
    if waste.is_empty:
        return None
    if waste.generic:
        return "**Descarte:** qualquer eletroeletrônico"
    if waste.items:
        labels = " + ".join(item.label for item in waste.items)
        ignored = f" (ignoramos: {', '.join(waste.unknown_words)})" if waste.unknown_words else ""
        return f"**Descarte:** entendemos {labels}{ignored}"
    return f"**Descarte:** procurando “{waste.query}” na descrição dos pontos"


def _place_note(label: str, place: PlaceInterpretation | None) -> str | None:
    if place is None:
        return None
    if place.strategy == PlaceStrategy.TEXT:
        if place.matched_names:
            return f"**{label}:** {', '.join(place.matched_names)}"
        return f"**{label}:** pontos com “{place.query}” no endereço ou no nome"
    if place.strategy == PlaceStrategy.NEARBY and place.reference and place.radius_m:
        return (
            f"**{label}:** nenhum ponto cadastrado com esse nome; mostrando os pontos a até "
            f"{format_distance(place.radius_m)} de {place.reference.label}"
        )
    return None
