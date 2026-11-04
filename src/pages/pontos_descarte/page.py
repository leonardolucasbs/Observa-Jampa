"""Página dos pontos de descarte de eletroeletrônicos. Tudo o que ela usa está nesta mesma pasta."""

import streamlit as st

from pages.pontos_descarte.ui import data, details, filters, map_view, results_table, route_panel

container = data.get_container()
settings = container.settings

st.title("Pontos de descarte de eletroeletrônicos")
st.caption(
    "Onde entregar pilhas, celulares, computadores e eletrodomésticos em João Pessoa e região. "
    + settings.texts.disclaimer
)

if not container.points:
    st.error("Os dados dos pontos ainda não foram gerados. Rode `uv run python -m pages.pontos_descarte.prepare`.")
    st.stop()

values = filters.render_filters()
with st.spinner("Buscando pontos…"):
    result = data.search(values.waste, values.neighborhood, values.address)
filters.render_interpretation(result)

map_col, panel_col = st.columns([3, 2], gap="medium")
with panel_col:
    # A rota considera só o tipo de descarte: o ponto mais próximo pode estar fora do bairro filtrado.
    waste_only = data.search(values.waste, "", "") if values.neighborhood or values.address else result
    panel = route_panel.render_route_panel(waste_only, settings.routing)
with map_col:
    st.markdown(f"**{len(result.matches)}** de {result.total_points} pontos")
    clicked_group = map_view.render_map(
        result.matches,
        config=settings.map,
        origin=panel.origin,
        route=panel.route,
        references=result.references,
        city=container.city_boundary,
    )

st.subheader("Pontos encontrados", anchor=False)
if result.matches:
    selected_point = results_table.render_results(result.matches, panel.origin)
else:
    selected_point = None
    st.info("Nenhum ponto corresponde aos filtros. Experimente apagar um deles.", icon=":material/filter_alt_off:")

# Só um modal por execução: clique no mapa, linha da tabela ou "Ver detalhes" do painel de rota.
points_to_show = None
if details.is_new_selection("mapa", clicked_group.id if clicked_group else None):
    points_to_show = clicked_group.points
if details.is_new_selection("tabela", str(selected_point.id) if selected_point else None) and not points_to_show:
    points_to_show = (selected_point,)
if panel.show_destination_details and panel.route:
    points_to_show = (panel.route.point,)
if points_to_show:
    details.show_details(points_to_show, panel.origin, panel.service)

st.divider()
st.caption(settings.texts.attribution)
