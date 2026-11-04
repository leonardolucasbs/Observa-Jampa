"""Localização do navegador (GPS) via componente do Streamlit (st.components.v2).

O componente roda na própria página (sem iframe), então `navigator.geolocation` funciona direto.
O navegador só libera a localização em HTTPS ou em localhost.
"""

from dataclasses import dataclass

import streamlit as st

_HTML = '<p class="geo-status" role="status">Aguardando a permissão de localização do navegador…</p>'

_CSS = """
.geo-status {
    margin: 0;
    font-size: 0.875rem;
    color: var(--st-text-color);
    opacity: 0.75;
}
"""

_JS = """
const ERRORS = {
    1: "Você não permitiu o acesso à localização. Libere nas configurações do navegador ou digite seu endereço.",
    2: "Não foi possível descobrir sua localização agora. Tente de novo ou digite seu endereço.",
    3: "O navegador demorou demais para responder. Tente de novo ou digite seu endereço.",
};

export default function (component) {
    const { data, setTriggerValue } = component;
    const requestId = data && data.request_id;
    window.__observajpGeoRequests = window.__observajpGeoRequests || new Set();
    if (!requestId || window.__observajpGeoRequests.has(requestId)) {
        return;
    }
    window.__observajpGeoRequests.add(requestId);

    if (!("geolocation" in navigator)) {
        setTriggerValue("error", "Este navegador não oferece localização. Digite seu endereço.");
        return;
    }
    navigator.geolocation.getCurrentPosition(
        (position) => setTriggerValue("position", {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
        }),
        (error) => setTriggerValue("error", ERRORS[error.code] || error.message),
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 60000 },
    );
}
"""

_component = st.components.v2.component("observajp_geolocation", html=_HTML, css=_CSS, js=_JS)


@dataclass(frozen=True)
class BrowserPosition:
    latitude: float
    longitude: float
    accuracy_m: float | None


@dataclass(frozen=True)
class GeolocationOutcome:
    position: BrowserPosition | None = None
    error: str | None = None

    @property
    def finished(self) -> bool:
        return self.position is not None or self.error is not None


def request_position(request_id: str) -> GeolocationOutcome:
    """Pede a localização ao navegador. O resultado chega numa nova execução da página."""
    result = _component(
        key=f"geolocation_{request_id}",
        data={"request_id": request_id},
        on_position_change=lambda: None,
        on_error_change=lambda: None,
    )
    position = getattr(result, "position", None)
    if position:
        return GeolocationOutcome(
            position=BrowserPosition(
                latitude=float(position["latitude"]),
                longitude=float(position["longitude"]),
                accuracy_m=position.get("accuracy"),
            )
        )
    error = getattr(result, "error", None)
    return GeolocationOutcome(error=str(error)) if error else GeolocationOutcome()
