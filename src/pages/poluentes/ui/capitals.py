from html import escape

import pandas as pd
import streamlit as st

from pages.poluentes.domain.guidance import guidance_for
from pages.poluentes.ui.theme import text_color_on


def render_capitals(current: pd.DataFrame, highlight_slug: str) -> None:
    st.subheader("E as outras capitais, como estão agora?")
    if current.empty:
        st.info("Sem dados das capitais no momento.")
        return
    st.caption("Ordenadas da melhor para a pior qualidade do ar neste momento.")
    ordered = current.sort_values("us_aqi", na_position="last")
    columns = st.columns(len(ordered))
    for column, row in zip(columns, ordered.itertuples(), strict=True):
        with column:
            st.html(_city_card(row.name, row.band_label, row.band_color, row.us_aqi, row.slug == highlight_slug))


def _city_card(name: str, band_label: str, color: str, value: float, highlighted: bool) -> str:
    guidance = guidance_for(band_label)
    title = f"📍 {escape(name)}" if highlighted else escape(name)
    index_text = "sem índice" if pd.isna(value) else f"índice {int(value)}"
    return (
        f'<div style="border-radius:12px;padding:14px 16px;background:{color};color:{text_color_on(band_label)};">'
        f'<div style="font-size:1.05rem;font-weight:{800 if highlighted else 600};">{title}</div>'
        f'<div style="font-size:1.1rem;margin-top:4px;">{guidance.icon} {guidance.name}</div>'
        f'<div style="font-size:.85rem;opacity:.85;">{index_text}</div></div>'
    )
