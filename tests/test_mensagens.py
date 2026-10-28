from dataclasses import replace
from datetime import datetime

import pytest

from apebot.mensagens import (
    COMANDOS,
    TEXTO_PAUSADO,
    TEXTO_RETOMADO,
    aviso_falha,
    aviso_recuperacao,
    aviso_sem_credito,
    botoes_imovel,
    confirmacao_start,
    formatar_reais,
    mensagem_imovel,
    proxima_rodada,
    resposta_padrao,
    texto_ajuda,
    texto_filtros,
    texto_status,
)
from apebot.modelos import FUSO, Anuncio, Contato, Filtro, Pessoa, Tipo

PESSOA = Pessoa(
    chat_id=1,
    nome="Heitor",
    filtro=Filtro(
        bairros=frozenset({"buritis", "santa-monica"}),
        aluguel_max_centavos=300_000,
        quartos_min=2,
        tipos=frozenset({Tipo.APARTAMENTO, Tipo.CASA_CONDOMINIO}),
    ),
)


def test_formatar_reais():
    assert formatar_reais(270_000) == "R$ 2.700,00"
    assert formatar_reais(1_250_050) == "R$ 12.500,50"
    assert formatar_reais(245_050) == "R$ 2.450,50"
    assert formatar_reais(90_000) == "R$ 900,00"
    assert formatar_reais(99) == "R$ 0,99"


def test_confirmacao_start():
    texto = confirmacao_start(PESSOA)
    assert texto.startswith(
        "Pronto, Heitor! Vou te avisar de imóveis novos às 06, 09, 12, 15, 18, 21 e 23h."
    )
    assert "Seus filtros: Buritis, Santa Mônica · até R$ 3.000,00 · 2+ quartos" in texto
    assert "Apartamento" in texto and "Casa em condomínio" in texto


ANUNCIO = Anuncio(
    fonte="quintoandar",
    id_externo="1",
    tipo=Tipo.APARTAMENTO,
    bairro="Buritis",
    bairro_slug="buritis",
    quartos=2,
    area_m2=70,
    aluguel_centavos=270_000,
    total_centavos=346_800,
    url="https://www.quintoandar.com.br/imovel/1",
)


def test_mensagem_imovel():
    assert mensagem_imovel(ANUNCIO) == (
        "Veja o imóvel que encontrei:\n"
        "2 quartos no bairro Buritis\n"
        "Valor: R$ 2.700,00\n"
        "Link: https://www.quintoandar.com.br/imovel/1"
    )


def test_mensagem_imovel_bairro_do_catalogo_e_singular():
    um_quarto = replace(ANUNCIO, quartos=1, bairro="alto caicaras", bairro_slug="alto-caicaras")
    assert "1 quarto no bairro Alto Caiçaras\n" in mensagem_imovel(um_quarto)
    kitnet = replace(ANUNCIO, tipo=Tipo.KITNET, quartos=0, aluguel_centavos=245_050)
    texto = mensagem_imovel(kitnet)
    assert "Kitnet/Studio no bairro Buritis\n" in texto
    assert "Valor: R$ 2.450,50" in texto


ZAP = replace(
    ANUNCIO,
    fonte="zap",
    id_externo="2919519749",
    bairro="Gutierrez",
    bairro_slug="gutierrez",
    url="https://www.zapimoveis.com.br/imovel/aluguel-id-2919519749/",
)
CONTATO = Contato(
    nome="Imobiliária <Teste> & Cia",
    telefone="(31) 98298-4510",
    whatsapp_url="https://wa.me/5531982984510",
)


def test_mensagem_imovel_com_contato():
    assert mensagem_imovel(ZAP, CONTATO) == (
        "Veja o imóvel que encontrei:\n"
        "2 quartos no bairro Gutierrez\n"
        "Valor: R$ 2.700,00\n"
        f"Link: {ZAP.url}\n"
        "👤 Imobiliária &lt;Teste&gt; &amp; Cia\n"
        "📞 (31) 98298-4510"
    )


def test_mensagem_imovel_com_contato_parcial():
    texto = mensagem_imovel(ZAP, Contato(nome=None, telefone="3100000000", whatsapp_url=None))
    assert "👤" not in texto
    assert texto.endswith("📞 3100000000")


FAVORITO = {"t": "⭐ Salvar como favorito", "c": "f:zap:2919519749"}


def test_botoes_imovel():
    abrir = {"t": "Abrir anúncio", "u": ZAP.url}
    assert botoes_imovel(ZAP) == [[abrir], [FAVORITO]]
    assert botoes_imovel(ZAP, CONTATO) == [
        [abrir, {"t": "WhatsApp", "u": "https://wa.me/5531982984510"}],
        [FAVORITO],
    ]
    sem_whats = Contato(nome="X", telefone="31982984510", whatsapp_url=None)
    assert botoes_imovel(ZAP, sem_whats) == [[abrir], [FAVORITO]]


def test_callback_de_favorito_cabe_no_limite_do_telegram():
    maior = replace(ZAP, fonte="quintoandar", id_externo="x" * 40)
    (favorito,) = botoes_imovel(maior)[-1]
    assert len(favorito["c"].encode()) <= 64


