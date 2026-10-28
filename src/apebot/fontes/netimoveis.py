"""Coleta no Netimóveis pelas buscas públicas por bairro e tipo (research R1–R8 da 005).

Só a 1ª página de cada busca (o robots.txt bloqueia `pag=`, preço e ordenação na URL); os dados vêm
dos blocos JSON-LD da página. Sonda de acesso: `python -m apebot.fontes.netimoveis [bairro] [tipo]`.
"""

import asyncio
import json
import logging
import random
import re
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from apebot.fontes.resultado import ResultadoFonte, bairro_do_catalogo, status_rodada
from apebot.modelos import Anuncio, Pessoa, Tipo, slug

log = logging.getLogger(__name__)

FONTE = "netimoveis"
BASE = "https://www.netimoveis.com"
CIDADE = "minas-gerais/belo-horizonte"
USER_AGENT = "ape-bot/0.1 (uso pessoal; baixo volume)"
TIMEOUT_SEGUNDOS = 20
INTERVALO_SEGUNDOS = (2.0, 5.0)
BACKOFF_SEGUNDOS = (5, 15, 45)
STATUS_REPETIR = {429, 500, 502, 503, 504}
DESAFIO = re.compile(r"just a moment|attention required|cf-chl", re.IGNORECASE)
URL_IMOVEL = re.compile(
    r"/imovel/locacao-(?P<tipo>.+?)-minas-gerais-belo-horizonte-(?P<bairro>.+)/(?P<id>\d+)$"
)


class ErroDeAcesso(Exception):
    """Resposta que não é a página da busca: HTTP de erro ou desafio antirrobô."""


class FormatoInvalido(Exception):
    """A página não tem o JSON-LD esperado: o portal mudou de formato."""


@dataclass
class ResultadoBusca:
    total: int = 0
    lidos: int = 0
    anuncios: list[Anuncio] = field(default_factory=list)
    descartados: Counter[str] = field(default_factory=Counter)


@dataclass
class Busca:
    bairro_slug: str
    tipo: Tipo
    resultado: ResultadoBusca = field(default_factory=ResultadoBusca)
    status_http: int | None = None
    erro: str | None = None
    erro_de_formato: bool = False


def url_busca(bairro_slug: str, tipo: Tipo, quartos: int) -> str:
    url = f"{BASE}/locacao/{CIDADE}/bairros/{bairro_slug}/{tipo.slug_netimoveis}"
    return f"{url}?quartos={quartos}" if quartos > 0 else url


def combinacoes(pessoas: Iterable[Pessoa]) -> list[tuple[str, Tipo]]:
    pares = {(b, t) for p in pessoas for b in p.filtro.bairros for t in p.filtro.tipos}
    return sorted(pares, key=lambda par: (par[0], par[1].value))


def quartos_minimo(pessoas: Iterable[Pessoa]) -> int:
    return min((p.filtro.quartos_min for p in pessoas), default=0)


def extrair(html: str, catalogo: frozenset[str]) -> ResultadoBusca:
    blocos = _jsonld(html)
    if not blocos:
        raise FormatoInvalido("página sem JSON-LD")
    lista = next((b for b in blocos if b.get("@type") == "ItemList"), None)
    if lista is None:
        return ResultadoBusca()  # busca sem nenhum imóvel: a página vem sem ItemList
    itens = lista.get("itemListElement")
    total = lista.get("numberOfItems")
    if not isinstance(itens, list) or not isinstance(total, int):
        raise FormatoInvalido("ItemList sem itemListElement ou numberOfItems")

    resultado = ResultadoBusca(total=total, lidos=len(itens))
    for elemento in itens:
        item = elemento.get("item") if isinstance(elemento, dict) else None
        motivo, anuncio = (
            _anuncio(item, catalogo) if isinstance(item, dict) else ("incompleto", None)
        )
        if anuncio is None:
            resultado.descartados[motivo] += 1
        else:
            resultado.anuncios.append(anuncio)
    return resultado


def _jsonld(html: str) -> list[dict]:
    blocos = []
    for script in BeautifulSoup(html, "html.parser").find_all("script", type="application/ld+json"):
        try:
            dados = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        blocos.extend(
            d for d in (dados if isinstance(dados, list) else [dados]) if isinstance(d, dict)
        )
    return blocos


def _anuncio(item: dict, catalogo: frozenset[str]) -> tuple[str, Anuncio | None]:
    url = str(item.get("url") or "").split("?", 1)[0]
    partes = URL_IMOVEL.search(url)
    if partes is None:
        return "fora_da_cidade", None
    tipo = Tipo.de_netimoveis(partes["tipo"])
    if tipo is None:
        return "tipo_nao_aceito", None
    bairro_slug = bairro_do_catalogo(slug(partes["bairro"]), catalogo)
    if bairro_slug is None:
        return "bairro_desconhecido", None
    oferta = item.get("offers") if isinstance(item.get("offers"), dict) else {}
    imovel = oferta.get("itemOffered") if isinstance(oferta.get("itemOffered"), dict) else {}
    aluguel = _inteiro(oferta.get("price"))
    quartos = imovel.get("numberOfBedrooms")
    if not aluguel or not isinstance(quartos, int) or quartos < 0:
        return "incompleto", None
    area = _inteiro((imovel.get("floorSize") or {}).get("value"))
    condominio = _condominio(imovel.get("additionalProperty"))
    return "", Anuncio(
        fonte=FONTE,
        id_externo=partes["id"],
        tipo=tipo,
        bairro=partes["bairro"],
        bairro_slug=bairro_slug,
        quartos=quartos,
        area_m2=area or None,
        aluguel_centavos=aluguel * 100,
        total_centavos=(aluguel + condominio) * 100 if condominio else None,
        url=f"{BASE}{url[url.index('/imovel/') :]}",
    )


