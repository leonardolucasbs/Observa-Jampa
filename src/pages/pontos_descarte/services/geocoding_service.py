"""Localiza o que a pessoa digitou: primeiro no índice de endereços do IBGE, depois no OpenStreetMap.

O índice local roda sem internet, aceita erros de digitação e acerta o número da casa. O Nominatim
cobre pontos de referência ("Manaíra Shopping", "UFPB") e ruas abertas depois do Censo 2022.
O Photon é a última tentativa, para lugares digitados com erro.
"""

import logging
from collections.abc import Callable, Sequence

from pages.pontos_descarte.clients.http import ServiceError
from pages.pontos_descarte.domain.addresses import AddressIndex
from pages.pontos_descarte.domain.models import GeocodedPlace

logger = logging.getLogger(__name__)

Geocoder = Callable[[str], GeocodedPlace | None]


class GeocodingService:
    def __init__(self, index: AddressIndex, fallbacks: Sequence[Geocoder], max_candidates: int = 5) -> None:
        self._index = index
        self._fallbacks = tuple(fallbacks)
        self._max_candidates = max_candidates

    def search(self, query: str) -> GeocodedPlace | None:
        """O lugar mais provável, ou None se nenhuma fonte achou."""
        found = self.candidates(query)
        return found[0] if found else None

    def candidates(self, query: str) -> list[GeocodedPlace]:
        """Lugares possíveis, do mais provável ao menos. Mais de um quando o texto é ambíguo
        (a mesma rua em bairros diferentes, "Rua" e "Avenida" com o mesmo nome).

        Levanta ServiceError só se nenhuma fonte achou o lugar e algum serviço externo falhou:
        aí não dá para afirmar que o endereço não existe.
        """
        if not query.strip():
            return []
        local = self._index.search(query, limit=self._max_candidates)
        if local:
            return local
        failure: ServiceError | None = None
        for geocode in self._fallbacks:
            try:
                place = geocode(query)
            except ServiceError as exc:
                logger.warning("Geocodificação de %r falhou: %s", query, exc)
                failure = exc
                continue
            if place:
                return [place]
        if failure:
            raise failure
        return []
