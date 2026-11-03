from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from pages.poluentes.domain.models import Location

T = TypeVar("T")


class DataSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchWindow:
    past_days: int
    forecast_days: int


class DataSourceClient(ABC, Generic[T]):
    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    def fetch(self, locations: Sequence[Location], window: FetchWindow) -> list[T]: ...
