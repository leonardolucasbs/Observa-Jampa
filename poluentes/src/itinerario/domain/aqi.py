from dataclasses import dataclass


@dataclass(frozen=True)
class AqiBand:
    label: str
    color: str
    upper_bound: int


EPA_BANDS: tuple[AqiBand, ...] = (
    AqiBand("Boa", "#00E400", 50),
    AqiBand("Moderada", "#FFFF00", 100),
    AqiBand("Ruim p/ sensíveis", "#FF7E00", 150),
    AqiBand("Ruim", "#FF0000", 200),
    AqiBand("Muito ruim", "#8F3F97", 300),
    AqiBand("Perigosa", "#7E0023", 10_000),
)

UNKNOWN_BAND = AqiBand("Sem dado", "#9E9E9E", -1)


def classify_us_aqi(value: float | None) -> AqiBand:
    if value is None or value != value or value < 0:
        return UNKNOWN_BAND
    return next(band for band in EPA_BANDS if value <= band.upper_bound)


def dominant_pollutant(sub_indices: dict[str, float | None]) -> str | None:
    available = {name: value for name, value in sub_indices.items() if value is not None}
    if not available:
        return None
    return max(available, key=lambda name: available[name])
