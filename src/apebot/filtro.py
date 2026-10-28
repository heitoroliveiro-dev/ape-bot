from collections.abc import Iterable

from apebot.modelos import Anuncio, Filtro, Pessoa, Tipo

Chave = tuple[str, str]

# Regras do cadastro pelo Telegram (spec 003, FR-020 e FR-022)
VALOR_MIN_CENTAVOS = 30_000
VALOR_MAX_CENTAVOS = 5_000_000
QUARTOS_OPCOES = (0, 1, 2, 3, 4)
PERCENTUAL_ACHADO = 70  # lembrete de achado (spec 004)


def aceita(filtro: Filtro, anuncio: Anuncio) -> bool:
    return (
        anuncio.bairro_slug in filtro.bairros
        and anuncio.tipo in filtro.tipos
        and anuncio.quartos >= filtro.quartos_min
        and anuncio.aluguel_centavos <= filtro.aluguel_max_centavos
    )


def limite_achado(filtro: Filtro) -> int:
    """Até quanto um imóvel é "achado": 70% do máximo, arredondado para baixo em centavos."""
    return filtro.aluguel_max_centavos * PERCENTUAL_ACHADO // 100


def e_achado(filtro: Filtro, anuncio: Anuncio) -> bool:
    return aceita(filtro, anuncio) and anuncio.aluguel_centavos <= limite_achado(filtro)


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


def filtros_somados(pessoas: Iterable[Pessoa]) -> Filtro | None:
    """Um filtro que aceita tudo o que alguma pessoa aceitaria (consulta única às fontes pagas)."""
    filtros = [p.filtro for p in pessoas]
    if not filtros:
        return None
    return Filtro(
        bairros=frozenset().union(*(f.bairros for f in filtros)),
        aluguel_max_centavos=max(f.aluguel_max_centavos for f in filtros),
        quartos_min=min(f.quartos_min for f in filtros),
        tipos=frozenset().union(*(f.tipos for f in filtros)),
    )


def filtro_para_json(filtro: Filtro) -> dict:
    """Formato de pessoa.filtros no MySQL (data-model.md da 003)."""
    return {
        "bairros": sorted(filtro.bairros),
        "aluguel_max_centavos": filtro.aluguel_max_centavos,
        "quartos_min": filtro.quartos_min,
        "tipos": sorted(t.value for t in filtro.tipos),
    }


def filtro_de_json(dados: object, catalogo: frozenset[str]) -> Filtro | None:
    """Filtro salvo → Filtro; None se estiver fora das regras do cadastro."""
    if not isinstance(dados, dict):
        return None
    bairros, tipos = dados.get("bairros"), dados.get("tipos")
    valor, quartos = dados.get("aluguel_max_centavos"), dados.get("quartos_min")
    if not isinstance(bairros, list) or not bairros or not set(bairros) <= catalogo:
        return None
    if not isinstance(tipos, list) or not tipos:
        return None
    try:
        tipos_validos = frozenset(Tipo(t) for t in tipos)
    except ValueError:
        return None
    if type(quartos) is not int or quartos not in QUARTOS_OPCOES:
        return None
    if type(valor) is not int or not VALOR_MIN_CENTAVOS <= valor <= VALOR_MAX_CENTAVOS:
        return None
    return Filtro(
        bairros=frozenset(bairros),
        aluguel_max_centavos=valor,
        quartos_min=quartos,
        tipos=tipos_validos,
    )
