"""Bot do Telegram: whitelist, comandos, despachante e entregador (R10 da 002, R2 da 003)."""

import asyncio
import logging
import random
import time
from collections.abc import Iterable
from datetime import datetime, timedelta

import redis.exceptions
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from apebot.banco import Banco
from apebot.cadastro import (
    JA_PASSOU,
    Resposta,
    Resultado,
    iniciar_cadastro,
    iniciar_edicao,
    processar,
    reapresentar,
)
from apebot.config import Configuracao
from apebot.fila import Fila, FilaPessoa, Mensagem
from apebot.filtro import aceita
from apebot.fontes.geckoapi import ClienteGecko, saldo
from apebot.mensagens import (
    CADASTRO_ABERTO,
    TEXTO_PAUSADO,
    TEXTO_RETOMADO,
    boas_vindas,
    botoes_imovel,
    filtros_salvos,
    mensagem_imovel,
    proxima_rodada,
    resposta_padrao,
    texto_ajuda,
    texto_filtros,
    texto_status,
)
from apebot.modelos import FUSO, Pessoa

log = logging.getLogger(__name__)

INTERVALO_POR_CHAT = 1.1
INTERVALO_GLOBAL = 0.05
MAX_TENTATIVAS = 3
JANELA_ENTREGA = (8, 22)  # horas em America/Sao_Paulo: de 08:00 a 21:59 (FR-003 da 003)
VOLTA_DESPACHANTE_SEGUNDOS = 20
SEM_PREVIA = LinkPreviewOptions(is_disabled=True)


