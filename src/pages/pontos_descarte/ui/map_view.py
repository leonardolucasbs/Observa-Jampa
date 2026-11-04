"""Mapa dos pontos (pydeck), com visual de GPS: mapa de ruas, município destacado em azul e rota contornada.

Clicar num marcador devolve o grupo de pontos daquele lugar.
"""

import hashlib
from collections.abc import Sequence

import pydeck as pdk
import streamlit as st

from pages.pontos_descarte.config import MapConfig
from pages.pontos_descarte.domain.geo import MapView, circle_bounds, fit_view, group_by_location
from pages.pontos_descarte.domain.models import (
    CityBoundary,
    Coordinates,
    GeocodedPlace,
    LocationGroup,
    MatchLevel,
)
from pages.pontos_descarte.services.routing_service import RouteResult
from pages.pontos_descarte.services.search_service import PlaceInterpretation, PointMatch

POINTS_LAYER = "pontos"
DESTINATION_LAYER = "destino"

LEVEL_COLORS = {MatchLevel.ACCEPTS: [29, 72, 153, 235], MatchLevel.POSSIBLE: [232, 125, 18, 235]}
ORIGIN_COLOR = [225, 29, 72, 255]
ROUTE_COLOR = [22, 163, 74, 225]
ROUTE_CASING_COLOR = [255, 255, 255, 235]
STRAIGHT_LINE_COLOR = [120, 120, 120, 200]
REFERENCE_COLOR = [29, 72, 153]
CITY_COLOR = [37, 99, 235]
CITY_LINE_ALPHA = 170
# Mapa de ruas no estilo dos apps de GPS (CARTO Voyager). Fixo, como o tema claro do app
# (src/.streamlit/config.toml): seguir o tema do navegador deixaria o mapa escuro numa página clara.
BASEMAP = pdk.map_styles.CARTO_ROAD
# O pydeck transforma qualquer string em expressão ("pixels" vira "@@=pixels", que o deck.gl não entende
# e então ignora a unidade). Entre aspas, a string chega literal ao navegador.
PIXELS = '"pixels"'
METERS = '"meters"'
# Teto para os marcadores: mesmo que a unidade seja mal interpretada, nenhum vira um disco gigante.
MAX_MARKER_PX = 24
MAP_WIDTH_PX = 680  # largura aproximada da coluna do mapa no layout largo (para calcular o zoom)


def render_map(
    matches: Sequence[PointMatch],
    *,
    config: MapConfig,
    origin: GeocodedPlace | None,
    route: RouteResult | None,
    references: Sequence[PlaceInterpretation],
    city: CityBoundary | None = None,
) -> LocationGroup | None:
    """Desenha o mapa e devolve o grupo de pontos clicado (ou None)."""
    deck, groups_by_id = build_deck(
        matches,
        config=config,
        origin=origin,
        route=route,
        references=references,
        city=city,
    )
    # A chave muda quando os dados mudam: o mapa reenquadra e a seleção antiga não sobra.
    signature = hashlib.md5(
        repr((sorted(groups_by_id), origin, route and route.point.id, [r.query for r in references])).encode()
    ).hexdigest()[:10]
    state = st.pydeck_chart(
        deck,
        height=config.height,
        on_select="rerun",
        selection_mode="single-object",
        key=f"mapa_{signature}",
        alt="Mapa de João Pessoa com os pontos de descarte de eletroeletrônicos",
    )
    _render_legend(bool(origin), route, city)

    for layer in (DESTINATION_LAYER, POINTS_LAYER):
        for selected in state.selection.objects.get(layer, []):
            if selected.get("group_id") in groups_by_id:
                return groups_by_id[selected["group_id"]]
    return None


