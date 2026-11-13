import io
import zipfile

import pytest

from pages.pontos_descarte.etl.addresses import build_segments, iter_cnefe_rows, number_range, split_street_name
from pages.pontos_descarte.repositories.address_repository import AddressRepository

# Cabeçalho real do CSV do CNEFE (Censo 2022); as linhas abaixo são inventadas no mesmo formato.
HEADER = (
    "COD_UNICO_ENDERECO;COD_UF;COD_MUNICIPIO;COD_DISTRITO;COD_SUBDISTRITO;COD_SETOR;NUM_QUADRA;NUM_FACE;CEP;"
    "DSC_LOCALIDADE;NOM_TIPO_SEGLOGR;NOM_TITULO_SEGLOGR;NOM_SEGLOGR;NUM_ENDERECO;DSC_MODIFICADOR;NOM_COMP_ELEM1;"
    "VAL_COMP_ELEM1;NOM_COMP_ELEM2;VAL_COMP_ELEM2;NOM_COMP_ELEM3;VAL_COMP_ELEM3;NOM_COMP_ELEM4;VAL_COMP_ELEM4;"
    "NOM_COMP_ELEM5;VAL_COMP_ELEM5;LATITUDE;LONGITUDE;NV_GEO_COORD;COD_ESPECIE;DSC_ESTABELECIMENTO;"
    "COD_INDICADOR_ESTAB_ENDERECO;COD_INDICADOR_CONST_ENDERECO;COD_INDICADOR_FINALIDADE_CONST;COD_TIPO_ESPECI"
)


def row(setor, quadra, face, cep, bairro, tipo, titulo, nome, numero, lat, lon) -> str:
    return (
        f"1;25;2507507;250750705;25075070500;{setor};{quadra};{face};{cep};{bairro};{tipo};{titulo};{nome};{numero};"
        f";;;;;;;;;;;{lat};{lon};1;1;;;;;"
    )


ROWS = [
    # Um trecho da Avenida Senador Ruy Carneiro: apartamentos "101 a 107" e um "5102" discrepante.
    *(row("S1", 1, 1, "58038000", "MIRAMAR", "AVENIDA", "SENADOR", "RUY CARNEIRO", n, -7.118, -34.840)
      for n in (101, 103, 105, 107)),
    row("S1", 1, 1, "58038000", "MIRAMAR", "AVENIDA", "SENADOR", "RUY CARNEIRO", 5102, -7.119, -34.841),
    # Outro trecho, só com endereços sem número, num bairro abreviado pelo IBGE.
    row("S2", 4, 2, "58070000", "CRISTO", "RUA", "", "DAS TRINCHEIRAS", "0", -7.150, -34.880),
    row("S2", 4, 2, "58070000", "PADDRE ZE", "RUA", "", "DAS TRINCHEIRAS", "0", -7.151, -34.881),
    row("S2", 4, 2, "58070000", "CRISTO", "RUA", "", "DAS TRINCHEIRAS", "0", -7.152, -34.882),
    # Rua sem nome oficial: fica de fora.
    row("S3", 9, 1, "58000000", "GRAMAME", "RUA", "", "SEM DENOMINACAO 12", 10, -7.250, -34.860),
]


def cnefe_zip(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("2507507_JOAO_PESSOA.csv", ("\n".join([HEADER, *lines]) + "\n").encode("latin-1"))
    return buffer.getvalue()


def test_cnefe_addresses_become_street_segments():
    segments = build_segments(iter_cnefe_rows(cnefe_zip(ROWS)), "João Pessoa")
    assert [segment.street for segment in segments] == ["Avenida Senador Ruy Carneiro", "Rua das Trincheiras"]

    avenue, street = segments
    assert (avenue.street_type, avenue.title, avenue.name) == ("Avenida", "Senador", "Ruy Carneiro")
    assert (avenue.number_min, avenue.number_max) == (101, 107)  # o 5102 ficou de fora da faixa
    assert avenue.addresses == 5
    assert (avenue.latitude, avenue.longitude) == (-7.118, -34.84)  # mediana: o discrepante não puxa
    assert avenue.postal_code == "58038-000"
    assert avenue.neighborhood == "Miramar"

    assert (street.number_min, street.number_max) == (0, 0)  # só S/N
    assert street.neighborhood == "Cristo Redentor"  # "CRISTO", o mais frequente do trecho, padronizado
    assert street.title is None


def test_zip_without_csv_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("leia-me.txt", "nada")
    with pytest.raises(ValueError):
        list(iter_cnefe_rows(buffer.getvalue()))


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        ([], (0, 0)),
        ([1, 30, 60], (1, 60)),  # rua curta: 1 e 60 são do mesmo trecho
        ([101, 103, 105, 107, 5102], (101, 107)),
        ([921, 941, 955, 987, 1019, 1037], (921, 1037)),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 2287], (1, 10)),
    ],
)
def test_number_range_drops_outliers(numbers, expected):
    assert number_range(numbers) == expected


def test_street_name_is_capitalized_as_a_whole():
    assert split_street_name("RUA", "", "DAS TRINCHEIRAS") == {
        "street_type": "Rua", "title": None, "name": "das Trincheiras",
    }
    assert split_street_name("AVENIDA", "NOSSA SENHORA", "DOS NAVEGANTES") == {
        "street_type": "Avenida", "title": "Nossa Senhora", "name": "dos Navegantes",
    }


def test_repository_round_trip(tmp_path):
    segments = tuple(build_segments(iter_cnefe_rows(cnefe_zip(ROWS)), "João Pessoa"))
    repository = AddressRepository(tmp_path / "enderecos.sqlite")
    repository.save(segments, {"fonte": "IBGE"})
    assert repository.load() == segments
    assert repository.metadata() == {"fonte": "IBGE"}
    assert not (tmp_path / "enderecos.tmp").exists()


def test_repository_missing_or_invalid_file_loads_empty(tmp_path):
    assert AddressRepository(tmp_path / "nao_existe.sqlite").load() == ()
    broken = tmp_path / "quebrado.sqlite"
    broken.write_text("isto não é um banco SQLite", encoding="utf-8")
    assert AddressRepository(broken).load() == ()
