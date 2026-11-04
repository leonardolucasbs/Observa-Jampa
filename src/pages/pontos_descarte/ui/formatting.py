from urllib.parse import urlencode

from pages.pontos_descarte.domain.models import Coordinates, DisposalPoint

# Serviço OSRM → modo de viagem do Google Maps (para o botão "Abrir no Google Maps").
GOOGLE_TRAVEL_MODES = {"routed-car": "driving", "routed-foot": "walking", "routed-bike": "bicycling"}


def format_distance(meters: float) -> str:
    if meters < 1000:
        return f"{round(meters / 10) * 10:.0f} m"
    return f"{meters / 1000:.1f} km".replace(".", ",")


def format_duration(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h {rest:02d} min"


def full_address(point: DisposalPoint) -> str:
    """"Rua X, 10 · Manaíra · João Pessoa/PB · CEP 58000-000"."""
    city = "/".join(part for part in (point.city, point.state) if part)
    postal = f"CEP {point.postal_code}" if point.postal_code else None
    parts = [part for part in (point.address, point.neighborhood, city, postal) if part]
    return " · ".join(parts) or "Endereço não informado"


def google_maps_place_url(point: DisposalPoint) -> str:
    return "https://www.google.com/maps/search/?" + urlencode(
        {"api": 1, "query": f"{point.latitude},{point.longitude}"}
    )


def google_maps_directions_url(origin: Coordinates | None, point: DisposalPoint, service: str | None) -> str:
    params = {"api": 1, "destination": f"{point.latitude},{point.longitude}"}
    if origin:
        params["origin"] = f"{origin.latitude},{origin.longitude}"
    if service in GOOGLE_TRAVEL_MODES:
        params["travelmode"] = GOOGLE_TRAVEL_MODES[service]
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def whatsapp_url(number: str) -> str:
    return "https://wa.me/" + "".join(char for char in number if char.isdigit())
