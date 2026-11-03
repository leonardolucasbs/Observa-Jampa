import logging
import sys

from pages.poluentes.bootstrap import build_container
from pages.poluentes.clients.base import DataSourceError
from pages.poluentes.config import load_settings
from pages.poluentes.etl.jobs import run_collect
from pages.poluentes.logging_setup import configure_logging

logger = logging.getLogger("pages.poluentes.collect")


def main() -> int:
    settings = load_settings()
    configure_logging(settings.log_level)
    try:
        run_collect(build_container(settings))
    except DataSourceError as exc:
        logger.error("Coleta falhou: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
