PRIMARY_SERIES = "#2a78d6"
SECONDARY_SERIES = "#eb6834"
MUTED_SERIES = "#a3a29c"
GUIDELINE = "#52514e"
GRID = "rgba(128,128,128,0.18)"

DARK_TEXT_BANDS = frozenset({"Boa", "Moderada", "Ruim p/ sensíveis", "Sem dado"})


def text_color_on(band_label: str) -> str:
    return "#111111" if band_label in DARK_TEXT_BANDS else "#ffffff"
