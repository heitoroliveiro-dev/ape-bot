"""Fluxo do bot com updates falsos: cadastro, edição e comandos, sem rede nem banco."""

import asyncio
from types import SimpleNamespace

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler

from apebot.config import Configuracao
from apebot.filtro import filtro_de_json, filtro_para_json
from apebot.mensagens import botoes_imovel
from apebot.modelos import Filtro, Pessoa, Tipo
from apebot.telegram_bot import _teclado, registrar_handlers
from tests.test_mensagens import CONTATO, ZAP

CHAT = 10


class BancoFalso:
    def __init__(self):
        self.pessoas: dict[int, Pessoa] = {}
        self.conversas = {}
        self.pausada = None
        self.favoritos = set()

    def registrar_pessoa(self, chat_id):
        pass

    def pessoa(self, chat_id):
        pessoa = self.pessoas.get(chat_id)
        return pessoa, self.pausada, pessoa is not None

    def conversa(self, chat_id):
        return self.conversas.get(chat_id)

    def salvar_conversa(self, chat_id, estado):
        self.conversas[chat_id] = estado

    def apagar_conversa(self, chat_id):
        self.conversas.pop(chat_id, None)

    def alternar_favorito(self, chat_id, chave):
        self.favoritos ^= {chave}
        return chave in self.favoritos

    def salvar_filtros(self, chat_id, nome, filtro):
        # passa pelo mesmo JSON do MySQL
        salvo = filtro_de_json(filtro_para_json(filtro), filtro.bairros)
        self.pessoas[chat_id] = Pessoa(chat_id=chat_id, nome=nome, filtro=salvo)


class Mensagem:
    def __init__(self, texto=None):
        self.text = texto
        self.enviadas = []

    async def reply_text(self, texto, **kwargs):
        self.enviadas.append((texto, kwargs.get("reply_markup")))


class Query:
    def __init__(self, dados, mensagem):
        self.data = dados
        self.message = mensagem
        self.avisos = []
        self.editadas = []
        self.teclados = []

    async def edit_message_reply_markup(self, reply_markup=None):
        self.teclados.append(reply_markup)

    async def answer(self, texto=None):
        self.avisos.append(texto)

    async def edit_message_text(self, texto, **kwargs):
        self.editadas.append((texto, kwargs.get("reply_markup")))


def _app():
    app = Application.builder().token("1:x").build()
    banco = BancoFalso()
    config = Configuracao(operador_chat_id=CHAT, autorizados={CHAT: None})
    registrar_handlers(app, config, banco, fila_pessoa=None, fontes_ligadas=["quintoandar"])
    return app, banco


def _handler(app, tipo, comando=None):
    for h in app.handlers[0]:
        if isinstance(h, tipo) and (comando is None or comando in h.commands):
            return h.callback
    raise LookupError(comando)


def _comando(app, nome):
    mensagem = Mensagem(f"/{nome}")
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=CHAT), effective_message=mensagem, callback_query=None
    )
    asyncio.run(_handler(app, CommandHandler, nome)(update, None))
    return mensagem.enviadas


def _texto(app, texto):
    mensagem = Mensagem(texto)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=CHAT), effective_message=mensagem, callback_query=None
    )
    asyncio.run(_handler(app, MessageHandler)(update, None))
    return mensagem.enviadas


def _tocar(app, dados, reply_markup=None):
    mensagem = Mensagem()
    mensagem.reply_markup = reply_markup
    query = Query(dados, mensagem)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=CHAT), effective_message=mensagem, callback_query=query
    )
    for h in app.handlers[0]:
        if isinstance(h, CallbackQueryHandler) and h.pattern.match(dados):
            asyncio.run(h.callback(update, None))
            return query
    raise LookupError(dados)


def _dados(markup):
    return [b.callback_data for linha in markup.inline_keyboard for b in linha if b.callback_data]


