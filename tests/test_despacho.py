import asyncio
import random
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from apebot.modelos import FUSO, Anuncio, Contato, Filtro, Pessoa, Tipo
from apebot.telegram_bot import (
    Despachante,
    dentro_da_janela,
    faltando_na_fila,
    sortear_intervalo,
)


def _sp(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 10, 28, hora, minuto, tzinfo=FUSO)


@pytest.mark.parametrize(
    ("momento", "esperado"),
    [
        (_sp(7, 59), False),
        (_sp(8, 0), True),
        (_sp(13, 30), True),
        (_sp(21, 59), True),
        (_sp(22, 0), False),
        (_sp(23, 30), False),
        (datetime(2026, 10, 28, 11, 0, tzinfo=UTC), True),  # 08:00 em São Paulo
        (datetime(2026, 10, 28, 10, 59, tzinfo=UTC), False),  # 07:59 em São Paulo
    ],
)
def test_dentro_da_janela(momento, esperado):
    assert dentro_da_janela(momento) is esperado


def test_sortear_intervalo_fica_na_faixa_e_varia():
    aleatorio = random.Random(1)
    sorteios = [sortear_intervalo((120, 300), aleatorio) for _ in range(50)]
    assert all(120 <= s <= 300 for s in sorteios)
    assert len(set(sorteios)) > 1


def test_faltando_na_fila():
    a, b, c, d = ("q", "1"), ("q", "2"), ("q", "3"), ("z", "4")
    assert faltando_na_fila({a, b, c, d}, na_fila={a}, em_entrega={b}) == {c, d}


# --- uma volta do despachante (fakes em memória, sem Redis nem MySQL) ---

FILTRO = Filtro(
    bairros=frozenset({"prado"}),
    aluguel_max_centavos=300_000,
    quartos_min=2,
    tipos=frozenset({Tipo.APARTAMENTO}),
)
ANA = Pessoa(chat_id=1, nome="Ana", filtro=FILTRO)
BIA = Pessoa(chat_id=2, nome="Bia", filtro=FILTRO)
BASE = Anuncio(
    fonte="quintoandar",
    id_externo="0",
    tipo=Tipo.APARTAMENTO,
    bairro="Prado",
    bairro_slug="prado",
    quartos=2,
    area_m2=None,
    aluguel_centavos=0,
    total_centavos=None,
    url="https://x/0",
)


def _anuncio(id_externo: str, aluguel: int) -> Anuncio:
    return replace(
        BASE, id_externo=id_externo, aluguel_centavos=aluguel, url=f"https://x/{id_externo}"
    )


class FilaPessoaFalsa:
    def __init__(self):
        self.itens: dict[int, dict] = {}
        self.proximos: dict[int, float] = {}

    async def adicionar(self, chat_id, anuncio, contato=None):
        fila = self.itens.setdefault(chat_id, {})
        if anuncio.chave in fila:
            return False
        fila[anuncio.chave] = (anuncio, contato)
        return True

    async def retirar_mais_barato(self, chat_id):
        fila = self.itens.get(chat_id) or {}
        if not fila:
            return None
        chave = min(fila, key=lambda k: (fila[k][0].aluguel_centavos, k))
        return fila.pop(chave)

    async def membros(self, chat_id):
        return set(self.itens.get(chat_id, {}))

    async def proximo(self, chat_id):
        return self.proximos.get(chat_id)

    async def marcar_proximo(self, chat_id, epoch):
        self.proximos[chat_id] = epoch


class FilaFalsa:
    def __init__(self, em_entrega=()):
        self.mensagens = []
        self.em_entrega = set(em_entrega)

    async def enfileirar(self, mensagem):
        self.mensagens.append(mensagem)

    async def chaves_em_entrega(self):
        return self.em_entrega


class BancoFalso:
    def __init__(self, pessoas, pendentes=None):
        self.pessoas = pessoas
        self.pendentes = pendentes or {}
        self.apagados = []

    def pessoas_ativas(self, autorizados):
        return [p for p in self.pessoas if p.chat_id in autorizados]

    def apagar_pendente(self, chat_id, chave):
        self.apagados.append((chat_id, chave))

    def pendentes_de(self, chat_id):
        return self.pendentes.get(chat_id, [])


def _despachante(pessoas, fila_pessoa, fila=None, banco=None, intervalo=(120, 300)):
    banco = banco or BancoFalso(pessoas)
    fila = fila or FilaFalsa()
    autorizados = {p.chat_id for p in pessoas}
    despachante = Despachante(fila, fila_pessoa, banco, autorizados, intervalo, random.Random(7))
    return despachante, fila, banco


def _encher(fila_pessoa, chat_id, *anuncios, contato=None):
    for anuncio in anuncios:
        asyncio.run(fila_pessoa.adicionar(chat_id, anuncio, contato))


def test_fora_da_janela_nao_despacha():
    fila_pessoa = FilaPessoaFalsa()
    _encher(fila_pessoa, 1, _anuncio("a", 250_000))
    despachante, fila, _ = _despachante([ANA], fila_pessoa)
    asyncio.run(despachante.uma_volta(_sp(22, 5)))
    assert fila.mensagens == []


