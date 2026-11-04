import hashlib
from collections.abc import Sequence

import pandas as pd
import streamlit as st

from pages.pontos_descarte.domain.geo import haversine_m
from pages.pontos_descarte.domain.models import CATEGORY_LABELS, Category, DisposalPoint, GeocodedPlace, MatchLevel
from pages.pontos_descarte.services.search_service import PointMatch

LEVEL_LABELS = {MatchLevel.ACCEPTS: "Aceita", MatchLevel.POSSIBLE: "Confirmar com o local"}
CATEGORY_ORDER = list(Category)


def render_results(matches: Sequence[PointMatch], origin: GeocodedPlace | None) -> DisposalPoint | None:
    """Tabela dos pontos filtrados. Selecionar uma linha devolve o ponto (para abrir o modal)."""
    if not matches:
        return None
    ordered = list(matches)
    if origin:
        ordered.sort(key=lambda match: haversine_m(origin.coordinates, match.point.coordinates))

    frame = pd.DataFrame(
        {
            "Ponto": [match.point.name for match in ordered],
            "Bairro": [match.point.neighborhood or "—" for match in ordered],
            "Cidade": [match.point.city or "—" for match in ordered],
            "Recebe": [_categories(match.point) for match in ordered],
            "Situação": [LEVEL_LABELS[match.level] for match in ordered],
            "Distância (km)": [
                haversine_m(origin.coordinates, match.point.coordinates) / 1000 if origin else None
                for match in ordered
            ],
        }
    )
    if not origin:
        frame = frame.drop(columns=["Distância (km)"])

    signature = hashlib.md5(repr([match.point.id for match in ordered]).encode()).hexdigest()[:10]
    event = st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=f"tabela_{signature}",
        column_config={
            "Ponto": st.column_config.TextColumn(width="large"),
            "Recebe": st.column_config.ListColumn(width="large"),
            "Distância (km)": st.column_config.NumberColumn(format="%.1f km", help="Em linha reta a partir de você"),
        },
    )
    st.caption("Selecione uma linha para ver os detalhes do ponto.")
    rows = event.selection.rows
    return ordered[rows[0]].point if rows else None


def _categories(point: DisposalPoint) -> list[str]:
    return [CATEGORY_LABELS[category] for category in sorted(point.categories, key=CATEGORY_ORDER.index)]
