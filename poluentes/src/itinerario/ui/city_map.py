import pandas as pd
import pydeck as pdk
import streamlit as st


def render_city_map(current: pd.DataFrame) -> None:
    if current.empty:
        st.info("Sem dados para o mapa.")
        return
    points = current.assign(
        fill=current["band_color"].map(_hex_to_rgba),
        aqi_text=current["us_aqi"].map(lambda value: "—" if pd.isna(value) else str(int(value))),
    )[["name", "latitude", "longitude", "fill", "aqi_text", "band_label"]]
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=points,
        get_position="[longitude, latitude]",
        get_fill_color="fill",
        get_line_color=[40, 40, 40, 220],
        line_width_min_pixels=1.5,
        stroked=True,
        radius_min_pixels=9,
        radius_max_pixels=30,
        get_radius=60_000,
        pickable=True,
    )
    view = pdk.ViewState(latitude=-13.5, longitude=-40.0, zoom=3.6)
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            tooltip={"text": "{name}\nUS AQI {aqi_text} · {band_label}"},
        ),
        height=440,
    )
    st.caption("Cor do ponto = faixa EPA do US AQI mais recente de cada capital.")


def _hex_to_rgba(color: str) -> list[int]:
    value = color.lstrip("#")
    return [int(value[i : i + 2], 16) for i in (0, 2, 4)] + [230]
