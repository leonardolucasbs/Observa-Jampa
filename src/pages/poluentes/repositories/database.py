from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
)

metadata = MetaData()

location_table = Table(
    "location",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("slug", String, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
)

air_quality_table = Table(
    "air_quality_measurement",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("location_id", Integer, ForeignKey("location.id"), nullable=False),
    Column("measured_at", DateTime, nullable=False),
    Column("us_aqi", Integer),
    Column("european_aqi", Integer),
    Column("pm2_5", Float),
    Column("pm10", Float),
    Column("nitrogen_dioxide", Float),
    Column("ozone", Float),
    Column("carbon_monoxide", Float),
    Column("sulphur_dioxide", Float),
    Column("dust", Float),
    Column("dominant_pollutant", String),
    Column("is_forecast", Boolean, nullable=False),
    Column("fetched_at", DateTime, nullable=False),
    Index("ux_air_quality_location_time", "location_id", "measured_at", unique=True),
)


def create_db_engine(url_or_path: str | Path) -> Engine:
    url = url_or_path if isinstance(url_or_path, str) else _sqlite_url(url_or_path)
    engine = create_engine(url)
    event.listen(engine, "connect", _enable_foreign_keys)
    metadata.create_all(engine)
    return engine


def _sqlite_url(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


def _enable_foreign_keys(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
