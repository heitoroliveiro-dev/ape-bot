"""Coleta no QuintoAndar por páginas públicas de busca (research R1–R5)."""

import asyncio
import json
import logging
import random
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

import httpx
from bs4 import BeautifulSoup

from apebot.fontes.resultado import ResultadoFonte, status_rodada
from apebot.modelos import Anuncio, Pessoa, Tipo, slug

log = logging.getLogger(__name__)

FONTE = "quintoandar"
BASE = "https://www.quintoandar.com.br"
CIDADE = "belo-horizonte-mg-brasil"
USER_AGENT = "ape-bot/0.1 (uso pessoal; baixo volume)"
TIMEOUT_SEGUNDOS = 20
INTERVALO_SEGUNDOS = (2.0, 5.0)
BACKOFF_SEGUNDOS = (5, 15, 45)
STATUS_REPETIR = {429, 500, 502, 503, 504}


class ErroDeAcesso(Exception):
    """Resposta HTTP que não é 200 depois das tentativas."""


class FormatoInvalido(Exception):
    """A página não tem o JSON esperado: o portal mudou de formato."""


class PaginaIncompleta(Exception):
    """A página veio sem a lista de imóveis carregada, mas o portal diz que há imóveis.

    Visto em 28/10/2026 (5 de 63 páginas; as mesmas URLs vieram completas minutos depois):
    é falha passageira de acesso, não mudança de formato.
    """


@dataclass
class ResultadoParse:
    anuncios: list[Anuncio]
    descartados: Counter[str] = field(default_factory=Counter)


@dataclass
class ResultadoPagina:
    bairro_slug: str
    tipo: Tipo
    anuncios: list[Anuncio] = field(default_factory=list)
    descartados: Counter[str] = field(default_factory=Counter)
    erro: str | None = None
    erro_de_formato: bool = False


def url_listagem(bairro_slug: str, tipo: Tipo) -> str:
    return f"{BASE}/alugar/imovel/{bairro_slug}-{CIDADE}/{tipo.slug_url}"


def combinacoes(pessoas: Iterable[Pessoa]) -> list[tuple[str, Tipo]]:
    pares = {(b, t) for p in pessoas for b in p.filtro.bairros for t in p.filtro.tipos}
    return sorted(pares, key=lambda par: (par[0], par[1].value))


def bairro_confere(bairro_json: str, bairro_slug: str) -> bool:
    do_anuncio = slug(bairro_json)
    return do_anuncio == bairro_slug or bairro_slug.startswith(do_anuncio + "-")


def extrair(html: str, bairro_slug: str) -> ResultadoParse:
    script = BeautifulSoup(html, "html.parser").find("script", id="__NEXT_DATA__")
    if script is None or not script.string:
        raise FormatoInvalido("script __NEXT_DATA__ ausente")
    try:
        estado = json.loads(script.string)["props"]["pageProps"]["initialState"]
        casas = estado["houses"]
        visiveis = estado["search"]["visibleHouses"]
        paginas = visiveis["pages"]
    except (json.JSONDecodeError, KeyError, TypeError) as erro:
        raise FormatoInvalido(f"JSON sem o caminho esperado: {erro!r}") from erro
    if not isinstance(paginas, dict) or "0" not in paginas:
        if visiveis.get("total") == 0:
            return ResultadoParse(anuncios=[])  # busca sem nenhum imóvel
        raise PaginaIncompleta(
            f"lista não carregada (total={visiveis.get('total')!r},"
            f" searched={visiveis.get('searched')!r}, error={visiveis.get('error')!r},"
            f" loading={visiveis.get('loading')!r})"
        )
    ids = paginas["0"]

    resultado = ResultadoParse(anuncios=[])
    for id_externo in ids:
        casa = casas.get(str(id_externo))
        anuncio = _anuncio(casa) if isinstance(casa, dict) else None
        if anuncio is None:
            resultado.descartados["incompleto"] += 1
        elif not bairro_confere(anuncio.bairro, bairro_slug):
            resultado.descartados["fora_do_bairro"] += 1
        else:
            resultado.anuncios.append(_com_bairro_slug(anuncio, bairro_slug))
    return resultado


