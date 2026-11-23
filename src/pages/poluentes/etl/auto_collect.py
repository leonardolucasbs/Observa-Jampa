"""Coleta automática disparada pela própria tela, no lugar do botão "Atualizar dados agora".

- A cada execução da tela, `ensure_fresh()` confere a hora da última coleta gravada no banco.
  Com menos de `interval_seconds`, nada acontece.
- Se ficou velha, a coleta roda numa thread em segundo plano: a tela não depende dela para abrir e
  mostra o que já está no banco. Quem quiser os dados novos espera com `wait()`.
- Uma coleta por vez para todas as sessões do app.
- O período buscado cobre todo o tempo sem coleta, então a lacuna de um app que ficou dias desligado
  se fecha sozinha. Com o banco vazio, carrega `backfill_days` de histórico.
- Depois de uma falha, só tenta de novo após `retry_after_failure_seconds`.

A última coleta é lida do banco, não da memória: a coleta da tarefa agendada
(`python -m pages.poluentes.collect`) também conta, e o app não repete o trabalho.
"""

import logging
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pages.poluentes.clients.base import DataSourceError
from pages.poluentes.clock import Clock
from pages.poluentes.config import AutoCollectConfig
from pages.poluentes.etl.pipeline import IngestionResult

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR = "erro inesperado na coleta; os detalhes estão no log"


@dataclass(frozen=True)
class CollectionStatus:
    last_collected_at: datetime | None  # None: banco vazio
    collecting: bool
    error: str | None = None  # motivo da última falha, enquanto os dados estiverem atrasados
    next_attempt_at: datetime | None = None


class AutoCollector:
    def __init__(
        self,
        *,
        fetch: Callable[[int], IngestionResult],
        last_collected_at: Callable[[], datetime | None],
        config: AutoCollectConfig,
        collect_past_days: int,
        clock: Clock,
        on_collected: Callable[[], None] = lambda: None,
    ) -> None:
        self._fetch = fetch  # recebe quantos dias para trás buscar
        self._read_last_collected_at = last_collected_at
        self._interval = timedelta(seconds=config.interval_seconds)
        self._retry_after = timedelta(seconds=config.retry_after_failure_seconds)
        self._backfill_days = config.backfill_days
        self._collect_past_days = collect_past_days
        self._clock = clock
        self._on_collected = on_collected  # roda na thread da coleta, depois de gravar
        self._lock = threading.Lock()  # protege o estado abaixo
        self._worker: threading.Thread | None = None
        self._last_collected_at: datetime | None = None
        self._last_error: str | None = None
        self._next_attempt_at: datetime | None = None

    def ensure_fresh(self) -> CollectionStatus:
        """Dispara a coleta em segundo plano se os dados estão velhos. Não espera por ela."""
        with self._lock:
            now = self._clock()
            if self._worker is None and self._is_due(now):
                past_days = self._past_days(now)
                logger.info(
                    "Coleta automática: última coleta em %s; buscando %d dias", self._last_collected_at, past_days
                )
                self._worker = threading.Thread(
                    target=self._run, args=(past_days,), name="poluentes-coleta-automatica", daemon=True
                )
                self._worker.start()
            return self._status(now)

    def wait(self, timeout_seconds: float | None) -> CollectionStatus:
        """Espera a coleta em andamento por até `timeout_seconds` (None: até terminar)."""
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout_seconds)
        with self._lock:
            return self._status(self._clock())

    def _is_due(self, now: datetime) -> bool:
        if self._is_recent(self._last_collected_at, now):
            return False
        # Relê o banco: a tarefa agendada pode ter coletado desde a última leitura.
        self._last_collected_at = self._read_last_collected_at()
        if self._is_recent(self._last_collected_at, now):
            return False
        return self._next_attempt_at is None or now >= self._next_attempt_at

    def _is_recent(self, moment: datetime | None, now: datetime) -> bool:
        return moment is not None and now - moment < self._interval

    def _past_days(self, now: datetime) -> int:
        if self._last_collected_at is None:
            return self._backfill_days
        days_without_collection = math.ceil((now - self._last_collected_at) / timedelta(days=1))
        return max(self._collect_past_days, days_without_collection)

    def _run(self, past_days: int) -> None:
        error: str | None = None
        last_collected_at: datetime | None = None
        try:
            self._fetch(past_days)
            last_collected_at = self._read_last_collected_at()
        except DataSourceError as exc:
            error = str(exc)
            logger.warning("Coleta automática falhou: %s. Nova tentativa em %s", exc, self._retry_after)
        except Exception:  # a thread não pode morrer com a coleta marcada como em andamento
            error = UNEXPECTED_ERROR
            logger.exception("Coleta automática falhou com erro inesperado")
        if error is None:
            self._notify_collected()
        with self._lock:
            if error is None:
                self._last_collected_at = last_collected_at
                self._last_error = self._next_attempt_at = None
            else:
                self._last_error = error
                self._next_attempt_at = self._clock() + self._retry_after
            self._worker = None

    def _notify_collected(self) -> None:
        try:
            self._on_collected()
        except Exception:  # os dados já estão no banco; o cache da tela vence sozinho pelo TTL
            logger.exception("Falha ao avisar a tela sobre a coleta nova")

    def _status(self, now: datetime) -> CollectionStatus:
        late = not self._is_recent(self._last_collected_at, now)
        return CollectionStatus(
            last_collected_at=self._last_collected_at,
            collecting=self._worker is not None,
            error=self._last_error if late else None,
            next_attempt_at=self._next_attempt_at if late else None,
        )
