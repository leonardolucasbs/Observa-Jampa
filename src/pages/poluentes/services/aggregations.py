from collections.abc import Sequence

import pandas as pd

HOURS_OF_DAY: range = range(24)


def hourly_profile(frame: pd.DataFrame, pollutants: Sequence[str]) -> pd.DataFrame:
    columns = list(pollutants)
    if frame.empty:
        return pd.DataFrame(index=pd.Index(HOURS_OF_DAY, name="hour"), columns=columns, dtype=float)
    hours = pd.to_datetime(frame["measured_at"]).dt.hour.rename("hour")
    profile = frame[columns].astype(float).groupby(hours).mean()
    return profile.reindex(pd.Index(HOURS_OF_DAY, name="hour"))


def daily_means(frame: pd.DataFrame, pollutants: Sequence[str]) -> pd.DataFrame:
    columns = list(pollutants)
    if frame.empty:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="date"), columns=columns, dtype=float)
    days = pd.to_datetime(frame["measured_at"]).dt.normalize().rename("date")
    return frame[columns].astype(float).groupby(days).mean()


def daily_median(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Mediana diária de `column` e quantas horas têm dado.

    Com número par de valores, fica o maior dos dois do meio (a mediana é sempre um valor observado).
    """
    if frame.empty:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="date"), columns=["median", "hours"], dtype=float)
    days = pd.to_datetime(frame["measured_at"]).dt.normalize().rename("date")
    grouped = frame[column].astype(float).groupby(days)
    return pd.DataFrame({"median": grouped.quantile(0.5, interpolation="higher"), "hours": grouped.count()})


def period_mean_by_location(frame: pd.DataFrame, pollutant: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["slug", "name", pollutant])
    means = (
        frame.assign(**{pollutant: frame[pollutant].astype(float)})
        .groupby(["slug", "name"], as_index=False)[pollutant]
        .mean()
    )
    return means.sort_values(pollutant, ascending=False, ignore_index=True)
