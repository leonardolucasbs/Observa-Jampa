"""Renderização da página com as fontes simuladas: dados, carregamento, erro, dados desatualizados e ausência de avisos."""

from contextlib import contextmanager
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from pages.chuvas.bootstrap import build_container
from tests.chuvas.conftest import FakeClock, FakeResponse, FakeSession, alerts_response, make_alert_item

PAGE = str(Path(__file__).resolve().parents[2] / "src" / "pages" / "chuvas" / "page.py")
NO_ALERTS = "Nenhum aviso meteorológico oficial encontrado para João Pessoa no momento"


@pytest.fixture
def page(monkeypatch, settings):
    """Abre a página com dublês no lugar das duas fontes. Devolve (AppTest, relógio)."""

    def open_page(forecast: FakeSession, alerts: FakeSession, clock: FakeClock | None = None):
        clock = clock or FakeClock()
        sessions = iter([forecast, alerts])
        monkeypatch.setattr("pages.chuvas.bootstrap.build_session", lambda config: next(sessions))
        container = build_container(settings, clock=clock)
        monkeypatch.setattr("pages.chuvas.ui.data.get_container", lambda: container)
        return AppTest.from_file(PAGE, default_timeout=30).run(), clock

    return open_page


def texts(elements) -> str:
    return "\n".join(str(element.value) for element in elements)


def metrics(app: AppTest) -> list[str]:
    """Volumes dos três cards, na ordem: hoje, amanhã e próximos 7 dias."""
    return [metric.value for metric in app.metric]


def test_renders_the_three_cards_and_no_alerts_message(page, forecast_payload, alerts_payload):
    app, _ = page(FakeSession(FakeResponse(forecast_payload)), FakeSession(FakeResponse(alerts_payload)))

    assert not app.exception
    assert app.title[0].value == "Previsão de chuva e alertas meteorológicos"
    assert metrics(app) == ["4,0 mm", "5,3 mm", "21,2 mm"]
    headings = texts(app.markdown)
    assert "#### 🌧️ Vai chover" in headings  # hoje e amanhã
    assert "#### 🌧️ Chove em 6 de 7 dias" in headings
    assert texts(app.markdown).count(":green-badge[Chuva fraca]") == 2  # intensidade de hoje e de amanhã
    captions = texts(app.caption)
    assert "Pico de 0,5 mm/h às 03h." in captions
    assert "Vai chover quando a previsão do dia chega a 1,0 mm" in captions
    assert "ter. 10/11" in texts(app.markdown) and "ter. 10/11 a seg. 16/11" in texts(app.markdown)  # período
    assert "até 86% em alguma hora do dia (não é volume)" in captions
    assert "última consulta bem-sucedida: 10/11/2026 às 22:39 (consultado agora)" in captions
    assert f"{NO_ALERTS}. Última consulta bem-sucedida: 10/11/2026 às 22:39." in texts(app.info)
    assert "não em tempo real" in captions
    assert not app.error


def test_shows_active_and_future_alerts_for_joao_pessoa(page, forecast_payload):
    feed = alerts_response(
        make_alert_item(severidade="Perigo", aviso_cor="#F96602"),
        future=(make_alert_item(id=2, id_aviso=2, descricao="Tempestade", inicio="2026-11-12 00:00",
                                fim="2026-11-12 23:59", instrucoes=[]),),
    )
    app, _ = page(FakeSession(FakeResponse(forecast_payload)), FakeSession(FakeResponse(feed)))

    cards = [element.proto.body for element in app.get("html")]
    assert len(cards) == 2
    active, future = cards
    assert "Acumulado de Chuva" in active and "Perigo" in active and "#F96602" in active and "Vigente" in active
    assert "10/11/2026 às 08:00" in active and "11/11/2026 às 23:59" in active
    assert "Baixo risco de alagamentos" in active and "Evite enfrentar o mau tempo." in active
    assert [button.proto.url for button in app.get("link_button")] == [
        "https://avisos.inmet.gov.br/90001",
        "https://avisos.inmet.gov.br/2",
    ]
    assert "Tempestade" in future and "Futuro" in future
    assert "A fonte não informou instruções para este aviso." in future
    assert NO_ALERTS not in texts(app.info)


