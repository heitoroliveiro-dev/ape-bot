"""Bot do Telegram: whitelist, /start e worker que entrega a fila (research R7)."""

import asyncio
import logging
import time
from datetime import timedelta

from telegram import LinkPreviewOptions, Update
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
from apebot.mensagens import confirmacao_start, mensagem_imovel, resposta_padrao

log = logging.getLogger(__name__)

INTERVALO_POR_CHAT = 1.1
INTERVALO_GLOBAL = 0.05
MAX_TENTATIVAS = 3
PENDENTE_ANTIGO_MINUTOS = 10
SEM_PREVIA = LinkPreviewOptions(is_disabled=True)


def registrar_handlers(app: Application, config: Configuracao, banco: Banco) -> None:
    pessoas = {p.chat_id: p for p in config.pessoas}
    autorizados = set(pessoas) | {config.operador_chat_id}

    async def barrar_nao_autorizados(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        if chat is None or chat.id not in autorizados:
            log.info("chat_nao_autorizado chat_id=%s", chat.id if chat else None)
            raise ApplicationHandlerStop

    async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        pessoa = pessoas.get(chat_id)
        if pessoa is None:  # operador sem filtros válidos
            await update.effective_message.reply_text("Você está sem filtros válidos.")
            return
        await asyncio.to_thread(banco.registrar_pessoa, chat_id)
        log.info("pessoa_registrada chat_id=%s", chat_id)
        await update.effective_message.reply_text(
            confirmacao_start(pessoa), parse_mode=ParseMode.HTML
        )

    async def padrao(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(resposta_padrao())

    app.add_handler(TypeHandler(Update, barrar_nao_autorizados), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, padrao))


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
                    texto=mensagem_imovel(anuncio),
                    anuncio_ids=[anuncio.chave],
                )
            )
        if pendentes:
            log.info("pendentes_reenfileirados quantidade=%d", len(pendentes))

    async def executar(self) -> None:
        await self.reenfileirar_pendentes()
        while True:
            try:
                mensagem = await self._fila.consumir(timeout=5)
                if mensagem is not None:
                    await self._entregar(mensagem)
            except asyncio.CancelledError:
                raise
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
                m.chat_id, m.texto, parse_mode=ParseMode.HTML, link_preview_options=SEM_PREVIA
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
