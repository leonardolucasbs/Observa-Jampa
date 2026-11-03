import logging

from pages.poluentes.bootstrap import Container
from pages.poluentes.clients.base import FetchWindow
from pages.poluentes.etl.pipeline import IngestionResult

logger = logging.getLogger(__name__)


def run_collect(container: Container) -> IngestionResult:
    config = container.settings.air_quality
    window = FetchWindow(past_days=config.collect_past_days, forecast_days=config.forecast_days)
    return container.air_quality_ingestion.run(window)


def run_backfill(container: Container, days: int) -> IngestionResult:
    config = container.settings.air_quality
    if days > config.max_past_days:
        logger.warning(
            "A API só guarda %d dias no parâmetro past_days; backfill limitado de %d para %d dias",
            config.max_past_days,
            days,
            config.max_past_days,
        )
    window = FetchWindow(past_days=min(max(days, 0), config.max_past_days), forecast_days=config.forecast_days)
    return container.air_quality_ingestion.run(window)
