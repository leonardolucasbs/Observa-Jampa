import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pages.pontos_descarte.config import HttpConfig

RETRYABLE_STATUS: tuple[int, ...] = (429, 500, 502, 503, 504)


class ServiceError(Exception):
    """Falha ao consultar um serviço externo (geocodificação ou rotas)."""


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
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.headers["User-Agent"] = config.user_agent
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_bytes(session: requests.Session, url: str, timeout: float) -> bytes:
    """Baixa um arquivo (ex.: os zips do IBGE)."""
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise ServiceError(f"Sem resposta de {url}: {exc}") from exc
    if response.status_code != 200:
        raise ServiceError(f"{url} respondeu HTTP {response.status_code}")
    return response.content


def get_json(session: requests.Session, url: str, params: dict | None, timeout: float) -> object:
    try:
        response = session.get(url, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise ServiceError(f"Sem resposta de {url}: {exc}") from exc
    if response.status_code != 200:
        raise ServiceError(f"{url} respondeu HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise ServiceError(f"{url} devolveu uma resposta que não é JSON") from exc
