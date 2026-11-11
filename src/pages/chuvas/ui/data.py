import logging

import streamlit as st

from pages.chuvas.bootstrap import Container, build_container
from pages.chuvas.domain.models import CityAlerts, RainOutlook
from pages.chuvas.services.cache import Snapshot, SourceUnavailable


@st.cache_resource
def get_container() -> Container:
    container = build_container()
    logging.basicConfig(
        level=container.settings.log_level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return container


def load_rain() -> Snapshot[RainOutlook] | SourceUnavailable:
    try:
        return get_container().rain_service.outlook()
    except SourceUnavailable as exc:
        return exc


def load_alerts() -> Snapshot[CityAlerts] | SourceUnavailable:
    try:
        return get_container().alerts_service.for_city()
    except SourceUnavailable as exc:
        return exc
