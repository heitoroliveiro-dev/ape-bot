"""Uma rodada: coleta por fonte → banco → filtro → fila de cada pessoa → registro e alerta.

Research R9/R10 da 001, R7/R8 da 002 e R4 da 003: cada fonte é coletada isoladamente e registrada
em rodada_fonte; o alerta é por fonte; a rodada não manda imóvel, só põe na fila da pessoa (o
despachante entrega um por vez); o contato do anunciante só vive em memória e nas filas Redis.
"""

import asyncio
import logging
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from apebot.banco import Banco, agora
from apebot.config import Configuracao
from apebot.fila import Fila, FilaPessoa, Mensagem
from apebot.filtro import novos_para
from apebot.fontes.geckoapi import ClienteGecko, saldo
from apebot.fontes.resultado import ResultadoFonte, status_rodada
from apebot.mensagens import aviso_falha, aviso_recuperacao, proxima_rodada, texto_resumo
from apebot.modelos import FUSO, Anuncio, Contato, Pessoa

__all__ = ["Coletor", "Rodada", "decidir_alerta", "enviar_resumos", "status_rodada"]

log = logging.getLogger(__name__)

FALHAS_PARA_ALERTA = 3
REAVISO = timedelta(hours=24)

Chave = tuple[str, str]


@dataclass(frozen=True)
class Coletor:
    fonte: str
    coletar: Callable[[list[Pessoa]], Awaitable[ResultadoFonte]]


def decidir_alerta(
    status: str, seguidas: int, ultimo_aviso: datetime | None, momento: datetime
) -> str:
    """abrir | reavisar | recuperar | nada. `ultimo_aviso` é None quando não há alerta aberto."""
    if status == "ok":
        return "recuperar" if ultimo_aviso is not None else "nada"
    if status != "falha":  # desligada ou sem_credito (este avisa na hora)
        return "nada"
    if ultimo_aviso is not None:
        return "reavisar" if momento - ultimo_aviso >= REAVISO else "nada"
    return "abrir" if seguidas >= FALHAS_PARA_ALERTA else "nada"


