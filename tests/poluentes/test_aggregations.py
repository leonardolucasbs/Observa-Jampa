import math

import pandas as pd
import pytest

from pages.poluentes.domain.aqi import classify_us_aqi, dominant_pollutant
from pages.poluentes.services.aggregations import daily_means, hourly_profile, period_mean_by_location


def frame(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    data = pd.DataFrame(rows, columns=["slug", "measured_at", "pm2_5"])
    data["measured_at"] = pd.to_datetime(data["measured_at"])
    data["name"] = data["slug"].str.title()
    return data


def test_hourly_profile_averages_same_hour_across_days_and_has_24_rows() -> None:
    data = frame(
        [
            ("jp", "2026-10-29 08:00", 10.0),
            ("jp", "2026-10-30 08:00", 20.0),
            ("jp", "2026-10-30 09:00", 5.0),
        ]
    )

    profile = hourly_profile(data, ["pm2_5"])

    assert list(profile.index) == list(range(24))
    assert profile.loc[8, "pm2_5"] == pytest.approx(15.0)
    assert profile.loc[9, "pm2_5"] == pytest.approx(5.0)
    assert math.isnan(profile.loc[0, "pm2_5"])


def test_daily_means_groups_by_calendar_day_ignoring_missing() -> None:
    data = frame(
        [
            ("jp", "2026-10-29 00:00", 10.0),
            ("jp", "2026-10-29 23:00", 20.0),
            ("jp", "2026-10-30 01:00", 6.0),
            ("jp", "2026-10-30 02:00", float("nan")),
        ]
    )

    means = daily_means(data, ["pm2_5"])

    assert list(means.index) == list(pd.to_datetime(["2026-10-29", "2026-10-30"]))
    assert means["pm2_5"].tolist() == pytest.approx([15.0, 6.0])


def test_period_mean_by_location_sorted_desc() -> None:
    data = frame(
        [
            ("jp", "2026-10-30 00:00", 10.0),
            ("jp", "2026-10-30 01:00", 12.0),
            ("sp", "2026-10-30 00:00", 30.0),
        ]
    )

    means = period_mean_by_location(data, "pm2_5")

    assert means["slug"].tolist() == ["sp", "jp"]
    assert means["pm2_5"].tolist() == pytest.approx([30.0, 11.0])


def test_aggregations_handle_empty_frame() -> None:
    empty = pd.DataFrame(columns=["slug", "name", "measured_at", "pm2_5"])

    assert len(hourly_profile(empty, ["pm2_5"])) == 24
    assert daily_means(empty, ["pm2_5"]).empty
    assert period_mean_by_location(empty, "pm2_5").empty


@pytest.mark.parametrize(
    ("value", "label"),
    [(0, "Boa"), (50, "Boa"), (51, "Moderada"), (101, "Ruim p/ sensíveis"), (151, "Ruim"), (201, "Muito ruim"), (301, "Perigosa"), (None, "Sem dado")],
)
def test_classify_us_aqi_epa_bands(value: int | None, label: str) -> None:
    assert classify_us_aqi(value).label == label


def test_dominant_pollutant_is_highest_sub_index() -> None:
    assert dominant_pollutant({"pm2_5": 52, "ozone": 20, "pm10": None}) == "pm2_5"
    assert dominant_pollutant({"pm2_5": None}) is None
