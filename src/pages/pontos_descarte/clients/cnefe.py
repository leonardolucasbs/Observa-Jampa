"""Download dos endereços do Censo 2022 (CNEFE) publicados pelo IBGE, um zip por município.

Dicionário das colunas: Arquivos_CNEFE/CSV/Dicionario_CNEFE_Censo_2022.xls, no mesmo servidor.
"""

import requests

from pages.pontos_descarte.clients.http import get_bytes
from pages.pontos_descarte.config import AddressesConfig


class CnefeClient:
    def __init__(self, session: requests.Session, config: AddressesConfig, timeout_seconds: float) -> None:
        self._session = session
        self._config = config
        self._timeout = timeout_seconds

    def download(self, file_name: str) -> bytes:
        """O zip de um município (ex.: "2507507_JOAO_PESSOA.zip"), com um CSV dentro."""
        return get_bytes(self._session, f"{self._config.base_url}/{file_name}", self._timeout)
