"""Textos em linguagem simples para quem não é da área, um por faixa do US AQI (EPA/AirNow)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BandGuidance:
    icon: str
    name: str
    headline: str
    meaning: str


BAND_GUIDANCE: dict[str, BandGuidance] = {
    "Boa": BandGuidance(
        icon="😊",
        name="Boa",
        headline="O ar está bom",
        meaning="A poluição oferece pouco ou nenhum risco à saúde.",
    ),
    "Moderada": BandGuidance(
        icon="🙂",
        name="Moderada",
        headline="O ar está moderado",
        meaning="Aceitável para a maioria. Quem é muito sensível à poluição pode sentir algum efeito.",
    ),
    "Ruim p/ sensíveis": BandGuidance(
        icon="😐",
        name="Ruim para grupos sensíveis",
        headline="O ar está ruim para grupos sensíveis",
        meaning="Grupos sensíveis podem ter problemas de saúde. O restante da população raramente sente efeitos.",
    ),
    "Ruim": BandGuidance(
        icon="😷",
        name="Ruim",
        headline="O ar está ruim",
        meaning="Qualquer pessoa pode começar a sentir efeitos; grupos sensíveis, de forma mais séria.",
    ),
    "Muito ruim": BandGuidance(
        icon="😫",
        name="Muito ruim",
        headline="O ar está muito ruim",
        meaning="Alerta de saúde: o risco de efeitos aumenta para todos.",
    ),
    "Perigosa": BandGuidance(
        icon="🚨",
        name="Perigosa",
        headline="Alerta: o ar está perigoso",
        meaning="Emergência de saúde: todos podem ser afetados.",
    ),
}

UNKNOWN_GUIDANCE = BandGuidance(
    icon="❔",
    name="Sem dado",
    headline="Sem dados no momento",
    meaning="Ainda não há uma estimativa recente para a cidade.",
)


def guidance_for(band_label: str) -> BandGuidance:
    return BAND_GUIDANCE.get(band_label, UNKNOWN_GUIDANCE)
