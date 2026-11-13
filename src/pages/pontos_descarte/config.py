import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FEATURE_DIR = Path(__file__).resolve().parent  # src/pages/pontos_descarte


@dataclass(frozen=True)
class DataConfig:
    spreadsheet: Path
    sheet: str
    points: Path
    city_boundary: Path
    addresses: Path


@dataclass(frozen=True)
class AddressesConfig:
    base_url: str
    max_candidates: int
    cities: dict[str, str]  # cidade → arquivo do CNEFE


@dataclass(frozen=True)
class HttpConfig:
    timeout_seconds: float
    retries: int
    backoff_factor: float
    user_agent: str


@dataclass(frozen=True)
class GeocodingConfig:
    base_url: str
    photon_url: str
    city_hint: str
    viewbox: tuple[float, float, float, float]  # oeste, norte, leste, sul
    min_interval_seconds: float


@dataclass(frozen=True)
class RoutingConfig:
    base_url: str
    candidates: int
    profiles: dict[str, str]  # rótulo → serviço OSRM


@dataclass(frozen=True)
class BoundaryConfig:
    base_url: str
    ibge_code: str
    name: str
    quality: str


@dataclass(frozen=True)
class SearchConfig:
    neighborhood_radius_km: float
    address_radius_km: float


@dataclass(frozen=True)
class MapConfig:
    latitude: float
    longitude: float
    zoom: float
    height: int
    city_fill_opacity: float


@dataclass(frozen=True)
class TextsConfig:
    attribution: str
    disclaimer: str


@dataclass(frozen=True)
class Settings:
    log_level: str
    data: DataConfig
    http: HttpConfig
    addresses: AddressesConfig
    geocoding: GeocodingConfig
    routing: RoutingConfig
    boundary: BoundaryConfig
    search: SearchConfig
    map: MapConfig
    texts: TextsConfig


def load_settings(config_path: Path | None = None) -> Settings:
    """Lê o config.toml do recurso. Caminhos de dados são relativos à pasta do recurso."""
    with (config_path or FEATURE_DIR / "config.toml").open("rb") as file:
        raw = tomllib.load(file)
    return _build_settings(raw, base_dir=FEATURE_DIR)


def _build_settings(raw: dict[str, Any], base_dir: Path) -> Settings:
    data = raw["data"]
    addresses = raw["addresses"]
    geocoding = raw["geocoding"]
    routing = raw["routing"]
    return Settings(
        log_level=raw.get("log_level", "INFO"),
        data=DataConfig(
            spreadsheet=base_dir / data["spreadsheet"],
            sheet=data["sheet"],
            points=base_dir / data["points"],
            city_boundary=base_dir / data["city_boundary"],
            addresses=base_dir / data["addresses"],
        ),
        http=HttpConfig(**raw["http"]),
        addresses=AddressesConfig(
            base_url=addresses["base_url"].rstrip("/"),
            max_candidates=addresses["max_candidates"],
            cities=dict(addresses["cities"]),
        ),
        geocoding=GeocodingConfig(
            base_url=geocoding["base_url"].rstrip("/"),
            photon_url=geocoding["photon_url"].rstrip("/"),
            city_hint=geocoding["city_hint"],
            viewbox=tuple(geocoding["viewbox"]),
            min_interval_seconds=geocoding["min_interval_seconds"],
        ),
        routing=RoutingConfig(
            base_url=routing["base_url"].rstrip("/"),
            candidates=routing["candidates"],
            profiles=dict(routing["profiles"]),
        ),
        boundary=BoundaryConfig(**{**raw["boundary"], "base_url": raw["boundary"]["base_url"].rstrip("/")}),
        search=SearchConfig(**raw["search"]),
        map=MapConfig(**raw["map"]),
        texts=TextsConfig(**raw["texts"]),
    )
