import asyncio
import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from apebot.fontes.geckoapi import (
    ClienteGecko,
    ErroGecko,
    RespostaInvalida,
    SemCredito,
    ler_resposta,
    sem_anunciante,
)

FIXTURES = Path(__file__).parent / "fixtures" / "geckoapi"


def _texto(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def _chaves(valor) -> set[str]:
    if isinstance(valor, dict):
        return set(valor) | set().union(*(_chaves(v) for v in valor.values()))
    if isinstance(valor, list):
        return set().union(*(_chaves(v) for v in valor)) if valor else set()
    return set()


def test_le_resposta_do_zap():
    resposta = ler_resposta(_texto("zap-plp-aluguel-bh.json"))

    assert resposta.fonte == "zapimoveis.com.br"
    assert resposta.request_id == "3136ff9f-c3fe-41cf-8bfc-bfd426c982a5"
    assert resposta.url.startswith(
        "https://www.zapimoveis.com.br/aluguel/imoveis/mg+belo-horizonte/"
    )
    assert resposta.total_resultados == 22060
    assert resposta.itens == 3
    assert resposta.extraida_em == datetime(2026, 10, 28, 2, 40, 11)


def test_resposta_do_zap_sai_sem_anunciante():
    bruto = json.loads(_texto("zap-plp-aluguel-bh.json"))
    assert "advertiser" in bruto["data"]["items"][0]

    corpo = ler_resposta(_texto("zap-plp-aluguel-bh.json")).corpo

    assert "advertiser" not in _chaves(corpo)
    assert "Imobiliária Fictícia" not in json.dumps(corpo, ensure_ascii=False)
    assert corpo["data"]["items"][0]["prices"] == bruto["data"]["items"][0]["prices"]


def test_le_resposta_da_olx():
    resposta = ler_resposta(_texto("olx-plp-aluguel-bh-localizacao-ignorada.json"))

    assert resposta.fonte == "olx.com.br"
    assert resposta.itens == 3
    assert resposta.total_resultados == 592033


def test_olx_ignorou_a_localizacao_pedida():
    """Registro do defeito da GeckoAPI em 27/10/2026: pedido em BH, itens de outros estados."""
    corpo = json.loads(_texto("olx-plp-aluguel-bh-localizacao-ignorada.json"))

    assert "belo-horizonte" in corpo["data"]["url"]
    assert {item["location"]["state"] for item in corpo["data"]["items"]} != {"MG"}


def test_sem_anunciante_remove_em_qualquer_nivel():
    corpo = {"a": [{"seller": {"x": 1}, "b": {"phones": ["31"], "c": 2}}], "email": "x@y"}

    assert sem_anunciante(corpo) == {"a": [{"b": {"c": 2}}]}


@pytest.mark.parametrize(
    "texto",
    ["não é json", "{}", '{"requestId": "x", "data": {"source": "s", "url": "u"}}'],
)
def test_resposta_fora_do_formato(texto):
    with pytest.raises(RespostaInvalida):
        ler_resposta(texto)


# --- ClienteGecko (sem rede: httpx.MockTransport) ---


def _cliente(*respostas, chamadas=None):
    fila = list(respostas)

    def responder(requisicao: httpx.Request) -> httpx.Response:
        if chamadas is not None:
            chamadas.append(requisicao)
        resposta = fila.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    return ClienteGecko("chave-teste", transport=httpx.MockTransport(responder))


def _ok():
    return httpx.Response(200, text=_texto("zap-plp-aluguel-bh.json"))


def test_cliente_extrai_e_devolve_resposta_sem_anunciante():
    chamadas = []
    resposta, bruto = asyncio.run(_cliente(_ok(), chamadas=chamadas).extrair({"target": "x"}))

    assert resposta.request_id == "3136ff9f-c3fe-41cf-8bfc-bfd426c982a5"
    assert "advertiser" not in json.dumps(resposta.corpo)
    assert "advertiser" in bruto["data"]["items"][0]  # bruto só para o parse, não é guardado
    (requisicao,) = chamadas
    assert requisicao.method == "POST"
    assert requisicao.url == "https://api.geckoapi.com.br/v1/extract"
    assert requisicao.headers["Authorization"] == "Bearer chave-teste"
    assert json.loads(requisicao.content) == {"target": "x"}


def test_cliente_not_found_e_erro():
    nao_achou = httpx.Response(200, json={"requestId": "r", "data": None, "notFound": True})
    with pytest.raises(ErroGecko, match="sem resultados"):
        asyncio.run(_cliente(nao_achou).extrair({}))


def test_cliente_sem_credito_bloqueia_as_chamadas_seguintes():
    chamadas = []
    cliente = _cliente(
        httpx.Response(402, json={"errorCode": "INSUFFICIENT_CREDITS"}), chamadas=chamadas
    )
    with pytest.raises(SemCredito) as primeira:
        asyncio.run(cliente.extrair({}))
    assert primeira.value.primeira_vez
    with pytest.raises(SemCredito) as segunda:
        asyncio.run(cliente.extrair({}))
    assert not segunda.value.primeira_vez
    assert len(chamadas) == 1
    assert cliente.sem_credito


def test_cliente_tenta_de_novo_uma_vez_em_5xx():
    chamadas = []
    cliente = _cliente(httpx.Response(502), _ok(), chamadas=chamadas)
    resposta, _ = asyncio.run(cliente.extrair({}))
    assert resposta.itens == 3
    assert len(chamadas) == 2


def test_cliente_desiste_depois_de_dois_5xx():
    with pytest.raises(ErroGecko, match="HTTP 500"):
        asyncio.run(_cliente(httpx.Response(500), httpx.Response(500)).extrair({}))


def test_cliente_nao_repete_tempo_esgotado():
    chamadas = []
    cliente = _cliente(httpx.ReadTimeout("lento"), _ok(), chamadas=chamadas)
    with pytest.raises(ErroGecko, match="tempo esgotado"):
        asyncio.run(cliente.extrair({}))
    assert len(chamadas) == 1


def test_cliente_4xx_vira_erro_sem_nova_tentativa():
    chamadas = []
    cliente = _cliente(httpx.Response(429), _ok(), chamadas=chamadas)
    with pytest.raises(ErroGecko, match="HTTP 429"):
        asyncio.run(cliente.extrair({}))
    assert len(chamadas) == 1


def test_cliente_creditos():
    saldo = httpx.Response(200, json={"currentCredits": 94, "creditsConsumed": {"last24Hours": 6}})
    chamadas = []
    dados = asyncio.run(_cliente(saldo, chamadas=chamadas).creditos())
    assert dados["currentCredits"] == 94
    assert chamadas[0].method == "GET"
    assert chamadas[0].url == "https://api.geckoapi.com.br/v1/me/credits"