class Rodada:
    def __init__(
        self,
        banco: Banco,
        fila: Fila,
        fila_pessoa: FilaPessoa,
        config: Configuracao,
        coletores: list[Coletor],
    ) -> None:
        self._banco = banco
        self._fila = fila
        self._fila_pessoa = fila_pessoa
        self._config = config
        self._coletores = coletores
        self._contatos: dict[Chave, Contato] = {}

    async def executar(self) -> str:
        rodada_id = await asyncio.to_thread(self._banco.iniciar_rodada)
        contagens: Counter[str] = Counter()
        resultados: list[ResultadoFonte] = []
        status, erro_resumo = "falha", None
        try:
            status, erro_resumo = await self._coletar_e_enfileirar(rodada_id, contagens, resultados)
        except Exception as erro:  # a rodada nunca derruba o robô (FR-017)
            log.exception("rodada_erro_inesperado rodada=%d", rodada_id)
            status, erro_resumo = "falha", f"inesperado: {erro!r}"
        finally:
            self._contatos = {}  # contato do anunciante não sobrevive à rodada
        await asyncio.to_thread(
            self._banco.finalizar_rodada, rodada_id, status, dict(contagens), erro_resumo
        )
        log.info(
            "rodada_fim rodada=%d status=%s %s erro=%s",
            rodada_id,
            status,
            " ".join(f"{k}={v}" for k, v in contagens.items()),
            erro_resumo,
        )
        for resultado in resultados:
            try:
                await self._avaliar_alerta(resultado)
            except Exception:
                log.exception("alerta_erro rodada=%d fonte=%s", rodada_id, resultado.fonte)
        return status

    async def _coletar(self, coletor: Coletor, pessoas: list[Pessoa]) -> ResultadoFonte:
        try:
            return await coletor.coletar(pessoas)
        except Exception as erro:  # falha de uma fonte não impede as outras (FR-010)
            log.exception("fonte_erro_inesperado fonte=%s", coletor.fonte)
            return ResultadoFonte(
                fonte=coletor.fonte, status="falha", consultas_erro=1, erro=f"inesperado: {erro!r}"
            )

    async def _coletar_e_enfileirar(
        self, rodada_id: int, contagens: Counter[str], resultados: list[ResultadoFonte]
    ) -> tuple[str, str | None]:
        # filtros lidos do MySQL no início da rodada: o que for salvo depois vale na próxima
        pessoas = await asyncio.to_thread(self._banco.pessoas_ativas, self._config.autorizados)
        if not pessoas:
            log.warning("rodada_sem_pessoas_ativas: peça /start ao bot")

        for coletor in self._coletores:
            resultado = await self._coletar(coletor, pessoas)
            resultados.append(resultado)
            await asyncio.to_thread(self._banco.registrar_fonte, rodada_id, resultado)
            log.info(
                "fonte_fim fonte=%s status=%s consultas=%d anuncios=%d descartados=%s erro=%s",
                resultado.fonte,
                resultado.status,
                resultado.consultas,
                len(resultado.anuncios),
                dict(resultado.descartados),
                resultado.erro,
            )
            if resultado.aviso_operador:
                await self._avisar_operador(resultado.aviso_operador)

        anuncios = [a for r in resultados for a in r.anuncios]
        for r in resultados:
            self._contatos.update(r.contatos)
        consultas = sum(r.consultas for r in resultados)
        consultas_erro = sum(r.consultas_erro for r in resultados)
        contagens["paginas_ok"] = consultas - consultas_erro
        contagens["paginas_erro"] = consultas_erro
        contagens["anuncios_vistos"] = len(anuncios)
        contagens["descartados"] = sum(sum(r.descartados.values()) for r in resultados)
        # o status da rodada (e a decisão de mandar resumo) continua vindo do QuintoAndar
        principal = next((r for r in resultados if r.fonte == "quintoandar"), None)
        status = "falha" if principal and principal.status == "falha" else "ok"
        contagens["anuncios_novos"] = await asyncio.to_thread(self._banco.salvar_anuncios, anuncios)

        for pessoa in pessoas:
            contagens["enfileirados"] += await self._enfileirar_para(pessoa, anuncios)
        erros = [f"{r.fonte}: {r.erro}" for r in resultados if r.erro]
        return status, (erros[-1] if erros else None)

    async def _enfileirar_para(self, pessoa: Pessoa, anuncios: list[Anuncio]) -> int:
        """Põe na fila da pessoa os imóveis novos para ela; tudo vai um a um (FR-007 da 003)."""
        ja_enviados = await asyncio.to_thread(self._banco.ja_enviados, pessoa.chat_id)
        candidatos = novos_para(pessoa, anuncios, ja_enviados)
        inseridos = set(
            await asyncio.to_thread(
                self._banco.criar_envios_pendentes, pessoa.chat_id, [a.chave for a in candidatos]
            )
        )
        novos = [a for a in candidatos if a.chave in inseridos]
        for anuncio in novos:
            await self._fila_pessoa.adicionar(
                pessoa.chat_id, anuncio, self._contatos.get(anuncio.chave)
            )
        if novos:
            log.info("imovel_enfileirado chat_id=%s quantidade=%d", pessoa.chat_id, len(novos))
        return len(novos)

    async def _avaliar_alerta(self, resultado: ResultadoFonte) -> None:
        fonte = resultado.fonte
        aberto = await asyncio.to_thread(self._banco.alerta_aberto, fonte)
        seguidas = await asyncio.to_thread(self._banco.seguidas_com_falha, fonte)
        decisao = decidir_alerta(resultado.status, seguidas, aberto[1] if aberto else None, agora())
        if decisao == "abrir":
            await asyncio.to_thread(self._banco.abrir_alerta, fonte)
        elif decisao == "reavisar":
            await asyncio.to_thread(self._banco.registrar_aviso, aberto[0])
        elif decisao == "recuperar":
            await asyncio.to_thread(self._banco.fechar_alerta, aberto[0])
            await self._avisar_operador(aviso_recuperacao(fonte, datetime.now(FUSO)))
            return
        else:
            return
        await self._avisar_operador(aviso_falha(fonte, seguidas, resultado.erro))

    async def _avisar_operador(self, texto: str) -> None:
        await self._fila.enfileirar(
            Mensagem(chat_id=self._config.operador_chat_id, tipo="operador", texto=texto)
        )


async def enviar_resumos(
    banco: Banco,
    fila: Fila,
    gecko: ClienteGecko | None,
    autorizados: Iterable[int],
    momento: datetime,
) -> int:
    """Resumo do dia para cada pessoa ativa, uma vez por dia (research R12 da 003)."""
    pessoas = await asyncio.to_thread(banco.pessoas_ativas, autorizados)
    if not pessoas:
        return 0
    creditos = await saldo(gecko)  # uma consulta para todos; não gasta crédito
    ultima = await asyncio.to_thread(banco.ultima_rodada)
    proxima = proxima_rodada(momento)
    dia = momento.astimezone(FUSO).date()
    enviados = 0
    for pessoa in pessoas:
        if not await asyncio.to_thread(banco.registrar_resumo, pessoa.chat_id, dia):
            continue
        por_fonte = await asyncio.to_thread(banco.recebidos_por_fonte_24h, pessoa.chat_id)
        # fora da janela de imóveis: vai direto para a entrega (FR-010)
        await fila.enfileirar(
            Mensagem(
                chat_id=pessoa.chat_id,
                tipo="resumo",
                texto=texto_resumo(ultima, proxima, por_fonte, creditos),
            )
        )
        log.info("resumo_enviado chat_id=%s", pessoa.chat_id)
        enviados += 1
    return enviados
