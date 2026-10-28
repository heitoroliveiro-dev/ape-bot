import pytest

from apebot.cadastro import (
    POR_PAGINA,
    Estado,
    iniciar_cadastro,
    iniciar_edicao,
    ler_valor,
    limpar_nome,
    processar,
    reapresentar,
)
from apebot.config import catalogo_bairros
from apebot.modelos import Filtro, Pessoa, Tipo

# --- valor máximo (research R7) ---


@pytest.mark.parametrize(
    ("texto", "centavos"),
    [
        ("3000", 300_000),
        ("3.000", 300_000),
        ("3.000,00", 300_000),
        ("R$ 3.000", 300_000),
        ("r$3000", 300_000),
        ("  R$  3.000,00  ", 300_000),
        ("3000,50", 300_050),
        ("3000,5", 300_050),
        ("3000,05", 300_005),
        ("12.500", 1_250_000),
        ("300", 30_000),
        ("50.000", 5_000_000),
    ],
)
def test_ler_valor_aceita(texto, centavos):
    assert ler_valor(texto) == centavos


@pytest.mark.parametrize(
    "texto",
    [
        "3k",
        "três mil",
        "-3000",
        "0",
        "3000.50",
        "3 000",
        "3.00",
        "30.00,0",
        "100",
        "999999",
        "",
        "R$",
        "3000,505",
        "50.000,01",
        "3,000",
        "1.0000",
    ],
)
def test_ler_valor_recusa(texto):
    assert ler_valor(texto) is None


# --- edição de filtros (research R6) ---

FILTRO = Filtro(
    bairros=frozenset({"prado", "barroca"}),
    aluguel_max_centavos=300_000,
    quartos_min=2,
    tipos=frozenset({Tipo.APARTAMENTO}),
)
PESSOA = Pessoa(chat_id=1, nome="Heitor", filtro=FILTRO)
OESTE = 6  # índice de "Oeste" em REGIONAIS


def _dados(resposta) -> list[str]:
    return [b.dados for linha in resposta.teclado for b in linha]


def _rotulos(resposta) -> list[str]:
    return [b.texto for linha in resposta.teclado for b in linha]


def _clicar(resultado, dados):
    assert dados in _dados(resultado.resposta), f"{dados} não está no teclado"
    return processar(resultado.estado, dados=dados)


def _ate_valor(resultado):
    resultado = _clicar(resultado, "c:tipos:ok")
    resultado = _clicar(resultado, "c:quartos:q:2")
    return _clicar(resultado, "c:regionais:ok")


def test_edicao_comeca_nos_tipos_com_os_filtros_atuais():
    r = iniciar_edicao(PESSOA)
    assert r.estado.modo == "edicao" and r.estado.etapa == "tipos"
    assert r.estado.rascunho["nome"] == "Heitor"
    assert r.resposta.texto.startswith("Você busca quais tipos de imóveis?")
    assert "✅ Apartamento" in _rotulos(r.resposta)
    assert "Casa" in _rotulos(r.resposta)
    assert "c:tipos:cancelar" in _dados(r.resposta)


def test_tipos_alterna_e_exige_um():
    r = iniciar_edicao(PESSOA)
    r = _clicar(r, "c:tipos:t:apartamento")
    assert r.estado.etapa == "tipos" and r.resposta.editar
    assert "Apartamento" in _rotulos(r.resposta)
    r = _clicar(r, "c:tipos:ok")
    assert r.estado.etapa == "tipos"
    assert r.resposta.aviso == "Marque pelo menos um tipo."
    r = _clicar(r, "c:tipos:t:casa")
    r = _clicar(r, "c:tipos:ok")
    assert r.estado.etapa == "quartos"
    assert r.estado.rascunho["tipos"] == ["casa"]


def test_quartos_marca_o_atual_e_avanca():
    r = _clicar(iniciar_edicao(PESSOA), "c:tipos:ok")
    assert r.resposta.texto == "Quantos quartos, no mínimo?"
    assert _rotulos(r.resposta)[:5] == ["Tanto faz", "1", "✅ 2", "3", "4 ou mais"]
    r = _clicar(r, "c:quartos:q:0")
    assert r.estado.etapa == "regionais"
    assert r.estado.rascunho["quartos"] == 0


