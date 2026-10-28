"""Bot do Telegram: whitelist, comandos e worker que entrega a fila (R7 da 001, R10 da 002)."""

import asyncio
import logging
import time
from datetime import datetime, timedelta

import redis.exceptions
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from apebot.banco import Banco
from apebot.config import Configuracao
from apebot.fila import Fila, Mensagem
from apebot.fontes.geckoapi import ClienteGecko, ErroGecko
from apebot.mensagens import (
    SEM_FILTROS,
    TEXTO_PAUSADO,
    TEXTO_RETOMADO,
    botoes_imovel,
    confirmacao_start,
    mensagem_imovel,
    proxima_rodada,
    resposta_padrao,
    texto_ajuda,
    texto_filtros,
    texto_status,
)
from apebot.modelos import FUSO

log = logging.getLogger(__name__)

INTERVALO_POR_CHAT = 1.1
INTERVALO_GLOBAL = 0.05
MAX_TENTATIVAS = 3
PENDENTE_ANTIGO_MINUTOS = 10
SEM_PREVIA = LinkPreviewOptions(is_disabled=True)


def registrar_handlers(
    app: Application,
    config: Configuracao,
    banco: Banco,
    fontes_ligadas: list[str],
    gecko: ClienteGecko | None = None,
) -> None:
    pessoas = {p.chat_id: p for p in config.pessoas}
    autorizados = set(pessoas) | {config.operador_chat_id}
    operador = pessoas.get(config.operador_chat_id)
    nome_operador = operador.nome if operador else "o operador"

    async def responder(update: Update, texto: str) -> None:
        await update.effective_message.reply_text(
            texto, parse_mode=ParseMode.HTML, link_preview_options=SEM_PREVIA
        )

    async def barrar_nao_autorizados(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        if chat is None or chat.id not in autorizados:
            log.info("chat_nao_autorizado chat_id=%s", chat.id if chat else None)
            raise ApplicationHandlerStop
        mensagem = update.effective_message
        texto = mensagem.text if mensagem and mensagem.text else ""
        log.info(
            "update_recebido chat_id=%s texto=%s",
            chat.id,
            texto.split()[0] if texto.startswith("/") else "mensagem",
        )

    async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        pessoa = pessoas.get(chat_id)
        if pessoa is None:  # operador sem filtros válidos
            await update.effective_message.reply_text("Você está sem filtros válidos.")
            return
        await asyncio.to_thread(banco.registrar_pessoa, chat_id)
        log.info("pessoa_registrada chat_id=%s", chat_id)
        pausada = await asyncio.to_thread(banco.pausada_em, chat_id)
        await responder(update, confirmacao_start(pessoa, pausada=pausada is not None))

    async def ajuda(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await responder(update, texto_ajuda(fontes_ligadas))

    async def ver_filtros(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        pessoa = pessoas.get(chat_id)
        if pessoa is None:
            await responder(update, SEM_FILTROS)
            return
        pausada = await asyncio.to_thread(banco.pausada_em, chat_id)
        await responder(update, texto_filtros(pessoa, pausada, nome_operador))

    async def status(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        ultima = await asyncio.to_thread(banco.ultima_rodada)
        estados = await asyncio.to_thread(banco.estados_fonte)
        recebidos = await asyncio.to_thread(banco.recebidos_24h, chat_id)
        creditos: dict | str | None = None
        if chat_id == config.operador_chat_id and gecko is not None:
            try:
                creditos = await gecko.creditos()
            except (ErroGecko, ValueError) as erro:
                log.warning("creditos_indisponiveis erro=%s", erro)
                creditos = "indisponível"
        texto = texto_status(
            ultima, proxima_rodada(datetime.now(FUSO)), recebidos, estados, fontes_ligadas, creditos
        )
        await responder(update, texto)

    async def pausar(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if chat_id not in pessoas:
            await responder(update, SEM_FILTROS)
            return
        await asyncio.to_thread(banco.pausar, chat_id)
        log.info("avisos_pausados chat_id=%s", chat_id)
        await responder(update, TEXTO_PAUSADO)

    async def retomar(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if chat_id not in pessoas:
            await responder(update, SEM_FILTROS)
            return
        await asyncio.to_thread(banco.retomar, chat_id)
        log.info("avisos_retomados chat_id=%s", chat_id)
        await responder(update, TEXTO_RETOMADO)

    async def padrao(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(resposta_padrao())

    app.add_handler(TypeHandler(Update, barrar_nao_autorizados), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("help", ajuda))
    app.add_handler(CommandHandler("filtros", ver_filtros))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("pausar", pausar))
    app.add_handler(CommandHandler("retomar", retomar))
    app.add_handler(MessageHandler(filters.ALL, padrao))


def _teclado(botoes: list[list[str]]) -> InlineKeyboardMarkup | None:
    if not botoes:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton(rotulo, url=url) for rotulo, url in botoes]])


class Entregador:
    """Consome a fila e entrega no Telegram respeitando o limite de taxa."""

    def __init__(self, app: Application, fila: Fila, banco: Banco) -> None:
        self._bot = app.bot
        self._fila = fila
        self._banco = banco
        self._ultimo_envio: dict[int, float] = {}

    async def reenfileirar_pendentes(self) -> None:
        if await self._fila.tamanho():
            return  # a fila persistida ainda tem as mensagens; não duplicar
        pendentes = await asyncio.to_thread(self._banco.pendentes_antigos, PENDENTE_ANTIGO_MINUTOS)
        for chat_id, anuncio in pendentes:
            await self._fila.enfileirar(
                Mensagem(
                    chat_id=chat_id,
                    tipo="imovel",
                    texto=mensagem_imovel(anuncio),  # sem contato: ele não fica no banco
                    anuncio_ids=[anuncio.chave],
                    botoes=botoes_imovel(anuncio),
                )
            )
        if pendentes:
            log.info("pendentes_reenfileirados quantidade=%d", len(pendentes))

    async def executar(self) -> None:
        await self.reenfileirar_pendentes()
        while True:
            try:
                mensagem = await self._fila.consumir()
                if mensagem is not None:
                    await self._entregar(mensagem)
            except asyncio.CancelledError:
                raise
            except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as erro:
                log.warning("fila_indisponivel erro=%s", erro)
                await asyncio.sleep(5)
            except Exception:
                log.exception("entregador_erro")
                await asyncio.sleep(5)

    async def _esperar_vez(self, chat_id: int) -> None:
        decorrido = time.monotonic() - self._ultimo_envio.get(chat_id, 0.0)
        await asyncio.sleep(max(INTERVALO_GLOBAL, INTERVALO_POR_CHAT - decorrido))

    async def _entregar(self, m: Mensagem) -> None:
        await self._esperar_vez(m.chat_id)
        try:
            await self._bot.send_message(
                m.chat_id,
                m.texto,
                parse_mode=ParseMode.HTML,
                link_preview_options=SEM_PREVIA,
                reply_markup=_teclado(m.botoes),
            )
        except RetryAfter as erro:
            espera = erro.retry_after
            segundos = espera.total_seconds() if isinstance(espera, timedelta) else float(espera)
            log.warning("telegram_retry_after chat_id=%s espera=%.0fs", m.chat_id, segundos)
            await asyncio.sleep(segundos)
            await self._fila.enfileirar_no_inicio(m)
            return
        except Forbidden:
            log.warning("telegram_bloqueado chat_id=%s", m.chat_id)
            await self._marcar(m, "falhou")
            return
        except TelegramError as erro:
            m.tentativas += 1
            log.warning(
                "telegram_erro chat_id=%s tentativa=%d erro=%s", m.chat_id, m.tentativas, erro
            )
            if m.tentativas < MAX_TENTATIVAS:
                await self._fila.enfileirar(m)
            else:
                await self._marcar(m, "falhou")
            return
        finally:
            self._ultimo_envio[m.chat_id] = time.monotonic()
        await self._marcar(m, "entregue")
        log.info(
            "mensagem_entregue chat_id=%s tipo=%s anuncios=%d",
            m.chat_id,
            m.tipo,
            len(m.anuncio_ids),
        )

    async def _marcar(self, m: Mensagem, status: str) -> None:
        if m.anuncio_ids:
            await asyncio.to_thread(self._banco.marcar_envio, m.chat_id, m.anuncio_ids, status)
