import asyncio
import json
import logging
import re
from pathlib import Path

import httpx
import pytest

from apebot.config import bairros_validos
from apebot.fontes import netimoveis
from apebot.fontes.netimoveis import (
    FormatoInvalido,
    coletar,
    combinacoes,
    extrair,
    quartos_minimo,
    url_busca,
)
from apebot.modelos import Filtro, Pessoa, Tipo

FIXTURES = Path(__file__).parent / "fixtures" / "netimoveis"
CATALOGO = bairros_validos()


def _fixture(nome: str) -> str:
    return (FIXTURES / nome).read_text(encoding="utf-8")


FUNCIONARIOS = _fixture("funcionarios-apartamento-2q.html")
KITCHENETTE = _fixture("centro-kitchenette.html")
VAZIA = _fixture("lourdes-casa-em-condominio.html")
SEM_JSONLD = _fixture("sem-jsonld.html")


def _pessoa(chat_id, bairros, tipos, quartos_min=2):
    return Pessoa(
        chat_id=chat_id,
        nome=str(chat_id),
        filtro=Filtro(
            bairros=frozenset(bairros),
            aluguel_max_centavos=200_000,
            quartos_min=quartos_min,
            tipos=frozenset(tipos),
        ),
    )


# --- parse ---


def test_extrai_busca_com_corte_da_primeira_pagina():
    busca = extrair(FUNCIONARIOS, CATALOGO)
    assert (busca.total, busca.lidos) == (31, 21)
    assert len(busca.anuncios) == 21
    assert not busca.descartados
    primeiro = busca.anuncios[0]
    assert primeiro.fonte == "netimoveis"
    assert primeiro.id_externo == "650010"
    assert primeiro.url == (
        "https://www.netimoveis.com/imovel/"
        "locacao-apartamento-minas-gerais-belo-horizonte-funcionarios/650010"
    )
    assert primeiro.tipo is Tipo.APARTAMENTO
    assert primeiro.bairro_slug == "funcionarios"
    assert primeiro.quartos == 2
    assert primeiro.area_m2 == 70
    assert primeiro.aluguel_centavos == 449_000
    assert primeiro.total_centavos == 449_000 + 119_800  # aluguel + condomínio
    assert all(a.id_externo.isdigit() and "?" not in a.url for a in busca.anuncios)
    assert all(a.tipo is Tipo.APARTAMENTO for a in busca.anuncios)  # cobertura e área privativa


def test_cobertura_e_area_privativa_contam_como_apartamento():
    busca = extrair(FUNCIONARIOS, CATALOGO)
    tipos_na_url = {
        re.search(r"/imovel/locacao-(.+)-minas-gerais", a.url)[1] for a in busca.anuncios
    }
    assert {"cobertura", "area-privativa"} <= tipos_na_url


def test_sem_condominio_o_total_fica_vazio():
    busca = extrair(FUNCIONARIOS, CATALOGO)
    sem = [a for a in busca.anuncios if a.id_externo == "1196627"]  # sem "Condominium Fee"
    assert sem and sem[0].total_centavos is None


def test_extrai_kitchenette_como_kitnet():
    busca = extrair(KITCHENETTE, CATALOGO)
    assert busca.total == busca.lidos == 2
    assert {a.tipo for a in busca.anuncios} == {Tipo.KITNET}
    assert {a.bairro_slug for a in busca.anuncios} == {"centro"}


def test_busca_vazia_nao_e_erro():
    busca = extrair(VAZIA, CATALOGO)
    assert (busca.total, busca.lidos, busca.anuncios) == (0, 0, [])


def test_pagina_sem_jsonld_e_formato_invalido():
    with pytest.raises(FormatoInvalido):
        extrair(SEM_JSONLD, CATALOGO)


# --- descartes (itens reais alterados em memória) ---