def test_regionais_mostram_contagem_e_abrem_os_bairros():
    r = _clicar(_clicar(iniciar_edicao(PESSOA), "c:tipos:ok"), "c:quartos:q:2")
    assert "Você já marcou 2 bairros." in r.resposta.texto
    assert "Oeste (2)" in _rotulos(r.resposta)
    r = _clicar(r, f"c:regionais:r:{OESTE}")
    assert r.estado.etapa == "bairros"
    assert r.resposta.texto.startswith("Oeste: toque para marcar ou desmarcar. Página 1/")
    assert "✅ Prado" in _rotulos(r.resposta) or "✅ Barroca" in _rotulos(r.resposta)


def test_bairros_pagina_marca_todos_e_volta():
    r = _clicar(_clicar(iniciar_edicao(PESSOA), "c:tipos:ok"), "c:quartos:q:2")
    r = _clicar(r, "c:regionais:r:3")  # Nordeste: 38 bairros, 2 páginas
    nordeste = [b.slug for b in catalogo_bairros() if b.regional == "Nordeste"]
    assert len(nordeste) > POR_PAGINA
    bairros_pagina_1 = [d for d in _dados(r.resposta) if d.startswith("c:bairros:t:")]
    assert len(bairros_pagina_1) == POR_PAGINA
    r = _clicar(r, "c:bairros:p:1")
    assert "Página 2/2" in r.resposta.texto
    assert "c:bairros:p:0" in _dados(r.resposta)
    r = _clicar(r, "c:bairros:todos")
    assert set(nordeste) <= set(r.estado.rascunho["bairros"])
    assert "Desmarcar todos" in _rotulos(r.resposta)
    r = _clicar(r, "c:bairros:nenhum")
    assert not set(nordeste) & set(r.estado.rascunho["bairros"])
    r = _clicar(r, "c:bairros:volta")
    assert r.estado.etapa == "regionais"


def test_bairro_alterna():
    r = _clicar(_clicar(iniciar_edicao(PESSOA), "c:tipos:ok"), "c:quartos:q:2")
    r = _clicar(r, f"c:regionais:r:{OESTE}")
    r = _clicar(r, "c:bairros:t:barroca")  # Prado fica na página 2 do Oeste
    assert "barroca" not in r.estado.rascunho["bairros"]
    r = _clicar(r, "c:bairros:t:barroca")
    assert "barroca" in r.estado.rascunho["bairros"]


def test_continuar_sem_bairro_avisa():
    r = _clicar(_clicar(iniciar_edicao(PESSOA), "c:tipos:ok"), "c:quartos:q:2")
    r = _clicar(r, f"c:regionais:r:{OESTE}")
    r = _clicar(r, "c:bairros:nenhum")
    r = _clicar(r, "c:bairros:volta")
    r = _clicar(r, "c:regionais:ok")
    assert r.estado.etapa == "regionais"
    assert r.resposta.aviso == "Marque pelo menos um bairro."


def test_valor_invalido_repete_e_manter_usa_o_atual():
    r = _ate_valor(iniciar_edicao(PESSOA))
    assert r.estado.etapa == "valor"
    assert "Atual: R$ 3.000,00" in r.resposta.texto
    r = processar(r.estado, texto="3k")
    assert r.estado.etapa == "valor"
    assert r.resposta.texto.startswith("Não entendi esse valor.")
    r = _clicar(r, "c:valor:manter")
    assert r.estado.etapa == "revisao"
    assert r.resposta.texto.startswith("Confere?")
    assert "Valores até R$ 3.000,00" in r.resposta.texto


def test_salvar_devolve_o_filtro_novo():
    r = _ate_valor(iniciar_edicao(PESSOA))
    r = processar(r.estado, texto="R$ 2.500,00")
    assert "Valores até R$ 2.500,00" in r.resposta.texto
    r = _clicar(r, "c:revisao:salvar")
    assert r.acao == "gravar" and r.estado is None
    assert r.nome == "Heitor"
    assert r.filtro == Filtro(
        bairros=FILTRO.bairros,
        aluguel_max_centavos=250_000,
        quartos_min=2,
        tipos=FILTRO.tipos,
    )


@pytest.mark.parametrize("etapa", ["tipos", "quartos", "regionais", "bairros", "valor", "revisao"])
def test_cancelar_em_qualquer_etapa(etapa):
    r = iniciar_edicao(PESSOA)
    estado = Estado(r.estado.modo, etapa, r.estado.rascunho | {"regional": OESTE, "pagina": 0})
    r = processar(estado, dados=f"c:{etapa}:cancelar")
    assert r.acao == "cancelar" and r.estado is None
    assert r.resposta.texto == "Edição cancelada. Seus filtros continuam os mesmos."


