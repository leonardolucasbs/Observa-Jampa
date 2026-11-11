"""Dublês e dados dos testes da página de chuvas. Nenhum teste acessa a rede.

As fixtures em `fixtures/` são respostas reais de 10/11/2026 (22:39, horário de João Pessoa):
- open_meteo_forecast.json: a mesma requisição que o client faz.
- inmet_avisos_ativos.json: /avisos/ativos, sem ícones e polígonos e com até 40 municípios por aviso.
  Nenhum aviso real desse dia abrangia João Pessoa; os casos com João Pessoa usam `make_alert_item`.
"""

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pages.chuvas.config import Settings, load_settings

FIXTURES = Path(__file__).parent / "fixtures"
JP_ZONE = ZoneInfo("America/Fortaleza")
BRASILIA = ZoneInfo("America/Sao_Paulo")
JOAO_PESSOA = "2507507"
CABEDELO = "2503209"
# Momento em que as fixtures foram gravadas.
RECORDED_AT = datetime(2026, 11, 10, 22, 39, tzinfo=JP_ZONE)


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def settings() -> Settings:
    return load_settings()


@pytest.fixture
def forecast_payload() -> dict[str, Any]:
    return load_fixture("open_meteo_forecast.json")


@pytest.fixture
def alerts_payload() -> dict[str, Any]:
    return load_fixture("inmet_avisos_ativos.json")


class FakeClock:
    def __init__(self, now: datetime = RECORDED_AT) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


class FakeResponse:
    def __init__(self, payload: Any = None, status_code: int = 200, headers: dict[str, str] | None = None,
                 text: str | None = None) -> None:
        self._payload = payload
        self._text = text
        self.status_code = status_code
        self.headers = headers or {}

    def json(self) -> Any:
        if self._text is not None:
            raise ValueError("não é JSON")
        return copy.deepcopy(self._payload)


class FakeSession:
    """Devolve as respostas (ou levanta as exceções) na ordem dada e registra as chamadas."""

    def __init__(self, *outcomes: FakeResponse | Exception) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict | None = None, timeout: float | None = None) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_alert_item(**overrides: Any) -> dict[str, Any]:
    """Um aviso no formato real do /avisos/ativos, por padrão vigente em 10/11/2026 e abrangendo João Pessoa."""
    item = {
        "id": 90001,
        "id_aviso": 40001,
        "id_sequencia": 1,
        "codigo": "urn:oid:2.49.0.0.76.0.2026.40001.1",
        "data_inicio": "2026-11-10T00:00:00.000Z",
        "hora_inicio": "08:00",
        "data_fim": "2026-11-11T00:00:00.000Z",
        "hora_fim": "23:59",
        "inicio": "2026-11-10 08:00",
        "fim": "2026-11-11 23:59",
        "municipios": f"Cabedelo - PB ({CABEDELO}),João Pessoa - PB ({JOAO_PESSOA}),Bayeux - PB (2501807)",
        "mesorregioes": "Mata Paraibana",
        "estados": "Paraíba",
        "geocodes": f"{CABEDELO},{JOAO_PESSOA},2501807",
        "alterado": False,
        "encerrado": False,
        "descricao": "Acumulado de Chuva",
        "aviso_cor": "#FFFE00",
        "severidade": "Perigo Potencial",
        "riscos": ["Chuva entre 20 a 30 mm/h ou até 50 mm/dia. Baixo risco de alagamentos e pequenos deslizamentos, "
                   "em cidades com tais áreas de risco."],
        "instrucoes": ["Evite enfrentar o mau tempo. ", "Observe alteração nas encostas. "],
    }
    item.update(overrides)
    return item


def alerts_response(*items: dict[str, Any], future: tuple[dict[str, Any], ...] = ()) -> dict[str, list]:
    return {"hoje": list(items), "futuro": list(future)}
