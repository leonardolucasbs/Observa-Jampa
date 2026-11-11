"""Regras dos avisos meteorológicos: situação (futuro, vigente, expirado) e abrangência do município.

A abrangência usa o código IBGE do município, que o INMET publica em cada aviso. Comparar nomes é
frágil: há municípios homônimos em estados diferentes e a grafia varia.
"""

from datetime import datetime

from pages.chuvas.domain.models import AlertFeed, AlertStatus, CityAlert, CityAlerts, WeatherAlert

STATUS_ORDER = {AlertStatus.ACTIVE: 0, AlertStatus.FUTURE: 1, AlertStatus.UNKNOWN: 2}


def alert_status(alert: WeatherAlert, now: datetime) -> AlertStatus:
    if alert.closed:
        return AlertStatus.EXPIRED
    if alert.ends_at is not None and now > alert.ends_at:
        return AlertStatus.EXPIRED
    if alert.starts_at is None or alert.ends_at is None:
        return AlertStatus.UNKNOWN
    if now < alert.starts_at:
        return AlertStatus.FUTURE
    return AlertStatus.ACTIVE


def alerts_for_city(feed: AlertFeed, ibge_code: str, now: datetime) -> CityAlerts:
    """Avisos vigentes e futuros que abrangem o município, os vigentes primeiro."""
    items: list[CityAlert] = []
    unverifiable = feed.unreadable
    for alert in latest_versions(feed.alerts):
        status = alert_status(alert, now)
        if status is AlertStatus.EXPIRED:
            continue
        if not alert.coverage_known:
            unverifiable += 1
        elif ibge_code in alert.geocodes:
            items.append(CityAlert(alert, status))
    items.sort(key=lambda item: (STATUS_ORDER[item.status], item.alert.starts_at or now, item.alert.id))
    return CityAlerts(items=tuple(items), unverifiable=unverifiable)


def latest_versions(alerts: tuple[WeatherAlert, ...]) -> list[WeatherAlert]:
    """Um aviso por identificador. A fonte repete o mesmo aviso nas listas "hoje" e "futuro",
    e uma versão nova (sequência maior) do mesmo aviso substitui as anteriores."""
    unique = {alert.id: alert for alert in alerts}
    latest: dict[str, WeatherAlert] = {}
    for alert in unique.values():
        key = alert.notice_id or f"id:{alert.id}"
        current = latest.get(key)
        if current is None or (alert.sequence or 0) > (current.sequence or 0):
            latest[key] = alert
    return list(latest.values())
