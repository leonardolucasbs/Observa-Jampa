"""Modal com os detalhes de um ponto (ou de todos os pontos de um mesmo local)."""

from collections.abc import Sequence

import streamlit as st

from pages.pontos_descarte.domain.geo import haversine_m
from pages.pontos_descarte.domain.models import CATEGORY_LABELS, Category, DisposalPoint, GeocodedPlace
from pages.pontos_descarte.ui.formatting import (
    format_distance,
    full_address,
    google_maps_directions_url,
    google_maps_place_url,
    whatsapp_url,
)

ROUTE_TARGET_KEY = "route_target_id"

# verificar_no_maps da planilha → (texto, cor do selo)
COORDINATE_CHECKS = {
    "Conferido (valor informado)": ("Localização conferida", "green"),
    "Menor risco": ("Localização aproximada, obtida pelo endereço", "orange"),
    "Em seguida": ("Localização aproximada, ainda não conferida", "orange"),
    "Coordenada original (não conferida)": ("Localização da fonte original, não conferida", "gray"),
}

CATEGORY_ORDER = list(Category)


def is_new_selection(widget: str, value: str | None) -> bool:
    """Evita reabrir o modal a cada execução enquanto o mesmo item continua selecionado."""
    state_key = f"_last_selection_{widget}"
    if st.session_state.get(state_key) == value:
        return False
    st.session_state[state_key] = value
    return value is not None


def show_details(points: Sequence[DisposalPoint], origin: GeocodedPlace | None, route_service: str | None) -> None:
    _details_dialog(tuple(points), origin, route_service)


@st.dialog("Ponto de descarte", width="large")
def _details_dialog(points: tuple[DisposalPoint, ...], origin: GeocodedPlace | None, route_service: str | None):
    if len(points) == 1:
        _render_point(points[0], origin, route_service)
        return
    st.caption(f"{len(points)} pontos de coleta neste mesmo local")
    for tab, point in zip(st.tabs([_short_name(point) for point in points]), points, strict=True):
        with tab:
            _render_point(point, origin, route_service)


def _render_point(point: DisposalPoint, origin: GeocodedPlace | None, route_service: str | None) -> None:
    st.subheader(point.name, anchor=False)
    categories = sorted(point.categories, key=CATEGORY_ORDER.index)
    st.markdown(
        " ".join(
            f":{'orange' if category == Category.UNSPECIFIED else 'blue'}-badge[{CATEGORY_LABELS[category]}]"
            for category in categories
        )
    )

    st.markdown("**O que recebe**")
    st.write(point.waste_description)

    st.markdown("**Endereço**")
    st.write(full_address(point))
    estimated = [
        label
        for label, flag in (("endereço", point.address_estimated), ("bairro", point.neighborhood_estimated))
        if flag
    ]
    if estimated:
        what = " e ".join(estimated).capitalize()
        approximate = "aproximados, completados" if len(estimated) > 1 else "aproximado, completado"
        st.caption(f"{what} {approximate} pelo OpenStreetMap a partir da localização do ponto.")

    if point.notes:
        st.markdown("**Observações**")
        st.write(point.notes)

    contacts = _contacts(point)
    if contacts:
        st.markdown("**Contato**")
        st.markdown("  \n".join(contacts))

    check_label, check_color = COORDINATE_CHECKS.get(point.coordinates_check or "", ("Localização não conferida", "gray"))
    distance = (
        f" · {format_distance(haversine_m(origin.coordinates, point.coordinates))} de você em linha reta" if origin else ""
    )
    st.markdown(f":{check_color}-badge[{check_label}]{distance}")
    if point.coordinates_status:
        st.caption(f"Origem da coordenada: {point.coordinates_status}.")

    st.space("small")
    maps_col, directions_col, route_col = st.columns(3)
    maps_col.link_button(
        "Ver no Google Maps", google_maps_place_url(point), icon=":material/map:", width="stretch"
    )
    directions_col.link_button(
        "Como chegar",
        google_maps_directions_url(origin.coordinates if origin else None, point, route_service),
        icon=":material/directions:",
        width="stretch",
    )
    if route_col.button(
        "Rota no mapa",
        key=f"route_to_{point.id}",
        icon=":material/route:",
        type="primary",
        width="stretch",
        disabled=origin is None,
        help=None if origin else "Informe sua localização no painel “Rota até o ponto mais próximo”.",
    ):
        st.session_state[ROUTE_TARGET_KEY] = point.id
        st.rerun()

    if point.source:
        st.caption(f"Fonte: {point.source}")


def _contacts(point: DisposalPoint) -> list[str]:
    contacts = []
    if point.phone:
        contacts.append(f":material/call: [{point.phone}](tel:{''.join(c for c in point.phone if c.isdigit())})")
    if point.whatsapp:
        contacts.append(f":material/chat: [WhatsApp {point.whatsapp}]({whatsapp_url(point.whatsapp)})")
    if point.email:
        contacts.append(f":material/mail: [{point.email}](mailto:{point.email})")
    return contacts


def _short_name(point: DisposalPoint) -> str:
    """"PEV GM&C - DROGASIL - MANAIRA 2" → "DROGASIL - MANAIRA 2" (o nome do programa fica no detalhe)."""
    name = point.name
    for prefix in ("PEV ABREE - ", "PEV GM&C - ", "PEV Reciclus - ", "PEV GREEN ELETRON - ", "PEV - "):
        if name.upper().startswith(prefix.upper()):
            name = name[len(prefix):]
            break
    return name if len(name) <= 32 else name[:30] + "…"
