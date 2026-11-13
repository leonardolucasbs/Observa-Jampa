"""Painel "Rota até o ponto mais próximo": origem (GPS ou endereço), meio de transporte e resultado."""

import uuid
from dataclasses import dataclass

import streamlit as st

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.config import RoutingConfig
from pages.pontos_descarte.domain.geo import haversine_m
from pages.pontos_descarte.domain.models import Coordinates, GeocodedPlace, MatchLevel
from pages.pontos_descarte.services.routing_service import RouteResult
from pages.pontos_descarte.services.search_service import SearchResult
from pages.pontos_descarte.ui import data, geolocation
from pages.pontos_descarte.ui.details import ROUTE_TARGET_KEY
from pages.pontos_descarte.ui.formatting import (
    format_distance,
    format_duration,
    full_address,
    google_maps_directions_url,
    precision_hint,
)

ORIGIN_KEY = "route_origin"
CANDIDATES_KEY = "route_origin_candidates"  # outros lugares com o nome digitado ("Você quis dizer?")
CANDIDATE_CHOICE_KEY = "route_origin_choice"
GEO_REQUEST_KEY = "geo_request_id"
GPS = "Usar GPS"
TYPED = "Digitar endereço"
FAR_AWAY_M = 60_000  # origem a mais de 60 km do centro de João Pessoa provavelmente está errada
CITY_CENTER = Coordinates(-7.12, -34.87)


@dataclass(frozen=True)
class RoutePanelState:
    origin: GeocodedPlace | None
    route: RouteResult | None
    service: str | None  # serviço OSRM do meio de transporte escolhido
    show_destination_details: bool = False


def render_route_panel(waste_only: SearchResult, routing: RoutingConfig) -> RoutePanelState:
    """`waste_only` é a busca só pelo tipo de descarte: bairro e endereço não limitam a rota."""
    with st.container(border=True):
        st.subheader("Rota até o ponto mais próximo", anchor=False)
        st.caption(_waste_caption(waste_only))
        origin = _render_origin_picker()
        if origin is None:
            return RoutePanelState(origin=None, route=None, service=None)

        profile = st.segmented_control(
            "Como você vai?", list(routing.profiles), default=next(iter(routing.profiles)), key="route_profile"
        ) or next(iter(routing.profiles))
        service = routing.profiles[profile]
        include_unconfirmed = st.toggle(
            "Incluir pontos que não detalham o que recebem",
            key="route_include_unconfirmed",
            disabled=not waste_only.waste.items,
            help="Esses pontos recebem eletroeletrônicos, mas é preciso confirmar se aceitam o seu item.",
        )
        route = _compute_route(origin, waste_only, profile, include_unconfirmed)
        show_details = _render_route_result(route, origin, service, profile)
        return RoutePanelState(origin=origin, route=route, service=service, show_destination_details=show_details)


def _waste_caption(waste_only: SearchResult) -> str:
    waste = waste_only.waste
    if waste.items:
        what = " + ".join(item.label.lower() for item in waste.items)
        return f"Procurando o ponto mais perto que recebe **{what}** (do campo “O que você quer descartar?”)."
    return "Considera qualquer ponto. Para filtrar pelo que você vai descartar, preencha “O que você quer descartar?”."


def _render_origin_picker() -> GeocodedPlace | None:
    origin: GeocodedPlace | None = st.session_state.get(ORIGIN_KEY)
    if origin:
        info_col, clear_col = st.columns([4, 1], vertical_alignment="center")
        info_col.markdown(f":red[:material/location_on:] **Saindo de:** {origin.label}")
        if clear_col.button("Trocar", key="clear_origin", width="stretch"):
            _set_origin(None)
            st.rerun()
        if hint := precision_hint(origin):
            st.caption(hint[:1].upper() + hint[1:] + ".")
        _render_other_candidates()
        return origin

    source = st.segmented_control("Sua localização", [GPS, TYPED], default=GPS, key="origin_source") or GPS
    if source == GPS:
        if st.button("Usar minha localização atual", icon=":material/my_location:", type="primary", width="stretch"):
            st.session_state[GEO_REQUEST_KEY] = uuid.uuid4().hex
        request_id = st.session_state.get(GEO_REQUEST_KEY)
        if request_id:
            outcome = geolocation.request_position(request_id)
            if outcome.finished:
                st.session_state.pop(GEO_REQUEST_KEY, None)
            if outcome.error:
                st.warning(outcome.error, icon=":material/location_disabled:")
            if outcome.position:
                accuracy = f" (±{format_distance(outcome.position.accuracy_m)})" if outcome.position.accuracy_m else ""
                return _set_origin(
                    GeocodedPlace(f"sua localização atual{accuracy}", outcome.position.latitude, outcome.position.longitude)
                )
        st.caption("O navegador vai pedir permissão. A localização fica só nesta sessão.")
        return None

    with st.form("origin_form", border=False, enter_to_submit=True):
        typed = st.text_input("Seu endereço", placeholder="ex.: Rua das Trincheiras, 100, Jaguaribe")
        submitted = st.form_submit_button("Buscar endereço", icon=":material/search:", width="stretch")
    if submitted and typed.strip():
        try:
            places = data.geocode_candidates(typed)
        except ServiceError:
            st.warning("O serviço de mapas não respondeu. Tente de novo em instantes.", icon=":material/cloud_off:")
            return None
        if not places:
            st.warning("Não encontramos esse endereço em João Pessoa e região.", icon=":material/location_off:")
            return None
        # Já usa o mais provável; se houver outros com o mesmo nome, a pessoa troca na lista.
        _set_origin(places[0], places)
        st.rerun()
    return None


