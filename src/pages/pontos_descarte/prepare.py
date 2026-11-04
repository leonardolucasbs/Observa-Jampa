"""Gera os dados que a página lê: os pontos de descarte e o limite do município.

Uso (na raiz do repositório):
    uv run python -m pages.pontos_descarte.prepare             # tudo
    uv run python -m pages.pontos_descarte.prepare --so pontos # só a planilha
    uv run python -m pages.pontos_descarte.prepare --so limite # só o limite do município

Rode de novo sempre que a planilha mudar. Os pontos consultam o OpenStreetMap (1 requisição por
segundo) para completar bairro e endereço que faltam, então levam cerca de 1 minuto. O limite do
município vem da API de malhas do IBGE e leva poucos segundos.
"""

import argparse
import logging
import sys

from pages.pontos_descarte.clients.http import ServiceError, build_session
from pages.pontos_descarte.clients.ibge import IbgeClient
from pages.pontos_descarte.clients.nominatim import NominatimClient
from pages.pontos_descarte.config import Settings, load_settings
from pages.pontos_descarte.etl.pipeline import prepare_points, read_spreadsheet, write_boundary, write_points

logger = logging.getLogger("pages.pontos_descarte.prepare")

STEPS = ("pontos", "limite")


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


if __name__ == "__main__":
    sys.exit(main())
