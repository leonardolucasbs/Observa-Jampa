import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from pages.poluentes.domain.models import POLLUTANT_LABELS, POLLUTANTS
from pages.poluentes.ui.theme import GRID, GUIDELINE, MUTED_SERIES, PRIMARY_SERIES, SECONDARY_SERIES

UNIT = "µg/m³"


def render_trend_with_guidelines(
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
    guidelines: dict[str, float],
) -> None:
    pollutants = list(guidelines)
    if hourly.empty:
        st.info("Sem dados no período.")
        return
    columns = st.columns(len(pollutants))
    for column, pollutant in zip(columns, pollutants, strict=True):
        with column:
            st.plotly_chart(_trend_figure(hourly, daily, pollutant, guidelines[pollutant]), width="stretch")


def _trend_figure(hourly: pd.DataFrame, daily: pd.DataFrame, pollutant: str, guideline: float) -> go.Figure:
    label = POLLUTANT_LABELS[pollutant]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=hourly["measured_at"],
            y=hourly[pollutant],
            name="Horário",
            mode="lines",
            line={"color": MUTED_SERIES, "width": 1},
            hovertemplate=f"%{{x|%d/%m %H:%M}}<br>{label}: %{{y:.1f}} {UNIT}<extra>Horário</extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=daily.index + pd.Timedelta(hours=12),
            y=daily[pollutant],
            name="Média diária",
            mode="lines+markers",
            line={"color": PRIMARY_SERIES, "width": 2},
            marker={"size": 6},
            hovertemplate=f"%{{x|%d/%m}}<br>Média 24h: %{{y:.1f}} {UNIT}<extra></extra>",
        )
    )
    figure.add_hline(
        y=guideline,
        line={"color": GUIDELINE, "dash": "dash", "width": 1.5},
        annotation_text=f"OMS 24h: {guideline:g}",
        annotation_position="top left",
    )
    figure.update_layout(
        title=f"{label} ({UNIT})",
        hovermode="x unified",
        legend={"orientation": "h", "y": -0.18},
        margin={"l": 10, "r": 10, "t": 50, "b": 10},
        height=360,
    )
    figure.update_yaxes(gridcolor=GRID, rangemode="tozero")
    figure.update_xaxes(showgrid=False)
    return figure


def render_hourly_profile(profile: pd.DataFrame) -> None:
    if profile.dropna(how="all").empty:
        st.info("Sem dados no período.")
        return
    rows = 2
    cols = (len(POLLUTANTS) + 1) // rows
    figure = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=[f"{POLLUTANT_LABELS[p]} ({UNIT})" for p in POLLUTANTS],
        horizontal_spacing=0.06,
        vertical_spacing=0.18,
    )
    for index, pollutant in enumerate(POLLUTANTS):
        figure.add_trace(
            go.Scatter(
                x=profile.index,
                y=profile[pollutant],
                mode="lines",
                line={"color": PRIMARY_SERIES, "width": 2},
                name=POLLUTANT_LABELS[pollutant],
                hovertemplate="%{x}h: %{y:.1f}<extra>" + POLLUTANT_LABELS[pollutant] + "</extra>",
            ),
            row=index // cols + 1,
            col=index % cols + 1,
        )
    figure.update_xaxes(tickvals=[0, 6, 12, 18, 23], showgrid=False)
    figure.update_yaxes(gridcolor=GRID, rangemode="tozero")
    figure.update_layout(showlegend=False, height=480, margin={"l": 10, "r": 10, "t": 40, "b": 10})
    st.plotly_chart(figure, width="stretch")


def render_city_comparison(comparison: pd.DataFrame, pollutant: str, highlight_slug: str) -> None:
    if comparison.empty:
        st.info("Sem dados no período.")
        return
    label = POLLUTANT_LABELS[pollutant]
    ordered = comparison.sort_values(pollutant)
    colors = [PRIMARY_SERIES if slug == highlight_slug else MUTED_SERIES for slug in ordered["slug"]]
    figure = go.Figure(
        go.Bar(
            x=ordered[pollutant],
            y=ordered["name"],
            orientation="h",
            marker={"color": colors},
            text=ordered[pollutant].map(lambda value: f"{value:.1f}"),
            textposition="outside",
            hovertemplate="%{y}: %{x:.2f} " + UNIT + "<extra></extra>",
        )
    )
    figure.update_layout(
        title=f"Média de {label} no período ({UNIT})",
        height=80 + 60 * len(ordered),
        margin={"l": 10, "r": 40, "t": 50, "b": 10},
        bargap=0.35,
    )
    figure.update_xaxes(gridcolor=GRID, rangemode="tozero")
    st.plotly_chart(figure, width="stretch")
