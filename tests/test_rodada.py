import asyncio
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from apebot.config import Configuracao, bairros_validos
from apebot.fontes.resultado import ResultadoFonte
from apebot.fontes.zap import extrair_zap
from apebot.modelos import FUSO, Filtro, Pessoa, Tipo
from apebot.rodada import (
    Coletor,
    Rodada,
    decidir_alerta,
    enviar_resumos,
    rodada_devida,
    status_rodada,
)
from tests.test_despacho import FilaPessoaFalsa


@pytest.mark.parametrize(
    ("ok", "erro", "formato", "esperado"),
    [
        (10, 0, False, "ok"),
        (6, 4, False, "ok"),
        (5, 5, False, "falha"),
        (0, 3, False, "falha"),
        (9, 1, True, "falha"),
        (0, 0, False, "ok"),
    ],
)
def test_status_rodada(ok, erro, formato, esperado):
    assert status_rodada(ok, erro, formato) == esperado


AGORA = datetime(2026, 10, 28, 12, 0)


@pytest.mark.parametrize(
    ("status", "seguidas", "aberto_em", "esperado"),
    [
        ("falha", 3, None, "abrir"),
        ("falha", 2, None, "nada"),
        ("falha", 5, AGORA - timedelta(hours=25), "reavisar"),
        ("falha", 5, AGORA - timedelta(hours=2), "nada"),
        ("ok", 0, AGORA - timedelta(hours=2), "recuperar"),
        ("ok", 0, None, "nada"),
        ("desligada", 0, None, "nada"),
        ("desligada", 0, AGORA - timedelta(hours=30), "nada"),
        ("sem_credito", 0, None, "nada"),
    ],
)
def test_decidir_alerta(status, seguidas, aberto_em, esperado):
    assert decidir_alerta(status, seguidas, aberto_em, AGORA) == esperado


def _sp(dia: int, hora: int, minuto: int = 0, segundo: int = 0) -> datetime:
    return datetime(2026, 10, dia, hora, minuto, segundo, tzinfo=FUSO)


@pytest.mark.parametrize(
    ("momento", "ultima_iniciada", "esperado"),
    [
        # PC acordou às 08:09; última rodada à 00:32 (03:32 UTC)
        (_sp(28, 8, 9), datetime(2026, 10, 28, 3, 32), _sp(28, 6)),
        (_sp(28, 9, 0, 30), datetime(2026, 10, 28, 9, 1), _sp(28, 9)),
        (_sp(28, 9, 30), datetime(2026, 10, 28, 12, 0), None),
        # 23h de ontem passou da janela: espera a das 06h
        (_sp(28, 5), datetime(2026, 10, 28, 0, 0), None),
        (_sp(28, 23, 30), datetime(2026, 10, 29, 0, 5), _sp(28, 23)),
        # virada do dia: às 00:30 a devida ainda é a das 23h de ontem
        (_sp(29, 0, 30), datetime(2026, 10, 29, 0, 5), _sp(28, 23)),
        (_sp(28, 10), None, _sp(28, 9)),
        (_sp(28, 11, 10), None, _sp(28, 9)),
        (_sp(28, 4), None, None),
    ],
)
def test_rodada_devida(momento, ultima_iniciada, esperado):
    assert rodada_devida(momento, ultima_iniciada) == esperado


# --- rodada com várias fontes (banco e fila falsos, sem rede) ---

PESSOA = Pessoa(
    chat_id=10,
    nome="Familiar",
    filtro=Filtro(
        bairros=frozenset({"gutierrez", "buritis", "funcionarios"}),
        aluguel_max_centavos=1_200_000,
        quartos_min=2,
        tipos=frozenset({Tipo.APARTAMENTO, Tipo.CASA}),
    ),
)
ZAP_FIXTURE = Path(__file__).parent / "fixtures" / "geckoapi" / "zap-plp-aluguel-bh.json"


class BancoFalso:
    def __init__(self):
        self.gravado = []
        self.fontes = []
        self.envios = set()

    def iniciar_rodada(self):
        return 1

    def finalizar_rodada(self, *args):
        self.gravado.append(("rodada", args))

    def pessoas_ativas(self, autorizados):
        return [PESSOA]

    def registrar_fonte(self, rodada_id, resultado):
        self.fontes.append((resultado.fonte, resultado.status))

    def salvar_anuncios(self, anuncios):
        self.gravado.append(("anuncios", [asdict(a) | {"tipo": a.tipo.value} for a in anuncios]))
        return len(anuncios)

    def ja_enviados(self, chat_id):
        return set(self.envios)

    def criar_envios_pendentes(self, chat_id, chaves):
        novas = [c for c in chaves if c not in self.envios]
        self.envios.update(novas)
        return novas

    def alerta_aberto(self, fonte):
        return None

    def seguidas_com_falha(self, fonte):
        return 0


class FilaFalsa:
    def __init__(self):
        self.mensagens = []

    async def enfileirar(self, mensagem):
        self.mensagens.append(mensagem)


def _rodar(coletores, banco=None, fila_pessoa=None):
    banco, fila = banco or BancoFalso(), FilaFalsa()
    fila_pessoa = fila_pessoa or FilaPessoaFalsa()
    config = Configuracao(operador_chat_id=PESSOA.chat_id, autorizados={PESSOA.chat_id: None})
    status = asyncio.run(Rodada(banco, fila, fila_pessoa, config, coletores).executar())
    return status, banco, fila, fila_pessoa


async def _quintoandar_vazio(pessoas):
    return ResultadoFonte(fonte="quintoandar", consultas=2)


async def _zap_da_fixture(pessoas):
    resultado = extrair_zap(json.loads(ZAP_FIXTURE.read_text()), bairros_validos())
    resultado.consultas = 1
    return resultado


