import sys

import pandas as pd
import streamlit as st

from pages.poluentes.bootstrap import Container, build_container
from pages.poluentes.config import load_settings
from pages.poluentes.etl.auto_collect import AutoCollector
from pages.poluentes.etl.jobs import build_auto_collector
from pages.poluentes.logging_setup import configure_logging
from pages.poluentes.services.air_quality_service import CurrentAirQuality

CACHE_TTL_SECONDS = load_settings().dashboard.cache_ttl_seconds


def _built_with_current_code(container: object) -> bool:
    """Ao salvar um arquivo, o Streamlit reimporta os módulos, mas o `cache_resource` guarda o
    container antigo, que passaria a criar objetos de classes velhas e o `cache_data` não
    conseguiria serializá-los (PicklingError). Aí o container é descartado e reconstruído.

    Consulta `sys.modules` em vez de `isinstance(..., Container)` porque o Streamlit mantém a
    primeira função `validate` registrada, que enxergaria a classe antiga.
    """
    cls = type(container)
    return getattr(sys.modules.get(cls.__module__), cls.__qualname__, None) is cls


@st.cache_resource(validate=_built_with_current_code)
def get_container() -> Container:
    container = build_container()
    configure_logging(container.settings.log_level)
    return container


@st.cache_resource(validate=_built_with_current_code)
def get_auto_collector() -> AutoCollector:
    """Um coletor para o app inteiro: todas as sessões compartilham a mesma coleta."""
    return build_auto_collector(get_container(), on_collected=clear_cached_queries)


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


CACHED_QUERIES = (
    load_current,
    load_current_by_location,
    load_hourly_series,
    load_daily_means,
    load_hourly_profile,
    load_city_comparison,
    load_daily_aqi,
)


def clear_cached_queries() -> None:
    """Descarta as consultas em cache desta página depois de uma coleta nova.

    Roda na thread da coleta. Limpa só as funções desta página: `st.cache_data.clear()` apagaria
    também o cache das outras páginas.
    """
    for query in CACHED_QUERIES:
        query.clear()
