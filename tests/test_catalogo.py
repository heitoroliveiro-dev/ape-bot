import pytest

from apebot.config import _ler_catalogo, bairros_validos, catalogo_bairros, nome_bairro
from apebot.modelos import REGIONAIS

FILTRO_ATUAL = {
    "barro-preto",
    "alto-barroca",
    "alto-caicaras",
    "barroca",
    "caicaras",
    "carlos-prates",
    "castelo",
    "centro",
    "cidade-nova",
    "cidade-jardim",
    "colegio-batista",
    "fernao-dias",
    "funcionarios",
    "grajau",
    "gutierrez",
    "lagoinha",
    "prado",
    "santa-tereza",
    "santa-efigenia",
    "santa-ines",
    "uniao",
}


def test_regionais_na_ordem_do_teclado():
    assert REGIONAIS == (
        "Barreiro",
        "Centro-Sul",
        "Leste",
        "Nordeste",
        "Noroeste",
        "Norte",
        "Oeste",
        "Pampulha",
        "Venda Nova",
        "Outros",
    )


def test_catalogo_tem_283_bairros_com_regional():
    catalogo = catalogo_bairros()
    assert len(catalogo) == 283
    assert all(b.regional in REGIONAIS for b in catalogo)
    assert bairros_validos() == frozenset(b.slug for b in catalogo)


def test_catalogo_sem_bairros_de_fora_de_bh():
    assert not [s for s in bairros_validos() if "-sp-brasil" in s or "justinopolis" in s]


def test_bairros_do_filtro_atual_estao_numa_regional():
    por_slug = {b.slug: b for b in catalogo_bairros()}
    assert FILTRO_ATUAL <= set(por_slug)
    assert all(por_slug[s].regional != "Outros" for s in FILTRO_ATUAL)


def test_nome_bairro():
    assert nome_bairro("alto-caicaras") == "Alto Caiçaras"
    assert nome_bairro("funcionarios") == "Funcionários"
    assert nome_bairro("bairro-que-nao-existe") == "Bairro Que Nao Existe"


def test_slug_repetido_no_csv_e_erro(tmp_path):
    arquivo = tmp_path / "bairros.csv"
    arquivo.write_text("slug,nome,regional\nprado,Prado,Oeste\nprado,Prado,Oeste\n")
    with pytest.raises(ValueError, match="prado"):
        _ler_catalogo(arquivo.read_text())