def _render_other_candidates() -> None:
    """Lista os outros lugares com o nome digitado, para trocar a origem sem digitar de novo."""
    candidates: tuple[GeocodedPlace, ...] = st.session_state.get(CANDIDATES_KEY) or ()
    if len(candidates) < 2:
        return
    st.selectbox(
        "Não é esse lugar? Outros com esse nome",
        range(len(candidates)),
        format_func=lambda index: candidates[index].label,
        key=CANDIDATE_CHOICE_KEY,
        on_change=_use_chosen_candidate,
    )


def _use_chosen_candidate() -> None:
    candidates = st.session_state.get(CANDIDATES_KEY) or ()
    index = st.session_state.get(CANDIDATE_CHOICE_KEY)
    if index is not None and index < len(candidates):
        st.session_state[ORIGIN_KEY] = candidates[index]
        st.session_state.pop(ROUTE_TARGET_KEY, None)


def _set_origin(
    origin: GeocodedPlace | None, candidates: tuple[GeocodedPlace, ...] = ()
) -> GeocodedPlace | None:
    st.session_state[ORIGIN_KEY] = origin
    st.session_state[CANDIDATES_KEY] = candidates
    st.session_state.pop(CANDIDATE_CHOICE_KEY, None)
    st.session_state.pop(ROUTE_TARGET_KEY, None)
    return origin


def _compute_route(
    origin: GeocodedPlace, waste_only: SearchResult, profile: str, include_unconfirmed: bool
) -> RouteResult | None:
    target_id = st.session_state.get(ROUTE_TARGET_KEY)
    with st.spinner("Calculando a rota…"):
        if target_id is not None:
            return data.route_to(origin.latitude, origin.longitude, target_id, profile)
        allowed = {MatchLevel.ACCEPTS, MatchLevel.POSSIBLE} if include_unconfirmed else {MatchLevel.ACCEPTS}
        candidates = tuple(match.point.id for match in waste_only.matches if match.level in allowed)
        return data.nearest_route(origin.latitude, origin.longitude, candidates, profile)


def _render_route_result(route: RouteResult | None, origin: GeocodedPlace, service: str, profile: str) -> bool:
    if haversine_m(origin.coordinates, CITY_CENTER) > FAR_AWAY_M:
        st.warning("Sua localização parece estar fora da região de João Pessoa.", icon=":material/travel_explore:")
    if route is None:
        st.info("Nenhum ponto recebe esse tipo de descarte. Tente incluir os pontos que não detalham o que recebem.")
        return False

    chosen = st.session_state.get(ROUTE_TARGET_KEY) is not None
    st.markdown(f"{'**Destino escolhido por você**' if chosen else '**Ponto mais próximo**'}  \n### {route.point.name}")
    st.caption(full_address(route.point))
    distance_col, time_col = st.columns(2)
    distance_col.metric("Distância", format_distance(route.distance_m), border=True)
    time_col.metric(
        f"Tempo ({profile.lower()})",
        format_duration(route.duration_s) if route.duration_s is not None else "—",
        border=True,
    )
    if route.straight_line:
        st.warning(
            "O serviço de rotas não respondeu: mostramos a distância em linha reta. "
            "Use “Abrir no Google Maps” para o trajeto.",
            icon=":material/cloud_off:",
        )

    details_col, maps_col = st.columns(2)
    show_details = details_col.button("Ver detalhes", icon=":material/info:", width="stretch", key="route_details")
    maps_col.link_button(
        "Abrir no Google Maps",
        google_maps_directions_url(origin.coordinates, route.point, service),
        icon=":material/directions:",
        width="stretch",
    )
    if chosen and st.button("Voltar para o mais próximo", icon=":material/near_me:", width="stretch"):
        st.session_state.pop(ROUTE_TARGET_KEY, None)
        st.rerun()
    return show_details