def _pagina_com(*urls_e_ajustes) -> str:
    """Página com o 1º item da fixture de Funcionários repetido, trocando URL e campos."""
    blocos = re.findall(r"<script[^>]*ld\+json[^>]*>(.*?)</script>", FUNCIONARIOS, flags=re.S)
    lista = next(json.loads(b) for b in blocos if '"ItemList"' in b)
    base = lista["itemListElement"][0]
    itens = []
    for url, ajuste in urls_e_ajustes:
        item = json.loads(json.dumps(base))
        item["item"]["url"] = url
        ajuste(item["item"])
        itens.append(item)
    lista["itemListElement"] = itens
    lista["numberOfItems"] = len(itens)
    return f'<script type="application/ld+json">{json.dumps(lista)}</script>'


def _url(tipo, bairro, id_externo="1"):
    return (
        f"https://www.netimoveis.com/imovel/locacao-{tipo}-minas-gerais-belo-horizonte-"
        f"{bairro}/{id_externo}?tipoUrl={tipo}"
    )


def _nada(_item):
    pass


def _sem_preco(item):
    del item["offers"]["price"]


def _sem_quartos(item):
    del item["offers"]["itemOffered"]["numberOfBedrooms"]


def test_descartes_por_motivo():
    html = _pagina_com(
        (
            "https://www.netimoveis.com/imovel/locacao-apartamento-sao-paulo-sao-paulo-moema/9",
            _nada,
        ),
        (_url("loja", "centro", "2"), _nada),
        (_url("apartamento", "bairro-que-nao-existe", "3"), _nada),
        (_url("apartamento", "centro", "4"), _sem_preco),
        (_url("apartamento", "centro", "5"), _sem_quartos),
        (_url("apartamento", "bandeirantes-(pampulha)", "6"), _nada),
    )
    busca = extrair(html, CATALOGO)
    assert dict(busca.descartados) == {
        "fora_da_cidade": 1,
        "tipo_nao_aceito": 1,
        "bairro_desconhecido": 1,
        "incompleto": 2,
    }
    assert [(a.id_externo, a.bairro_slug) for a in busca.anuncios] == [
        ("6", "bandeirantes-pampulha")
    ]


# --- buscas ---


def test_combinacoes_e_quartos_minimo():
    pessoas = [
        _pessoa(1, {"centro", "floresta"}, {Tipo.APARTAMENTO}, quartos_min=2),
        _pessoa(2, {"centro"}, {Tipo.APARTAMENTO, Tipo.KITNET}, quartos_min=1),
    ]
    assert combinacoes(pessoas) == [
        ("centro", Tipo.APARTAMENTO),
        ("centro", Tipo.KITNET),
        ("floresta", Tipo.APARTAMENTO),
    ]
    assert quartos_minimo(pessoas) == 1
    assert quartos_minimo([]) == 0


def test_url_de_busca():
    assert url_busca("centro", Tipo.APARTAMENTO, 2) == (
        "https://www.netimoveis.com/locacao/minas-gerais/belo-horizonte/bairros/centro/"
        "apartamento?quartos=2"
    )
    assert url_busca("lourdes", Tipo.CASA_CONDOMINIO, 0) == (
        "https://www.netimoveis.com/locacao/minas-gerais/belo-horizonte/bairros/lourdes/"
        "casa-em-condominio"
    )


@pytest.mark.parametrize("tipo", list(Tipo))
def test_url_de_busca_so_usa_caminho_permitido(tipo):
    url = url_busca("centro", tipo, 3)
    for proibido in ("pag=", "preco", "ordem=", "/pesquisa/", "/api/", "area"):
        assert proibido not in url


# --- coleta (sem rede) ---


@pytest.fixture
def sem_espera(monkeypatch):
    monkeypatch.setattr(netimoveis, "INTERVALO_SEGUNDOS", (0.0, 0.0))
    monkeypatch.setattr(netimoveis, "BACKOFF_SEGUNDOS", (0, 0, 0))


