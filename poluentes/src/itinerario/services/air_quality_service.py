from dataclasses import dataclass
from datetime import datetime, time, timedelta

import pandas as pd

from itinerario.clock import Clock
from itinerario.domain.aqi import EPA_BANDS, UNKNOWN_BAND, AqiBand, band_severity, classify_us_aqi
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
        return _with_bands(self._repository.find_latest_until(self._clock()))

    def observed(self, days: int, slugs: list[str] | None = None) -> pd.DataFrame:
        return self._observed_since(self._clock() - timedelta(days=days), slugs)

    def hourly_series(self, slug: str, days: int, pollutants: list[str]) -> pd.DataFrame:
        frame = self.observed(days, [slug])
        return frame[["measured_at", *pollutants]].reset_index(drop=True)

    def daily_means(self, slug: str, days: int, pollutants: list[str]) -> pd.DataFrame:
        return aggregations.daily_means(self.observed(days, [slug]), pollutants)

    def hourly_profile(self, slug: str, days: int) -> pd.DataFrame:
        return aggregations.hourly_profile(self.observed(days, [slug]), POLLUTANTS)

    def city_comparison(self, pollutant: str, days: int) -> pd.DataFrame:
        return aggregations.period_mean_by_location(self.observed(days), pollutant)

    def daily_aqi(self, slug: str, days: int) -> pd.DataFrame:
        """Um registro por dia de calendário (hoje incluso), com a faixa do dia e as horas com dado.

        Cada hora observada é classificada numa faixa EPA e o dia recebe a mediana dessas
        classificações. Um dia completo tem 24 horas; no empate entre as duas faixas do meio,
        fica a pior, para não esconder um dia que passou metade do tempo numa faixa pior.
        """
        calendar = self._calendar(days)
        frame = self._observed_since(calendar[0].to_pydatetime(), [slug])
        if not frame.empty:
            frame = frame.assign(severity=frame["us_aqi"].map(_severity))
        daily = aggregations.daily_median(frame, "severity").reindex(calendar)
        bands = daily["median"].map(_band_at)
        return pd.DataFrame(
            {
                "band_label": bands.map(lambda band: band.label),
                "band_color": bands.map(lambda band: band.color),
                "hours": daily["hours"].fillna(0).astype(int),
            },
            index=calendar,
        )

    def has_data(self) -> bool:
        return self._repository.count() > 0

    def _observed_since(self, start: datetime, slugs: list[str] | None) -> pd.DataFrame:
        frame = self._repository.find_between(start, self._clock(), slugs)
        return frame[~frame["is_forecast"]] if not frame.empty else frame

    def _calendar(self, days: int) -> pd.DatetimeIndex:
        today = datetime.combine(self._clock().date(), time.min)
        return pd.date_range(end=today, periods=days, freq="D", name="date")


def _band(value: object) -> AqiBand:
    return classify_us_aqi(None if pd.isna(value) else float(value))


def _severity(value: object) -> float:
    """Posição da faixa EPA (0 = Boa); NaN sem dado, para ficar fora da mediana."""
    level = band_severity(_band(value))
    return float(level) if level >= 0 else float("nan")


def _band_at(severity: float) -> AqiBand:
    return UNKNOWN_BAND if pd.isna(severity) else EPA_BANDS[int(severity)]


def _with_bands(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.assign(band_label=pd.Series(dtype=str), band_color=pd.Series(dtype=str))
    bands = frame["us_aqi"].map(_band)
    return frame.assign(
        band_label=bands.map(lambda band: band.label),
        band_color=bands.map(lambda band: band.color),
    )
