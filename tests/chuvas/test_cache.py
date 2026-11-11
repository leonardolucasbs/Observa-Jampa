import threading

import pytest

from pages.chuvas.bootstrap import build_container
from pages.chuvas.clients.http import SourceError
from pages.chuvas.services.cache import CachedSource, Freshness, SourceUnavailable
from tests.chuvas.conftest import RECORDED_AT, FakeClock, FakeResponse, FakeSession


class FlakySource:
    """Fonte dublê: devolve "v1", "v2"... ou falha quando `fail` está ligado."""

    def __init__(self) -> None:
        self.calls = 0
        self.fail: SourceError | None = None

    def __call__(self) -> str:
        self.calls += 1
        if self.fail:
            raise self.fail
        return f"v{self.calls}"


def cached(source, clock, ttl=600, max_stale=3600, retry_after=120) -> CachedSource:
    return CachedSource(source, ttl_seconds=ttl, max_stale_seconds=max_stale, retry_after_seconds=retry_after,
                        clock=clock, name="Fonte de teste")


def test_first_call_fetches_and_records_the_time_of_success():
    clock, source = FakeClock(), FlakySource()

    snapshot = cached(source, clock).get()

    assert (snapshot.value, snapshot.freshness, snapshot.fetched_at) == ("v1", Freshness.FRESH, RECORDED_AT)


def test_repeated_calls_within_the_interval_do_not_hit_the_source():
    clock, source = FakeClock(), FlakySource()
    cache = cached(source, clock)
    cache.get()

    clock.advance(seconds=599)
    snapshots = [cache.get() for _ in range(20)]

    assert source.calls == 1
    assert {snapshot.freshness for snapshot in snapshots} == {Freshness.CACHED}
    assert {snapshot.fetched_at for snapshot in snapshots} == {RECORDED_AT}


def test_refreshes_after_the_interval():
    clock, source = FakeClock(), FlakySource()
    cache = cached(source, clock)
    cache.get()

    clock.advance(seconds=600)
    snapshot = cache.get()

    assert (snapshot.value, snapshot.freshness, snapshot.fetched_at) == ("v2", Freshness.FRESH, clock.now)


def test_failure_keeps_last_valid_data_marked_as_stale_with_its_original_time():
    clock, source = FakeClock(), FlakySource()
    cache = cached(source, clock)
    cache.get()
    source.fail = SourceError("INMET não respondeu em 10 s")

    clock.advance(seconds=700)
    snapshot = cache.get()

    assert snapshot.value == "v1"
    assert snapshot.freshness is Freshness.STALE
    assert snapshot.fetched_at == RECORDED_AT  # não finge que é uma atualização recente
    assert snapshot.error == "INMET não respondeu em 10 s"


def test_waits_before_trying_again_after_a_failure():
    clock, source = FakeClock(), FlakySource()
    cache = cached(source, clock, retry_after=120)
    cache.get()
    source.fail = SourceError("fora do ar")
    clock.advance(seconds=700)
    cache.get()  # falha: 2ª chamada

    clock.advance(seconds=60)
    cache.get()
    assert source.calls == 2  # ainda dentro da espera

    source.fail = None
    clock.advance(seconds=60)
    snapshot = cache.get()
    assert source.calls == 3
    assert (snapshot.value, snapshot.freshness) == ("v3", Freshness.FRESH)


def test_rate_limit_retry_after_extends_the_wait():
    clock, source = FakeClock(), FlakySource()
    cache = cached(source, clock, retry_after=120)
    cache.get()
    source.fail = SourceError("limitou as consultas (HTTP 429)", retry_after_seconds=900)
    clock.advance(seconds=700)
    cache.get()

    clock.advance(seconds=600)
    cache.get()

    assert source.calls == 2


def test_too_old_data_is_not_shown():
    clock, source = FakeClock(), FlakySource()
    cache = cached(source, clock, ttl=600, max_stale=3600)
    cache.get()
    source.fail = SourceError("fora do ar")

    clock.advance(seconds=3601)
    with pytest.raises(SourceUnavailable) as error:
        cache.get()

    assert error.value.last_success_at == RECORDED_AT
    assert "fora do ar" in str(error.value)


def test_failure_without_any_previous_data_is_unavailable():
    source = FlakySource()
    source.fail = SourceError("Sem conexão com Open-Meteo")

    with pytest.raises(SourceUnavailable, match="Sem conexão") as error:
        cached(source, FakeClock()).get()

    assert error.value.last_success_at is None


def test_concurrent_sessions_share_a_single_fetch():
    clock = FakeClock()
    started, release = threading.Event(), threading.Event()
    calls = []

    def slow_fetch() -> str:
        calls.append(1)
        started.set()
        release.wait(timeout=5)
        return "valor"

    cache = cached(slow_fetch, clock)
    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.get())) for _ in range(5)]
    threads[0].start()
    started.wait(timeout=5)
    for thread in threads[1:]:
        thread.start()
    release.set()
    for thread in threads:
        thread.join(timeout=5)

    assert len(calls) == 1
    assert sorted(snapshot.freshness for snapshot in results) == [Freshness.FRESH] + [Freshness.CACHED] * 4


def test_one_source_failing_does_not_affect_the_other(settings, forecast_payload, monkeypatch):
    """Integração bootstrap → services com as duas fontes: o INMET fora do ar não impede a previsão."""
    sessions = iter([FakeSession(FakeResponse(forecast_payload)), FakeSession(FakeResponse(text="erro", status_code=503))])
    monkeypatch.setattr("pages.chuvas.bootstrap.build_session", lambda config: next(sessions))

    container = build_container(settings, clock=FakeClock())

    assert container.rain_service.outlook().value.week.precipitation_mm == 21.2
    with pytest.raises(SourceUnavailable, match="HTTP 503"):
        container.alerts_service.for_city()
