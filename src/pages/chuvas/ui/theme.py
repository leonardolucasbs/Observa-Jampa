PRIMARY = "#1D4899"
TEXT = "#021047"
SOFT_BACKGROUND = "#F0F4FF"
BORDER = "rgba(2, 16, 71, 0.15)"
NO_SEVERITY_COLOR = "#A3A29C"  


def readable_text_on(hex_color: str) -> str:
    red, green, blue = (int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5))
    luminance = 0.2126 * _linear(red) + 0.7152 * _linear(green) + 0.0722 * _linear(blue)
    return "#111111" if (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) else "#ffffff"


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
