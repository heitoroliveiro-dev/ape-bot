from dataclasses import replace

from apebot.mensagens import (
    aviso_falha,
    aviso_recuperacao,
    confirmacao_start,
    formatar_reais,
    mensagem_imovel,
    mensagens_resumo,
    resposta_padrao,
)
from apebot.modelos import Anuncio, Filtro, Pessoa, Tipo

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
    assert formatar_reais(270_000) == "R$ 2.700"
    assert formatar_reais(1_250_050) == "R$ 12.500"
    assert formatar_reais(90_000) == "R$ 900"


def test_confirmacao_start():
    texto = confirmacao_start(PESSOA)
    assert texto.startswith(
        "Pronto, Heitor! Vou te avisar de imóveis novos às 06, 09, 12, 15, 18, 21 e 23h."
    )
    assert "Seus filtros: Buritis, Santa Monica · até R$ 3.000 · 2+ quartos" in texto
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
        "🏠 Apartamento · Buritis\n"
        "2 quartos · 70 m²\n"
        "Aluguel: R$ 2.700 · Total: R$ 3.468\n"
        "https://www.quintoandar.com.br/imovel/1"
    )


def test_mensagem_imovel_com_campos_ausentes():
    texto = mensagem_imovel(replace(ANUNCIO, area_m2=None, total_centavos=None))
    assert "2 quartos · não informado" in texto
    assert "Total: não informado" in texto


def test_resposta_padrao():
    assert resposta_padrao() == ("Eu aviso os imóveis nos horários 06, 09, 12, 15, 18, 21 e 23h.")


def _anuncios(n):
    return [
        replace(
            ANUNCIO, id_externo=str(i), url=f"https://www.quintoandar.com.br/imovel/{900000000 + i}"
        )
        for i in range(n)
    ]


def test_resumo_sem_resultados():
    assert mensagens_resumo([]) == [
        "Ainda não achei imóveis com os seus filtros. Continuo procurando."
    ]


def test_resumo_com_40_imoveis():
    partes = mensagens_resumo(_anuncios(40))
    texto = "\n".join(partes)
    assert partes[0].startswith("Encontrei 40 imóveis com os seus filtros:")
    assert texto.count("\n• ") + texto.count("• ") >= 40
    assert texto.count("Buritis · 2q · R$ 2.700 · https://www.quintoandar.com.br/imovel/") == 40
    assert "(+" not in texto


def test_resumo_grande_limitado_a_5_partes():
    partes = mensagens_resumo(_anuncios(200))
    assert 1 <= len(partes) <= 5
    assert all(len(p) <= 4000 for p in partes)
    linhas = "\n".join(partes).count("• ")
    if linhas < 200:
        assert partes[-1].rstrip().endswith(f"(+{200 - linhas} imóveis)")


def test_resumo_enorme_corta_com_contagem():
    partes = mensagens_resumo(_anuncios(1000))
    assert len(partes) == 5
    assert all(len(p) <= 4000 for p in partes)
    linhas = "\n".join(partes).count("• ")
    assert partes[-1].rstrip().endswith(f"(+{1000 - linhas} imóveis)")


def test_aviso_falha():
    assert aviso_falha(3, "acesso: HTTP 503") == (
        "⚠️ ape-bot: 3 rodadas seguidas com falha. Último erro: acesso: HTTP 503"
    )


def test_aviso_recuperacao():
    from datetime import datetime

    quando = datetime(2026, 10, 28, 12, 0, 5)
    assert aviso_recuperacao(quando) == "✅ ape-bot voltou a funcionar (28/10/2026 12:00)."
