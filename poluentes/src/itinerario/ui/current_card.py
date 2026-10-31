import streamlit as st

from itinerario.domain.aqi import EPA_BANDS
from itinerario.services.air_quality_service import CurrentAirQuality

DARK_TEXT_BANDS = {"Boa", "Moderada", "Ruim p/ sensíveis"}


def render_current_card(current: CurrentAirQuality | None) -> None:
    if current is None:
        st.info("Ainda não há dados para a localização principal. Rode o backfill ou clique em “Atualizar dados agora”.")
        return
    text_color = "#111111" if current.band.label in DARK_TEXT_BANDS else "#ffffff"
    aqi_text = "—" if current.us_aqi is None else str(current.us_aqi)
    st.markdown(
        f"""
        <div style="border-radius:12px;padding:20px 24px;background:{current.band.color};color:{text_color};">
          <div style="font-size:0.95rem;font-weight:600;opacity:.85;">Ar agora em {current.location_name}</div>
          <div style="display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;">
            <span style="font-size:4rem;font-weight:700;line-height:1.1;">{aqi_text}</span>
            <span style="font-size:1.5rem;font-weight:600;">{current.band.label}</span>
          </div>
          <div style="font-size:0.95rem;">
            US AQI (EPA) · poluente dominante: <b>{current.dominant_pollutant_label}</b>
            · referência {current.measured_at:%d/%m %H:%M}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Faixas do índice EPA"):
        st.table(
            {
                "Faixa": [band.label for band in EPA_BANDS],
                "US AQI até": [str(band.upper_bound) if band.upper_bound < 10_000 else "500+" for band in EPA_BANDS],
            }
        )
