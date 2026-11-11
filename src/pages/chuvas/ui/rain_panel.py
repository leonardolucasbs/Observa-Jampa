from datetime import datetime

import pandas as pd
import streamlit as st

from pages.chuvas.config import Settings
from pages.chuvas.domain.models import RainOutlook, RainTotal
from pages.chuvas.services.cache import Snapshot, SourceUnavailable
from pages.chuvas.ui.formatting import format_day, format_days, format_mm, format_period
from pages.chuvas.ui.source_status import render_source_status, render_stale_warning, render_unavailable

SOURCE = "Open-Meteo (modelos de previsão do tempo)"


def render_rain_panel(result: Snapshot[RainOutlook] | SourceUnavailable, settings: Settings, now: datetime) -> None:
    st.subheader("Chuva prevista", anchor=False)
    if isinstance(result, SourceUnavailable):
        render_unavailable(result, SOURCE, "a previsão de chuva")
        return
    render_stale_warning(result, now)

    outlook = result.value
    today_col, tomorrow_col, week_col = st.columns(3)
    with today_col:
        _render_card("Hoje", "Chuva prevista", outlook.today, "dia inteiro, de 0h a 24h")
    with tomorrow_col:
        _render_card("Amanhã", "Chuva prevista", outlook.tomorrow, "dia inteiro, de 0h a 24h")
    with week_col:
        _render_card(
            "Próximos 7 dias", "Acumulado previsto", outlook.week, "soma da chuva prevista de cada dia, hoje incluído"
        )
    st.caption(f"ℹ️ {settings.texts.rain_disclaimer}")
    render_source_status(result, SOURCE, settings.forecast.refresh_seconds, now)
    _render_daily_table(outlook)


def _render_card(title: str, label: str, total: RainTotal, scope: str) -> None:
    with st.container(border=True, height="stretch"):
        st.metric(f"{title} · {label}", format_mm(total.precipitation_mm))
        st.caption(f"**{format_period(total.start, total.end)}** · {scope}")
        if total.precipitation_mm is None:
            st.caption("Sem dado de previsão para este período.")
        elif total.missing_days:
            st.caption(
                f"Parcial: soma de {total.days - len(total.missing_days)} de {total.days} dias. "
                f"Sem previsão para {format_days(total.missing_days)}."
            )
        if total.probability_max_pct is not None:
            st.caption(
                f"Probabilidade de chuva: até {total.probability_max_pct}% em alguma hora do dia (não é volume)."
            )
        if total.from_hourly:
            st.caption("Total calculado pela soma das previsões horárias.")


def _render_daily_table(outlook: RainOutlook) -> None:
    if not outlook.daily:
        return
    with st.expander("Previsão dia a dia"):
        st.dataframe(
            pd.DataFrame(
                {
                    "Dia": [format_day(entry.day) for entry in outlook.daily],
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
