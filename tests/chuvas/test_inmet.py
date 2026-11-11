from datetime import datetime, timezone

import pytest
import requests

from pages.chuvas.clients.http import SourceError
from pages.chuvas.clients.inmet_alerts import InmetAlertsClient, parse_alerts
from pages.chuvas.domain.alerts import alert_status, alerts_for_city, latest_versions
from pages.chuvas.domain.models import AlertStatus
from tests.chuvas.conftest import (
    BRASILIA,
    JOAO_PESSOA,
    JP_ZONE,
    RECORDED_AT,
    FakeResponse,
    FakeSession,
    alerts_response,
    make_alert_item,
)

PAGE_URL = "https://avisos.inmet.gov.br/{id}"


def parse(payload):
    return parse_alerts(payload, BRASILIA, PAGE_URL)


def city_alerts(payload, now=RECORDED_AT):
    return alerts_for_city(parse(payload), JOAO_PESSOA, now)


# --- resposta real -------------------------------------------------------------------------------------------


def test_reads_every_field_of_the_real_response(alerts_payload):
    feed = parse(alerts_payload)
    first = feed.alerts[0]

    assert len(feed.alerts) == 10 and feed.unreadable == 0
    assert first.id == "56356" and first.notice_id == "28669" and first.sequence == 2
    assert first.event == "Acumulado de Chuva"
    assert (first.severity, first.color) == ("Perigo Potencial", "#FFFE00")
    assert first.starts_at == datetime(2026, 11, 10, 0, 1, tzinfo=BRASILIA)
    assert first.ends_at == datetime(2026, 11, 13, 23, 59, tzinfo=BRASILIA)
    assert first.municipalities[0] == "Alcobaça"  # acentos preservados (resposta em UTF-8)
    assert len(first.geocodes) == 40 and "2900801" in first.geocodes
    assert first.regions == ("Sul Baiano", "Metropolitana de Salvador", "Centro Sul Baiano")
    assert first.states == ("Bahia",)
    assert first.risks[0].startswith("Chuva entre 20 a 30 mm/h")
    assert first.instructions[0] == "Evite enfrentar o mau tempo."  # espaço final da fonte removido
    assert first.url == "https://avisos.inmet.gov.br/56356"
    assert not first.closed


def test_real_alert_appearing_in_both_lists_is_counted_once(alerts_payload):
    feed = parse(alerts_payload)

    ids = [alert.id for alert in latest_versions(feed.alerts)]

    assert len(feed.alerts) == 10
    assert len(ids) == len(set(ids)) == 8  # 56356 e 56365 estão em "hoje" e em "futuro"


def test_real_response_of_the_day_has_no_alert_for_joao_pessoa(alerts_payload):
    result = city_alerts(alerts_payload)

    assert result.items == ()
    assert result.unverifiable == 0


def test_real_statuses_at_recording_time_and_after_midnight(alerts_payload):
    alerts = {alert.id: alert for alert in parse(alerts_payload).alerts}
    after_midnight = datetime(2026, 11, 11, 0, 0, tzinfo=JP_ZONE)

    assert alert_status(alerts["56356"], RECORDED_AT) is AlertStatus.ACTIVE  # 10/11 00:01 a 13/11 23:59
    assert alert_status(alerts["56369"], RECORDED_AT) is AlertStatus.FUTURE  # 11/11 00:00 a 11/11 23:59
    assert alert_status(alerts["56371"], RECORDED_AT) is AlertStatus.ACTIVE  # termina 10/11 23:59
    assert alert_status(alerts["56371"], after_midnight) is AlertStatus.EXPIRED
    assert alert_status(alerts["56369"], after_midnight) is AlertStatus.ACTIVE


# --- filtragem para João Pessoa ------------------------------------------------------------------------------


def test_keeps_only_alerts_whose_ibge_codes_include_joao_pessoa():
    payload = alerts_response(
        make_alert_item(id=1, id_aviso=1),
        make_alert_item(id=2, id_aviso=2, geocodes="2503209,2501807",
                        municipios="Cabedelo - PB (2503209),Bayeux - PB (2501807)"),
    )

    assert [item.alert.id for item in city_alerts(payload).items] == ["1"]


def test_name_alone_is_not_enough_but_ibge_code_in_municipalities_is():
    homonym = make_alert_item(id=1, id_aviso=1, geocodes="9999999", municipios="João Pessoa - XX (9999999)")
    without_geocodes = make_alert_item(id=2, id_aviso=2, geocodes=None,
                                       municipios=f"João Pessoa - PB ({JOAO_PESSOA})")

    assert [item.alert.id for item in city_alerts(alerts_response(homonym, without_geocodes)).items] == ["2"]


def test_alert_without_any_area_is_reported_as_unverifiable_not_dropped_silently():
    payload = alerts_response(make_alert_item(geocodes=None, municipios=None))

    result = city_alerts(payload)

    assert result.items == ()
    assert result.unverifiable == 1


# --- situação: vigente, futuro, expirado ---------------------------------------------------------------------


def test_expired_and_closed_alerts_are_excluded():
    payload = alerts_response(
        make_alert_item(id=1, id_aviso=1, inicio="2026-11-09 00:00", fim="2026-11-10 12:00"),  # terminou
        make_alert_item(id=2, id_aviso=2, encerrado=True),  # encerrado pelo INMET antes do fim
        make_alert_item(id=3, id_aviso=3),  # vigente
    )

    assert [item.alert.id for item in city_alerts(payload).items] == ["3"]


