from datetime import timedelta

import streamlit as st

from pages.chuvas.ui import alerts_panel, data, rain_panel
from pages.chuvas.ui.formatting import format_interval

container = data.get_container()
settings = container.settings
rerun_every = timedelta(seconds=settings.ui.rerun_seconds)

st.title("Previsão de chuva e alertas meteorológicos")
st.caption(
    f"Previsão de chuva e acompanhamento dos avisos meteorológicos oficiais para {settings.location.name}. "
    f"Atualização automática, não em tempo real: a previsão é consultada no máximo a cada "
    f"{format_interval(settings.forecast.refresh_seconds)} e os avisos, a cada "
    f"{format_interval(settings.alerts.refresh_seconds)}."
)


@st.fragment(run_every=rerun_every, parallel=True)
def rain_section() -> None:
    with st.spinner("Consultando a previsão de chuva…"):
        result = data.load_rain()
    rain_panel.render_rain_panel(result, settings, container.clock())


@st.fragment(run_every=rerun_every, parallel=True)
def alerts_section() -> None:
    with st.spinner("Consultando os avisos do INMET…"):
        result = data.load_alerts()
    alerts_panel.render_alerts_panel(result, settings, container.clock())


rain_section()
alerts_section()

st.divider()
st.caption(settings.texts.attribution)