def build_deck(
    matches: Sequence[PointMatch],
    *,
    config: MapConfig,
    origin: GeocodedPlace | None,
    route: RouteResult | None,
    references: Sequence[PlaceInterpretation],
    city: CityBoundary | None = None,
) -> tuple[pdk.Deck, dict[str, LocationGroup]]:
    """Monta o mapa (camadas e enquadramento) e o índice {id do grupo: grupo} usado no clique."""
    levels = {match.point.id: match.level for match in matches}
    groups = group_by_location(match.point for match in matches)
    groups_by_id = {group.id: group for group in groups}

    # Ordem de desenho: o município fica por baixo de tudo, a pessoa por cima.
    layers = [
        *_city_layers(city, config.city_fill_opacity),
        *_reference_layers(references),
        *_route_layers(route),
        *_point_layers(groups, levels),
    ]
    if route:
        destination = LocationGroup(
            id=f"destino-{route.point.id}", latitude=route.point.latitude, longitude=route.point.longitude,
            points=(route.point,),
        )
        groups_by_id[destination.id] = destination
        layers.append(_destination_layer(destination))
    if origin:
        layers += _origin_layers(origin)

    view = _view(groups, origin, route, references, config)
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(latitude=view.latitude, longitude=view.longitude, zoom=view.zoom),
        map_style=BASEMAP,
        tooltip={
            "html": "<b>{title}</b><br/>{subtitle}<br/><small>Clique para ver os detalhes</small>",
            "style": {"fontSize": "0.85rem", "maxWidth": "280px"},
        },
    )
    return deck, groups_by_id


def _city_layers(city: CityBoundary | None, fill_opacity: float) -> list[pdk.Layer]:
    """O município pintado de azul translúcido, com o contorno um pouco mais forte."""
    if city is None:
        return []
    alpha = round(max(0.0, min(fill_opacity, 1.0)) * 255)
    return [
        pdk.Layer(
            "PolygonLayer",
            id="municipio",
            data=[
                {"polygon": [[list(position) for position in ring] for ring in polygon]}
                for polygon in city.polygons
            ],
            get_polygon="polygon",
            filled=True,
            get_fill_color=[*CITY_COLOR, alpha],
            stroked=True,
            get_line_color=[*CITY_COLOR, CITY_LINE_ALPHA],
            line_width_units=PIXELS,
            get_line_width=2,
            pickable=False,
        )
    ]


def _point_layers(groups: Sequence[LocationGroup], levels: dict[int, MatchLevel]) -> list[pdk.Layer]:
    rows = []
    for group in groups:
        accepts = any(levels[point.id] == MatchLevel.ACCEPTS for point in group.points)
        best = MatchLevel.ACCEPTS if accepts else MatchLevel.POSSIBLE
        rows.append(
            {
                "group_id": group.id,
                "latitude": group.latitude,
                "longitude": group.longitude,
                "title": group.title,
                "subtitle": _subtitle(group),
                "fill": LEVEL_COLORS[best],
                "radius": 11 if len(group.points) > 1 else 8,
                "count": str(len(group.points)) if len(group.points) > 1 else "",
            }
        )
    markers = pdk.Layer(
        "ScatterplotLayer",
        id=POINTS_LAYER,
        data=rows,
        get_position="[longitude, latitude]",
        get_fill_color="fill",
        get_line_color=[255, 255, 255, 255],
        get_radius="radius",
        radius_units=PIXELS,
        radius_max_pixels=MAX_MARKER_PX,
        stroked=True,
        line_width_units=PIXELS,
        get_line_width=2,
        pickable=True,
        auto_highlight=True,
    )
    counts = pdk.Layer(
        "TextLayer",
        id="contagem",
        data=[row for row in rows if row["count"]],
        get_position="[longitude, latitude]",
        get_text="count",
        get_size=12,
        get_color=[255, 255, 255, 255],
        get_text_anchor='"middle"',
        get_alignment_baseline='"center"',
        font_weight=700,
        pickable=False,
    )
    return [markers, counts]


def _subtitle(group: LocationGroup) -> str:
    if len(group.points) > 1:
        return "<br/>".join(f"• {point.name}" for point in group.points[:5])
    point = group.points[0]
    return " · ".join(part for part in (point.neighborhood, point.city) if part)


def _destination_layer(destination: LocationGroup) -> pdk.Layer:
    return pdk.Layer(
        "ScatterplotLayer",
        id=DESTINATION_LAYER,
        data=[
            {
                "group_id": destination.id,
                "latitude": destination.latitude,
                "longitude": destination.longitude,
                "title": f"Destino: {destination.points[0].name}",
                "subtitle": _subtitle(destination),
            }
        ],
        get_position="[longitude, latitude]",
        get_radius=17,
        radius_units=PIXELS,
        radius_max_pixels=MAX_MARKER_PX,
        filled=False,
        stroked=True,
        get_line_color=ROUTE_COLOR,
        line_width_units=PIXELS,
        get_line_width=4,
        pickable=True,
    )