def registrar_handlers(
    app: Application,
    config: Configuracao,
    banco: Banco,
    fila_pessoa: FilaPessoa,
    fontes_ligadas: list[str],
    gecko: ClienteGecko | None = None,
) -> None:
    autorizados = set(config.autorizados) | {config.operador_chat_id}

    async def responder(update: Update, texto: str, botoes=None) -> None:
        await update.effective_message.reply_text(
            texto,
            parse_mode=ParseMode.HTML,
            link_preview_options=SEM_PREVIA,
            reply_markup=_teclado(botoes or []),
        )

    async def barrar_nao_autorizados(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        if chat is None or chat.id not in autorizados:
            log.info("chat_nao_autorizado chat_id=%s", chat.id if chat else None)
            raise ApplicationHandlerStop
        if update.callback_query is not None:
            entrada = "botao"
        else:
            mensagem = update.effective_message
            texto = mensagem.text if mensagem and mensagem.text else ""
            entrada = texto.split()[0] if texto.startswith("/") else "mensagem"
        log.info("update_recebido chat_id=%s texto=%s", chat.id, entrada)

    async def cadastrada(update: Update) -> Pessoa | None:
        """A pessoa com cadastro completo; senão, pede para terminar o cadastro."""
        pessoa, _, _ = await asyncio.to_thread(banco.pessoa, update.effective_chat.id)
        if pessoa is None:
            await responder(update, CADASTRO_ABERTO)
        return pessoa

    # --- cadastro e edição (research R6 da 003) ---

    async def mostrar(update: Update, resposta: Resposta | None) -> None:
        query = update.callback_query
        if query is not None:
            await query.answer(resposta.aviso if resposta else None)
        if resposta is None or resposta.texto is None:
            return
        teclado = _teclado(
            [[{"t": b.texto, "c": b.dados} for b in linha] for linha in resposta.teclado]
        )
        if query is not None and resposta.editar:
            try:
                await query.edit_message_text(
                    resposta.texto,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=SEM_PREVIA,
                    reply_markup=teclado,
                )
            except BadRequest as erro:
                if "not modified" not in str(erro):
                    raise
            return
        await update.effective_message.reply_text(
            resposta.texto,
            parse_mode=ParseMode.HTML,
            link_preview_options=SEM_PREVIA,
            reply_markup=teclado,
        )

    async def aplicar(update: Update, modo: str, resultado: Resultado) -> None:
        chat_id = update.effective_chat.id
        if resultado.acao == "seguir":
            await asyncio.to_thread(banco.salvar_conversa, chat_id, resultado.estado)
            await mostrar(update, resultado.resposta)
            return
        await asyncio.to_thread(banco.apagar_conversa, chat_id)
        if resultado.acao == "cancelar":
            await mostrar(update, resultado.resposta)
            return
        await asyncio.to_thread(banco.salvar_filtros, chat_id, resultado.nome, resultado.filtro)
        if modo == "cadastro":
            log.info("cadastro_concluido chat_id=%s", chat_id)
            texto = boas_vindas(resultado.nome)
        else:
            log.info("filtros_salvos chat_id=%s", chat_id)
            texto = filtros_salvos(proxima_rodada(datetime.now(FUSO)))
        await mostrar(update, Resposta(texto, editar=True))

    async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        await asyncio.to_thread(banco.registrar_pessoa, chat_id)
        log.info("pessoa_registrada chat_id=%s", chat_id)
        conversa = await asyncio.to_thread(banco.conversa, chat_id)
        if conversa is not None and conversa.modo == "cadastro":  # retomada (FR-023)
            await mostrar(update, reapresentar(conversa))
            return
        pessoa, _, _ = await asyncio.to_thread(banco.pessoa, chat_id)
        if pessoa is not None:
            await mostrar_filtros(update, chat_id)
            return
        await aplicar(update, "cadastro", iniciar_cadastro())

    async def editar(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        pessoa, _, _ = await asyncio.to_thread(banco.pessoa, update.effective_chat.id)
        if pessoa is None:
            await update.callback_query.answer(JA_PASSOU)
            return
        resultado = iniciar_edicao(pessoa)
        resultado.resposta.editar = True
        await aplicar(update, "edicao", resultado)

    async def botao_conversa(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        estado = await asyncio.to_thread(banco.conversa, update.effective_chat.id)
        if estado is None:
            await update.callback_query.answer(JA_PASSOU)
            return
        await aplicar(update, estado.modo, processar(estado, dados=update.callback_query.data))

    async def texto_livre(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        estado = await asyncio.to_thread(banco.conversa, update.effective_chat.id)
        mensagem = update.effective_message
        if estado is not None and mensagem.text and mensagem.text.startswith("/"):
            # comando desconhecido no meio da conversa não vira resposta (ex.: nome "/x")
            await responder(
                update, CADASTRO_ABERTO if estado.modo == "cadastro" else resposta_padrao()
            )
            return
        if estado is None or not mensagem.text:
            await mensagem.reply_text(resposta_padrao())
            return
        await aplicar(update, estado.modo, processar(estado, texto=mensagem.text))

    # --- comandos ---

    async def ajuda(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await responder(update, texto_ajuda(fontes_ligadas))

    async def ver_filtros(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if await cadastrada(update) is None:
            return
        await mostrar_filtros(update, chat_id)

    async def mostrar_filtros(update: Update, chat_id: int) -> None:
        """Texto Filtros com "Editar filtros"; uma edição aberta e abandonada é descartada."""
        await asyncio.to_thread(banco.apagar_conversa, chat_id)
        pessoa, pausada, _ = await asyncio.to_thread(banco.pessoa, chat_id)
        await responder(update, texto_filtros(pessoa, pausada), BOTAO_EDITAR)

    async def status(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if await cadastrada(update) is None:
            return
        ultima = await asyncio.to_thread(banco.ultima_rodada)
        estados = await asyncio.to_thread(banco.estados_fonte)
        recebidos = await asyncio.to_thread(banco.recebidos_24h, chat_id)
        texto = texto_status(
            ultima,
            proxima_rodada(datetime.now(FUSO)),
            recebidos,
            estados,
            fontes_ligadas,
            await saldo(gecko),  # créditos para todas as pessoas (decisão do dono, FR-031)
            await fila_pessoa.tamanho(chat_id),
        )
        await responder(update, texto)

    async def pausar(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if await cadastrada(update) is None:
            return
        await asyncio.to_thread(banco.pausar, chat_id)
        # os imóveis que não saíram voltam a ser candidatos depois do /retomar (research R4)
        await fila_pessoa.limpar(chat_id)
        await asyncio.to_thread(banco.apagar_pendentes, chat_id)
        log.info("avisos_pausados chat_id=%s", chat_id)
        await responder(update, TEXTO_PAUSADO)

    async def retomar(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if await cadastrada(update) is None:
            return
        await asyncio.to_thread(banco.retomar, chat_id)
        log.info("avisos_retomados chat_id=%s", chat_id)
        await responder(update, TEXTO_RETOMADO)

    app.add_handler(TypeHandler(Update, barrar_nao_autorizados), group=-1)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("help", ajuda))
    app.add_handler(CommandHandler("filtros", ver_filtros))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("pausar", pausar))
    app.add_handler(CommandHandler("retomar", retomar))
    app.add_handler(CallbackQueryHandler(editar, pattern=r"^e:inicio$"))
    app.add_handler(CallbackQueryHandler(botao_conversa, pattern=r"^c:"))
    app.add_handler(MessageHandler(filters.ALL, texto_livre))


BOTAO_EDITAR = [[{"t": "✏️ Editar filtros", "c": "e:inicio"}]]


def _botao(botao: dict[str, str]) -> InlineKeyboardButton:
    if "u" in botao:
        return InlineKeyboardButton(botao["t"], url=botao["u"])
    return InlineKeyboardButton(botao["t"], callback_data=botao["c"])


def _teclado(linhas: list[list[dict[str, str]]]) -> InlineKeyboardMarkup | None:
    if not linhas:
        return None
    return InlineKeyboardMarkup([[_botao(b) for b in linha] for linha in linhas])


def dentro_da_janela(momento: datetime) -> bool:
    inicio, fim = JANELA_ENTREGA
    return inicio <= momento.astimezone(FUSO).hour < fim


def sortear_intervalo(intervalo: tuple[int, int], aleatorio: random.Random) -> int:
    return aleatorio.randint(*intervalo)


Chave = tuple[str, str]


def faltando_na_fila(
    pendentes: Iterable[Chave], na_fila: set[Chave], em_entrega: set[Chave]
) -> set[Chave]:
    return set(pendentes) - na_fila - em_entrega


class Despachante:
    """Tira um imóvel por pessoa da fila dela, no ritmo sorteado, e põe na fila de entrega."""

    def __init__(
        self,
        fila: Fila,
        fila_pessoa: FilaPessoa,
        banco: Banco,
        autorizados: Iterable[int],
        intervalo: tuple[int, int],
        aleatorio: random.Random | None = None,
    ) -> None:
        self._fila = fila
        self._fila_pessoa = fila_pessoa
        self._banco = banco
        self._autorizados = set(autorizados)
        self._intervalo = intervalo
        self._aleatorio = aleatorio or random.Random()

    async def reconciliar(self) -> None:
        """Recoloca na fila da pessoa os pendentes que se perderam num reinício (research R3)."""
        pessoas = await asyncio.to_thread(self._banco.pessoas_ativas, self._autorizados)
        em_entrega = await self._fila.chaves_em_entrega()
        for pessoa in pessoas:
            pendentes = await asyncio.to_thread(self._banco.pendentes_de, pessoa.chat_id)
            por_chave = {a.chave: a for a in pendentes}
            faltando = faltando_na_fila(
                por_chave,
                await self._fila_pessoa.membros(pessoa.chat_id),
                {(f, i) for c, f, i in em_entrega if c == pessoa.chat_id},
            )
            for chave in faltando:  # do banco: sem contato
                await self._fila_pessoa.adicionar(pessoa.chat_id, por_chave[chave])
            if faltando:
                log.info("reconciliacao chat_id=%s recolocados=%d", pessoa.chat_id, len(faltando))

    async def uma_volta(self, agora: datetime) -> None:
        if not dentro_da_janela(agora):
            return
        pessoas = await asyncio.to_thread(self._banco.pessoas_ativas, self._autorizados)
        for pessoa in pessoas:
            try:
                await self._despachar(pessoa, agora)
            except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError):
                raise
            except Exception:  # uma pessoa com problema não para as outras
                log.exception("despacho_erro chat_id=%s", pessoa.chat_id)

    async def _despachar(self, pessoa: Pessoa, agora: datetime) -> None:
        chat_id = pessoa.chat_id
        proximo = await self._fila_pessoa.proximo(chat_id)
        if proximo is not None and agora.timestamp() < proximo:
            return
        while (item := await self._fila_pessoa.retirar_mais_barato(chat_id)) is not None:
            anuncio, contato = item
            if not aceita(pessoa.filtro, anuncio):  # filtros mudaram depois que entrou (FR-006)
                await asyncio.to_thread(self._banco.apagar_pendente, chat_id, anuncio.chave)
                log.info("imovel_descartado_filtro chat_id=%s", chat_id)
                continue
            await self._fila.enfileirar(
                Mensagem(
                    chat_id=chat_id,
                    tipo="imovel",
                    texto=mensagem_imovel(anuncio, contato),
                    anuncio_ids=[anuncio.chave],
                    botoes=botoes_imovel(anuncio, contato),
                )
            )
            espera = sortear_intervalo(self._intervalo, self._aleatorio)
            await self._fila_pessoa.marcar_proximo(chat_id, agora.timestamp() + espera)
            log.info("imovel_despachado chat_id=%s proximo_em=%ds", chat_id, espera)
            return

    async def executar(self) -> None:
        while True:
            try:
                await self.reconciliar()
                break
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("reconciliacao_erro")
                await asyncio.sleep(5)
        while True:
            try:
                await self.uma_volta(datetime.now(FUSO))
                await asyncio.sleep(VOLTA_DESPACHANTE_SEGUNDOS)
            except asyncio.CancelledError:
                raise
            except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as erro:
                log.warning("fila_indisponivel erro=%s", erro)
                await asyncio.sleep(5)
            except Exception:
                log.exception("despachante_erro")
                await asyncio.sleep(5)


class Entregador:
    """Consome a fila e entrega no Telegram respeitando o limite de taxa."""

    def __init__(self, app: Application, fila: Fila, banco: Banco) -> None:
        self._bot = app.bot
        self._fila = fila
        self._banco = banco
        self._ultimo_envio: dict[int, float] = {}

    async def executar(self) -> None:
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
