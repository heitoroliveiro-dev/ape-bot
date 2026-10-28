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
    formatar_reais,
    mensagem_imovel,
    proxima_rodada,
    resposta_padrao,
    texto_ajuda,
    texto_favoritos,
    texto_filtros,
    texto_resumo,
    texto_status,
    trocar_botao_favorito,
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
    assert [c for c, _ in COMANDOS] == [
        "ajuda",
        "filtros",
        "favoritos",
        "status",
        "pausar",
        "retomar",
    ]
    assert dict(COMANDOS)["filtros"] == "Ver e editar meus filtros"
    assert dict(COMANDOS)["favoritos"] == "Imóveis que salvei"
    assert all(descricao for _, descricao in COMANDOS)


def test_texto_ajuda_lista_so_portais_ligados():
    texto = texto_ajuda(["quintoandar", "zap"])
    assert "Portais: QuintoAndar, Zap" in texto
    assert "OLX" not in texto
    for comando in ("/filtros", "/status", "/pausar", "/retomar"):
        assert comando in texto
    assert "06, 09, 12, 15, 18, 21 e 23h" in texto


def test_texto_filtros_ativo_e_pausado():
    ativo = texto_filtros(PESSOA, None)
    assert ativo == (
        "Seus filtros -\n"
        "Bairros: Buritis, Santa Mônica\n"
        "Valores até R$ 3.000,00\n"
        "Apartamento, Casa em condomínio com 2+ quartos\n"
        "Avisos: ativos"
    )
    assert "fale com" not in ativo
    pausado = texto_filtros(PESSOA, datetime(2026, 10, 28, 15, 30))  # UTC no banco
    assert pausado.endswith("Avisos: pausados desde 28/10 12:30")


def test_texto_filtros_sem_minimo_de_quartos():
    qualquer = replace(PESSOA, filtro=replace(PESSOA.filtro, quartos_min=0))
    assert "Casa em condomínio com qualquer número de quartos\n" in texto_filtros(qualquer, None)


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
        na_fila=12,
    )
    assert texto.splitlines() == [
        "📊 Última rodada: 28/10 12:00 · próxima: 15:00",
        "Você recebeu 4 imóveis nas últimas 24 h.",
        "Na sua fila: 12 imóveis (envio das 8h às 22h).",
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


def test_texto_status_singular():
    texto = texto_status(None, datetime(2026, 10, 28, 15, 0, tzinfo=FUSO), 1, {}, [], na_fila=1)
    assert "Você recebeu 1 imóvel nas últimas 24 h." in texto
    assert "Na sua fila: 1 imóvel (envio das 8h às 22h)." in texto


def test_texto_resumo():
    texto = texto_resumo(
        datetime(2026, 10, 29, 2, 0),  # UTC → 23:00 de 28/10 em São Paulo
        datetime(2026, 10, 29, 6, 0, tzinfo=FUSO),
        {"quintoandar": 5, "zap": 2},
        {"currentCredits": 94, "creditsConsumed": {"last24Hours": 7}},
    )
    assert texto.splitlines() == [
        "📊 Última rodada: 28/10 23:00 · próxima: 06:00",
        "Você recebeu 7 imóveis nas últimas 24 h.",
        "QuintoAndar: 5",
        "Zap: 2",
        "OLX: 0",
        "💳 Créditos: 94 (gastos em 24 h: 7)",
    ]


def test_texto_resumo_sem_creditos_e_singular():
    proxima = datetime(2026, 10, 29, 6, 0, tzinfo=FUSO)
    texto = texto_resumo(None, proxima, {"zap": 1}, None)
    assert "Você recebeu 1 imóvel nas últimas 24 h." in texto
    assert "💳" not in texto
    assert texto_resumo(None, proxima, {}, "erro").endswith("💳 Créditos: saldo indisponível")


def test_texto_favoritos_vazio():
    assert texto_favoritos([]) == [
        'Você ainda não tem favoritos. Toque em "⭐ Salvar como favorito" numa mensagem de imóvel.'
    ]


def test_texto_favoritos_lista_com_link():
    (texto,) = texto_favoritos([ZAP, ANUNCIO])
    assert texto == (
        "⭐ Seus favoritos (2):\n"
        f"⭐ 2 quartos · Gutierrez · R$ 2.700,00 · Zap\n{ZAP.url}\n"
        f"⭐ 2 quartos · Buritis · R$ 2.700,00 · QuintoAndar\n{ANUNCIO.url}"
    )


def test_texto_favoritos_longo_em_blocos_sem_cortar_item():
    muitos = [replace(ANUNCIO, id_externo=str(i), url=f"{ANUNCIO.url}{i:05d}") for i in range(120)]
    blocos = texto_favoritos(muitos)
    assert len(blocos) > 1
    assert all(len(b) <= 4000 for b in blocos)
    assert sum(b.count("⭐ 2 quartos") for b in blocos) == 120
    assert all(linha.startswith(("⭐", "https://")) for b in blocos for linha in b.splitlines())


def test_trocar_botao_favorito():
    linhas = botoes_imovel(ZAP, CONTATO)
    salvo = trocar_botao_favorito(linhas, salvo=True)
    assert salvo[0] == linhas[0]  # Abrir anúncio e WhatsApp continuam
    assert salvo[1] == [{"t": "✅ Favorito · toque para remover", "c": "f:zap:2919519749"}]
    assert trocar_botao_favorito(salvo, salvo=False) == linhas