def _coletar(respostas, pessoas, simular_falha=False):
    """`respostas`: caminho da URL → (status, html). Devolve (resultado, URLs pedidas)."""
    pedidas = []

    def responder(request: httpx.Request) -> httpx.Response:
        pedidas.append(str(request.url))
        caminho = request.url.raw_path.decode()
        status, html = respostas.get(caminho, (404, ""))
        return httpx.Response(status, text=html)

    transporte = httpx.MockTransport(responder)
    resultado = asyncio.run(
        coletar(pessoas, CATALOGO, simular_falha=simular_falha, transporte=transporte)
    )
    return resultado, pedidas


BUSCA = "/locacao/minas-gerais/belo-horizonte/bairros"


def test_coleta_junta_as_buscas(sem_espera):
    pessoas = [_pessoa(1, {"funcionarios", "centro"}, {Tipo.APARTAMENTO, Tipo.KITNET}, 2)]
    resultado, pedidas = _coletar(
        {
            f"{BUSCA}/funcionarios/apartamento?quartos=2": (200, FUNCIONARIOS),
            f"{BUSCA}/centro/kitchenette?quartos=2": (200, KITCHENETTE),
            f"{BUSCA}/funcionarios/kitchenette?quartos=2": (200, VAZIA),
        },
        pessoas,
    )
    assert resultado.fonte == "netimoveis"
    assert resultado.status == "ok"
    assert resultado.consultas == 4
    assert resultado.consultas_erro == 0  # centro/apartamento deu 404: busca vazia
    assert len(resultado.anuncios) == 23
    assert len(pedidas) == 4


def test_todas_404_e_falha(sem_espera):
    resultado, _ = _coletar({}, [_pessoa(1, {"centro", "floresta"}, {Tipo.APARTAMENTO})])
    assert resultado.status == "falha"
    assert resultado.consultas == 2


def test_formato_invalido_e_falha(sem_espera):
    resultado, _ = _coletar(
        {f"{BUSCA}/centro/apartamento?quartos=2": (200, SEM_JSONLD)},
        [_pessoa(1, {"centro"}, {Tipo.APARTAMENTO})],
    )
    assert resultado.status == "falha"
    assert resultado.erro_de_formato
    assert resultado.erro.startswith("formato:")


def test_desafio_antirrobo_e_erro_de_acesso(sem_espera):
    resultado, _ = _coletar(
        {
            f"{BUSCA}/centro/apartamento?quartos=2": (403, "<title>Just a moment...</title>"),
            f"{BUSCA}/floresta/apartamento?quartos=2": (200, "<title>Just a moment...</title>"),
        },
        [_pessoa(1, {"centro", "floresta"}, {Tipo.APARTAMENTO})],
    )
    assert resultado.status == "falha"
    assert resultado.consultas_erro == 2
    assert resultado.erro.startswith("acesso:")
    assert not resultado.erro_de_formato


def test_simular_falha_nao_acessa_a_rede(sem_espera):
    resultado, pedidas = _coletar(
        {}, [_pessoa(1, {"centro"}, {Tipo.APARTAMENTO})], simular_falha=True
    )
    assert pedidas == []
    assert resultado.status == "falha"
    assert resultado.consultas_erro == 1


def test_coleta_sem_pessoas_nao_busca(sem_espera):
    resultado, pedidas = _coletar({}, [])
    assert pedidas == []
    assert resultado.consultas == 0
    assert resultado.status == "ok"


# --- corte da 1ª página (US3) ---


def test_registra_corte_da_primeira_pagina(sem_espera, caplog):
    caplog.set_level(logging.INFO, logger="apebot.fontes.netimoveis")
    _coletar(
        {
            f"{BUSCA}/funcionarios/apartamento?quartos=2": (200, FUNCIONARIOS),
            f"{BUSCA}/centro/kitchenette?quartos=2": (200, KITCHENETTE),
        },
        [
            _pessoa(1, {"funcionarios"}, {Tipo.APARTAMENTO}),
            _pessoa(2, {"centro"}, {Tipo.KITNET}),
        ],
    )
    cortes = [r.getMessage() for r in caplog.records if "netimoveis_corte" in r.getMessage()]
    assert cortes == ["netimoveis_corte bairro=funcionarios tipo=apartamento total=31 lidos=21"]
