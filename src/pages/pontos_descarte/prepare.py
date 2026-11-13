"""Gera os dados que a página lê: os pontos de descarte, o limite do município e o índice de endereços.

Uso (na raiz do repositório):
    uv run python -m pages.pontos_descarte.prepare                # tudo
    uv run python -m pages.pontos_descarte.prepare --so pontos    # só a planilha
    uv run python -m pages.pontos_descarte.prepare --so limite    # só o limite do município
    uv run python -m pages.pontos_descarte.prepare --so enderecos # só o índice de endereços

Rode de novo sempre que a planilha mudar. Os pontos consultam o OpenStreetMap (1 requisição por
segundo) para completar bairro e endereço que faltam, então levam cerca de 1 minuto. O limite do
município vem da API de malhas do IBGE e leva poucos segundos. O índice de endereços baixa os
endereços do Censo 2022 (CNEFE/IBGE) das cidades do config.toml, cerca de 10 MB, e leva menos de 1 minuto.
"""

import argparse
import logging
import sys

from pages.pontos_descarte.clients.cnefe import CnefeClient
from pages.pontos_descarte.clients.http import ServiceError, build_session
from pages.pontos_descarte.clients.ibge import IbgeClient
from pages.pontos_descarte.clients.nominatim import NominatimClient
from pages.pontos_descarte.config import Settings, load_settings
from pages.pontos_descarte.domain.models import StreetSegment
from pages.pontos_descarte.etl.addresses import build_segments, iter_cnefe_rows
from pages.pontos_descarte.etl.pipeline import prepare_points, read_spreadsheet, write_boundary, write_points
from pages.pontos_descarte.repositories.address_repository import AddressRepository

logger = logging.getLogger("pages.pontos_descarte.prepare")

STEPS = ("pontos", "limite", "enderecos")
ADDRESSES_SOURCE = "IBGE, Cadastro Nacional de Endereços para Fins Estatísticos (CNEFE), Censo Demográfico 2022"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--so", choices=STEPS, help="gera só uma das partes")
    args = parser.parse_args(argv)

    settings = load_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    steps = (args.so,) if args.so else STEPS
    ok = True
    if "pontos" in steps:
        ok = prepare_points_file(settings) and ok
    if "limite" in steps:
        ok = prepare_boundary_file(settings) and ok
    if "enderecos" in steps:
        ok = prepare_addresses_file(settings) and ok
    return 0 if ok else 1


def prepare_points_file(settings: Settings) -> bool:
    if not settings.data.spreadsheet.exists():
        logger.error("Planilha não encontrada: %s", settings.data.spreadsheet)
        return False
    geocoder = NominatimClient(build_session(settings.http), settings.geocoding, settings.http.timeout_seconds)
    records = prepare_points(read_spreadsheet(settings.data.spreadsheet, settings.data.sheet), geocoder.reverse)
    write_points(records, settings.data.points)
    logger.info("%s pontos gravados em %s", len(records), settings.data.points)
    return True


def prepare_boundary_file(settings: Settings) -> bool:
    client = IbgeClient(build_session(settings.http), settings.boundary, settings.http.timeout_seconds)
    try:
        geojson = client.municipality_boundary()
    except ServiceError:
        logger.exception("Não foi possível baixar o limite do município; o arquivo atual foi mantido")
        return False
    write_boundary(geojson, settings.data.city_boundary)
    logger.info("Limite de %s gravado em %s", settings.boundary.name, settings.data.city_boundary)
    return True


def prepare_addresses_file(settings: Settings) -> bool:
    client = CnefeClient(build_session(settings.http), settings.addresses, settings.http.timeout_seconds)
    segments: list[StreetSegment] = []
    for city, file_name in settings.addresses.cities.items():
        try:
            content = client.download(file_name)
            city_segments = build_segments(iter_cnefe_rows(content), city)
        except (ServiceError, ValueError, KeyError):
            logger.exception("Não foi possível ler os endereços de %s; o índice atual foi mantido", city)
            return False
        logger.info("%s: %s trechos de rua", city, len(city_segments))
        segments.extend(city_segments)
    metadata = {"fonte": ADDRESSES_SOURCE, "cidades": ", ".join(settings.addresses.cities)}
    AddressRepository(settings.data.addresses).save(segments, metadata)
    logger.info("%s trechos de rua gravados em %s", len(segments), settings.data.addresses)
    return True


if __name__ == "__main__":
    sys.exit(main())