def test_texto_numa_etapa_de_botoes():
    r = iniciar_edicao(PESSOA)
    r = processar(r.estado, texto="apartamento")
    assert r.estado.etapa == "tipos"
    assert r.resposta.texto.startswith("Use os botões para responder. 👇")
    assert not r.resposta.editar


def test_botao_de_etapa_que_ja_passou():
    r = _clicar(iniciar_edicao(PESSOA), "c:tipos:ok")
    antes = r.estado
    r = processar(antes, dados="c:tipos:t:casa")
    assert r.estado == antes
    assert r.resposta.aviso == "Essa pergunta já passou."
    assert r.resposta.texto is None


def test_callback_data_cabe_no_limite_do_telegram():
    r = _clicar(_clicar(iniciar_edicao(PESSOA), "c:tipos:ok"), "c:quartos:q:2")
    dados = list(_dados(r.resposta))
    for indice in range(10):
        dados += _dados(processar(r.estado, dados=f"c:regionais:r:{indice}").resposta)
    assert max(len(d.encode()) for d in dados) <= 64


# --- nome (research R8) ---


@pytest.mark.parametrize(
    ("texto", "nome"),
    [
        ("  maria   clara ", "Maria Clara"),
        ("joão da silva", "João da Silva"),
        ("Ana & <Bia>", "Ana Bia"),
        ("ANA", "Ana"),
        ("José 🙂", "José"),
        ("Ana\x00\nBia", "Ana Bia"),
    ],
)
def test_limpar_nome(texto, nome):
    assert limpar_nome(texto) == nome


@pytest.mark.parametrize("texto", ["🙂🙂", "", "   ", "123", "<>&"])
def test_limpar_nome_recusa(texto):
    assert limpar_nome(texto) is None


def test_limpar_nome_corta_em_40():
    assert len(limpar_nome("a" * 60)) == 40


# --- cadastro (US3) ---


def _cadastro_ate_valor():
    r = iniciar_cadastro()
    r = processar(r.estado, texto="  maria   clara ")
    r = _clicar(r, "c:tipos:t:apartamento")
    r = _clicar(r, "c:tipos:ok")
    r = _clicar(r, "c:quartos:q:2")
    r = _clicar(r, f"c:regionais:r:{OESTE}")
    r = _clicar(r, "c:bairros:t:barroca")
    r = _clicar(r, "c:bairros:volta")
    return _clicar(r, "c:regionais:ok")


def test_cadastro_comeca_pelo_nome():
    r = iniciar_cadastro()
    assert r.estado.modo == "cadastro" and r.estado.etapa == "nome"
    assert r.resposta.texto == (
        "Oi! Eu procuro imóveis para alugar em BH e te aviso por aqui. Como devo te chamar?"
    )


def test_cadastro_nome_invalido_repete():
    r = processar(iniciar_cadastro().estado, texto="🙂")
    assert r.estado.etapa == "nome"
    assert r.resposta.texto == "Me diga um nome com letras, de até 40 caracteres."


def test_cadastro_sem_cancelar_e_grava_no_valor():
    r = processar(iniciar_cadastro().estado, texto="maria clara")
    assert r.estado.etapa == "tipos"
    assert not [d for d in _dados(r.resposta) if d.endswith(":cancelar")]
    r = _cadastro_ate_valor()
    assert "Manter" not in _rotulos(r.resposta)
    r = processar(r.estado, texto="2.500")
    assert r.acao == "gravar" and r.estado is None
    assert r.nome == "Maria Clara"
    assert r.filtro == Filtro(
        bairros=frozenset({"barroca"}),
        aluguel_max_centavos=250_000,
        quartos_min=2,
        tipos=frozenset({Tipo.APARTAMENTO}),
    )


def test_reapresentar_retoma_a_etapa_com_o_rascunho():
    r = _cadastro_ate_valor()
    retomada = reapresentar(r.estado)
    assert retomada.texto == r.resposta.texto
    r = processar(iniciar_cadastro().estado, texto="Maria")
    r = _clicar(r, "c:tipos:t:casa")
    assert "✅ Casa" in _rotulos(reapresentar(r.estado))
