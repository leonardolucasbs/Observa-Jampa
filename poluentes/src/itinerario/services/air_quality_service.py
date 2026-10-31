from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

from itinerario.clock import Clock
from itinerario.domain.aqi import AqiBand, classify_us_aqi
from itinerario.domain.models import POLLUTANT_LABELS, POLLUTANTS
from itinerario.repositories.air_quality_repository import AirQualityRepository
from itinerario.services import aggregations


@dataclass(frozen=True)
class CurrentAirQuality:
    slug: str
    location_name: str
    measured_at: datetime
    us_aqi: int | None
    band: AqiBand
    dominant_pollutant: str | None
    dominant_pollutant_label: str


class AirQualityService:
    def __init__(self, repository: AirQualityRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def current(self, slug: str) -> CurrentAirQuality | None:
        latest = self.current_by_location()
        match = latest[latest["slug"] == slug]
        if match.empty:
            return None
        row = match.iloc[0]
        us_aqi = None if pd.isna(row["us_aqi"]) else int(row["us_aqi"])
        dominant = None if pd.isna(row["dominant_pollutant"]) else str(row["dominant_pollutant"])
        return CurrentAirQuality(
            slug=slug,
            location_name=str(row["name"]),
            measured_at=pd.Timestamp(row["measured_at"]).to_pydatetime(),
            us_aqi=us_aqi,
            band=classify_us_aqi(us_aqi),
            dominant_pollutant=dominant,
            dominant_pollutant_label=POLLUTANT_LABELS.get(dominant, "—") if dominant else "—",
        )

    def current_by_location(self) -> pd.DataFrame:
        latest = self._repository.find_latest_until(self._clock())
        if latest.empty:
            return latest.assign(band_label=pd.Series(dtype=str), band_color=pd.Series(dtype=str))
        bands = latest["us_aqi"].map(lambda value: classify_us_aqi(None if pd.isna(value) else float(value)))
        return latest.assign(
            band_label=bands.map(lambda band: band.label),
            band_color=bands.map(lambda band: band.color),
        )

    def observed(self, days: int, slugs: list[str] | None = None) -> pd.DataFrame:
        end = self._clock()
        start = end - timedelta(days=days)
        frame = self._repository.find_between(start, end, slugs)
        return frame[~frame["is_forecast"]] if not frame.empty else frame

    def hourly_series(self, slug: str, days: int, pollutants: list[str]) -> pd.DataFrame:
        frame = self.observed(days, [slug])
        return frame[["measured_at", *pollutants]].reset_index(drop=True)

    def daily_means(self, slug: str, days: int, pollutants: list[str]) -> pd.DataFrame:
        return aggregations.daily_means(self.observed(days, [slug]), pollutants)

    def hourly_profile(self, slug: str, days: int) -> pd.DataFrame:
        return aggregations.hourly_profile(self.observed(days, [slug]), POLLUTANTS)

    def city_comparison(self, pollutant: str, days: int) -> pd.DataFrame:
        return aggregations.period_mean_by_location(self.observed(days), pollutant)

    def has_data(self) -> bool:
        return self._repository.count() > 0
