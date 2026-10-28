import textwrap

import pytest

from apebot.config import (
    ConfiguracaoInvalida,
    carregar_configuracao,
    carregar_filtros,
    carregar_segredos,
    problemas_entrega,
    problemas_gecko,
    problemas_netimoveis,
)
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
    assert config.autorizados == {1: "Heitor"}
    (pessoa,) = config.sementes
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
    assert config.sementes[0].filtro.bairros == frozenset({"buritis", "funcionarios"})
    assert any("Bairro Inventado" in p for p in config.problemas)


def test_nenhum_bairro_valido_nao_vira_semente(tmp_path):
    config = _carregar(
        tmp_path, VALIDO.replace("[Buritis, funcionarios, Santa Mônica]", "[Atlantida]")
    )
    assert config.sementes == []
    assert 1 in config.autorizados  # continua autorizada: pode se cadastrar
    assert config.problemas


@pytest.mark.parametrize("valor", ["0", "-10", "abc"])
def test_aluguel_max_invalido_nao_vira_semente(tmp_path, valor):
    config = _carregar(tmp_path, VALIDO.replace("aluguel_max: 3000", f"aluguel_max: {valor}"))
    assert config.sementes == []
    assert 1 in config.autorizados  # continua autorizada: pode se cadastrar
    assert config.problemas


def test_quartos_min_negativo_nao_vira_semente(tmp_path):
    config = _carregar(tmp_path, VALIDO.replace("quartos_min: 2", "quartos_min: -1"))
    assert config.sementes == []
    assert 1 in config.autorizados  # continua autorizada: pode se cadastrar


def test_tipo_invalido_e_ignorado(tmp_path):
    config = _carregar(tmp_path, VALIDO.replace("casa_condominio]", "casa_condominio, mansao]"))
    assert config.sementes[0].filtro.tipos == frozenset({Tipo.APARTAMENTO, Tipo.CASA_CONDOMINIO})
    assert any("mansao" in p for p in config.problemas)


def test_tipos_vazio_nao_vira_semente(tmp_path):
    config = _carregar(tmp_path, VALIDO.replace("[apartamento, casa_condominio]", "[]"))
    assert config.sementes == []
    assert 1 in config.autorizados  # continua autorizada: pode se cadastrar
    assert config.problemas


@pytest.fixture
def ambiente(monkeypatch):
    for nome, valor in {
        "TELEGRAM_TOKEN": "t",
        "MYSQL_USER": "u",
        "MYSQL_PASSWORD": "p",
    }.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.delenv("GECKO_API_KEY", raising=False)
    monkeypatch.delenv("GECKO_FONTES", raising=False)
    monkeypatch.delenv("ENTREGA_INTERVALO", raising=False)
    monkeypatch.delenv("FILTROS_YAML", raising=False)
    monkeypatch.delenv("NETIMOVEIS", raising=False)
    return monkeypatch


def test_gecko_padrao_zap_sem_chave(ambiente):
    segredos = carregar_segredos()
    assert segredos.gecko_api_key == ""
    assert segredos.gecko_fontes == ("zap",)
    assert problemas_gecko(segredos) == ["GECKO_API_KEY ausente: Zap/OLX desligados"]


def test_gecko_com_chave_e_fontes(ambiente):
    ambiente.setenv("GECKO_API_KEY", "chave")
    ambiente.setenv("GECKO_FONTES", " zap , OLX ")
    segredos = carregar_segredos()
    assert segredos.gecko_fontes == ("zap", "olx")
    assert problemas_gecko(segredos) == []


def test_gecko_fonte_desconhecida_ignorada(ambiente):
    ambiente.setenv("GECKO_API_KEY", "chave")
    ambiente.setenv("GECKO_FONTES", "zap,vivareal")
    segredos = carregar_segredos()
    assert segredos.gecko_fontes == ("zap",)
    assert problemas_gecko(segredos) == ["GECKO_FONTES: valor desconhecido 'vivareal' ignorado"]


def test_gecko_sem_fontes_nao_reclama_da_chave(ambiente):
    ambiente.setenv("GECKO_FONTES", "")
    segredos = carregar_segredos()
    assert segredos.gecko_fontes == ()
    assert problemas_gecko(segredos) == []


def test_pessoa_so_com_chat_id_e_autorizada_sem_semente(tmp_path):
    config = _carregar(tmp_path, VALIDO + "  - chat_id: 2\n")
    assert config.autorizados == {1: "Heitor", 2: None}
    assert [p.chat_id for p in config.sementes] == [1]
    assert config.problemas == []


def test_entrega_intervalo_padrao(ambiente):
    segredos = carregar_segredos()
    assert segredos.entrega_intervalo == (120, 300)
    assert problemas_entrega(segredos) == []


def test_entrega_intervalo_configurado(ambiente):
    ambiente.setenv("ENTREGA_INTERVALO", " 5-10 ")
    assert carregar_segredos().entrega_intervalo == (5, 10)


@pytest.mark.parametrize("valor", ["300-120", "0-10", "abc", "10-4000", "10"])
def test_entrega_intervalo_invalido_usa_padrao(ambiente, valor):
    ambiente.setenv("ENTREGA_INTERVALO", valor)
    segredos = carregar_segredos()
    assert segredos.entrega_intervalo == (120, 300)
    assert problemas_entrega(segredos) == [f"ENTREGA_INTERVALO inválido '{valor}'; usando 120-300"]


def test_filtros_yaml_na_variavel_tem_prioridade(ambiente, tmp_path):
    ambiente.setenv("FILTROS_PATH", str(tmp_path / "nao-existe.yaml"))
    ambiente.setenv("FILTROS_YAML", textwrap.dedent(VALIDO))
    config = carregar_configuracao(carregar_segredos(), BAIRROS)
    assert config.autorizados == {1: "Heitor"}


def test_sem_variavel_le_o_arquivo(ambiente, tmp_path):
    caminho = tmp_path / "filtros.yaml"
    caminho.write_text(textwrap.dedent(VALIDO), encoding="utf-8")
    ambiente.setenv("FILTROS_PATH", str(caminho))
    assert carregar_configuracao(carregar_segredos(), BAIRROS).operador_chat_id == 1


def test_netimoveis_desligado_por_padrao(ambiente):
    segredos = carregar_segredos()
    assert segredos.netimoveis is False
    assert problemas_netimoveis(segredos) == []


@pytest.mark.parametrize(
    ("valor", "ligado"), [("ligado", True), (" Ligado ", True), ("desligado", False)]
)
def test_netimoveis_ligado_e_desligado(ambiente, valor, ligado):
    ambiente.setenv("NETIMOVEIS", valor)
    segredos = carregar_segredos()
    assert segredos.netimoveis is ligado
    assert problemas_netimoveis(segredos) == []


def test_netimoveis_valor_desconhecido_fica_desligado(ambiente):
    ambiente.setenv("NETIMOVEIS", "talvez")
    segredos = carregar_segredos()
    assert segredos.netimoveis is False
    assert problemas_netimoveis(segredos) == [
        "NETIMOVEIS: valor desconhecido 'talvez'; Netimóveis desligado"
    ]
