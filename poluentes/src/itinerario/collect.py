import logging
import sys

from itinerario.bootstrap import build_container
from itinerario.clients.base import DataSourceError
from itinerario.config import load_settings
from itinerario.etl.jobs import run_collect
from itinerario.logging_setup import configure_logging

logger = logging.getLogger("itinerario.collect")


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