def test_despacha_o_mais_barato_e_agenda_o_proximo():
    fila_pessoa = FilaPessoaFalsa()
    _encher(fila_pessoa, 1, _anuncio("a", 250_000), _anuncio("b", 180_000), _anuncio("c", 200_000))
    despachante, fila, _ = _despachante([ANA], fila_pessoa)
    agora = _sp(10)
    asyncio.run(despachante.uma_volta(agora))

    (mensagem,) = fila.mensagens
    assert mensagem.chat_id == 1 and mensagem.tipo == "imovel"
    assert mensagem.anuncio_ids == [("quintoandar", "b")]
    assert "Valor: R$ 1.800,00" in mensagem.texto
    espera = fila_pessoa.proximos[1] - agora.timestamp()
    assert 120 <= espera <= 300


def test_nao_despacha_antes_do_proximo():
    fila_pessoa = FilaPessoaFalsa()
    _encher(fila_pessoa, 1, _anuncio("a", 250_000), _anuncio("b", 180_000))
    despachante, fila, _ = _despachante([ANA], fila_pessoa)
    agora = _sp(10)
    asyncio.run(despachante.uma_volta(agora))
    asyncio.run(despachante.uma_volta(agora + timedelta(seconds=60)))
    assert len(fila.mensagens) == 1
    asyncio.run(despachante.uma_volta(agora + timedelta(seconds=301)))
    assert len(fila.mensagens) == 2


def test_imovel_fora_do_filtro_atual_e_descartado_e_o_proximo_sai():
    fora_do_bairro = replace(_anuncio("x", 100_000), bairro_slug="centro")
    acima_do_valor = _anuncio("y", 160_000)
    ok = _anuncio("ok", 150_000)
    fila_pessoa = FilaPessoaFalsa()
    _encher(fila_pessoa, 1, fora_do_bairro, ok, acima_do_valor)
    # a pessoa editou os filtros depois que esses imóveis entraram na fila dela
    editada = replace(ANA, filtro=replace(FILTRO, aluguel_max_centavos=150_000))
    despachante, fila, banco = _despachante([editada], fila_pessoa)
    asyncio.run(despachante.uma_volta(_sp(10)))

    assert banco.apagados == [(1, fora_do_bairro.chave)]
    assert [m.anuncio_ids for m in fila.mensagens] == [[ok.chave]]


def test_pessoas_despacham_de_forma_independente():
    fila_pessoa = FilaPessoaFalsa()
    _encher(fila_pessoa, 1, _anuncio("a", 200_000))
    _encher(fila_pessoa, 2, _anuncio("b", 210_000))
    fila_pessoa.proximos[1] = _sp(11).timestamp()  # Ana ainda espera
    despachante, fila, _ = _despachante([ANA, BIA], fila_pessoa)
    asyncio.run(despachante.uma_volta(_sp(10)))
    assert [m.chat_id for m in fila.mensagens] == [2]


def test_pessoa_inativa_nao_despacha():
    fila_pessoa = FilaPessoaFalsa()
    _encher(fila_pessoa, 1, _anuncio("a", 200_000))
    banco = BancoFalso([])  # pausada, sem cadastro ou removida do arquivo
    despachante, fila, _ = _despachante([ANA], fila_pessoa, banco=banco)
    asyncio.run(despachante.uma_volta(_sp(10)))
    assert fila.mensagens == []


def test_contato_em_transito_vai_na_mensagem():
    fila_pessoa = FilaPessoaFalsa()
    contato = Contato(nome="Imobiliária", telefone="31982984510", whatsapp_url="https://wa.me/55")
    _encher(fila_pessoa, 1, _anuncio("a", 200_000), contato=contato)
    despachante, fila, _ = _despachante([ANA], fila_pessoa)
    asyncio.run(despachante.uma_volta(_sp(10)))
    (mensagem,) = fila.mensagens
    assert "👤 Imobiliária" in mensagem.texto
    assert {"t": "WhatsApp", "u": "https://wa.me/55"} in mensagem.botoes[0]


def test_reconciliar_recoloca_so_o_que_sumiu():
    na_fila, em_entrega, sumido = _anuncio("a", 1), _anuncio("b", 2), _anuncio("c", 3)
    fila_pessoa = FilaPessoaFalsa()
    _encher(fila_pessoa, 1, na_fila)
    banco = BancoFalso([ANA], pendentes={1: [na_fila, em_entrega, sumido]})
    fila = FilaFalsa(em_entrega={(1, *em_entrega.chave)})
    despachante, _, _ = _despachante([ANA], fila_pessoa, fila=fila, banco=banco)
    asyncio.run(despachante.reconciliar())
    assert set(fila_pessoa.itens[1]) == {na_fila.chave, sumido.chave}
    assert fila_pessoa.itens[1][sumido.chave][1] is None  # do banco: sem contato
