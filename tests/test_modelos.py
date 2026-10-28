import pytest

from apebot.modelos import Tipo, slug


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Santa Mônica", "santa-monica"),
        ("Funcionários", "funcionarios"),
        ("  Aparecida 7ª Seção ", "aparecida-7a-secao"),
        ("bandeirantes-pampulha", "bandeirantes-pampulha"),
    ],
)
def test_slug(texto, esperado):
    assert slug(texto) == esperado


@pytest.mark.parametrize(
    ("tipo", "slug_url", "tipo_json"),
    [
        (Tipo.APARTAMENTO, "apartamento", "Apartamento"),
        (Tipo.CASA, "casa", "Casa"),
        (Tipo.CASA_CONDOMINIO, "casacondominio", "CasaCondominio"),
        (Tipo.KITNET, "kitnet", "StudioOuKitchenette"),
    ],
)
def test_mapeamento_de_tipo(tipo, slug_url, tipo_json):
    assert tipo.slug_url == slug_url
    assert Tipo.de_json(tipo_json) is tipo


def test_tipo_json_desconhecido():
    assert Tipo.de_json("Cobertura") is None


def test_tipo_do_yaml():
    assert Tipo("casa_condominio") is Tipo.CASA_CONDOMINIO
