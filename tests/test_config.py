import textwrap

import pytest

from apebot.config import ConfiguracaoInvalida, carregar_filtros
from apebot.modelos import Tipo

BAIRROS = frozenset({"buritis", "funcionarios", "santa-monica", "sion"})


def _carregar(tmp_path, conteudo):
    caminho = tmp_path / "filtros.yaml"
    caminho.write_text(textwrap.dedent(conteudo), encoding="utf-8")
    return carregar_filtros(caminho, BAIRROS)


VALIDO = """
operador_chat_id: 1
pessoas:
  - nome: Heitor
    chat_id: 1
    filtros:
      bairros: [Buritis, funcionarios, Santa Mônica]
      aluguel_max: 3000
      quartos_min: 2
      tipos: [apartamento, casa_condominio]
"""


def test_configuracao_valida(tmp_path):
    config = _carregar(tmp_path, VALIDO)
    assert config.operador_chat_id == 1
    assert config.problemas == []
    (pessoa,) = config.pessoas
    assert pessoa.nome == "Heitor"
    assert pessoa.filtro.bairros == frozenset({"buritis", "funcionarios", "santa-monica"})
    assert pessoa.filtro.aluguel_max_centavos == 300_000
    assert pessoa.filtro.quartos_min == 2
    assert pessoa.filtro.tipos == frozenset({Tipo.APARTAMENTO, Tipo.CASA_CONDOMINIO})


def test_operador_ausente_e_fatal(tmp_path):
    with pytest.raises(ConfiguracaoInvalida):
        _carregar(tmp_path, VALIDO.replace("operador_chat_id: 1", ""))


def test_operador_fora_das_pessoas_e_fatal(tmp_path):
    with pytest.raises(ConfiguracaoInvalida):
        _carregar(tmp_path, VALIDO.replace("operador_chat_id: 1", "operador_chat_id: 99"))


def test_chat_id_duplicado_e_fatal(tmp_path):
    duplicado = (
        VALIDO
        + """
  - nome: Outra
    chat_id: 1
    filtros:
      bairros: [Sion]
      aluguel_max: 2000
      quartos_min: 1
      tipos: [casa]
"""
    )
    with pytest.raises(ConfiguracaoInvalida):
        _carregar(tmp_path, duplicado)


def test_bairro_desconhecido_e_ignorado_com_problema(tmp_path):
    config = _carregar(tmp_path, VALIDO.replace("Santa Mônica", "Bairro Inventado"))
    assert config.pessoas[0].filtro.bairros == frozenset({"buritis", "funcionarios"})
    assert any("Bairro Inventado" in p for p in config.problemas)


def test_nenhum_bairro_valido_ignora_pessoa(tmp_path):
    config = _carregar(
        tmp_path, VALIDO.replace("[Buritis, funcionarios, Santa Mônica]", "[Atlantida]")
    )
    assert config.pessoas == []
    assert config.problemas


@pytest.mark.parametrize("valor", ["0", "-10", "abc"])
def test_aluguel_max_invalido_ignora_pessoa(tmp_path, valor):
    config = _carregar(tmp_path, VALIDO.replace("aluguel_max: 3000", f"aluguel_max: {valor}"))
    assert config.pessoas == []
    assert config.problemas


def test_quartos_min_negativo_ignora_pessoa(tmp_path):
    config = _carregar(tmp_path, VALIDO.replace("quartos_min: 2", "quartos_min: -1"))
    assert config.pessoas == []


def test_tipo_invalido_e_ignorado(tmp_path):
    config = _carregar(tmp_path, VALIDO.replace("casa_condominio]", "casa_condominio, mansao]"))
    assert config.pessoas[0].filtro.tipos == frozenset({Tipo.APARTAMENTO, Tipo.CASA_CONDOMINIO})
    assert any("mansao" in p for p in config.problemas)


def test_tipos_vazio_ignora_pessoa(tmp_path):
    config = _carregar(tmp_path, VALIDO.replace("[apartamento, casa_condominio]", "[]"))
    assert config.pessoas == []
    assert config.problemas
