import copy
import json
from pathlib import Path

import pytest

from apebot.config import bairros_validos
from apebot.fontes.olx import extrair_olx, payload_olx
from apebot.modelos import Filtro, Pessoa, Tipo

FIXTURE = (
    Path(__file__).parent / "fixtures" / "geckoapi" / "olx-plp-aluguel-bh-localizacao-ignorada.json"
)
CATALOGO = bairros_validos()
BH = {"city": "Belo Horizonte", "state": "MG", "neighborhood": "Buritis"}


def _corpo() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _item_em_bh(indice: int, **mudancas) -> dict:
    corpo = _corpo()
    item = copy.deepcopy(corpo["data"]["items"][indice])
    item["location"] = {**item["location"], **BH}
    propriedades = {p["name"]: p for p in item["properties"]}
    for nome, valor in mudancas.items():
        if nome not in propriedades:
            item[nome] = valor
        elif valor is None:
            item["properties"] = [p for p in item["properties"] if p["name"] != nome]
        else:
            propriedades[nome]["value"] = valor
    corpo["data"]["items"] = [item]
    return corpo


def test_localizacao_ignorada_pela_api_e_barrada_aqui():
    """27/10/2026: pedido em BH, a GeckoAPI devolveu SP, GO e PR; nada passa (FR-007, SC-002)."""
    resultado = extrair_olx(_corpo(), CATALOGO)
    assert resultado.anuncios == []
    assert resultado.descartados == {"fora_da_cidade": 3}


def test_item_em_bh_vira_anuncio():
    (anuncio,) = extrair_olx(_item_em_bh(0), CATALOGO).anuncios
    assert anuncio.fonte == "olx"
    assert anuncio.id_externo == "1544571237"
    assert anuncio.tipo is Tipo.CASA_CONDOMINIO
    assert (anuncio.bairro, anuncio.bairro_slug) == ("Buritis", "buritis")
    assert (anuncio.quartos, anuncio.area_m2) == (3, 230)
    assert anuncio.aluguel_centavos == 950_000
    assert anuncio.total_centavos == (9500 + 497 + 200) * 100
    assert (
        anuncio.url == "https://sp.olx.com.br/grande-campinas/imoveis/casa-em-condominio-1544571237"
    )


def test_tipos_e_quartos_da_olx():
    (apto,) = extrair_olx(_item_em_bh(1), CATALOGO).anuncios
    assert apto.tipo is Tipo.APARTAMENTO
    (casa,) = extrair_olx(_item_em_bh(2), CATALOGO).anuncios
    assert casa.tipo is Tipo.CASA
    assert casa.quartos == 5  # "5 ou mais"
    assert casa.total_centavos is None  # sem condomínio informado
    assert casa.area_m2 is None


@pytest.mark.parametrize(
    ("mudancas", "motivo"),
    [
        ({"real_estate_type": "Aluguel - temporada"}, "tipo"),
        (
            {"category": "Terrenos", "real_estate_type": "Aluguel - terreno", "re_types": "Lote"},
            "tipo",
        ),
        ({"price": None}, "incompleto"),
        ({"rooms": None}, "incompleto"),
    ],
)
def test_descartes_da_olx(mudancas, motivo):
    resultado = extrair_olx(_item_em_bh(0, **mudancas), CATALOGO)
    assert resultado.anuncios == []
    assert resultado.descartados == {motivo: 1}


def test_bairro_fora_do_catalogo():
    corpo = _item_em_bh(0)
    corpo["data"]["items"][0]["location"]["neighborhood"] = None
    assert extrair_olx(corpo, CATALOGO).descartados == {"bairro_desconhecido": 1}


def test_payload_olx():
    pessoa = Pessoa(
        chat_id=1,
        nome="H",
        filtro=Filtro(
            bairros=frozenset({"buritis"}),
            aluguel_max_centavos=300_000,
            quartos_min=2,
            tipos=frozenset({Tipo.APARTAMENTO}),
        ),
    )
    assert payload_olx([pessoa]) == {
        "target": "olx.com.br",
        "type": "plp",
        "page": 1,
        "state": "MG",
        "city": "Belo Horizonte",
        "categoryPath": "imoveis/aluguel",
        "sort": "date",
        "priceMax": 3000,
    }
