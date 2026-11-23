"""Página de qualidade do ar com a Open-Meteo simulada: a coleta acontece sozinha, sem botão."""

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import requests
from streamlit.testing.v1 import AppTest

from pages.poluentes.bootstrap import build_container
from pages.poluentes.config import load_settings
from pages.poluentes.etl.jobs import build_auto_collector
from pages.poluentes.ui import data
from tests.poluentes.conftest import JOAO_PESSOA, RECIFE, FakeClock

PAGE = str(Path(__file__).resolve().parents[2] / "src" / "pages" / "poluentes" / "page.py")


class FakeResponse:
    status_code = 200
    ok = True

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return copy.deepcopy(self._payload)


class FakeOpenMeteo:
    """Sessão HTTP dublê: responde com a fixture gravada ou falha. Registra o past_days de cada consulta."""

    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.failure: Exception | None = None
        self.past_days: list[int] = []

    def get(self, url: str, params: dict | None = None, timeout: float | None = None) -> FakeResponse:
        self.past_days.append(params["past_days"])
        if self.failure is not None:
            raise self.failure
        return FakeResponse(self.payload)


@pytest.fixture
def api(multi_location_payload) -> FakeOpenMeteo:
    return FakeOpenMeteo(multi_location_payload)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def open_page(monkeypatch, tmp_path, api, clock):
    """Abre a página com um banco novo em arquivo (a coleta roda em outra thread) e a API simulada."""

    def open_() -> AppTest:
        settings = replace(load_settings(), database_path=tmp_path / "poluentes.db", locations=(JOAO_PESSOA, RECIFE))
        monkeypatch.setattr("pages.poluentes.bootstrap.build_session", lambda config: api)
        container = build_container(settings, clock=clock)
        collector = build_auto_collector(container, on_collected=data.clear_cached_queries)
        monkeypatch.setattr("pages.poluentes.ui.data.get_container", lambda: container)
        monkeypatch.setattr("pages.poluentes.ui.data.get_auto_collector", lambda: collector)
        data.clear_cached_queries()  # o cache do Streamlit é do processo e passaria de um teste para outro
        return AppTest.from_file(PAGE, default_timeout=30).run()

    return open_


def texts(elements) -> str:
    return "\n".join(str(element.value) for element in elements)


def test_first_visit_loads_the_history_and_has_no_refresh_button(open_page, api):
    app = open_page()

    assert not app.exception
    assert api.past_days == [90]
    assert not app.button
    assert len(app.tabs) == 2
    assert (
        "Atualização automática a cada 1 h · última coleta: 30/10/2026 às 12:25 (há menos de 1 min) · "
        "horário de João Pessoa"
    ) in texts(app.caption)


def test_reopening_within_the_hour_does_not_query_the_api(open_page, api, clock):
    app = open_page()

    clock.advance(minutes=59)
    app.run()

    assert api.past_days == [90]
    assert "última coleta: 30/10/2026 às 12:25 (há 59 min)" in texts(app.caption)


def test_collects_again_after_an_hour_and_shows_the_new_time(open_page, api, clock):
    app = open_page()

    clock.advance(hours=1, minutes=5)
    app.run()

    assert not app.exception
    assert api.past_days == [90, 2]
    assert "última coleta: 30/10/2026 às 13:30 (há menos de 1 min)" in texts(app.caption)
    assert "Não foi possível atualizar" not in texts(app.warning)


def test_api_down_keeps_the_old_data_with_a_warning_and_waits_to_retry(open_page, api, clock):
    app = open_page()
    api.failure = requests.ConnectionError("sem rede")

    clock.advance(hours=3)
    app.run()

    assert not app.exception
    assert len(app.tabs) == 2  # os dados antigos continuam na tela
    warning = texts(app.warning)
    assert "Não foi possível atualizar agora (Falha de rede ao consultar Open-Meteo: sem rede)" in warning
    assert "Os dados abaixo são da última coleta, em 30/10/2026 às 12:25 (há 3 h 00 min)" in warning
    assert "Uma nova tentativa é feita automaticamente em até 10 min" in warning

    clock.advance(minutes=5)
    app.run()
    assert api.past_days == [90, 2]  # dentro da espera depois da falha, não consultou de novo


def test_first_visit_with_the_api_down_explains_instead_of_breaking(open_page, api):
    api.failure = requests.ConnectionError("sem rede")

    app = open_page()

    assert not app.exception
    assert not app.tabs
    assert "Não foi possível carregar os dados de qualidade do ar (Falha de rede ao consultar Open-Meteo: sem rede)" in (
        texts(app.error)
    )
