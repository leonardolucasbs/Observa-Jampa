from datetime import datetime

import streamlit as st

from pages.chuvas.services.cache import Freshness, Snapshot, SourceUnavailable
from pages.chuvas.ui.formatting import format_age, format_interval, format_moment


def render_stale_warning(snapshot: Snapshot, now: datetime) -> None:
    if snapshot.freshness is not Freshness.STALE:
        return
    st.warning(
        f"Não foi possível atualizar agora ({snapshot.error}). Os dados abaixo são da última consulta "
        f"bem-sucedida, em {format_moment(snapshot.fetched_at)} ({format_age(now - snapshot.fetched_at)}), "
        "e podem estar desatualizados.",
        icon=":material/history:",
    )


def render_source_status(snapshot: Snapshot, source: str, refresh_seconds: int, now: datetime) -> None:
    state = {
        Freshness.FRESH: "consultado agora",
        Freshness.CACHED: f"em cache, consultado {format_age(now - snapshot.fetched_at)}",
        Freshness.STALE: "desatualizado",
    }[snapshot.freshness]
    st.caption(
        f"Fonte: {source} · última consulta bem-sucedida: {format_moment(snapshot.fetched_at)} ({state}) · "
        f"nova consulta no máximo a cada {format_interval(refresh_seconds)} · horário de João Pessoa"
    )


def render_unavailable(error: SourceUnavailable, source: str, what: str) -> None:
    last = (
        f" A última consulta bem-sucedida foi em {format_moment(error.last_success_at)}, antiga demais para exibir."
        if error.last_success_at
        else ""
    )
    st.error(
        f"Não foi possível obter {what} agora ({error}).{last} Uma nova tentativa é feita automaticamente.",
        icon=":material/cloud_off:",
    )
    st.caption(f"Fonte: {source}")
