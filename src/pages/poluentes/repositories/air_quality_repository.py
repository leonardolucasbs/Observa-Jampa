from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime

import pandas as pd
from sqlalchemy import Engine, Select, and_, func, select
from sqlalchemy.dialects.sqlite import insert

from pages.poluentes.domain.models import AirQualityReading
from pages.poluentes.repositories.database import air_quality_table, location_table

UPDATABLE_COLUMNS: tuple[str, ...] = tuple(
    column.name
    for column in air_quality_table.columns
    if column.name not in {"id", "location_id", "measured_at"}
)

MEASUREMENT_DATETIME_COLUMNS: tuple[str, ...] = ("measured_at", "fetched_at")


class AirQualityRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert(self, readings: Sequence[AirQualityReading], location_ids: Mapping[str, int]) -> int:
        if not readings:
            return 0
        rows = [self._to_row(reading, location_ids) for reading in readings]
        statement = insert(air_quality_table)
        statement = statement.on_conflict_do_update(
            index_elements=[air_quality_table.c.location_id, air_quality_table.c.measured_at],
            set_={name: statement.excluded[name] for name in UPDATABLE_COLUMNS},
        )
        with self._engine.begin() as connection:
            connection.execute(statement, rows)
        return len(rows)

    def find_between(
        self,
        start: datetime,
        end: datetime,
        slugs: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        conditions = [
            air_quality_table.c.measured_at >= start,
            air_quality_table.c.measured_at <= end,
        ]
        if slugs:
            conditions.append(location_table.c.slug.in_(slugs))
        statement = self._base_select().where(and_(*conditions)).order_by(
            location_table.c.slug, air_quality_table.c.measured_at
        )
        return self._read(statement)

    def find_latest_until(self, moment: datetime) -> pd.DataFrame:
        latest = (
            select(
                air_quality_table.c.location_id,
                func.max(air_quality_table.c.measured_at).label("measured_at"),
            )
            .where(air_quality_table.c.measured_at <= moment)
            .group_by(air_quality_table.c.location_id)
            .subquery()
        )
        statement = self._base_select().join(
            latest,
            and_(
                latest.c.location_id == air_quality_table.c.location_id,
                latest.c.measured_at == air_quality_table.c.measured_at,
            ),
        )
        return self._read(statement)

    def count(self) -> int:
        with self._engine.connect() as connection:
            return int(connection.execute(select(func.count()).select_from(air_quality_table)).scalar_one())

    def _base_select(self) -> Select:
        return select(
            location_table.c.slug,
            location_table.c.name,
            location_table.c.latitude,
            location_table.c.longitude,
            *[column for column in air_quality_table.columns if column.name not in {"id", "location_id"}],
        ).join(location_table, location_table.c.id == air_quality_table.c.location_id)

    def _read(self, statement: Select) -> pd.DataFrame:
        with self._engine.connect() as connection:
            frame = pd.DataFrame(connection.execute(statement).mappings().all())
        if frame.empty:
            return pd.DataFrame(columns=[column.name for column in statement.selected_columns])
        for column in MEASUREMENT_DATETIME_COLUMNS:
            frame[column] = pd.to_datetime(frame[column])
        frame["is_forecast"] = frame["is_forecast"].astype(bool)
        return frame

    @staticmethod
    def _to_row(reading: AirQualityReading, location_ids: Mapping[str, int]) -> dict[str, object]:
        row = asdict(reading)
        slug = row.pop("location_slug")
        if slug not in location_ids:
            raise KeyError(f"Localização '{slug}' não cadastrada")
        row["location_id"] = location_ids[slug]
        return row
