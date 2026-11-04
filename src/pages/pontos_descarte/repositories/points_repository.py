import json
from pathlib import Path
from typing import Any

from pages.pontos_descarte.domain.models import DisposalPoint
from pages.pontos_descarte.domain.waste import categories_from_description


class PointsRepository:
    """Lê os pontos do JSON gerado pelo `prepare` (a página não depende de rede para isso)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def exists(self) -> bool:
        return self._path.exists()

    def all(self) -> tuple[DisposalPoint, ...]:
        records = json.loads(self._path.read_text(encoding="utf-8"))
        return tuple(point_from_record(record) for record in records)


def point_from_record(record: dict[str, Any]) -> DisposalPoint:
    return DisposalPoint(
        **record,
        categories=categories_from_description(record["waste_description"]),
    )