def test_cadastro_completo_pelo_start():
    app, banco = _app()
    ((texto, _),) = _comando(app, "start")
    assert texto.endswith("Como devo te chamar?")
    ((texto, markup),) = _texto(app, "maria clara")
    assert texto.startswith("Você busca quais tipos")
    assert "c:tipos:t:apartamento" in _dados(markup)
    _tocar(app, "c:tipos:t:apartamento")
    _tocar(app, "c:tipos:ok")
    _tocar(app, "c:quartos:q:2")
    _tocar(app, "c:regionais:r:6")
    _tocar(app, "c:bairros:t:barroca")
    _tocar(app, "c:bairros:volta")
    query = _tocar(app, "c:regionais:ok")
    assert query.editadas[-1][0].startswith("Qual valor máximo")
    ((texto, _),) = _texto(app, "3k")
    assert texto.startswith("Não entendi esse valor.")
    ((texto, _),) = _texto(app, "2.500")
    assert texto.startswith("Perfeito, Maria Clara!")
    assert banco.conversas == {}
    assert banco.pessoas[CHAT].filtro.aluguel_max_centavos == 250_000


def test_retomada_e_comandos_no_meio_do_cadastro():
    app, banco = _app()
    _comando(app, "start")
    _texto(app, "Ana")
    ((texto, _),) = _comando(app, "filtros")
    assert texto == "Termine o cadastro primeiro: /start"
    ((texto, _),) = _texto(app, "/favoritos")
    assert texto == "Termine o cadastro primeiro: /start"
    ((texto, _),) = _comando(app, "start")
    assert texto.startswith("Você busca quais tipos")


def test_filtros_editar_e_cancelar():
    app, banco = _app()
    filtro = Filtro(
        bairros=frozenset({"prado"}),
        aluguel_max_centavos=300_000,
        quartos_min=2,
        tipos=frozenset({Tipo.APARTAMENTO}),
    )
    banco.pessoas[CHAT] = Pessoa(chat_id=CHAT, nome="Heitor", filtro=filtro)
    ((texto, markup),) = _comando(app, "filtros")
    assert texto.startswith("Seus filtros -\nBairros: Prado\nValores até R$ 3.000,00")
    assert _dados(markup) == ["e:inicio"]
    query = _tocar(app, "e:inicio")
    assert query.editadas[-1][0].startswith("Você busca quais tipos")
    query = _tocar(app, "c:tipos:cancelar")
    assert query.editadas[-1][0] == "Edição cancelada. Seus filtros continuam os mesmos."
    assert banco.conversas == {}
    query = _tocar(app, "c:tipos:ok")  # botão velho
    assert query.avisos == ["Essa pergunta já passou."]


def test_editar_e_salvar_o_valor():
    app, banco = _app()
    filtro = Filtro(
        bairros=frozenset({"prado"}),
        aluguel_max_centavos=300_000,
        quartos_min=2,
        tipos=frozenset({Tipo.APARTAMENTO}),
    )
    banco.pessoas[CHAT] = Pessoa(chat_id=CHAT, nome="Heitor", filtro=filtro)
    _tocar(app, "e:inicio")
    _tocar(app, "c:tipos:ok")
    _tocar(app, "c:quartos:q:2")
    _tocar(app, "c:regionais:ok")
    ((texto, _),) = _texto(app, "R$ 2.000,00")
    assert texto.startswith("Confere?")
    query = _tocar(app, "c:revisao:salvar")
    assert query.editadas[-1][0].startswith("Filtros salvos! Eles valem a partir da próxima rodada")
    assert banco.pessoas[CHAT].filtro.aluguel_max_centavos == 200_000


def test_favorito_alterna_e_troca_so_o_botao():
    app, banco = _app()
    markup = _teclado(botoes_imovel(ZAP, CONTATO))
    query = _tocar(app, "f:zap:2919519749", markup)
    assert query.avisos == ["⭐ Salvo nos favoritos"]
    assert banco.favoritos == {("zap", "2919519749")}
    (novo,) = query.teclados
    rotulos = [b.text for linha in novo.inline_keyboard for b in linha]
    assert rotulos == ["Abrir anúncio", "WhatsApp", "✅ Favorito · toque para remover"]
    query = _tocar(app, "f:zap:2919519749", novo)
    assert query.avisos == ["Removido dos favoritos"]
    assert banco.favoritos == set()
