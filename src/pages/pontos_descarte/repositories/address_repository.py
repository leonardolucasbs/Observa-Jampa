"""Índice de endereços (trechos de rua do CNEFE/IBGE) num arquivo SQLite gerado pelo `prepare`.

A página lê o arquivo inteiro uma vez e monta o índice em memória (`domain/addresses.py`).
"""

import logging
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import closing
from pathlib import Path

from pages.pontos_descarte.domain.models import StreetSegment

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE streets (
    id INTEGER PRIMARY KEY,
    city TEXT NOT NULL,
    street_type TEXT NOT NULL,  -- "Avenida"
    title TEXT,                 -- "Senador"
    name TEXT NOT NULL          -- "Ruy Carneiro"
);
CREATE TABLE segments (         -- um trecho de rua entre duas esquinas (face de quadra)
    street_id INTEGER NOT NULL REFERENCES streets (id),
    neighborhood TEXT,
    postal_code TEXT,
    number_min INTEGER NOT NULL,  -- 0 quando o trecho só tem endereços sem número
    number_max INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    addresses INTEGER NOT NULL    -- quantos endereços o IBGE contou no trecho
);
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

LOAD_QUERY = """
SELECT s.city, s.street_type, s.title, s.name, g.neighborhood, g.postal_code,
       g.number_min, g.number_max, g.latitude, g.longitude, g.addresses
FROM segments AS g JOIN streets AS s ON s.id = g.street_id
ORDER BY g.rowid
"""


class AddressRepository:
    def __init__(self, path: Path) -> None:
        self._path = path

    def exists(self) -> bool:
        return self._path.exists()

    def save(self, segments: Iterable[StreetSegment], metadata: Mapping[str, str]) -> None:
        """Grava num arquivo temporário e troca no fim: se algo falhar, o índice atual continua valendo."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.unlink(missing_ok=True)
        with closing(sqlite3.connect(temporary)) as connection:
            connection.executescript(SCHEMA)
            street_ids: dict[tuple, int] = {}
            for segment in segments:
                street = (segment.city, segment.street_type, segment.title, segment.name)
                if street not in street_ids:
                    street_ids[street] = len(street_ids) + 1
                    connection.execute("INSERT INTO streets VALUES (?, ?, ?, ?, ?)", (street_ids[street], *street))
                connection.execute(
                    "INSERT INTO segments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        street_ids[street],
                        segment.neighborhood,
                        segment.postal_code,
                        segment.number_min,
                        segment.number_max,
                        segment.latitude,
                        segment.longitude,
                        segment.addresses,
                    ),
                )
            connection.executemany("INSERT INTO metadata VALUES (?, ?)", sorted(metadata.items()))
            connection.commit()
            connection.execute("VACUUM")
        temporary.replace(self._path)

    def load(self) -> tuple[StreetSegment, ...]:
        """Vazio se o arquivo faltar ou estiver inválido: a busca de endereços usa só o OpenStreetMap."""
        if not self.exists():
            logger.warning("Índice de endereços não encontrado em %s", self._path)
            return ()
        try:
            with closing(sqlite3.connect(f"{self._path.as_uri()}?mode=ro", uri=True)) as connection:
                return tuple(StreetSegment(*row) for row in connection.execute(LOAD_QUERY))
        except sqlite3.Error:
            logger.warning("Índice de endereços inválido em %s", self._path, exc_info=True)
            return ()

    def metadata(self) -> dict[str, str]:
        if not self.exists():
            return {}
        with closing(sqlite3.connect(f"{self._path.as_uri()}?mode=ro", uri=True)) as connection:
            return dict(connection.execute("SELECT key, value FROM metadata"))
