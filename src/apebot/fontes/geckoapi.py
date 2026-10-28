"""GeckoAPI: cliente, leitura da resposta e coleta (constituição 2.2.0, exceção do princípio III).

A resposta guardada sai sem os dados de anunciante; o corpo bruto só serve ao parse da rodada.
Contrato em specs/002-geckoapi-zap-olx-telegram/contracts/geckoapi.md.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from apebot.fontes.resultado import ResultadoFonte
from apebot.mensagens import aviso_sem_credito

log = logging.getLogger(__name__)

BASE = "https://api.geckoapi.com.br"
TIMEOUT_EXTRACAO_SEGUNDOS = 90  # no Playground a extração levou de 10 a 20 s
TIMEOUT_CONTA_SEGUNDOS = 10

# Chaves com dados de anunciante (nome, telefone, e-mail) em qualquer nível da resposta.
CHAVES_DE_ANUNCIANTE = frozenset(
    {
        "advertiser",
        "seller",
        "sellerName",
        "sellerId",
        "phone",
        "phones",
        "phoneNumbers",
        "whatsAppNumber",
        "email",
        "contact",
        "contacts",
        "account",
    }
)


class RespostaInvalida(Exception):
    """O JSON não tem o formato de resposta da GeckoAPI."""


@dataclass(frozen=True)
class RespostaGecko:
    fonte: str
    request_id: str
    url: str
    extraida_em: datetime
    total_resultados: int | None
    itens: int
    corpo: dict[str, Any]


def sem_anunciante(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {
            chave: sem_anunciante(item)
            for chave, item in valor.items()
            if chave not in CHAVES_DE_ANUNCIANTE
        }
    if isinstance(valor, list):
        return [sem_anunciante(item) for item in valor]
    return valor


def ler_resposta(texto: str) -> RespostaGecko:
    try:
        corpo = json.loads(texto)
        dados = corpo["data"]
        request_id = str(corpo["requestId"])
        fonte = str(dados["source"])
        url = str(dados["url"])
        itens = dados["items"]
        extraida_em = datetime.fromisoformat(dados["extractedAt"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as erro:
        raise RespostaInvalida(f"formato inesperado: {erro!r}") from erro
    if not isinstance(itens, list):
        raise RespostaInvalida("data.items não é lista")

    total = dados.get("totalResults")
    return RespostaGecko(
        fonte=fonte,
        request_id=request_id,
        url=url,
        extraida_em=extraida_em.astimezone(UTC).replace(tzinfo=None, microsecond=0),
        total_resultados=total if isinstance(total, int) else None,
        itens=len(itens),
        corpo=sem_anunciante(corpo),
    )


class ErroGecko(Exception):
    """Falha numa chamada à GeckoAPI; `formato` indica resposta fora do contrato."""

    def __init__(self, mensagem: str, formato: bool = False) -> None:
        super().__init__(mensagem)
        self.formato = formato


class SemCredito(ErroGecko):
    """402: a conta ficou sem créditos. Depois do primeiro, nenhuma chamada sai."""

    def __init__(self, primeira_vez: bool) -> None:
        super().__init__("sem crédito na GeckoAPI")
        self.primeira_vez = primeira_vez


class ClienteGecko:
    def __init__(self, chave: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._chave = chave
        self._transport = transport
        self.sem_credito = False

    def _http(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=BASE,
            headers={"Authorization": f"Bearer {self._chave}"},
            timeout=timeout,
            transport=self._transport,
        )

    async def extrair(self, payload: dict[str, Any]) -> tuple[RespostaGecko, dict[str, Any]]:
        """POST /v1/extract. Uma nova tentativa só em 5xx (a GeckoAPI estorna o crédito)."""
        if self.sem_credito:
            raise SemCredito(primeira_vez=False)
        async with self._http(TIMEOUT_EXTRACAO_SEGUNDOS) as http:
            for tentativa in (1, 2):
                try:
                    resposta = await http.post("/v1/extract", json=payload)
                except httpx.TimeoutException as erro:  # pode ter cobrado: não repete
                    raise ErroGecko("tempo esgotado") from erro
                except httpx.HTTPError as erro:
                    raise ErroGecko(f"acesso: {type(erro).__name__}") from erro
                if resposta.status_code < 500 or tentativa == 2:
                    break
                log.info("gecko_5xx status=%d tentativa=%d", resposta.status_code, tentativa)
        if resposta.status_code == 402:
            self.sem_credito = True
            raise SemCredito(primeira_vez=True)
        if resposta.status_code != 200:
            raise ErroGecko(f"HTTP {resposta.status_code}")
        try:
            bruto = resposta.json()
        except ValueError as erro:
            raise ErroGecko("formato: JSON inválido", formato=True) from erro
        if not isinstance(bruto, dict) or bruto.get("notFound") or bruto.get("data") is None:
            raise ErroGecko("sem resultados (notFound)", formato=True)
        try:
            return ler_resposta(resposta.text), bruto
        except RespostaInvalida as erro:
            raise ErroGecko(f"formato: {erro}", formato=True) from erro

    async def creditos(self) -> dict[str, Any]:
        """GET /v1/me/credits: currentCredits e creditsConsumed (fora do /v1/extract)."""
        async with self._http(TIMEOUT_CONTA_SEGUNDOS) as http:
            try:
                resposta = await http.get("/v1/me/credits")
            except httpx.HTTPError as erro:
                raise ErroGecko(f"acesso: {type(erro).__name__}") from erro
        if resposta.status_code != 200:
            raise ErroGecko(f"HTTP {resposta.status_code}")
        return resposta.json()


async def saldo(gecko: "ClienteGecko | None") -> dict[str, Any] | str | None:
    """Créditos para o /status e o resumo: dict, "indisponível" em erro, None sem GeckoAPI."""
    if gecko is None:
        return None
    try:
        return await gecko.creditos()
    except (ErroGecko, ValueError) as erro:
        log.warning("creditos_indisponiveis erro=%s", erro)
        return "indisponível"


class _SalvaResposta(Protocol):
    def salvar_resposta(self, resposta: RespostaGecko) -> bool: ...


async def coletar_listagem(
    fonte: str,
    cliente: ClienteGecko,
    payload: dict[str, Any],
    extrair: Callable[[dict[str, Any]], ResultadoFonte],
    banco: _SalvaResposta,
) -> ResultadoFonte:
    """Uma chamada de listagem: guarda a resposta (sem anunciante) e faz o parse do bruto."""
    try:
        resposta, bruto = await cliente.extrair(payload)
    except SemCredito as erro:
        return ResultadoFonte(
            fonte=fonte,
            status="sem_credito",
            consultas=int(erro.primeira_vez),
            erro=str(erro),
            aviso_operador=aviso_sem_credito() if erro.primeira_vez else None,
        )
    except ErroGecko as erro:
        return ResultadoFonte(
            fonte=fonte,
            status="falha",
            consultas=1,
            consultas_erro=1,
            erro=str(erro),
            erro_de_formato=erro.formato,
        )
    try:
        await asyncio.to_thread(banco.salvar_resposta, resposta)
    except Exception:  # guardar para conferência não pode custar os anúncios da rodada
        log.exception("resposta_nao_guardada fonte=%s request_id=%s", fonte, resposta.request_id)
    resultado = extrair(bruto)
    resultado.consultas = 1
    if resultado.status == "falha":
        resultado.consultas_erro = 1
    return resultado
