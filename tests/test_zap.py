import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from apebot.config import bairros_validos
from apebot.fontes.geckoapi import ler_resposta
from apebot.fontes.zap import extrair_zap, payload_zap
from apebot.modelos import Contato, Filtro, Pessoa, Tipo

FIXTURE = Path(__file__).parent / "fixtures" / "geckoapi" / "zap-plp-aluguel-bh.json"
CATALOGO = bairros_validos()


def _corpo() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _com_item(**mudancas) -> dict:
    """Corpo com só o primeiro item da fixture, alterado."""
    corpo = _corpo()
    item = copy.deepcopy(corpo["data"]["items"][0])
    for caminho, valor in mudancas.items():
        alvo = item
        *pais, chave = caminho.split("__")
        for pai in pais:
            alvo = alvo[pai]
        alvo[chave] = valor
    corpo["data"]["items"] = [item]
    return corpo


def test_extrai_os_tres_anuncios_da_fixture():
    resultado = extrair_zap(_corpo(), CATALOGO)

    assert resultado.fonte == "zap"
    assert not resultado.descartados
    assert [a.id_externo for a in resultado.anuncios] == ["2919519749", "2917812668", "2919116764"]
    primeiro, casa, buritis = resultado.anuncios
    assert primeiro.fonte == "zap"
    assert primeiro.tipo is Tipo.APARTAMENTO
    assert (primeiro.bairro, primeiro.bairro_slug) == ("Gutierrez", "gutierrez")
    assert (primeiro.quartos, primeiro.area_m2) == (2, 80)
    assert primeiro.aluguel_centavos == 489_000
    assert primeiro.total_centavos == (4890 + 564) * 100  # iptu None fica de fora
    assert primeiro.url.startswith("https://www.zapimoveis.com.br/imovel/")
    assert primeiro.url.endswith("-id-2919519749/")
    assert (casa.tipo, casa.bairro_slug, casa.total_centavos) == (
        Tipo.CASA,
        "funcionarios",
        1_100_000,
    )
    assert buritis.total_centavos == (3650 + 400 + 222) * 100


def test_contato_do_anunciante_vem_separado():
    resultado = extrair_zap(_corpo(), CATALOGO)
    contato = resultado.contatos[("zap", "2919519749")]

    assert contato == Contato(
        nome="Imobiliária Fictícia",
        telefone="3100000000",  # número inválido: exibido como veio
        whatsapp_url="https://wa.me/5531900000000",
    )


def test_sem_condominio_o_total_fica_sem_informacao():
    resultado = extrair_zap(_com_item(prices__condominium=None), CATALOGO)
    assert resultado.anuncios[0].total_centavos is None


@pytest.mark.parametrize(
    ("mudancas", "motivo"),
    [
        ({"business": "SALE"}, "venda"),
        ({"unitTypes": ["COMMERCIAL_BUILDING"]}, "tipo"),
        ({"unitTypes": []}, "tipo"),
        ({"address__city": "Contagem"}, "fora_da_cidade"),
        ({"address__state": "SP"}, "fora_da_cidade"),
        ({"address__neighborhood": "Bairro Que Não Existe"}, "bairro_desconhecido"),
        ({"prices__rent": None}, "incompleto"),
        ({"attributes__bedrooms": []}, "incompleto"),
    ],
)
def test_itens_descartados_e_contados(mudancas, motivo):
    resultado = extrair_zap(_com_item(**mudancas), CATALOGO)
    assert resultado.anuncios == []
    assert resultado.contatos == {}
    assert resultado.descartados == {motivo: 1}


def test_corpo_sem_itens_e_formato_invalido():
    corpo = _corpo()
    corpo["data"]["items"] = None
    resultado = extrair_zap(corpo, CATALOGO)
    assert resultado.status == "falha"
    assert resultado.erro_de_formato


def _pessoa(chat_id, aluguel_max, quartos_min, tipos, bairros=("buritis",)):
    return Pessoa(
        chat_id=chat_id,
        nome=str(chat_id),
        filtro=Filtro(
            bairros=frozenset(bairros),
            aluguel_max_centavos=aluguel_max * 100,
            quartos_min=quartos_min,
            tipos=frozenset(tipos),
        ),
    )


def test_payload_com_filtros_somados():
    pessoas = [
        _pessoa(1, 3000, 2, {Tipo.APARTAMENTO}),
        _pessoa(2, 2500, 1, {Tipo.CASA}, bairros=("sion",)),
    ]
    assert payload_zap(pessoas) == {
        "target": "zapimoveis.com.br",
        "type": "plp",
        "page": 1,
        "businessType": "rent",
        "state": "MG",
        "city": "Belo Horizonte",
        "priceMax": 3000,
        "bedrooms": [1, 2, 3, 4],
        "propertyTypes": ["apartment", "penthouse", "house", "two_story_house"],
    }


def test_payload_sem_minimo_de_quartos_nao_filtra_quartos():
    payload = payload_zap([_pessoa(1, 2000, 0, {Tipo.KITNET})])
    assert "bedrooms" not in payload
    assert payload["propertyTypes"] == ["kitnet", "flat"]
    assert "neighborhood" not in payload and "sort" not in payload


def test_nem_anuncio_nem_resposta_guardada_levam_o_anunciante():
    """SC-004: nome e telefones do anunciante não chegam a nada que vá para o banco."""
    texto = FIXTURE.read_text(encoding="utf-8")
    resultado = extrair_zap(json.loads(texto), CATALOGO)
    guardado = json.dumps(
        [asdict(a) | {"tipo": a.tipo.value} for a in resultado.anuncios]
        + [ler_resposta(texto).corpo],
        ensure_ascii=False,
    )
    for dado in ("Imobiliária Fictícia", "3100000000", "31900000000", "00000-J-MG"):
        assert dado not in guardado