def test_rodada_coloca_cada_imovel_na_fila_da_pessoa_com_contato():
    status, banco, fila, fila_pessoa = _rodar(
        [Coletor("quintoandar", _quintoandar_vazio), Coletor("zap", _zap_da_fixture)]
    )

    assert status == "ok"
    assert banco.fontes == [("quintoandar", "ok"), ("zap", "ok")]
    assert [m for m in fila.mensagens if m.tipo in ("imovel", "resumo")] == []  # nada em bloco
    na_fila = fila_pessoa.itens[PESSOA.chat_id]
    assert len(na_fila) == 3  # Gutierrez, Funcionários (casa) e Buritis
    contatos = [c for _, c in na_fila.values() if c is not None]
    assert any(c.nome == "Imobiliária Fictícia" for c in contatos)
    gravado = json.dumps(banco.gravado, ensure_ascii=False, default=str)
    assert "Imobiliária Fictícia" not in gravado and "3100000000" not in gravado


def test_imovel_ja_decidido_nao_volta_para_a_fila():
    banco = BancoFalso()
    _rodar([Coletor("zap", _zap_da_fixture)], banco=banco)
    fila_pessoa = FilaPessoaFalsa()
    _rodar([Coletor("zap", _zap_da_fixture)], banco=banco, fila_pessoa=fila_pessoa)
    assert fila_pessoa.itens == {}


def test_rodada_com_falha_tambem_enfileira():
    async def quintoandar_falhou(pessoas):
        return ResultadoFonte(fonte="quintoandar", status="falha", consultas=2, erro="acesso")

    status, _, _, fila_pessoa = _rodar(
        [Coletor("quintoandar", quintoandar_falhou), Coletor("zap", _zap_da_fixture)]
    )
    assert status == "falha"
    assert len(fila_pessoa.itens[PESSOA.chat_id]) == 3


async def _zap_quebrado(pessoas):
    raise RuntimeError("bug no parse")


def test_falha_do_zap_nao_derruba_o_quintoandar():
    status, banco, _, _ = _rodar(
        [Coletor("quintoandar", _quintoandar_vazio), Coletor("zap", _zap_quebrado)]
    )
    assert status == "ok"  # o status da rodada vem do QuintoAndar
    assert banco.fontes == [("quintoandar", "ok"), ("zap", "falha")]


async def _zap_sem_credito(pessoas):
    return ResultadoFonte(fonte="zap", status="sem_credito", aviso_operador="💳 sem crédito")


def test_sem_credito_avisa_o_operador_na_hora():
    _, banco, fila, _ = _rodar(
        [Coletor("quintoandar", _quintoandar_vazio), Coletor("zap", _zap_sem_credito)]
    )
    operador = [m for m in fila.mensagens if m.tipo == "operador"]
    assert [m.texto for m in operador] == ["💳 sem crédito"]
    assert Counter(s for _, s in banco.fontes) == {"ok": 1, "sem_credito": 1}


# --- resumo diário (US4) ---


class BancoResumo:
    def __init__(self, pessoas, ja_enviado=()):
        self.pessoas = pessoas
        self.registrados = []
        self.ja_enviado = set(ja_enviado)

    def pessoas_ativas(self, autorizados):
        return [p for p in self.pessoas if p.chat_id in autorizados]

    def registrar_resumo(self, chat_id, dia):
        self.registrados.append((chat_id, dia))
        return chat_id not in self.ja_enviado

    def recebidos_por_fonte_24h(self, chat_id):
        return {"quintoandar": 5, "zap": 2}

    def ultima_rodada(self):
        return datetime(2026, 10, 29, 2, 0)


class GeckoFalso:
    def __init__(self):
        self.chamadas = 0

    async def creditos(self):
        self.chamadas += 1
        return {"currentCredits": 94, "creditsConsumed": {"last24Hours": 7}}


OUTRA = Pessoa(chat_id=20, nome="Outra", filtro=PESSOA.filtro)
AS_23H30 = datetime(2026, 10, 29, 2, 30, tzinfo=UTC)  # 23:30 de 28/10 em São Paulo


def _resumos(banco, gecko, autorizados=(PESSOA.chat_id, OUTRA.chat_id)):
    fila = FilaFalsa()
    asyncio.run(enviar_resumos(banco, fila, gecko, set(autorizados), AS_23H30))
    return fila.mensagens


def test_resumo_para_cada_pessoa_ativa_com_uma_consulta_de_creditos():
    banco, gecko = BancoResumo([PESSOA, OUTRA]), GeckoFalso()
    mensagens = _resumos(banco, gecko)
    assert [m.chat_id for m in mensagens] == [PESSOA.chat_id, OUTRA.chat_id]
    assert all(m.tipo == "resumo" for m in mensagens)
    assert gecko.chamadas == 1
    assert "💳 Créditos: 94 (gastos em 24 h: 7)" in mensagens[0].texto
    assert banco.registrados[0] == (PESSOA.chat_id, date(2026, 10, 28))  # dia de São Paulo


def test_resumo_so_uma_vez_por_dia_e_so_para_ativas():
    banco = BancoResumo([PESSOA, OUTRA], ja_enviado={OUTRA.chat_id})
    mensagens = _resumos(banco, GeckoFalso(), autorizados=[PESSOA.chat_id, OUTRA.chat_id, 99])
    assert [m.chat_id for m in mensagens] == [PESSOA.chat_id]


def test_resumo_sem_geckoapi_omite_creditos():
    (mensagem,) = _resumos(BancoResumo([PESSOA]), None)
    assert "💳" not in mensagem.texto
