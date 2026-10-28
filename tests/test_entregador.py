import asyncio

from telegram.error import Forbidden

from apebot.fila import Mensagem
from apebot.telegram_bot import Entregador


class BotFalso:
    def __init__(self, erro=None):
        self.erro = erro
        self.enviadas = []

    async def send_message(self, chat_id, texto, **kwargs):
        if self.erro:
            raise self.erro
        self.enviadas.append((chat_id, texto))


class BancoFalso:
    def __init__(self):
        self.marcados = []
        self.lembrados = []

    def marcar_envio(self, chat_id, chaves, status):
        self.marcados.append((chat_id, list(chaves), status))

    def marcar_lembrado(self, chat_id, chaves):
        self.lembrados.append((chat_id, list(chaves)))


def _entregar(tipo, erro=None):
    banco = BancoFalso()
    app = type("App", (), {"bot": BotFalso(erro)})()
    entregador = Entregador(app, fila=None, banco=banco)
    mensagem = Mensagem(chat_id=1, tipo=tipo, texto="x", anuncio_ids=[("zap", "9")])
    asyncio.run(entregador._entregar(mensagem))
    return banco


def test_lembrete_entregue_marca_lembrado_e_nao_mexe_no_envio():
    banco = _entregar("lembrete")
    assert banco.lembrados == [(1, [("zap", "9")])]
    assert banco.marcados == []


def test_lembrete_bloqueado_tambem_conta_como_lembrado():
    banco = _entregar("lembrete", Forbidden("bloqueado"))
    assert banco.lembrados == [(1, [("zap", "9")])]
    assert banco.marcados == []


def test_imovel_continua_marcando_o_envio():
    banco = _entregar("imovel")
    assert banco.marcados == [(1, [("zap", "9")], "entregue")]
    assert banco.lembrados == []
