import streamlit as st

from itinerario.domain.models import POLLUTANT_LABELS, POLLUTANTS
from itinerario.ui import charts, city_map, current_card, data, footer, sidebar

st.set_page_config(page_title="Itinerário · Qualidade do ar", page_icon="🌫️", layout="wide")

settings = data.get_container().settings
primary = settings.primary_location
state = sidebar.render_sidebar(settings.dashboard.period_options)

if state.refresh_requested:
    with st.spinner("Coletando dados da Open-Meteo..."):
        sidebar.render_refresh_feedback(data.refresh_now())

st.title("Qualidade do ar")
footer.render_model_disclaimer(settings.dashboard.disclaimer)

if not data.has_data():
    st.info("Banco vazio. Rode `uv run python -m itinerario.backfill --days 90` ou clique em “Atualizar dados agora”.")
else:
    current_card.render_current_card(data.load_current(primary))

    guideline_pollutants = tuple(settings.who_guidelines_24h)
    st.subheader(f"PM2.5 e NO₂ nos últimos {state.days} dias")
    charts.render_trend_with_guidelines(
        data.load_hourly_series(primary, state.days, guideline_pollutants),
        data.load_daily_means(primary, state.days, guideline_pollutants),
        settings.who_guidelines_24h,
    )
    st.caption("Linha tracejada: diretriz da OMS (2021) para média de 24h — compare com a média diária, não com o valor horário.")

    st.subheader("Padrão por hora do dia")
    charts.render_hourly_profile(data.load_hourly_profile(primary, state.days))

    left, right = st.columns(2)
    with left:
        st.subheader("Comparativo entre capitais")
        pollutant = st.selectbox(
            "Poluente",
            options=list(POLLUTANTS),
            format_func=lambda key: POLLUTANT_LABELS[key],
        )
        charts.render_city_comparison(data.load_city_comparison(pollutant, state.days), pollutant, primary)
    with right:
        st.subheader("Mapa · AQI atual")
        city_map.render_city_map(data.load_current_by_location())

footer.render_footer(settings.dashboard.attribution)
