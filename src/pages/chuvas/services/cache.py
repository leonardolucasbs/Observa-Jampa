"""Cache de uma fonte externa, compartilhado por todas as sessões do app.

- Dentro de `ttl_seconds`, devolve a última resposta sem consultar a fonte.
- Vencido o prazo, consulta de novo. Se a consulta falhar, devolve a última resposta válida marcada
  como desatualizada, por até `max_stale_seconds` desde a última consulta bem-sucedida.
- Depois de uma falha, só tenta de novo após `retry_after_seconds` (ou o Retry-After da fonte, se maior).
- Uma consulta por vez: as sessões que chegam durante a consulta esperam e recebem o mesmo resultado.

Ao contrário do `st.cache_data`, guarda o horário da última consulta bem-sucedida e mantém a resposta
antiga quando a fonte cai, em vez de consultar de novo a cada execução da tela.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Generic, TypeVar

from pages.chuvas.clients.http import SourceError

logger = logging.getLogger(__name__)

T = TypeVar("T")
U = TypeVar("U")
Clock = Callable[[], datetime]


class Freshness(StrEnum):
    FRESH = "atual"  # consultada agora
    CACHED = "em cache"  # consultada há menos que o intervalo de atualização
    STALE = "desatualizado"  # a fonte falhou; é a última resposta válida


@dataclass(frozen=True)
class Snapshot(Generic[T]):
    value: T
    fetched_at: datetime  # última consulta bem-sucedida
    freshness: Freshness
    error: str | None = None  # motivo da falha mais recente, quando desatualizado

    def with_value(self, value: U) -> "Snapshot[U]":
        return replace(self, value=value)


class SourceUnavailable(Exception):
    """A fonte falhou e não há resposta válida recente para mostrar no lugar."""

    def __init__(self, message: str, last_success_at: datetime | None) -> None:
        super().__init__(message)
        self.last_success_at = last_success_at


class CachedSource(Generic[T]):
    def __init__(
        self,
        fetch: Callable[[], T],
        *,
        ttl_seconds: float,
        max_stale_seconds: float,
        retry_after_seconds: float,
        clock: Clock,
        name: str,
    ) -> None:
        self._fetch = fetch
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_stale = timedelta(seconds=max_stale_seconds)
        self._retry_after = retry_after_seconds
        self._clock = clock
        self._name = name
        self._lock = threading.Lock()
        self._value: T | None = None
        self._fetched_at: datetime | None = None
        self._last_error: str | None = None
        self._next_attempt_at: datetime | None = None

    def get(self) -> Snapshot[T]:
        with self._lock:
            now = self._clock()
            if self._fetched_at is not None and now - self._fetched_at < self._ttl:
                return Snapshot(self._value, self._fetched_at, Freshness.CACHED)
            if self._next_attempt_at is not None and now < self._next_attempt_at:
                return self._fallback(now)
            try:
                value = self._fetch()
            except SourceError as exc:
                wait = max(self._retry_after, exc.retry_after_seconds or 0)
                self._last_error = str(exc)
                self._next_attempt_at = now + timedelta(seconds=wait)
                logger.warning("%s indisponível (%s); nova tentativa em %.0f s", self._name, exc, wait)
                return self._fallback(now)
            self._value, self._fetched_at = value, now
            self._last_error = self._next_attempt_at = None
            return Snapshot(value, now, Freshness.FRESH)

    def _fallback(self, now: datetime) -> Snapshot[T]:
        if self._fetched_at is not None and now - self._fetched_at <= self._max_stale:
            return Snapshot(self._value, self._fetched_at, Freshness.STALE, self._last_error)
        raise SourceUnavailable(self._last_error or f"{self._name} indisponível", self._fetched_at)
