import streamlit as st

from itinerario.etl.pipeline import IngestionResult


def render_sidebar() -> bool:
    """Desenha a barra lateral; devolve True quando pedem para atualizar os dados."""
    with st.sidebar:
        st.header("Itinerário · Ar")
        return st.button("Atualizar dados agora", type="primary", width="stretch")


def render_refresh_feedback(outcome: IngestionResult | str) -> None:
    if isinstance(outcome, str):
        st.sidebar.error(f"Não foi possível atualizar agora. Os dados já salvos continuam disponíveis.\n\n{outcome}")
    else:
        st.sidebar.success(f"{outcome.upserted} registros atualizados.")
