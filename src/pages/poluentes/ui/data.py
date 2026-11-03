import pandas as pd
import streamlit as st

from pages.poluentes.bootstrap import Container, build_container
from pages.poluentes.clients.base import DataSourceError
from pages.poluentes.config import load_settings
from pages.poluentes.etl.jobs import run_collect
from pages.poluentes.etl.pipeline import IngestionResult
from pages.poluentes.logging_setup import configure_logging
from pages.poluentes.services.air_quality_service import CurrentAirQuality

CACHE_TTL_SECONDS = load_settings().dashboard.cache_ttl_seconds


@st.cache_resource
def get_container() -> Container:
    container = build_container()
    configure_logging(container.settings.log_level)
    return container


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_current(slug: str) -> CurrentAirQuality | None:
    return get_container().air_quality_service.current(slug)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_current_by_location() -> pd.DataFrame:
    return get_container().air_quality_service.current_by_location()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_hourly_series(slug: str, days: int, pollutants: tuple[str, ...]) -> pd.DataFrame:
    return get_container().air_quality_service.hourly_series(slug, days, list(pollutants))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_daily_means(slug: str, days: int, pollutants: tuple[str, ...]) -> pd.DataFrame:
    return get_container().air_quality_service.daily_means(slug, days, list(pollutants))


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_hourly_profile(slug: str, days: int) -> pd.DataFrame:
    return get_container().air_quality_service.hourly_profile(slug, days)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_city_comparison(pollutant: str, days: int) -> pd.DataFrame:
    return get_container().air_quality_service.city_comparison(pollutant, days)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_daily_aqi(slug: str, days: int) -> pd.DataFrame:
    return get_container().air_quality_service.daily_aqi(slug, days)


def has_data() -> bool:
    return get_container().air_quality_service.has_data()


def refresh_now() -> IngestionResult | str:
    try:
        result = run_collect(get_container())
    except DataSourceError as exc:
        return str(exc)
    st.cache_data.clear()
    return result
