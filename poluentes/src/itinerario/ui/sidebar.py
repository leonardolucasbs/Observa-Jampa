from dataclasses import dataclass

import streamlit as st

from itinerario.etl.pipeline import IngestionResult


@dataclass(frozen=True)
class SidebarState:
    days: int
    refresh_requested: bool


def render_sidebar(period_options: tuple[int, ...]) -> SidebarState:
    with st.sidebar:
        st.header("Itinerário · Ar")
        days = st.radio(
            "Período",
            options=list(period_options),
            index=len(period_options) - 1,
            format_func=lambda value: f"{value} dias",
        )
        refresh = st.button("Atualizar dados agora", type="primary", width="stretch")
    return SidebarState(days=int(days), refresh_requested=refresh)


def render_refresh_feedback(outcome: IngestionResult | str) -> None:
    if isinstance(outcome, str):
        st.sidebar.error(f"Não foi possível atualizar agora. Os dados já salvos continuam disponíveis.\n\n{outcome}")
    else:
        st.sidebar.success(f"{outcome.upserted} registros atualizados.")
