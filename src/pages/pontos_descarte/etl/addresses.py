"""CNEFE do IBGE (endereços do Censo 2022) → trechos de rua do índice de endereços.

Cada endereço do CNEFE tem coordenada própria. Para o índice ficar pequeno, os endereços são
agrupados por face de quadra (o lado de um quarteirão, entre duas esquinas): cada trecho guarda a
faixa de números e a coordenada mediana. O erro fica em dezenas de metros, bem menor que o raio
de busca da página.
"""

import csv
import io
import statistics
import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from pages.pontos_descarte.domain.models import StreetSegment
from pages.pontos_descarte.domain.places import canonical_neighborhood, smart_title
from pages.pontos_descarte.domain.text import normalize

CNEFE_ENCODING = "latin-1"
CNEFE_DELIMITER = ";"
UNNAMED_PREFIX = "sem denominacao"  # "SEM DENOMINACAO 12": rua sem nome oficial, ninguém busca por ela
COORDINATE_DECIMALS = 5  # ~1 m
# Números muito longe da mediana do trecho são ruído (apartamentos "101, 102..." registrados como
# número da casa) e esticariam a faixa: um trecho "101 a 5102" "conteria" o 1000 de outro bairro.
OUTLIER_FACTOR = 3
OUTLIER_SLACK = 50  # folga para ruas curtas, em que 1 e 60 são números legítimos do mesmo trecho


def iter_cnefe_rows(content: bytes) -> Iterator[dict[str, str]]:
    """Linhas do CSV dentro do zip do CNEFE, uma de cada vez (o de João Pessoa tem 73 MB)."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        name = next((name for name in archive.namelist() if name.lower().endswith(".csv")), None)
        if name is None:
            raise ValueError("O arquivo do CNEFE não tem um CSV dentro")
        with archive.open(name) as raw:
            text = io.TextIOWrapper(raw, encoding=CNEFE_ENCODING, newline="")
            yield from csv.DictReader(text, delimiter=CNEFE_DELIMITER)


@dataclass
class _Face:
    numbers: list[int] = field(default_factory=list)
    latitudes: list[float] = field(default_factory=list)
    longitudes: list[float] = field(default_factory=list)
    neighborhoods: Counter[str] = field(default_factory=Counter)
    postal_codes: Counter[str] = field(default_factory=Counter)

    def add(self, row: dict[str, str]) -> None:
        number = row["NUM_ENDERECO"].strip()
        if number.isdigit() and int(number) > 0:
            self.numbers.append(int(number))
        self.latitudes.append(float(row["LATITUDE"]))
        self.longitudes.append(float(row["LONGITUDE"]))
        if row["DSC_LOCALIDADE"].strip():
            self.neighborhoods[row["DSC_LOCALIDADE"].strip()] += 1
        if row["CEP"].strip():
            self.postal_codes[row["CEP"].strip()] += 1


def build_segments(rows: Iterable[dict[str, str]], city: str) -> list[StreetSegment]:
    """Agrupa os endereços de uma cidade em trechos de rua (face de quadra)."""
    faces: dict[tuple[str, ...], _Face] = {}
    for row in rows:
        name = row["NOM_SEGLOGR"].strip()
        if not name or normalize(name).startswith(UNNAMED_PREFIX):
            continue
        key = (
            row["NOM_TIPO_SEGLOGR"].strip(),
            row["NOM_TITULO_SEGLOGR"].strip(),
            name,
            row["COD_SETOR"],
            row["NUM_QUADRA"],
            row["NUM_FACE"],
        )
        faces.setdefault(key, _Face()).add(row)

    neighborhoods: dict[str, str | None] = {}  # o mesmo bairro aparece em milhares de trechos
    segments = []
    for (street_type, title, name, *_), face in faces.items():
        raw_neighborhood = face.neighborhoods.most_common(1)[0][0] if face.neighborhoods else None
        if raw_neighborhood not in neighborhoods:
            neighborhoods[raw_neighborhood] = canonical_neighborhood(raw_neighborhood, fuzzy=True)
        number_min, number_max = number_range(face.numbers)
        segments.append(
            StreetSegment(
                city=city,
                **split_street_name(street_type, title, name),
                neighborhood=neighborhoods[raw_neighborhood],
                postal_code=format_postal_code(face.postal_codes.most_common(1)[0][0]) if face.postal_codes else None,
                number_min=number_min,
                number_max=number_max,
                latitude=round(statistics.median(face.latitudes), COORDINATE_DECIMALS),
                longitude=round(statistics.median(face.longitudes), COORDINATE_DECIMALS),
                addresses=len(face.latitudes),
            )
        )
    return sorted(segments, key=_segment_order)


def number_range(numbers: list[int]) -> tuple[int, int]:
    """Faixa de números do trecho sem os discrepantes; (0, 0) se o trecho só tem endereços S/N."""
    if not numbers:
        return 0, 0
    median = statistics.median(numbers)
    kept = [n for n in numbers if median / OUTLIER_FACTOR - OUTLIER_SLACK <= n <= median * OUTLIER_FACTOR + OUTLIER_SLACK]
    return min(kept), max(kept)


def split_street_name(street_type: str, title: str, name: str) -> dict[str, str | None]:
    """Capitaliza o nome inteiro de uma vez ("Rua das Trincheiras", não "Rua Das Trincheiras")
    e separa de novo em tipo, título e nome."""
    words = smart_title(" ".join(part for part in (street_type, title, name) if part)).split()
    type_size, title_size = len(street_type.split()), len(title.split())
    return {
        "street_type": " ".join(words[:type_size]),
        "title": " ".join(words[type_size : type_size + title_size]) or None,
        "name": " ".join(words[type_size + title_size :]),
    }


def format_postal_code(raw: str) -> str:
    digits = "".join(char for char in raw if char.isdigit())
    return f"{digits[:5]}-{digits[5:]}" if len(digits) == 8 else raw


def _segment_order(segment: StreetSegment) -> tuple:
    return (
        segment.city,
        segment.street,
        segment.neighborhood or "",
        segment.number_min,
        segment.number_max,
        segment.latitude,
        segment.longitude,
    )
