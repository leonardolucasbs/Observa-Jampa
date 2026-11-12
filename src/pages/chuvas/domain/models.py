"""Modelos da página de previsão de chuva e avisos meteorológicos.

Valores ausentes são `None`, nunca zero: "sem dado" e "0 mm previstos" são coisas diferentes.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


@dataclass(frozen=True)
class DailyRain:
    """Previsão de um dia (data local de João Pessoa)."""

    day: date
    precipitation_mm: float | None  # volume previsto para o dia inteiro
    probability_max_pct: int | None  # maior probabilidade horária de chuva no dia; não é volume
    from_hourly: bool = False  # True quando o total diário veio da soma das 24 horas (daily ausente)


@dataclass(frozen=True)
class HourlyRain:
    """Chuva prevista em uma hora (horário local de João Pessoa, sem fuso explícito)."""

    moment: datetime
    precipitation_mm: float | None  # volume previsto para essa hora, ou seja, mm/h


@dataclass(frozen=True)
class RainForecast:
    timezone: str
    days: tuple[DailyRain, ...]  # uma entrada por data, sem repetição
    hours: tuple[HourlyRain, ...] = ()  # previsão hora a hora; pode vir vazia se a fonte não trouxe


class Intensity(StrEnum):
    """Intensidade da chuva pelo pico em uma hora (mm/h). Escala usual de referência, não oficial."""

    FRACA = "fraca"
    MODERADA = "moderada"
    FORTE = "forte"
    MUITO_FORTE = "muito forte"


@dataclass(frozen=True)
class RainTotal:
    """Chuva prevista acumulada de `start` a `end` (inclusive)."""

    start: date
    end: date
    precipitation_mm: float | None  # None quando nenhum dia do período tem previsão
    missing_days: tuple[date, ...] = ()  # dias do período sem previsão (não entram na soma)
    probability_max_pct: int | None = None  # só para períodos de um dia
    from_hourly: bool = False
    will_rain: bool | None = None  # só para períodos de um dia: None quando não há previsão
    peak_mm_per_hour: float | None = None  # só para períodos de um dia: maior chuva em uma hora
    peak_at: datetime | None = None  # hora em que ocorre o pico
    intensity: Intensity | None = None  # só quando vai chover e há hora a hora

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def complete(self) -> bool:
        return self.precipitation_mm is not None and not self.missing_days


@dataclass(frozen=True)
class RainOutlook:
    today: RainTotal
    tomorrow: RainTotal
    week: RainTotal
    daily: tuple[DailyRain, ...]  # dias do período de 7 dias que a fonte trouxe, para a tabela dia a dia
    rainy_days: int = 0  # dias da semana com chuva prevista (a partir de RAIN_THRESHOLD_MM)
    known_days: int = 0  # dias da semana com previsão de volume


class AlertStatus(StrEnum):
    ACTIVE = "vigente"
    FUTURE = "futuro"
    EXPIRED = "expirado"
    UNKNOWN = "validade não informada"


@dataclass(frozen=True)
class WeatherAlert:
    """Um aviso meteorológico como a fonte o publicou. Campos ausentes na fonte ficam vazios."""

    id: str
    event: str | None  # fenômeno, ex.: "Chuvas Intensas"
    severity: str | None  # texto da fonte, ex.: "Perigo Potencial"
    color: str | None  # cor oficial do aviso (#RRGGBB)
    starts_at: datetime | None
    ends_at: datetime | None
    closed: bool  # encerrado antes do fim previsto
    geocodes: frozenset[str]  # códigos IBGE dos municípios abrangidos
    municipalities: tuple[str, ...]
    regions: tuple[str, ...]  # mesorregiões
    states: tuple[str, ...]
    risks: tuple[str, ...]
    instructions: tuple[str, ...]
    url: str | None
    notice_id: str | None = None  # mesmo aviso em versões sucessivas
    sequence: int | None = None  # versão do aviso (a maior substitui as anteriores)

    @property
    def coverage_known(self) -> bool:
        return bool(self.geocodes)


@dataclass(frozen=True)
class AlertFeed:
    alerts: tuple[WeatherAlert, ...]
    unreadable: int = 0  # itens da fonte que não puderam ser lidos


@dataclass(frozen=True)
class CityAlert:
    alert: WeatherAlert
    status: AlertStatus


@dataclass(frozen=True)
class CityAlerts:
    """Avisos que abrangem o município, sem os expirados."""

    items: tuple[CityAlert, ...]
    unverifiable: int = 0  # avisos da fonte sem área legível: não dá para saber se incluem o município
