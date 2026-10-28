import hashlib
import json
from collections.abc import Iterable

from apebot.modelos import Anuncio, Filtro, Pessoa

Chave = tuple[str, str]


def aceita(filtro: Filtro, anuncio: Anuncio) -> bool:
    return (
        anuncio.bairro_slug in filtro.bairros
        and anuncio.tipo in filtro.tipos
        and anuncio.quartos >= filtro.quartos_min
        and anuncio.aluguel_centavos <= filtro.aluguel_max_centavos
    )


def novos_para(
    pessoa: Pessoa, anuncios: Iterable[Anuncio], ja_enviados: set[Chave]
) -> list[Anuncio]:
    vistos = set(ja_enviados)
    novos = []
    for anuncio in anuncios:
        if anuncio.chave not in vistos and aceita(pessoa.filtro, anuncio):
            vistos.add(anuncio.chave)
            novos.append(anuncio)
    return novos


def hash_filtros(filtro: Filtro) -> str:
    canonico = json.dumps(
        {
            "bairros": sorted(filtro.bairros),
            "aluguel_max_centavos": filtro.aluguel_max_centavos,
            "quartos_min": filtro.quartos_min,
            "tipos": sorted(t.value for t in filtro.tipos),
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonico.encode()).hexdigest()