def test_resposta_padrao():
    assert resposta_padrao() == (
        "Eu aviso os imóveis às 06, 09, 12, 15, 18, 21 e 23h. Envie /ajuda para ver os comandos."
    )


def test_aviso_falha():
    assert aviso_falha("zap", 3, "HTTP 503") == (
        "⚠️ ape-bot: Zap com falha em 3 rodadas seguidas. Último erro: HTTP 503"
    )


def test_aviso_sem_credito():
    assert aviso_sem_credito() == (
        "💳 ape-bot: a GeckoAPI recusou por falta de créditos. "
        "Zap/OLX parados até reiniciar o robô."
    )


def test_aviso_recuperacao():
    from datetime import datetime

    quando = datetime(2026, 10, 28, 12, 0, 5)
    assert aviso_recuperacao("quintoandar", quando) == (
        "✅ ape-bot: QuintoAndar voltou a funcionar (28/10/2026 12:00)."
    )


def test_comandos_do_menu():
    assert [c for c, _ in COMANDOS] == ["ajuda", "filtros", "status", "pausar", "retomar"]
    assert all(descricao for _, descricao in COMANDOS)


def test_texto_ajuda_lista_so_portais_ligados():
    texto = texto_ajuda(["quintoandar", "zap"])
    assert "Portais: QuintoAndar, Zap" in texto
    assert "OLX" not in texto
    for comando in ("/filtros", "/status", "/pausar", "/retomar"):
        assert comando in texto
    assert "06, 09, 12, 15, 18, 21 e 23h" in texto


def test_texto_filtros_ativo_e_pausado():
    ativo = texto_filtros(PESSOA, None, "Heitor")
    assert ativo.startswith("Seus filtros: Buritis, Santa Mônica · até R$ 3.000,00 · 2+ quartos")
    assert "Avisos: ativos" in ativo
    assert ativo.endswith("Para mudar os filtros, fale com Heitor.")
    pausado = texto_filtros(PESSOA, datetime(2026, 10, 28, 15, 30), "Heitor")  # UTC no banco
    assert "Avisos: pausados desde 28/10 12:30" in pausado


def test_confirmacao_start_pausada():
    texto = confirmacao_start(PESSOA, pausada=True)
    assert texto.endswith("Seus avisos estão pausados. Use /retomar para voltar.")
    assert "pausados" not in confirmacao_start(PESSOA)


def test_textos_de_pausa():
    assert TEXTO_PAUSADO == "⏸️ Avisos pausados. Use /retomar quando quiser voltar."
    assert TEXTO_RETOMADO == (
        "▶️ Avisos retomados. Na próxima rodada eu volto a te mandar o que encontrar."
    )


@pytest.mark.parametrize(
    ("agora", "esperado"),
    [
        (datetime(2026, 10, 28, 10, 0, tzinfo=FUSO), datetime(2026, 10, 28, 12, 0, tzinfo=FUSO)),
        (datetime(2026, 10, 28, 12, 0, tzinfo=FUSO), datetime(2026, 10, 28, 15, 0, tzinfo=FUSO)),
        (datetime(2026, 10, 28, 23, 30, tzinfo=FUSO), datetime(2026, 10, 29, 6, 0, tzinfo=FUSO)),
        (datetime(2026, 10, 28, 2, 0, tzinfo=FUSO), datetime(2026, 10, 28, 6, 0, tzinfo=FUSO)),
    ],
)
def test_proxima_rodada(agora, esperado):
    assert proxima_rodada(agora) == esperado


ESTADOS = {
    "quintoandar": ("ok", None),
    "zap": ("falha", "HTTP 503 <servidor>"),
}


def test_texto_status_pessoa():
    texto = texto_status(
        datetime(2026, 10, 28, 15, 0),  # UTC → 12:00 em São Paulo
        datetime(2026, 10, 28, 15, 0, tzinfo=FUSO),
        4,
        ESTADOS,
        ["quintoandar", "zap"],
    )
    assert texto.splitlines() == [
        "📊 Última rodada: 28/10 12:00 · próxima: 15:00",
        "Você recebeu 4 imóveis nas últimas 24 h.",
        "QuintoAndar: ✅ ok",
        "Zap: ⚠️ falha (HTTP 503 &lt;servidor&gt;)",
        "OLX: ⏹️ desligado",
    ]


def test_texto_status_operador_e_estados_especiais():
    texto = texto_status(
        None,
        datetime(2026, 10, 28, 15, 0, tzinfo=FUSO),
        0,
        {"zap": ("sem_credito", "sem crédito")},
        ["quintoandar", "zap"],
        creditos={"currentCredits": 94, "creditsConsumed": {"last24Hours": 6}},
    )
    linhas = texto.splitlines()
    assert linhas[0] == "📊 Ainda não houve rodada. Próxima: 15:00"
    assert "QuintoAndar: ⏳ aguardando a primeira rodada" in linhas
    assert "Zap: 💳 sem crédito" in linhas
    assert linhas[-1] == "💳 Créditos: 94 (gastos em 24 h: 6)"
    assert texto_status(
        None, datetime(2026, 10, 28, 15, 0, tzinfo=FUSO), 0, {}, [], creditos="erro"
    ).endswith("💳 Créditos: saldo indisponível")
