"""Coleta automática: quando coleta, quanto busca, uma coleta por vez e o que acontece quando falha."""

import threading
from datetime import datetime, timedelta

from pages.poluentes.clients.base import DataSourceError
from pages.poluentes.config import AutoCollectConfig
from pages.poluentes.etl.auto_collect import UNEXPECTED_ERROR, AutoCollector, CollectionStatus
from pages.poluentes.etl.pipeline import IngestionResult
from tests.poluentes.conftest import FakeClock

CONFIG = AutoCollectConfig(interval_seconds=3600, retry_after_failure_seconds=600, backfill_days=90, wait_seconds=5)


class FakeSource:
    """Faz o papel da Open-Meteo e do banco: cada coleta bem-sucedida grava a hora do relógio."""

    def __init__(self, clock: FakeClock, last_collected_at: datetime | None = None) -> None:
        self.clock = clock
        self.last = last_collected_at
        self.past_days: list[int] = []
        self.reads = 0
        self.failure: Exception | None = None
        self.release: threading.Event | None = None  # se definido, a coleta só termina depois do set()

    def fetch(self, past_days: int) -> IngestionResult:
        self.past_days.append(past_days)
        if self.release is not None:
            self.release.wait(timeout=5)
        if self.failure is not None:
            raise self.failure
        self.last = self.clock()
        return IngestionResult(source="dublê", locations=2, upserted=48, forecast=11)

    def last_collected_at(self) -> datetime | None:
        self.reads += 1
        return self.last


def make_collector(source: FakeSource, clock: FakeClock, on_collected=lambda: None) -> AutoCollector:
    return AutoCollector(
        fetch=source.fetch,
        last_collected_at=source.last_collected_at,
        config=CONFIG,
        collect_past_days=2,
        clock=clock,
        on_collected=on_collected,
    )


def collect(collector: AutoCollector) -> CollectionStatus:
    """Dispara a coleta, se for a hora, e espera ela terminar."""
    collector.ensure_fresh()
    return collector.wait(None)


def test_empty_database_loads_the_history_and_refreshes_the_screen() -> None:
    clock = FakeClock()
    source = FakeSource(clock)
    refreshes = []
    collector = make_collector(source, clock, on_collected=lambda: refreshes.append(1))

    status = collect(collector)

    assert source.past_days == [90]
    assert status == CollectionStatus(last_collected_at=clock.now, collecting=False)
    assert refreshes == [1]


def test_recent_data_is_not_collected_again_nor_read_again_from_the_database() -> None:
    clock = FakeClock()
    source = FakeSource(clock, last_collected_at=clock.now - timedelta(minutes=59))
    collector = make_collector(source, clock)

    statuses = [collector.ensure_fresh() for _ in range(10)]

    assert source.past_days == []
    assert source.reads == 1  # as outras execuções da tela usam a hora que já está em memória
    assert {status.collecting for status in statuses} == {False}


def test_data_older_than_the_interval_triggers_the_regular_collection() -> None:
    clock = FakeClock()
    source = FakeSource(clock, last_collected_at=clock.now - timedelta(minutes=61))

    status = collect(make_collector(source, clock))

    assert source.past_days == [2]
    assert status.last_collected_at == clock.now


def test_a_gap_of_several_days_is_filled_in_a_single_collection() -> None:
    clock = FakeClock()
    source = FakeSource(clock, last_collected_at=clock.now - timedelta(days=5, hours=3))

    collect(make_collector(source, clock))

    assert source.past_days == [6]


def test_a_collection_made_by_the_scheduled_task_counts() -> None:
    clock = FakeClock()
    source = FakeSource(clock, last_collected_at=clock.now - timedelta(minutes=30))
    collector = make_collector(source, clock)
    collector.ensure_fresh()

    clock.advance(minutes=40)  # em memória, a última coleta tem 70 min...
    source.last = clock.now - timedelta(minutes=5)  # ...mas a tarefa agendada acabou de coletar
    status = collector.ensure_fresh()

    assert source.past_days == []
    assert status.last_collected_at == source.last


def test_sessions_arriving_during_a_collection_share_it() -> None:
    clock = FakeClock()
    source = FakeSource(clock, last_collected_at=clock.now - timedelta(hours=2))
    source.release = threading.Event()
    collector = make_collector(source, clock)

    statuses: list[CollectionStatus] = []
    sessions = [threading.Thread(target=lambda: statuses.append(collector.ensure_fresh())) for _ in range(5)]
    for session in sessions:
        session.start()
    for session in sessions:
        session.join(timeout=5)
    source.release.set()
    final = collector.wait(None)

    assert source.past_days == [2]
    assert {status.collecting for status in statuses} == {True}
    assert not final.collecting


def test_wait_gives_up_after_the_timeout_and_the_collection_goes_on() -> None:
    clock = FakeClock()
    source = FakeSource(clock, last_collected_at=clock.now - timedelta(hours=2))
    source.release = threading.Event()
    collector = make_collector(source, clock)
    collector.ensure_fresh()

    slow = collector.wait(0.05)
    source.release.set()
    done = collector.wait(None)

    assert slow.collecting and slow.last_collected_at == clock.now - timedelta(hours=2)
    assert not done.collecting and done.last_collected_at == clock.now


def test_failure_keeps_the_old_data_and_waits_before_trying_again() -> None:
    clock = FakeClock()
    old = clock.now - timedelta(hours=2)
    source = FakeSource(clock, last_collected_at=old)
    source.failure = DataSourceError("Falha de rede ao consultar Open-Meteo: sem rede")
    refreshes = []
    collector = make_collector(source, clock, on_collected=lambda: refreshes.append(1))

    failed = collect(collector)

    assert failed == CollectionStatus(
        last_collected_at=old,
        collecting=False,
        error="Falha de rede ao consultar Open-Meteo: sem rede",
        next_attempt_at=clock.now + timedelta(minutes=10),
    )
    assert refreshes == []

    clock.advance(minutes=9)
    collector.ensure_fresh()
    assert source.past_days == [2]  # ainda dentro da espera

    source.failure = None
    clock.advance(minutes=1)
    recovered = collect(collector)
    assert source.past_days == [2, 2]
    assert recovered == CollectionStatus(last_collected_at=clock.now, collecting=False)
    assert refreshes == [1]


def test_error_is_no_longer_shown_once_the_data_is_recent_again() -> None:
    clock = FakeClock()
    source = FakeSource(clock, last_collected_at=clock.now - timedelta(hours=2))
    source.failure = DataSourceError("fora do ar")
    collector = make_collector(source, clock)
    collect(collector)

    source.last = clock.now  # a tarefa agendada conseguiu coletar
    status = collector.ensure_fresh()

    assert status.error is None and status.next_attempt_at is None


def test_unexpected_error_does_not_leave_the_collection_stuck() -> None:
    clock = FakeClock()
    source = FakeSource(clock)
    source.failure = RuntimeError("bug")
    collector = make_collector(source, clock)

    failed = collect(collector)
    source.failure = None
    clock.advance(minutes=10)
    recovered = collect(collector)

    assert (failed.error, failed.collecting) == (UNEXPECTED_ERROR, False)
    assert source.past_days == [90, 90]
    assert recovered.last_collected_at == clock.now


def test_failing_to_refresh_the_screen_does_not_turn_the_collection_into_an_error() -> None:
    clock = FakeClock()
    source = FakeSource(clock)

    def broken_refresh() -> None:
        raise RuntimeError("cache")

    status = collect(make_collector(source, clock, on_collected=broken_refresh))

    assert status == CollectionStatus(last_collected_at=clock.now, collecting=False)
