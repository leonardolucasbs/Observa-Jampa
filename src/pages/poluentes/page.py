from datetime import timedelta

import streamlit as st

from pages.poluentes.domain.models import POLLUTANT_LABELS, POLLUTANTS
from pages.poluentes.ui import (
    capitals,
    charts,
    city_map,
    collection_status,
    current_card,
    data,
    footer,
    history,
    period,
    verdict,
)

container = data.get_container()
settings = container.settings
primary = settings.primary_location
primary_name = next(location.name for location in settings.locations if location.slug == primary)
period_options = settings.dashboard.period_options

st.title(f"Qualidade do ar em {primary_name}")


@st.fragment(run_every=timedelta(seconds=settings.dashboard.rerun_seconds))
def dashboard() -> None:
    """Redesenha sozinho: a cada execução, confere se há coleta a fazer e mostra os dados mais novos do banco."""
    status = collection_status.keep_data_fresh(data.get_auto_collector(), settings.auto_collect)
    if not data.has_data():
        collection_status.render_no_data(status, settings.auto_collect)
        return
    collection_status.render_collection_status(status, settings.auto_collect, container.clock(), primary_name)

    summary_tab, technical_tab = st.tabs(["Resumo", "Detalhes técnicos"])

    with summary_tab:
        verdict.render_verdict(data.load_current(primary), settings.dashboard.plain_disclaimer)
        history_days = period.render_period_heading(
            lambda days: f"Como foi o ar nos últimos {days} dias", period_options, key="history_days"
        )
        history.render_history(data.load_daily_aqi(primary, history_days))
        capitals.render_capitals(data.load_current_by_location(), primary)
        verdict.render_scale_explainer()

    with technical_tab:
        footer.render_model_disclaimer(settings.dashboard.disclaimer)
        current_card.render_current_card(data.load_current(primary))

        guideline_pollutants = tuple(settings.who_guidelines_24h)
        technical_days = period.render_period_heading(
            lambda days: f"PM2.5 e NO₂ nos últimos {days} dias", period_options, key="technical_days"
        )
        charts.render_trend_with_guidelines(
            data.load_hourly_series(primary, technical_days, guideline_pollutants),
            data.load_daily_means(primary, technical_days, guideline_pollutants),
            settings.who_guidelines_24h,
        )
        st.caption("Linha tracejada: diretriz da OMS (2021) para média de 24h — compare com a média diária, não com o valor horário.")

        st.subheader("Padrão por hora do dia")
        charts.render_hourly_profile(data.load_hourly_profile(primary, technical_days))

        left, right = st.columns(2)
        with left:
            st.subheader("Comparativo entre capitais")
            pollutant = st.selectbox(
                "Poluente",
                options=list(POLLUTANTS),
                format_func=lambda key: POLLUTANT_LABELS[key],
            )
            charts.render_city_comparison(data.load_city_comparison(pollutant, technical_days), pollutant, primary)
        with right:
            st.subheader("Mapa · AQI atual")
            city_map.render_city_map(data.load_current_by_location())


dashboard()
footer.render_footer(settings.dashboard.attribution)