def test_alert_text_from_the_source_is_escaped(page, forecast_payload):
    feed = alerts_response(make_alert_item(descricao="<script>alert(1)</script>Chuva"))
    app, _ = page(FakeSession(FakeResponse(forecast_payload)), FakeSession(FakeResponse(feed)))

    card = app.get("html")[0].proto.body
    assert "<script>" not in card and "&lt;script&gt;" in card


def test_forecast_down_keeps_alerts_visible(page, alerts_payload):
    app, _ = page(FakeSession(requests.Timeout("lento")), FakeSession(FakeResponse(alerts_payload)))

    assert not app.exception
    assert "Não foi possível obter a previsão de chuva agora (Open-Meteo não respondeu em 10 s)" in texts(app.error)
    assert not app.metric
    assert NO_ALERTS in texts(app.info)


def test_alerts_down_keeps_forecast_visible_and_never_says_there_are_no_alerts(page, forecast_payload):
    app, _ = page(FakeSession(FakeResponse(forecast_payload)), FakeSession(requests.ConnectionError("reset")))

    assert not app.exception
    assert "Não foi possível obter os avisos do INMET agora (Sem conexão com INMET)" in texts(app.error)
    assert metrics(app)[0] == "4,0 mm"
    assert NO_ALERTS not in texts(app.info)


def test_missing_forecast_values_show_no_data_instead_of_zero(page, forecast_payload, alerts_payload):
    forecast_payload["daily"]["precipitation_sum"][1] = None
    forecast_payload["hourly"]["precipitation"][24] = None  # sem fallback horário para amanhã
    app, _ = page(FakeSession(FakeResponse(forecast_payload)), FakeSession(FakeResponse(alerts_payload)))

    values = metrics(app)
    assert values[1] == "—"
    assert values[2] == "15,9 mm"  # 21,2 − 5,3
    assert "#### ❔ Sem previsão" in texts(app.markdown)
    captions = texts(app.caption)
    assert "Sem dado de previsão para este dia." in captions
    assert "Parcial: soma de 6 de 7 dias. Sem previsão para 11/11." in captions


def test_refresh_uses_cache_then_marks_old_data_as_stale(page, forecast_payload, alerts_payload):
    forecast = FakeSession(FakeResponse(forecast_payload), requests.Timeout("lento"))
    alerts = FakeSession(FakeResponse(alerts_payload))
    app, clock = page(forecast, alerts)

    clock.advance(minutes=5)
    app.run()
    assert len(forecast.calls) == 1  # redesenhar a tela não consultou a fonte de novo
    assert "(em cache, consultado há 5 min)" in texts(app.caption)

    clock.advance(minutes=40)  # passou o intervalo de 30 min: nova consulta, que falha
    app.run()
    assert len(forecast.calls) == 2
    assert metrics(app)[0] == "4,0 mm"
    warning = texts(app.warning)
    assert "Não foi possível atualizar agora (Open-Meteo não respondeu em 10 s)" in warning
    assert "última consulta bem-sucedida, em 10/11/2026 às 22:39 (há 45 min)" in warning
    assert "(desatualizado)" in texts(app.caption)


def test_loading_indicator_wraps_each_source_query(page, forecast_payload, alerts_payload, monkeypatch):
    events: list[str] = []
    real_spinner = __import__("streamlit").spinner

    @contextmanager
    def recording_spinner(text, *args, **kwargs):
        events.append(f"início: {text}")
        with real_spinner(text, *args, **kwargs):
            yield
        events.append(f"fim: {text}")

    monkeypatch.setattr("streamlit.spinner", recording_spinner)
    forecast = FakeSession(FakeResponse(forecast_payload))
    alerts = FakeSession(FakeResponse(alerts_payload))
    original_get = forecast.get

    def get_during_loading(*args, **kwargs):
        events.append("consulta à Open-Meteo")
        return original_get(*args, **kwargs)

    forecast.get = get_during_loading
    page(forecast, alerts)

    rain = events.index("início: Consultando a previsão de chuva…")
    assert events[rain + 1] == "consulta à Open-Meteo"
    assert "fim: Consultando a previsão de chuva…" in events[rain + 2 :]
    assert "início: Consultando os avisos do INMET…" in events
