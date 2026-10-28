import pytest

from apebot.modelos import NOMES_FONTE, Tipo, slug


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


@pytest.mark.parametrize(
    ("unit_type", "esperado"),
    [
        ("APARTMENT", Tipo.APARTAMENTO),
        ("PENTHOUSE", Tipo.APARTAMENTO),
        ("HOME", Tipo.CASA),
        ("TWO_STORY_HOUSE", Tipo.CASA),
        ("CONDOMINIUM", Tipo.CASA_CONDOMINIO),
        ("KITNET", Tipo.KITNET),
        ("FLAT", Tipo.KITNET),
        ("ALLOTMENT_LAND", None),
    ],
)
def test_tipo_do_zap(unit_type, esperado):
    assert Tipo.de_zap(unit_type) is esperado


def test_property_types_do_zap():
    assert Tipo.APARTAMENTO.zap_property_types == ("apartment", "penthouse")
    assert Tipo.CASA.zap_property_types == ("house", "two_story_house")
    assert Tipo.CASA_CONDOMINIO.zap_property_types == ("condominium",)
    assert Tipo.KITNET.zap_property_types == ("kitnet", "flat")


def test_nomes_de_fonte():
    assert NOMES_FONTE == {"quintoandar": "QuintoAndar", "zap": "Zap", "olx": "OLX"}