def test_future_alerts_are_shown_after_active_ones():
    payload = alerts_response(
        make_alert_item(id=1, id_aviso=1),
        future=(make_alert_item(id=2, id_aviso=2, inicio="2026-11-12 00:00", fim="2026-11-12 23:59"),),
    )

    items = city_alerts(payload).items

    assert [(item.alert.id, item.status) for item in items] == [("1", AlertStatus.ACTIVE), ("2", AlertStatus.FUTURE)]


def test_status_boundaries_use_brasilia_time_from_the_source():
    alert = parse(alerts_response(make_alert_item(inicio="2026-11-10 08:00", fim="2026-11-10 18:00"))).alerts[0]

    assert alert_status(alert, datetime(2026, 11, 10, 7, 59, tzinfo=JP_ZONE)) is AlertStatus.FUTURE
    assert alert_status(alert, datetime(2026, 11, 10, 8, 0, tzinfo=JP_ZONE)) is AlertStatus.ACTIVE
    assert alert_status(alert, datetime(2026, 11, 10, 18, 0, tzinfo=JP_ZONE)) is AlertStatus.ACTIVE
    # 21:00 UTC é 18:00 em Brasília (ainda vigente); 21:01 UTC já passou do fim
    assert alert_status(alert, datetime(2026, 11, 10, 21, 0, tzinfo=timezone.utc)) is AlertStatus.ACTIVE
    assert alert_status(alert, datetime(2026, 11, 10, 21, 1, tzinfo=timezone.utc)) is AlertStatus.EXPIRED


def test_newer_version_of_the_same_notice_replaces_the_older():
    payload = alerts_response(
        make_alert_item(id=10, id_aviso=7, id_sequencia=1, severidade="Perigo Potencial"),
        make_alert_item(id=11, id_aviso=7, id_sequencia=2, severidade="Perigo", aviso_cor="#F96602"),
    )

    items = city_alerts(payload).items

    assert [(item.alert.id, item.alert.severity) for item in items] == [("11", "Perigo")]


# --- dados incompletos ou inválidos --------------------------------------------------------------------------


def test_missing_optional_fields_stay_empty_instead_of_being_invented():
    item = make_alert_item()
    for field in ("descricao", "severidade", "aviso_cor", "riscos", "instrucoes", "mesorregioes", "estados"):
        item.pop(field)

    alert = city_alerts(alerts_response(item)).items[0].alert

    assert alert.event is None and alert.severity is None and alert.color is None
    assert alert.risks == () and alert.instructions == ()


def test_dates_fall_back_to_separate_date_and_time_fields():
    item = make_alert_item()
    item.pop("inicio")
    item.pop("fim")

    alert = parse(alerts_response(item)).alerts[0]

    assert alert.starts_at == datetime(2026, 11, 10, 8, 0, tzinfo=BRASILIA)
    assert alert.ends_at == datetime(2026, 11, 11, 23, 59, tzinfo=BRASILIA)


def test_alert_without_valid_period_is_kept_with_unknown_validity():
    item = make_alert_item(inicio="amanhã", fim=None, data_fim=None, hora_fim=None)

    items = city_alerts(alerts_response(item)).items

    assert [item.status for item in items] == [AlertStatus.UNKNOWN]


def test_invalid_color_and_wrong_types_are_ignored():
    item = make_alert_item(aviso_cor="javascript:alert(1)", riscos="Texto único", instrucoes=[None, " ", 3])

    alert = parse(alerts_response(item)).alerts[0]

    assert alert.color is None
    assert alert.risks == ("Texto único",)
    assert alert.instructions == ("3",)


def test_unreadable_items_are_counted():
    payload = alerts_response(make_alert_item(), "lixo", {"sem_id": True})

    feed = parse(payload)

    assert len(feed.alerts) == 1 and feed.unreadable == 2
    assert alerts_for_city(feed, JOAO_PESSOA, RECORDED_AT).unverifiable == 2


@pytest.mark.parametrize("payload", [[], {}, {"hoje": []}, {"hoje": None, "futuro": []}, {"avisos": []}])
def test_changed_response_format_is_an_error_not_an_empty_list(payload):
    """Sem as duas listas não dá para afirmar que não há avisos."""
    with pytest.raises(SourceError, match="Formato inesperado"):
        parse(payload)


def test_empty_lists_mean_no_alerts():
    assert city_alerts(alerts_response()).items == ()


# --- client --------------------------------------------------------------------------------------------------


def test_client_reads_the_feed(settings, alerts_payload):
    session = FakeSession(FakeResponse(alerts_payload))

    feed = InmetAlertsClient(session, settings.alerts, timeout_seconds=5).fetch()

    assert session.calls[0]["url"] == "https://apiprevmet3.inmet.gov.br/avisos/ativos"
    assert len(feed.alerts) == 10


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (requests.Timeout("lento"), "INMET não respondeu em 5 s"),
        (requests.ConnectionError("reset"), "Sem conexão com INMET"),
        (FakeResponse(text="<html>manutenção</html>", status_code=503), "INMET respondeu HTTP 503"),
        (FakeResponse({"hoje": "x", "futuro": []}), "Formato inesperado"),
    ],
)
def test_client_failures_become_source_error(settings, outcome, message):
    with pytest.raises(SourceError, match=message):
        InmetAlertsClient(FakeSession(outcome), settings.alerts, timeout_seconds=5).fetch()