def _anuncio(casa: dict) -> Anuncio | None:
    tipo = Tipo.de_json(str(casa.get("type")))
    aluguel = casa.get("rentPrice")
    quartos = casa.get("bedrooms")
    bairro = casa.get("neighbourhood")
    id_externo = casa.get("id")
    if tipo is None or not isinstance(aluguel, int) or not isinstance(quartos, int):
        return None
    if not bairro or not id_externo:
        return None
    area = casa.get("area")
    total = casa.get("totalCost")
    return Anuncio(
        fonte=FONTE,
        id_externo=str(id_externo),
        tipo=tipo,
        bairro=str(bairro),
        bairro_slug=slug(str(bairro)),
        quartos=quartos,
        area_m2=area if isinstance(area, int) and area > 0 else None,
        aluguel_centavos=aluguel * 100,
        total_centavos=total * 100 if isinstance(total, int) and total > 0 else None,
        url=f"{BASE}/imovel/{id_externo}",
    )


def _com_bairro_slug(anuncio: Anuncio, bairro_slug: str) -> Anuncio:
    return replace(anuncio, bairro_slug=bairro_slug)


async def coletar(pessoas: list[Pessoa], simular_falha: bool = False) -> ResultadoFonte:
    """Todas as páginas (bairro, tipo) das pessoas, consolidadas como uma fonte."""
    paginas = await buscar_paginas(combinacoes(pessoas), simular_falha)
    erros = [p.erro for p in paginas if p.erro]
    resultado = ResultadoFonte(
        fonte=FONTE,
        anuncios=[a for p in paginas for a in p.anuncios],
        consultas=len(paginas),
        consultas_erro=len(erros),
        erro=erros[-1] if erros else None,
        erro_de_formato=any(p.erro_de_formato for p in paginas),
    )
    for pagina in paginas:
        resultado.descartados.update(pagina.descartados)
    resultado.status = status_rodada(
        len(paginas) - len(erros), len(erros), resultado.erro_de_formato
    )
    return resultado


async def buscar_paginas(
    pares: list[tuple[str, Tipo]], simular_falha: bool = False
) -> list[ResultadoPagina]:
    """Busca cada par (bairro, tipo) em sequência, com intervalo; nunca lança."""
    resultados = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
        timeout=TIMEOUT_SEGUNDOS,
    ) as cliente:
        for indice, (bairro_slug, tipo) in enumerate(pares):
            if indice:
                await asyncio.sleep(random.uniform(*INTERVALO_SEGUNDOS))
            resultados.append(await _buscar_pagina(cliente, bairro_slug, tipo, simular_falha))
    return resultados


async def _buscar_pagina(
    cliente: httpx.AsyncClient, bairro_slug: str, tipo: Tipo, simular_falha: bool
) -> ResultadoPagina:
    pagina = ResultadoPagina(bairro_slug=bairro_slug, tipo=tipo)
    url = url_listagem(bairro_slug, tipo)
    if simular_falha:
        pagina.erro = "falha simulada"
        return pagina
    try:
        html = await _get_com_backoff(cliente, url)
        try:
            parse = extrair(html, bairro_slug)
        except PaginaIncompleta as erro:  # passageira: uma nova tentativa, com o intervalo normal
            log.info("pagina_incompleta url=%s %s; tentando de novo", url, erro)
            await asyncio.sleep(random.uniform(*INTERVALO_SEGUNDOS))
            parse = extrair(await _get_com_backoff(cliente, url), bairro_slug)
        pagina.anuncios, pagina.descartados = parse.anuncios, parse.descartados
    except PaginaIncompleta as erro:
        pagina.erro = f"acesso: {erro}"
    except FormatoInvalido as erro:
        pagina.erro, pagina.erro_de_formato = f"formato: {erro}", True
    except (httpx.HTTPError, ErroDeAcesso) as erro:
        pagina.erro = f"acesso: {erro}"
    if pagina.erro:
        log.warning("pagina_com_erro url=%s erro=%s", url, pagina.erro)
    else:
        log.info(
            "pagina_ok url=%s anuncios=%d descartados=%s",
            url,
            len(pagina.anuncios),
            dict(pagina.descartados),
        )
    return pagina


async def _get_com_backoff(cliente: httpx.AsyncClient, url: str) -> str:
    for tentativa, espera in enumerate((*BACKOFF_SEGUNDOS, None)):
        resposta = await cliente.get(url)
        if resposta.status_code == 200:
            return resposta.text
        if resposta.status_code not in STATUS_REPETIR or espera is None:
            raise ErroDeAcesso(f"HTTP {resposta.status_code}")
        retry_after = resposta.headers.get("Retry-After", "")
        espera_real = int(retry_after) if retry_after.isdigit() else espera
        log.info(
            "backoff url=%s status=%d tentativa=%d espera=%ds",
            url,
            resposta.status_code,
            tentativa + 1,
            espera_real,
        )
        await asyncio.sleep(espera_real)
    raise ErroDeAcesso("tentativas esgotadas")
