import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pages.chuvas.config import HttpConfig

# 429 não entra: repetir na hora só piora o limite. O cache espera o Retry-After antes de tentar de novo.
RETRYABLE_STATUS: tuple[int, ...] = (500, 502, 503, 504)


class SourceError(Exception):
    """Falha ao consultar ou interpretar uma fonte externa (rede, HTTP, formato da resposta)."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def build_session(config: HttpConfig) -> requests.Session:
    retry = Retry(
        total=config.retries,
        connect=config.retries,
        read=config.retries,
        status=config.retries,
        backoff_factor=config.backoff_factor,
        status_forcelist=RETRYABLE_STATUS,
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
        respect_retry_after_header=False,  # a tela não fica parada esperando; quem respeita o prazo é o cache
    )
    session = requests.Session()
    # O servidor do INMET derrubou uma conexão sem User-Agent identificado durante a validação.
    session.headers["User-Agent"] = config.user_agent
    session.headers["Accept"] = "application/json"
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_json(session: requests.Session, url: str, params: dict | None, timeout: float, source: str) -> object:
    try:
        response = session.get(url, params=params, timeout=timeout)
    except requests.Timeout as exc:
        raise SourceError(f"{source} não respondeu em {timeout:.0f} s") from exc
    except requests.RequestException as exc:
        raise SourceError(f"Sem conexão com {source}") from exc
    if response.status_code == 429:
        raise SourceError(
            f"{source} limitou as consultas (HTTP 429)", retry_after_seconds=_retry_after(response)
        )
    if response.status_code != 200:
        reason = _reason(response)
        raise SourceError(f"{source} respondeu HTTP {response.status_code}" + (f": {reason}" if reason else ""))
    try:
        return response.json()
    except ValueError as exc:
        raise SourceError(f"{source} devolveu uma resposta que não é JSON") from exc


def _reason(response: requests.Response) -> str | None:
    """A Open-Meteo explica o erro em {"error": true, "reason": "..."}."""
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload.get("reason") if isinstance(payload, dict) else None


def _retry_after(response: requests.Response) -> float | None:
    try:
        return float(response.headers.get("Retry-After", ""))
    except ValueError:
        return None
