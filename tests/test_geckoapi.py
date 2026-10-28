import json
from datetime import datetime
from pathlib import Path

import pytest

from apebot.fontes.geckoapi import RespostaInvalida, ler_resposta, sem_anunciante

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