def _origin_layers(origin: GeocodedPlace) -> list[pdk.Layer]:
    """A pessoa como nos apps de GPS: um ponto com borda branca e um halo translúcido em volta."""
    data = [{"latitude": origin.latitude, "longitude": origin.longitude}]
    halo = pdk.Layer(
        "ScatterplotLayer",
        id="origem_halo",
        data=data,
        get_position="[longitude, latitude]",
        get_fill_color=[*ORIGIN_COLOR[:3], 55],
        get_radius=20,
        radius_units=PIXELS,
        radius_max_pixels=MAX_MARKER_PX,
        pickable=False,
    )
    dot = pdk.Layer(
        "ScatterplotLayer",
        id="origem",
        data=data,
        get_position="[longitude, latitude]",
        get_fill_color=ORIGIN_COLOR,
        get_line_color=[255, 255, 255, 255],
        get_radius=9,
        radius_units=PIXELS,
        radius_max_pixels=MAX_MARKER_PX,
        stroked=True,
        line_width_units=PIXELS,
        get_line_width=3,
        pickable=False,
    )
    return [halo, dot]


def _route_layers(route: RouteResult | None) -> list[pdk.Layer]:
    if not route:
        return []
    data = [{"path": [list(coordinate) for coordinate in route.path]}]
    # Contorno branco por baixo da linha, como nos apps de GPS: a rota se destaca sobre as ruas e sobre o azul.
    return [
        _path_layer("rota_contorno", data, ROUTE_CASING_COLOR, width=9),
        _path_layer("rota", data, STRAIGHT_LINE_COLOR if route.straight_line else ROUTE_COLOR, width=5),
    ]


def _path_layer(layer_id: str, data: list[dict], color: list[int], *, width: int) -> pdk.Layer:
    return pdk.Layer(
        "PathLayer",
        id=layer_id,
        data=data,
        get_path="path",
        get_color=color,
        get_width=width,
        width_units=PIXELS,
        cap_rounded=True,
        joint_rounded=True,
        pickable=False,
    )


def _reference_layers(references: Sequence[PlaceInterpretation]) -> list[pdk.Layer]:
    rows = [
        {"latitude": place.reference.latitude, "longitude": place.reference.longitude, "radius": place.radius_m}
        for place in references
        if place.reference and place.radius_m
    ]
    if not rows:
        return []
    return [
        pdk.Layer(
            "ScatterplotLayer",
            id="raio_busca",
            data=rows,
            get_position="[longitude, latitude]",
            get_radius="radius",
            radius_units=METERS,
            get_fill_color=[*REFERENCE_COLOR, 22],
            get_line_color=[*REFERENCE_COLOR, 140],
            stroked=True,
            line_width_units=PIXELS,
            get_line_width=1.5,
            pickable=False,
        )
    ]


def _view(
    groups: Sequence[LocationGroup],
    origin: GeocodedPlace | None,
    route: RouteResult | None,
    references: Sequence[PlaceInterpretation],
    config: MapConfig,
) -> MapView:
    """Enquadra a rota, se houver; senão, todos os pontos filtrados, o círculo de busca e a pessoa."""
    default = MapView(config.latitude, config.longitude, config.zoom)
    if route:
        coordinates = [Coordinates(lat, lon) for lon, lat in route.path]
    else:
        coordinates = [Coordinates(group.latitude, group.longitude) for group in groups]
        for place in references:
            if place.reference and place.radius_m:
                coordinates += circle_bounds(place.reference.coordinates, place.radius_m)
    if origin:
        coordinates.append(origin.coordinates)
    return fit_view(coordinates, default=default, width_px=MAP_WIDTH_PX, height_px=config.height)


def _render_legend(has_origin: bool, route: RouteResult | None, city: CityBoundary | None) -> None:
    items = [":primary[●] aceita o que você procura", ":orange[●] recebe eletroeletrônicos, confirme o item"]
    if city:
        items.append(f":blue[■] município de {city.name}")
    if has_origin:
        items.append(":red[●] você")
    if route:
        items.append(":gray[━] linha reta (rota indisponível)" if route.straight_line else ":green[━] rota")
    items.append("número no marcador = vários pontos no mesmo lugar")
    st.caption(" · ".join(items))
