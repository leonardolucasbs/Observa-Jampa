from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from pages.chuvas.config import Settings
from pages.chuvas.domain.models import AlertStatus, CityAlert, CityAlerts
from pages.chuvas.services.cache import Snapshot, SourceUnavailable
from pages.chuvas.ui.formatting import format_moment
from pages.chuvas.ui.source_status import render_source_status, render_stale_warning, render_unavailable
from pages.chuvas.ui.theme import BORDER, NO_SEVERITY_COLOR, PRIMARY, SOFT_BACKGROUND, readable_text_on

SOURCE = "INMET — Instituto Nacional de Meteorologia"
STATUS_LABELS = {
    AlertStatus.ACTIVE: "Vigente",
    AlertStatus.FUTURE: "Futuro",
    AlertStatus.UNKNOWN: "Validade não informada",
}


def render_alerts_panel(result: Snapshot[CityAlerts] | SourceUnavailable, settings: Settings, now: datetime) -> None:
    city = settings.location.name
    st.subheader("Avisos meteorológicos oficiais", anchor=False)
    if isinstance(result, SourceUnavailable):
        render_unavailable(result, SOURCE, "os avisos do INMET")
        return
    render_stale_warning(result, now)

    city_alerts = result.value
    if city_alerts.items:
        st.markdown(f"**{len(city_alerts.items)}** aviso(s) vigente(s) ou futuro(s) que abrangem {city}.")
        for item in city_alerts.items:
            st.html(alert_card_html(item, city, ZoneInfo(settings.timezone)))
            # Link fora do HTML: o st.html remove o target="_blank" e o link tiraria a pessoa do app.
            if item.alert.url:
                st.link_button("Ver o aviso no site do INMET", item.alert.url, icon=":material/open_in_new:")
    else:
        st.info(
            f"Nenhum aviso meteorológico oficial encontrado para {city} no momento. "
            f"Última consulta bem-sucedida: {format_moment(result.fetched_at)}.",
            icon=":material/info:",
        )
    if city_alerts.unverifiable:
        st.warning(
            f"{city_alerts.unverifiable} aviso(s) da fonte vieram sem a lista de municípios ou com formato ilegível "
            f"e não puderam ser conferidos. Consulte o mapa oficial em https://avisos.inmet.gov.br.",
            icon=":material/help:",
        )
    st.caption(f"ℹ️ {settings.texts.alerts_disclaimer}")
    render_source_status(result, SOURCE, settings.alerts.refresh_seconds, now)


def alert_card_html(item: CityAlert, city: str, zone: ZoneInfo) -> str:
    alert = item.alert
    starts_at = alert.starts_at.astimezone(zone) if alert.starts_at else None
    ends_at = alert.ends_at.astimezone(zone) if alert.ends_at else None
    color = alert.color or NO_SEVERITY_COLOR
    severity = alert.severity or "Severidade não informada"
    area = _area_text(item, city)
    risks = _list_html("Riscos", alert.risks, "A fonte não informou riscos para este aviso.")
    instructions = _list_html("Instruções oficiais", alert.instructions, "A fonte não informou instruções para este aviso.")
    link = "" if alert.url else " · link do aviso não informado"
    return (
        f'<div style="border:1px solid {BORDER};border-left:10px solid {color};border-radius:16px;'
        f'padding:16px 20px;margin-bottom:4px;">'
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">'
        f'<span style="background:{color};color:{readable_text_on(color)};padding:3px 12px;border-radius:999px;'
        f'font-weight:700;">{escape(severity)}</span>'
        f"{_status_chip(item.status)}</div>"
        f'<div style="font-size:1.35rem;font-weight:700;margin:10px 0 4px;">'
        f"{escape(alert.event or 'Fenômeno não informado')}</div>"
        f'<div style="margin-bottom:4px;"><b>Início:</b> {format_moment(starts_at)} · '
        f"<b>Término:</b> {format_moment(ends_at)} <span style=\"opacity:.75;\">(horário de {escape(city)})</span></div>"
        f'<div style="margin-bottom:8px;"><b>Área:</b> {area}</div>'
        f"{risks}{instructions}"
        f'<div style="font-size:.9rem;opacity:.85;margin-top:8px;">Fonte: {escape(SOURCE)}{link}</div>'
        "</div>"
    )


def _status_chip(status: AlertStatus) -> str:
    if status is AlertStatus.ACTIVE:
        style = f"background:{PRIMARY};color:#ffffff;"
    else:
        style = f"background:{SOFT_BACKGROUND};color:{PRIMARY};border:1px solid {PRIMARY};"
    return (
        f'<span style="{style}padding:2px 10px;border-radius:999px;font-size:.85rem;font-weight:600;">'
        f"{STATUS_LABELS[status]}</span>"
    )


def _area_text(item: CityAlert, city: str) -> str:
    alert = item.alert
    others = len(alert.geocodes) - 1
    parts = [f"abrange {escape(city)}" + (f" e mais {others} município(s)" if others > 0 else "")]
    if alert.regions:
        parts.append("mesorregiões: " + escape(", ".join(alert.regions)))
    if alert.states:
        parts.append("estados: " + escape(", ".join(alert.states)))
    return " · ".join(parts)


def _list_html(title: str, entries: tuple[str, ...], empty: str) -> str:
    if not entries:
        return f'<div style="margin-bottom:6px;"><b>{title}:</b> <i>{empty}</i></div>'
    rows = "".join(f"<li>{escape(entry)}</li>" for entry in entries)
    return f'<div style="margin-bottom:6px;"><b>{title}:</b><ul style="margin:4px 0 0 0;">{rows}</ul></div>'
