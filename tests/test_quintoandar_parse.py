import json
import re
from pathlib import Path

import pytest

from apebot.fontes.quintoandar import (
    FormatoInvalido,
    bairro_confere,
    combinacoes,
    extrair,
    url_listagem,
)
from apebot.modelos import Filtro, Pessoa, Tipo

FIXTURES = Path(__file__).parent / "fixtures" / "quintoandar"


def _html(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


def _ids_da_pagina(html: str) -> list[str]:
    dados = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S
    )
    estado = json.loads(dados.group(1))["props"]["pageProps"]["initialState"]
    return estado["search"]["visibleHouses"]["pages"]["0"]


def test_extrai_listagem_por_bairro_e_tipo():
    html = _html("listagem-bairro-tipo-buritis-apartamento.html")
    resultado = extrair(html, "buritis")

    assert len(resultado.anuncios) == 24
    assert [a.id_externo for a in resultado.anuncios] == _ids_da_pagina(html)
    primeiro = resultado.anuncios[0]
    assert primeiro.fonte == "quintoandar"
    assert primeiro.id_externo == "895660418"
    assert primeiro.tipo is Tipo.APARTAMENTO
    assert primeiro.bairro == "Buritis"
    assert primeiro.bairro_slug == "buritis"
    assert primeiro.quartos == 3
    assert primeiro.area_m2 == 120
    assert primeiro.aluguel_centavos == 600_000
    assert primeiro.total_centavos == 725_800
    assert primeiro.url == "https://www.quintoandar.com.br/imovel/895660418"


def test_extrai_bairro_com_acento():
    resultado = extrair(_html("listagem-bairro-funcionarios.html"), "funcionarios")
    assert len(resultado.anuncios) == 24
    assert resultado.anuncios[0].bairro == "Funcionários"
    assert resultado.anuncios[0].aluguel_centavos == 480_000


def test_descarta_anuncios_de_outros_bairros():
    resultado = extrair(_html("listagem-cidade-bh.html"), "buritis")
    assert all(a.bairro_slug == "buritis" for a in resultado.anuncios)
    assert resultado.descartados["fora_do_bairro"] == 24 - len(resultado.anuncios)


@pytest.mark.parametrize(
    ("bairro_json", "bairro_slug", "esperado"),
    [
        ("Buritis", "buritis", True),
        ("Funcionários", "funcionarios", True),
        ("Bandeirantes", "bandeirantes-pampulha", True),
        ("Sion", "buritis", False),
        ("Santa", "santa-monica", True),
    ],
)
def test_bairro_confere(bairro_json, bairro_slug, esperado):
    assert bairro_confere(bairro_json, bairro_slug) is esperado


def test_sem_next_data_e_formato_invalido():
    with pytest.raises(FormatoInvalido):
        extrair("<html><body>nada</body></html>", "buritis")


def test_json_sem_houses_e_formato_invalido():
    html = '<script id="__NEXT_DATA__" type="application/json">{"props": {}}</script>'
    with pytest.raises(FormatoInvalido):
        extrair(html, "buritis")


def _pagina(casa: dict) -> str:
    dados = {
        "props": {
            "pageProps": {
                "initialState": {
                    "houses": {"1": casa},
                    "search": {"visibleHouses": {"pages": {"0": ["1"]}}},
                }
            }
        }
    }
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(dados)}</script>'


CASA = {
    "id": "1",
    "type": "Apartamento",
    "neighbourhood": "Buritis",
    "bedrooms": 2,
    "area": 60,
    "rentPrice": 2000,
    "totalCost": 2500,
}


@pytest.mark.parametrize("campo", ["rentPrice", "bedrooms", "type", "neighbourhood"])
def test_campo_obrigatorio_ausente_descarta(campo):
    casa = {k: v for k, v in CASA.items() if k != campo}
    resultado = extrair(_pagina(casa), "buritis")
    assert resultado.anuncios == []
    assert resultado.descartados["incompleto"] == 1


def test_tipo_desconhecido_descarta():
    resultado = extrair(_pagina({**CASA, "type": "Cobertura"}), "buritis")
    assert resultado.anuncios == []
    assert resultado.descartados["incompleto"] == 1


def test_area_e_total_ausentes_viram_none():
    casa = {k: v for k, v in CASA.items() if k not in ("area", "totalCost")}
    (anuncio,) = extrair(_pagina(casa), "buritis").anuncios
    assert anuncio.area_m2 is None
    assert anuncio.total_centavos is None


def test_url_listagem():
    assert url_listagem("buritis", Tipo.APARTAMENTO) == (
        "https://www.quintoandar.com.br/alugar/imovel/buritis-belo-horizonte-mg-brasil/apartamento"
    )
    assert url_listagem("sion", Tipo.CASA_CONDOMINIO).endswith(
        "/sion-belo-horizonte-mg-brasil/casacondominio"
    )


def test_combinacoes_distintas_da_uniao_dos_filtros():
    def pessoa(chat_id, bairros, tipos):
        return Pessoa(chat_id, "x", Filtro(frozenset(bairros), 100_000, 1, frozenset(tipos)))

    pessoas = [
        pessoa(1, {"buritis", "sion"}, {Tipo.APARTAMENTO}),
        pessoa(2, {"buritis"}, {Tipo.APARTAMENTO, Tipo.CASA}),
    ]
    assert combinacoes(pessoas) == [
        ("buritis", Tipo.APARTAMENTO),
        ("buritis", Tipo.CASA),
        ("sion", Tipo.APARTAMENTO),
    ]
