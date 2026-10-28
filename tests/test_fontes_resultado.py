import pytest

from apebot.fontes.resultado import bairro_do_catalogo, na_cidade, telefone_legivel, whatsapp_url

CATALOGO = frozenset(
    {"gutierrez", "bandeirantes-pampulha", "santa-monica", "sao-bento", "sao-bento-x"}
)


@pytest.mark.parametrize(
    ("cidade", "uf", "esperado"),
    [
        ("Belo Horizonte", "MG", True),
        ("belo horizonte", "Minas Gerais", True),
        ("BH", "mg", True),
        ("BELO-HORIZONTE", "MG", True),
        ("Contagem", "MG", False),
        ("Belo Horizonte", "SP", False),
        (None, "MG", False),
        ("Belo Horizonte", None, False),
        ("", "", False),
    ],
)
def test_na_cidade(cidade, uf, esperado):
    assert na_cidade(cidade, uf) is esperado


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Gutierrez", "gutierrez"),
        ("Santa Mônica", "santa-monica"),
        ("Bandeirantes", "bandeirantes-pampulha"),
        ("São Bento", "sao-bento"),
        ("Savassi", None),
        ("", None),
        (None, None),
    ],
)
def test_bairro_do_catalogo(nome, esperado):
    assert bairro_do_catalogo(nome, CATALOGO) == esperado


def test_bairro_ambiguo_por_prefixo_fica_de_fora():
    catalogo = frozenset({"jardim-america", "jardim-atlantico"})
    assert bairro_do_catalogo("Jardim", catalogo) is None


@pytest.mark.parametrize(
    ("numero", "esperado"),
    [
        ("31982984510", "https://wa.me/5531982984510"),
        ("5531982984510", "https://wa.me/5531982984510"),
        ("(31) 98298-4510", "https://wa.me/5531982984510"),
        ("+55 31 3045-4545", "https://wa.me/553130454545"),
        ("982984510", None),
        ("0031982984510", None),
        ("3100000000", None),
        ("", None),
        (None, None),
    ],
)
def test_whatsapp_url(numero, esperado):
    assert whatsapp_url(numero) == esperado


@pytest.mark.parametrize(
    ("numero", "esperado"),
    [
        ("31982984510", "(31) 98298-4510"),
        ("3130454545", "(31) 3045-4545"),
        ("5531982984510", "(31) 98298-4510"),
        ("1234", "1234"),
        ("3100000000", "3100000000"),
    ],
)
def test_telefone_legivel(numero, esperado):
    assert telefone_legivel(numero) == esperado
