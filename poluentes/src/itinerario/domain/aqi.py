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

SCALE_MAX = 500


def classify_us_aqi(value: float | None) -> AqiBand:
    if value is None or value != value or value < 0:
        return UNKNOWN_BAND
    return next(band for band in EPA_BANDS if value <= band.upper_bound)


def band_severity(band: AqiBand) -> int:
    """Posição da faixa na escala EPA (0 = Boa); -1 quando não há dado."""
    return EPA_BANDS.index(band) if band in EPA_BANDS else -1


def band_lower_bound(band: AqiBand) -> int:
    index = band_severity(band)
    return 0 if index <= 0 else EPA_BANDS[index - 1].upper_bound + 1


def scale_position(value: float | None) -> float | None:
    """Posição de 0 a 1 numa escala com as seis faixas EPA de mesma largura."""
    band = classify_us_aqi(value)
    index = band_severity(band)
    if index < 0:
        return None
    lower = 0 if index == 0 else EPA_BANDS[index - 1].upper_bound
    upper = min(band.upper_bound, SCALE_MAX)
    fraction = min(max((value - lower) / (upper - lower), 0.0), 1.0)
    return (index + fraction) / len(EPA_BANDS)


def dominant_pollutant(sub_indices: dict[str, float | None]) -> str | None:
    available = {name: value for name, value in sub_indices.items() if value is not None}
    if not available:
        return None
    return max(available, key=lambda name: available[name])
