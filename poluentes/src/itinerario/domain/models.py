from dataclasses import dataclass
from datetime import datetime

POLLUTANTS: tuple[str, ...] = (
    "pm2_5",
    "pm10",
    "nitrogen_dioxide",
    "ozone",
    "carbon_monoxide",
    "sulphur_dioxide",
    "dust",
)

POLLUTANT_LABELS: dict[str, str] = {
    "pm2_5": "PM2.5",
    "pm10": "PM10",
    "nitrogen_dioxide": "NO₂",
    "ozone": "O₃",
    "carbon_monoxide": "CO",
    "sulphur_dioxide": "SO₂",
    "dust": "Poeira",
}


@dataclass(frozen=True)
class Location:
    slug: str
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class AirQualityReading:
    location_slug: str
    measured_at: datetime
    us_aqi: int | None
    european_aqi: int | None
    pm2_5: float | None
    pm10: float | None
    nitrogen_dioxide: float | None
    ozone: float | None
    carbon_monoxide: float | None
    sulphur_dioxide: float | None
    dust: float | None
    dominant_pollutant: str | None
    is_forecast: bool
    fetched_at: datetime
