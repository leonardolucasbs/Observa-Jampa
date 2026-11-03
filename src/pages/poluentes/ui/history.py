import pandas as pd
import streamlit as st

from pages.poluentes.domain.aqi import UNKNOWN_BAND
from pages.poluentes.domain.guidance import guidance_for
from pages.poluentes.ui.theme import text_color_on

WEEKDAYS = ("D", "S", "T", "Q", "Q", "S", "S")
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def render_history(daily: pd.DataFrame) -> None:
    if (daily["band_label"] == UNKNOWN_BAND.label).all():
        st.info("Ainda não há dados suficientes para este período.")
        return
    st.html(_calendar_html(daily))
    st.caption(
        "Cada dia tem a cor da mediana das classificações da qualidade do ar hora a hora. "
        "Passe o mouse (ou toque) num dia para ver o detalhe."
    )


def _calendar_html(daily: pd.DataFrame) -> str:
    first = daily.index[0]
    offset = (first.weekday() + 1) % 7  # semana começando no domingo
    header = "".join(f'<div style="text-align:center;font-size:.7rem;opacity:.7;">{day}</div>' for day in WEEKDAYS)
    blanks = "<div></div>" * offset
    last_position = len(daily) - 1
    cells = "".join(
        _day_cell(date, row, is_first=index == 0, is_today=index == last_position)
        for index, (date, row) in enumerate(daily.iterrows())
    )
    return (
        '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;max-width:300px;">'
        f"{header}{blanks}{cells}</div>"
    )


def _day_cell(date: pd.Timestamp, row: pd.Series, is_first: bool, is_today: bool) -> str:
    band_label, color, hours = row["band_label"], row["band_color"], int(row["hours"])
    guidance = guidance_for(band_label)
    label = f"{date.day}/{MONTHS[date.month - 1]}" if is_first or date.day == 1 else str(date.day)
    if is_today:
        label = f'<span>{label}<span style="display:block;font-size:.6rem;font-weight:400;">hoje</span></span>'
    detail = "" if hours == 0 else f" (mediana de {hours} {'hora' if hours == 1 else 'horas'})"
    title = f"{date:%d/%m}: {guidance.name}{detail}"
    if band_label == UNKNOWN_BAND.label:
        style = "background:rgba(128,128,128,.15);opacity:.7;"
    else:
        style = f"background:{color};color:{text_color_on(band_label)};"
    return (
        f'<div title="{title}" style="{style}aspect-ratio:1;border-radius:6px;display:flex;'
        "align-items:center;justify-content:center;text-align:center;font-size:.72rem;font-weight:600;"
        f'line-height:1.1;">{label}</div>'
    )
