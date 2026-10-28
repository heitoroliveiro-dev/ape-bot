"""Uma rodada: coleta → banco → filtro → fila → registro e alerta (research R9, R10)."""

import asyncio
import logging
from collections import Counter
from datetime import datetime, timedelta

from apebot.banco import Banco, agora
from apebot.config import Configuracao
from apebot.fila import Fila, Mensagem
from apebot.filtro import hash_filtros, novos_para
from apebot.fontes.quintoandar import buscar_paginas, combinacoes
from apebot.mensagens import aviso_falha, aviso_recuperacao, mensagem_imovel, mensagens_resumo
from apebot.modelos import FUSO, Anuncio, Pessoa

log = logging.getLogger(__name__)

FALHAS_PARA_ALERTA = 3
REAVISO = timedelta(hours=24)


def status_rodada(paginas_ok: int, paginas_erro: int, erro_de_formato: bool) -> str:
    if erro_de_formato:
        return "falha"
    total = paginas_ok + paginas_erro
    if total and paginas_erro * 2 >= total:
        return "falha"
    return "ok"


class Rodada:
    def __init__(
        self, banco: Banco, fila: Fila, config: Configuracao, simular_falha: bool = False
    ) -> None:
        self._banco = banco
        self._fila = fila
        self._config = config
        self._simular_falha = simular_falha

    async def executar(self) -> str:
        rodada_id = await asyncio.to_thread(self._banco.iniciar_rodada)
        contagens: Counter[str] = Counter()
        status, erro_resumo = "falha", None
        try:
            status, erro_resumo = await self._coletar_e_enfileirar(contagens)
        except Exception as erro:  # a rodada nunca derruba o robô (FR-017)
            log.exception("rodada_erro_inesperado rodada=%d", rodada_id)
            status, erro_resumo = "falha", f"inesperado: {erro!r}"
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
        try:
            await self._avaliar_alerta(status, erro_resumo)
        except Exception:
            log.exception("alerta_erro rodada=%d", rodada_id)
        return status

    async def _coletar_e_enfileirar(self, contagens: Counter[str]) -> tuple[str, str | None]:
        registradas = await asyncio.to_thread(self._banco.pessoas_registradas)
        pessoas = [p for p in self._config.pessoas if p.chat_id in registradas]
        if not pessoas:
            log.warning("rodada_sem_pessoas_registradas: peça /start ao bot")
        paginas = await buscar_paginas(combinacoes(pessoas), self._simular_falha)

        anuncios = [a for pagina in paginas for a in pagina.anuncios]
        erros = [pagina.erro for pagina in paginas if pagina.erro]
        contagens["paginas_ok"] = len(paginas) - len(erros)
        contagens["paginas_erro"] = len(erros)
        contagens["anuncios_vistos"] = len(anuncios)
        contagens["descartados"] = sum(sum(p.descartados.values()) for p in paginas)
        status = status_rodada(
            contagens["paginas_ok"],
            contagens["paginas_erro"],
            any(p.erro_de_formato for p in paginas),
        )
        contagens["anuncios_novos"] = await asyncio.to_thread(self._banco.salvar_anuncios, anuncios)

        for pessoa in pessoas:
            contagens["enfileirados"] += await self._enfileirar_para(
                pessoa, anuncios, registradas[pessoa.chat_id], status
            )
        return status, (erros[-1] if erros else None)

    async def _enfileirar_para(
        self, pessoa: Pessoa, anuncios: list[Anuncio], hash_anterior: str | None, status: str
    ) -> int:
        hash_atual = hash_filtros(pessoa.filtro)
        modo_resumo = hash_anterior != hash_atual
        if modo_resumo and status == "falha":
            return 0  # resumo só com coleta confiável; tenta de novo na próxima rodada

        ja_enviados = await asyncio.to_thread(self._banco.ja_enviados, pessoa.chat_id)
        candidatos = novos_para(pessoa, anuncios, ja_enviados)
        inseridos = set(
            await asyncio.to_thread(
                self._banco.criar_envios_pendentes, pessoa.chat_id, [a.chave for a in candidatos]
            )
        )
        novos = [a for a in candidatos if a.chave in inseridos]

        if modo_resumo:
            partes = mensagens_resumo(novos)
            for indice, texto in enumerate(partes):
                ultima = indice == len(partes) - 1
                await self._fila.enfileirar(
                    Mensagem(
                        chat_id=pessoa.chat_id,
                        tipo="resumo",
                        texto=texto,
                        anuncio_ids=[a.chave for a in novos] if ultima else [],
                    )
                )
            await asyncio.to_thread(self._banco.atualizar_filtros_hash, pessoa.chat_id, hash_atual)
            return len(partes)

        for anuncio in novos:
            await self._fila.enfileirar(
                Mensagem(
                    chat_id=pessoa.chat_id,
                    tipo="imovel",
                    texto=mensagem_imovel(anuncio),
                    anuncio_ids=[anuncio.chave],
                )
            )
        return len(novos)

    async def _avaliar_alerta(self, status: str, erro_resumo: str | None) -> None:
        aberto = await asyncio.to_thread(self._banco.alerta_aberto)
        if status == "ok":
            if aberto:
                await asyncio.to_thread(self._banco.fechar_alerta, aberto[0])
                await self._avisar_operador(aviso_recuperacao(datetime.now(FUSO)))
            return

        ultimas = await asyncio.to_thread(self._banco.ultimas_rodadas, 50)
        seguidas = next((i for i, (s, _) in enumerate(ultimas) if s != "falha"), len(ultimas))
        if aberto:
            alerta_id, ultimo_aviso = aberto
            if agora() - ultimo_aviso >= REAVISO:
                await asyncio.to_thread(self._banco.registrar_aviso, alerta_id)
                await self._avisar_operador(aviso_falha(seguidas, erro_resumo))
        elif seguidas >= FALHAS_PARA_ALERTA:
            await asyncio.to_thread(self._banco.abrir_alerta)
            await self._avisar_operador(aviso_falha(seguidas, erro_resumo))

    async def _avisar_operador(self, texto: str) -> None:
        await self._fila.enfileirar(
            Mensagem(chat_id=self._config.operador_chat_id, tipo="operador", texto=texto)
        )
