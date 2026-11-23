from datetime import datetime

import streamlit as st

from pages.poluentes.config import AutoCollectConfig
from pages.poluentes.etl.auto_collect import AutoCollector, CollectionStatus
from pages.poluentes.ui.formatting import format_age, format_interval, format_moment


def keep_data_fresh(collector: AutoCollector, config: AutoCollectConfig) -> CollectionStatus:
    """Dispara a coleta se os dados estão velhos e espera um pouco por ela.

    Com o banco vazio, espera o histórico carregar até o fim, porque não há nada para mostrar antes.
    A coleta tem timeout e tentativas próprias (seção [http] do config.toml), então a espera tem fim.
    """
    status = collector.ensure_fresh()
    if not status.collecting:
        return status
    if status.last_collected_at is None:
        with st.spinner(f"Carregando o histórico de qualidade do ar ({config.backfill_days} dias) pela primeira vez…"):
            return collector.wait(None)
    with st.spinner("Buscando dados novos da Open-Meteo…"):
        return collector.wait(config.wait_seconds)


def render_collection_status(status: CollectionStatus, config: AutoCollectConfig, now: datetime, place: str) -> None:
    last = status.last_collected_at
    if last is None:
        return
    if status.error:
        st.warning(
            f"Não foi possível atualizar agora ({status.error}). Os dados abaixo são da última coleta, "
            f"em {format_moment(last)} ({format_age(now - last)}). Uma nova tentativa é feita automaticamente "
            f"em até {format_interval(config.retry_after_failure_seconds)}.",
            icon=":material/history:",
        )
    collecting = " · buscando dados novos agora" if status.collecting else ""
    st.caption(
        f"Atualização automática a cada {format_interval(config.interval_seconds)} · "
        f"última coleta: {format_moment(last)} ({format_age(now - last)}){collecting} · horário de {place}"
    )


def render_no_data(status: CollectionStatus, config: AutoCollectConfig) -> None:
    if status.error:
        st.error(
            f"Não foi possível carregar os dados de qualidade do ar ({status.error}). Uma nova tentativa é feita "
            f"automaticamente em até {format_interval(config.retry_after_failure_seconds)}, e a página se "
            "atualiza sozinha.",
            icon=":material/cloud_off:",
        )
    else:
        st.info("Carregando os dados de qualidade do ar. A página se atualiza sozinha.", icon=":material/hourglass:")
