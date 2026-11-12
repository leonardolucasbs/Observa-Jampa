from datetime import datetime

import pandas as pd
import streamlit as st

from pages.chuvas.config import Settings
from pages.chuvas.domain.models import Intensity, RainOutlook, RainTotal
from pages.chuvas.domain.rain import INTENSITY_FLOORS, RAIN_THRESHOLD_MM, is_rainy
from pages.chuvas.services.cache import Snapshot, SourceUnavailable
from pages.chuvas.ui.formatting import (
    format_day,
    format_days,
    format_hour,
    format_mm,
    format_mm_per_hour,
    format_period,
)
from pages.chuvas.ui.source_status import render_source_status, render_stale_warning, render_unavailable

SOURCE = "Open-Meteo (modelos de previsão do tempo)"
INTENSITY_BADGE_COLOR = {
    Intensity.FRACA: "green",
    Intensity.MODERADA: "orange",
    Intensity.FORTE: "red",
    Intensity.MUITO_FORTE: "red",
}


def render_rain_panel(result: Snapshot[RainOutlook] | SourceUnavailable, settings: Settings, now: datetime) -> None:
    st.subheader("Vai chover?", anchor=False)
    if isinstance(result, SourceUnavailable):
        render_unavailable(result, SOURCE, "a previsão de chuva")
        return
    render_stale_warning(result, now)

    outlook = result.value
    st.caption(_how_to_read())
    today_col, tomorrow_col, week_col = st.columns(3)
    with today_col:
        _render_day_card("Hoje", outlook.today)
    with tomorrow_col:
        _render_day_card("Amanhã", outlook.tomorrow)
    with week_col:
        _render_week_card(outlook)
    st.caption(f"ℹ️ {settings.texts.rain_disclaimer}")
    render_source_status(result, SOURCE, settings.forecast.refresh_seconds, now)
    _render_daily_table(outlook)


def _render_day_card(title: str, total: RainTotal) -> None:
    with st.container(border=True, height="stretch"):
        st.markdown(f"**{title}** · {format_period(total.start, total.end)}")
        st.markdown(f"#### {_day_verdict(total)}")
        if total.intensity is not None:
            st.badge(f"Chuva {total.intensity}", color=INTENSITY_BADGE_COLOR[total.intensity])
        st.metric("Volume previsto", format_mm(total.precipitation_mm))
        if total.precipitation_mm is None:
            st.caption("Sem dado de previsão para este dia.")
        elif total.will_rain is False:
            st.caption(f"Total abaixo de {format_mm(RAIN_THRESHOLD_MM)}: no máximo garoa isolada.")
        elif total.will_rain and total.intensity is None:
            st.caption("A fonte não informou a chuva por hora, então a intensidade não foi calculada.")
        if total.peak_mm_per_hour is not None and total.will_rain:
            st.caption(f"Pico de {format_mm_per_hour(total.peak_mm_per_hour)} às {format_hour(total.peak_at)}.")
        if total.probability_max_pct is not None:
            st.caption(
                f"Probabilidade de chuva: até {total.probability_max_pct}% em alguma hora do dia (não é volume)."
            )
        if total.from_hourly:
            st.caption("Total calculado pela soma das previsões horárias.")


def _render_week_card(outlook: RainOutlook) -> None:
    week = outlook.week
    with st.container(border=True, height="stretch"):
        st.markdown(f"**Próximos 7 dias** · {format_period(week.start, week.end)}")
        st.markdown(f"#### {_week_verdict(outlook)}")
        st.metric("Volume previsto na semana", format_mm(week.precipitation_mm))
        if week.missing_days:
            st.caption(
                f"Parcial: soma de {week.days - len(week.missing_days)} de {week.days} dias. "
                f"Sem previsão para {format_days(week.missing_days)}."
            )
        wettest = _wettest_day(outlook)
        if wettest is not None:
            st.caption(f"Dia mais chuvoso: {format_day(wettest.day)}, com {format_mm(wettest.precipitation_mm)}.")
        st.caption("Soma da chuva prevista de cada dia, hoje incluído.")


def _day_verdict(total: RainTotal) -> str:
    if total.will_rain is None:
        return "❔ Sem previsão"
    if not total.will_rain:
        return "☀️ Não deve chover"
    return "🌧️ Vai chover"


def _week_verdict(outlook: RainOutlook) -> str:
    if outlook.known_days == 0:
        return "❔ Sem previsão"
    if outlook.rainy_days == 0:
        return "☀️ Nenhum dia com chuva"
    return f"🌧️ Chove em {outlook.rainy_days} de {outlook.known_days} dias"


def _wettest_day(outlook: RainOutlook):
    known = [entry for entry in outlook.daily if entry.precipitation_mm is not None]
    if not known:
        return None
    wettest = max(known, key=lambda entry: entry.precipitation_mm)
    return wettest if is_rainy(wettest.precipitation_mm) else None


def _how_to_read() -> str:
    """Legenda gerada a partir da mesma escala usada para classificar a intensidade."""
    floors = sorted(INTENSITY_FLOORS)  # do mais fraco para o mais forte
    parts = []
    for index, (floor, intensity) in enumerate(floors):
        if index == 0:
            parts.append(f"{intensity} (até {_number(floors[index + 1][0])} mm/h)")
        elif index == len(floors) - 1:
            parts.append(f"{intensity} (acima de {_number(floor)} mm/h)")
        else:
            parts.append(f"{intensity} ({_number(floor)} a {_number(floors[index + 1][0])} mm/h)")
    return (
        f"Vai chover quando a previsão do dia chega a {format_mm(RAIN_THRESHOLD_MM)}. "
        "A intensidade vem da hora mais forte do dia: " + ", ".join(parts) + ". "
        "A escala é uma referência usual, não um critério oficial."
    )


def _number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def _render_daily_table(outlook: RainOutlook) -> None:
    if not outlook.daily:
        return
    with st.expander("Previsão dia a dia"):
        st.dataframe(
            pd.DataFrame(
                {
                    "Dia": [format_day(entry.day) for entry in outlook.daily],
                    "Vai chover?": [_yes_no(entry.precipitation_mm) for entry in outlook.daily],
                    "Chuva prevista": [format_mm(entry.precipitation_mm) for entry in outlook.daily],
                    "Probabilidade máxima": [
                        "—" if entry.probability_max_pct is None else f"{entry.probability_max_pct}%"
                        for entry in outlook.daily
                    ],
                }
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption("A probabilidade é a chance de chover na hora mais provável do dia; ela não soma entre os dias.")


def _yes_no(precipitation_mm: float | None) -> str:
    rainy = is_rainy(precipitation_mm)
    return "—" if rainy is None else ("Sim" if rainy else "Não")
