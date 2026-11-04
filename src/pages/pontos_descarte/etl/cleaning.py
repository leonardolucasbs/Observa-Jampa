"""Limpeza das linhas da planilha de pontos de descarte.

A planilha veio de um mapa colaborativo e mistura grafias ("MANAIRA", "Manaíra"), campos trocados
(telefone e e-mail dentro do CEP), sobras de importação (", 0", aspas soltas) e endereços "Brasil".
"""

import math
import re
from typing import Any

from pages.pontos_descarte.domain.places import canonical_neighborhood, smart_title
from pages.pontos_descarte.domain.text import normalize

KNOWN_CITIES = {
    "joao pessoa": "João Pessoa",
    "cabedelo": "Cabedelo",
    "santa rita": "Santa Rita",
    "bayeux": "Bayeux",
    "conde": "Conde",
}

_CEP = re.compile(r"\b(\d{5})-?(\d{3})\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"telefone\s*:?\s*(\(?\d{2}\)?\s*\d{4,5}-?\d{4})", re.IGNORECASE)
_WHATSAPP = re.compile(r"whats\s*app\s*:?\s*(\+?[\d\s()-]{8,}\d)", re.IGNORECASE)
_CITY_SUFFIX = re.compile(r",?\s*\b(jo[aã]o pessoa|santa rita|cabedelo|bayeux)\b.*$", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


def clean_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Uma linha da aba "Pontos" → registro limpo (ainda sem o enriquecimento do OpenStreetMap)."""
    contact_text = " ".join(filter(None, (text(raw.get("cep")), text(raw.get("informacoes")))))
    return {
        "id": int(raw["id_marcador"]),
        "name": text(raw.get("nome")) or f"Ponto {raw['id_marcador']}",
        "latitude": float(raw["latitude"]),
        "longitude": float(raw["longitude"]),
        "waste_description": clean_description(raw.get("tipo_descarte")),
        "address": clean_address(raw.get("endereco_rua")),
        "neighborhood": canonical_neighborhood(text(raw.get("bairro"))),
        "city": clean_city(raw.get("cidade")),
        "state": clean_state(raw.get("estado")),
        "postal_code": extract_postal_code(raw.get("cep")),
        "notes": text(raw.get("informacoes")),
        "phone": _first_group(_PHONE, contact_text),
        "email": _first_match(_EMAIL, contact_text),
        "whatsapp": _first_group(_WHATSAPP, contact_text),
        "address_estimated": False,
        "neighborhood_estimated": False,
        "coordinates_status": text(raw.get("status_coordenadas")),
        "coordinates_check": text(raw.get("verificar_no_maps")),
        "source": text(raw.get("fonte")),
    }


def text(value: Any) -> str | None:
    """Texto sem espaços duplicados nem aspas soltas; vazio/NaN → None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    cleaned = _SPACES.sub(" ", str(value).replace('"', "")).strip()
    return cleaned or None


def clean_description(value: Any) -> str:
    description = text(value) or "Resíduos eletroeletrônicos (detalhes não especificados)"
    description = description.strip("() ") if description.startswith("(") else description
    return description[:1].upper() + description[1:]


def clean_address(value: Any) -> str | None:
    """"AV. PRESIDENTE EPITÁCIO PESSOA, 1883, 0" → "Av. Presidente Epitácio Pessoa, 1883"."""
    address = text(value)
    if not address or normalize(address) in {"brasil", ""}:
        return None
    address = _CITY_SUFFIX.sub("", address)
    address = re.sub(r"^(rua|av|avenida)\s*:", r"\1", address, flags=re.IGNORECASE)
    parts = [part.strip() for part in address.split(",")]
    parts = [part for part in parts if part not in {"", "0", "-", "."}]
    address = ", ".join(parts)
    if not address:
        return None
    letters = [char for char in address if char.isalpha()]
    if letters and all(char.isupper() for char in letters):
        address = smart_title(address)
    return address


def clean_city(value: Any) -> str | None:
    city = text(value)
    if not city:
        return None
    return KNOWN_CITIES.get(normalize(city), smart_title(city))


def clean_state(value: Any) -> str | None:
    state = text(value)
    if not state:
        return None
    return "PB" if normalize(state) in {"pb", "paraiba"} else state


def extract_postal_code(value: Any) -> str | None:
    match = _CEP.search(text(value) or "")
    return f"{match.group(1)}-{match.group(2)}" if match else None


def _first_match(pattern: re.Pattern[str], value: str) -> str | None:
    match = pattern.search(value)
    return match.group(0).rstrip(".") if match else None


def _first_group(pattern: re.Pattern[str], value: str) -> str | None:
    match = pattern.search(value)
    return _SPACES.sub(" ", match.group(1)).strip() if match else None
