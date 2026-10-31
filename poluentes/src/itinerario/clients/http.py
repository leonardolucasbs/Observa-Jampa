import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from itinerario.config import HttpConfig

RETRYABLE_STATUS: tuple[int, ...] = (429, 500, 502, 503, 504)


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
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
