import json

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.etl.cleaning import clean_address, clean_row
from pages.pontos_descarte.etl.pipeline import enrich, prepare_points, write_points
from pages.pontos_descarte.repositories.points_repository import PointsRepository
from pages.pontos_descarte.domain.models import Category

RAW_LG = {
    "id_marcador": 72,
    "nome": "Descarte de aparelhos LG",
    "latitude": -7.1160536,
    "longitude": -34.8866922,
    "endereco_rua": "Rua: Da Areia, 447,Varadouro João Pessoa",
    "bairro": float("nan"),
    "cep": "58010-640 Telefone: (83) 3241-5655 E-mail: proclimax@uol.com.br",
    "cidade": float("nan"),
    "estado": float("nan"),
    "tipo_descarte": "Resíduos eletroeletrônicos (confirmar categorias aceitas diretamente com o ponto).",
    "informacoes": float("nan"),
    "status_coordenadas": "coordenadas disponíveis",
    "verificar_no_maps": "Coordenada original (não conferida)",
    "fonte": 'Google My Maps - Descarte de resíduos eletroeletrônicos em João Pessoa/PB"',
}

RAW_ABREE = {
    "id_marcador": 1,
    "nome": "PEV ABREE - LOJA VIVO TAMBIA SHOPPING",
    "latitude": -7.1157007,
    "longitude": -34.8801605,
    "endereco_rua": "RUA DEPUTADO ODON BEZERRA, 184, LOJA 80",
    "bairro": "TAMBIA",
    "cep": "58020-500",
    "cidade": "João Pessoa",
    "estado": "Paraíba",
    "tipo_descarte": "entrega de celulares, carregadores, fones de ouvido, pilhas, baterias",
    "informacoes": "Agendamento pelo e-mail  coleta@abree.org.br ou via WhatsApp +55 11 97656-2374.",
    "status_coordenadas": "coordenadas disponíveis",
    "verificar_no_maps": "Conferido (valor informado)",
    "fonte": "Google My Maps",
}


def test_clean_row_fixes_case_accents_and_extracts_contacts():
    record = clean_row(RAW_ABREE)
    assert record["address"] == "Rua Deputado Odon Bezerra, 184, Loja 80"
    assert record["neighborhood"] == "Tambiá"
    assert record["state"] == "PB"
    assert record["postal_code"] == "58020-500"
    assert record["email"] == "coleta@abree.org.br"
    assert record["whatsapp"] == "+55 11 97656-2374"
    assert record["waste_description"].startswith("Entrega de celulares")
    assert record["notes"] == "Agendamento pelo e-mail coleta@abree.org.br ou via WhatsApp +55 11 97656-2374."


def test_clean_row_separates_fields_mixed_into_postal_code():
    record = clean_row(RAW_LG)
    assert record["postal_code"] == "58010-640"
    assert record["phone"] == "(83) 3241-5655"
    assert record["email"] == "proclimax@uol.com.br"
    assert record["address"] == "Rua Da Areia, 447, Varadouro"
    assert record["source"] == "Google My Maps - Descarte de resíduos eletroeletrônicos em João Pessoa/PB"
    assert record["neighborhood"] is None and record["city"] is None


def test_clean_address_removes_import_leftovers():
    assert clean_address("AV. PRESIDENTE EPITÁCIO PESSOA, 1883, 0") == "Av. Presidente Epitácio Pessoa, 1883"
    assert clean_address("Rua Josefa Taveira, 1350, .") == "Rua Josefa Taveira, 1350"
    assert clean_address("Av. Pres. Epitácio Pessoa, 531, Centro, João Pessoa, PB.") == (
        "Av. Pres. Epitácio Pessoa, 531, Centro"
    )
    assert clean_address("Brasil") is None
    assert clean_address(float("nan")) is None


def test_enrich_fills_only_missing_fields_and_marks_them_estimated():
    osm = {"road": "Rua da Areia", "house_number": "447", "suburb": "Varadouro", "city": "João Pessoa",
           "state": "Paraíba", "postcode": "58010-640"}
    record = enrich(clean_row(RAW_LG), lambda lat, lon: osm)
    assert record["neighborhood"] == "Varadouro" and record["neighborhood_estimated"]
    assert record["address"] == "Rua Da Areia, 447, Varadouro" and not record["address_estimated"]
    assert record["city"] == "João Pessoa" and record["state"] == "PB"

    untouched = clean_row(RAW_ABREE)
    assert enrich(untouched, lambda lat, lon: osm) == untouched


def test_enrich_keeps_record_when_service_fails():
    def offline(lat, lon):
        raise ServiceError("fora do ar")

    record = clean_row(RAW_LG)
    assert enrich(record, offline) == record


def test_prepare_and_repository_round_trip(tmp_path):
    records = prepare_points([RAW_LG, RAW_ABREE], lambda lat, lon: {"suburb": "Varadouro", "city": "João Pessoa"})
    assert [record["id"] for record in records] == [1, 72]

    path = tmp_path / "pontos.json"
    write_points(records, path)
    assert json.loads(path.read_text(encoding="utf-8"))[1]["neighborhood"] == "Varadouro"

    points = PointsRepository(path).all()
    assert points[0].categories == frozenset({Category.PHONES, Category.BATTERIES})
    assert points[1].categories == frozenset({Category.UNSPECIFIED})
