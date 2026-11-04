"""Planilha → registros limpos → enriquecidos pelo OpenStreetMap → JSON lido pela página."""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.clients.nominatim import CITY_KEYS, NEIGHBORHOOD_KEYS, first_of
from pages.pontos_descarte.domain.places import canonical_neighborhood
from pages.pontos_descarte.domain.text import normalize
from pages.pontos_descarte.etl.cleaning import KNOWN_CITIES, clean_row

logger = logging.getLogger(__name__)

ReverseGeocoder = Callable[[float, float], dict[str, str]]


def read_spreadsheet(path: Path, sheet: str) -> list[dict[str, Any]]:
    frame = pd.read_excel(path, sheet_name=sheet)
    frame = frame.dropna(subset=["id_marcador", "latitude", "longitude"])
    return frame.to_dict("records")


def needs_enrichment(record: dict[str, Any]) -> bool:
    return not record["neighborhood"] or not record["address"] or not record["city"]


def enrich(record: dict[str, Any], reverse: ReverseGeocoder) -> dict[str, Any]:
    """Completa bairro, endereço e cidade que faltam com o endereço da coordenada no OpenStreetMap.

    Os campos completados ficam marcados (`*_estimated`) para a tela avisar que são aproximados.
    """
    if not needs_enrichment(record):
        return record
    try:
        address = reverse(record["latitude"], record["longitude"])
    except ServiceError as exc:
        logger.warning("Ponto %s: não deu para consultar o OpenStreetMap (%s)", record["id"], exc)
        return record
    enriched = dict(record)
    neighborhood = canonical_neighborhood(first_of(address, NEIGHBORHOOD_KEYS))
    if not record["neighborhood"] and neighborhood:
        enriched["neighborhood"] = neighborhood
        enriched["neighborhood_estimated"] = True
    road = address.get("road")
    if not record["address"] and road:
        number = address.get("house_number")
        enriched["address"] = f"{road}, {number}" if number else road
        enriched["address_estimated"] = True
        enriched["postal_code"] = record["postal_code"] or address.get("postcode")
    city = first_of(address, CITY_KEYS)
    if not record["city"] and city:
        enriched["city"] = KNOWN_CITIES.get(normalize(city), city)
        enriched["state"] = record["state"] or ("PB" if normalize(address.get("state")) == "paraiba" else None)
    return enriched


def prepare_points(rows: list[dict[str, Any]], reverse: ReverseGeocoder) -> list[dict[str, Any]]:
    records = [clean_row(row) for row in rows]
    pending = sum(needs_enrichment(record) for record in records)
    logger.info("%s pontos lidos; %s precisam de bairro/endereço do OpenStreetMap", len(records), pending)
    return sorted((enrich(record, reverse) for record in records), key=lambda record: record["id"])


def write_points(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_boundary(geojson: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(geojson, ensure_ascii=False) + "\n", encoding="utf-8")