def _inteiro(valor: object) -> int | None:
    """Inteiro positivo em reais (o JSON-LD traz int ou float); senão None."""
    if isinstance(valor, bool) or not isinstance(valor, int | float) or valor <= 0:
        return None
    return int(valor)


def _condominio(propriedades: object) -> int | None:
    for propriedade in propriedades if isinstance(propriedades, list) else [propriedades]:
        if isinstance(propriedade, dict) and propriedade.get("name") == "Condominium Fee":
            return _inteiro(propriedade.get("value"))
    return None


async def coletar(
    pessoas: list[Pessoa],
    catalogo: frozenset[str],
    simular_falha: bool = False,
    transporte: httpx.AsyncBaseTransport | None = None,
) -> ResultadoFonte:
    """Todas as buscas (bairro, tipo) das pessoas, consolidadas como uma fonte."""
    quartos = quartos_minimo(pessoas)
    buscas = []
    async with _cliente(transporte) as cliente:
        for indice, (bairro_slug, tipo) in enumerate(combinacoes(pessoas)):
            if indice:
                await asyncio.sleep(random.uniform(*INTERVALO_SEGUNDOS))
            busca = Busca(bairro_slug, tipo)
            if simular_falha:
                busca.erro = "acesso: falha simulada"
            else:
                await _buscar(cliente, busca, quartos, catalogo)
            buscas.append(busca)

    erros = [b.erro for b in buscas if b.erro]
    resultado = ResultadoFonte(
        fonte=FONTE,
        anuncios=[a for b in buscas for a in b.resultado.anuncios],
        consultas=len(buscas),
        consultas_erro=len(erros),
        erro=erros[-1] if erros else None,
        erro_de_formato=any(b.erro_de_formato for b in buscas),
    )
    for busca in buscas:
        resultado.descartados.update(busca.resultado.descartados)
    resultado.status = status_rodada(
        len(buscas) - len(erros), len(erros), resultado.erro_de_formato
    )
    if buscas and all(b.status_http == 404 for b in buscas):  # research R4: URL do portal mudou?
        resultado.status, resultado.erro = "falha", "acesso: todas as buscas responderam 404"
    return resultado


def _cliente(transporte: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
        timeout=TIMEOUT_SEGUNDOS,
        transport=transporte,
    )


async def _buscar(
    cliente: httpx.AsyncClient, busca: Busca, quartos: int, catalogo: frozenset[str]
) -> None:
    url = url_busca(busca.bairro_slug, busca.tipo, quartos)
    try:
        busca.status_http, html = await _get_com_backoff(cliente, url)
        if busca.status_http == 404:
            log.info("busca_inexistente url=%s", url)
            return
        busca.resultado = extrair(html, catalogo)
    except FormatoInvalido as erro:
        busca.erro, busca.erro_de_formato = f"formato: {erro}", True
    except (httpx.HTTPError, ErroDeAcesso) as erro:
        busca.erro = f"acesso: {erro}"
    if busca.erro:
        log.warning("pagina_com_erro url=%s erro=%s", url, busca.erro)
        return
    resultado = busca.resultado
    log.info(
        "pagina_ok url=%s anuncios=%d descartados=%s",
        url,
        len(resultado.anuncios),
        dict(resultado.descartados),
    )
    if resultado.total > resultado.lidos:
        log.info(
            "netimoveis_corte bairro=%s tipo=%s total=%d lidos=%d",
            busca.bairro_slug,
            busca.tipo.slug_netimoveis,
            resultado.total,
            resultado.lidos,
        )


async def _get_com_backoff(cliente: httpx.AsyncClient, url: str) -> tuple[int, str]:
    for tentativa, espera in enumerate((*BACKOFF_SEGUNDOS, None)):
        resposta = await cliente.get(url)
        if resposta.status_code in (200, 404):
            if DESAFIO.search(resposta.text[:5000]):
                raise ErroDeAcesso(f"desafio antirrobô (HTTP {resposta.status_code})")
            return resposta.status_code, resposta.text
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


async def _sondar(bairro_slug: str, tipo: Tipo) -> int:
    """Uma busca, sem banco, Redis nem Telegram: valida o acesso a partir do IP onde roda."""
    from apebot.config import bairros_validos

    busca = Busca(bairro_slug, tipo)
    async with _cliente(None) as cliente:
        await _buscar(cliente, busca, 0, bairros_validos())
    if busca.erro:
        print(f"erro={busca.erro}", flush=True)
        return 1
    r = busca.resultado
    print(
        f"status={busca.status_http} total={r.total} lidos={r.lidos} "
        f"anuncios={len(r.anuncios)} descartados={dict(r.descartados)}",
        flush=True,
    )
    return 0


def _tipo_da_sonda(texto: str) -> Tipo:
    return next(t for t in Tipo if texto in (t.value, t.slug_netimoveis))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    argumentos = sys.argv[1:]
    bairro = argumentos[0] if argumentos else "centro"
    tipo = _tipo_da_sonda(argumentos[1]) if len(argumentos) > 1 else Tipo.APARTAMENTO
    sys.exit(asyncio.run(_sondar(bairro, tipo)))
