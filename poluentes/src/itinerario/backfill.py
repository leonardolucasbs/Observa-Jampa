import argparse
import logging
import sys

from itinerario.bootstrap import build_container
from itinerario.clients.base import DataSourceError
from itinerario.config import load_settings
from itinerario.etl.jobs import run_backfill
from itinerario.logging_setup import configure_logging

logger = logging.getLogger("itinerario.backfill")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carrega o histórico de qualidade do ar da Open-Meteo.")
    parser.add_argument("--days", type=int, default=90, help="Dias de histórico (máximo aceito pela API: 92)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    configure_logging(settings.log_level)
    try:
        run_backfill(build_container(settings), args.days)
    except DataSourceError as exc:
        logger.error("Backfill falhou: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
