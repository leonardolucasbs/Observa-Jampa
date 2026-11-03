from collections.abc import Sequence

from sqlalchemy import Engine, select
from sqlalchemy.dialects.sqlite import insert

from pages.poluentes.domain.models import Location
from pages.poluentes.repositories.database import location_table


class LocationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def sync(self, locations: Sequence[Location]) -> dict[str, int]:
        if locations:
            statement = insert(location_table)
            statement = statement.on_conflict_do_update(
                index_elements=[location_table.c.slug],
                set_={
                    "name": statement.excluded.name,
                    "latitude": statement.excluded.latitude,
                    "longitude": statement.excluded.longitude,
                },
            )
            with self._engine.begin() as connection:
                connection.execute(
                    statement,
                    [
                        {
                            "slug": location.slug,
                            "name": location.name,
                            "latitude": location.latitude,
                            "longitude": location.longitude,
                        }
                        for location in locations
                    ],
                )
        return self.ids_by_slug()

    def ids_by_slug(self) -> dict[str, int]:
        with self._engine.connect() as connection:
            rows = connection.execute(select(location_table.c.slug, location_table.c.id))
            return {slug: location_id for slug, location_id in rows}
