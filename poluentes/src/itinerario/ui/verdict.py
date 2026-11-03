from html import escape

import streamlit as st

from itinerario.domain.aqi import EPA_BANDS, SCALE_MAX, AqiBand, band_lower_bound, scale_position
from itinerario.domain.guidance import guidance_for
from itinerario.services.air_quality_service import CurrentAirQuality
from itinerario.ui.theme import text_color_on


def render_verdict(current: CurrentAirQuality | None, note: str) -> None:
    if current is None:
        st.info("Ainda não há dados para a cidade. Clique em “Atualizar dados agora” na barra lateral.")
        return
    guidance = guidance_for(current.band.label)
    index_text = "Sem índice no momento" if current.us_aqi is None else f"Índice {current.us_aqi} numa escala de 0 a 500"
    st.html(
        f'<div style="border-radius:16px;padding:22px 26px;background:{current.band.color};'
        f'color:{text_color_on(current.band.label)};">'
        f'<div style="font-size:1rem;font-weight:600;opacity:.85;">'
        f"Como está o ar em {escape(current.location_name)} agora</div>"
        f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:6px 0 8px;">'
        f'<span style="font-size:3.2rem;line-height:1;">{guidance.icon}</span>'
        f'<span style="font-size:2.3rem;font-weight:700;line-height:1.15;">{guidance.headline}</span></div>'
        f'<div style="font-size:1.1rem;">{guidance.meaning}</div>'
        f'<div style="font-size:.9rem;opacity:.85;margin-top:10px;">'
        f"{index_text} · atualizado às {current.measured_at:%H:%M} de {current.measured_at:%d/%m}</div>"
        f"</div>"
        f"{_scale_html(current.us_aqi)}"
    )
    st.caption(f"ℹ️ {note}")


def render_scale_explainer() -> None:
    with st.expander("Entenda a escala de cores"):
        st.markdown(
            "O número vem do **US AQI**, índice da agência ambiental dos Estados Unidos (EPA). "
            "Ele junta vários poluentes num único valor de 0 a 500: **quanto maior, pior o ar**."
        )
        rows = "".join(_explainer_row(band) for band in EPA_BANDS)
        st.html(f'<div style="display:flex;flex-direction:column;gap:6px;">{rows}</div>')


def _scale_html(value: int | None) -> str:
    segments = "".join(f'<div style="flex:1;background:{band.color};"></div>' for band in EPA_BANDS)
    labels = "".join(
        f'<div style="flex:1;text-align:center;padding:0 2px;">{guidance_for(band.label).name}</div>'
        for band in EPA_BANDS
    )
    position = scale_position(value)
    marker = ""
    if position is not None:
        marker = (
            f'<div style="position:absolute;left:{position * 100:.1f}%;top:-5px;transform:translateX(-50%);'
            "box-sizing:border-box;width:22px;height:22px;border-radius:50%;background:#ffffff;"
            'border:5px solid #111111;box-shadow:0 1px 4px rgba(0,0,0,.45);" aria-hidden="true"></div>'
        )
    return (
        '<div style="margin:22px 11px 0;" role="img" '
        f'aria-label="Posição do índice atual na escala de qualidade do ar">'
        f'<div style="position:relative;"><div style="display:flex;height:12px;border-radius:6px;overflow:hidden;">'
        f"{segments}</div>{marker}</div>"
        f'<div style="display:flex;font-size:.75rem;line-height:1.2;margin-top:10px;opacity:.85;">{labels}</div>'
        "</div>"
    )


def _explainer_row(band: AqiBand) -> str:
    guidance = guidance_for(band.label)
    lower = band_lower_bound(band)
    value_range = f"acima de {lower - 1}" if band.upper_bound > SCALE_MAX else f"{lower} a {band.upper_bound}"
    return (
        '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
        f'<span style="min-width:290px;padding:6px 10px;border-radius:8px;background:{band.color};'
        f'color:{text_color_on(band.label)};font-weight:600;">{guidance.icon} {guidance.name} · {value_range}</span>'
        f'<span style="flex:1;min-width:220px;">{guidance.meaning}</span></div>'
    )
