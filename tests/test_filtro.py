from dataclasses import replace

from apebot.filtro import aceita, hash_filtros, novos_para
from apebot.modelos import Anuncio, Filtro, Pessoa, Tipo

FILTRO = Filtro(
    bairros=frozenset({"buritis", "funcionarios"}),
    aluguel_max_centavos=300_000,
    quartos_min=2,
    tipos=frozenset({Tipo.APARTAMENTO}),
)

ANUNCIO = Anuncio(
    fonte="quintoandar",
    id_externo="1",
    tipo=Tipo.APARTAMENTO,
    bairro="Buritis",
    bairro_slug="buritis",
    quartos=2,
    area_m2=70,
    aluguel_centavos=300_000,
    total_centavos=420_000,
    url="https://www.quintoandar.com.br/imovel/1",
)


def test_aceita_quando_todos_os_criterios_batem():
    assert aceita(FILTRO, ANUNCIO)


def test_rejeita_aluguel_acima_do_maximo():
    assert not aceita(FILTRO, replace(ANUNCIO, aluguel_centavos=310_000))


def test_ignora_custo_total_na_comparacao():
    assert aceita(FILTRO, replace(ANUNCIO, total_centavos=900_000))


def test_rejeita_menos_quartos():
    assert not aceita(FILTRO, replace(ANUNCIO, quartos=1))


def test_rejeita_tipo_nao_aceito():
    assert not aceita(FILTRO, replace(ANUNCIO, tipo=Tipo.CASA))


def test_rejeita_bairro_fora_do_filtro():
    assert not aceita(FILTRO, replace(ANUNCIO, bairro="Sion", bairro_slug="sion"))


def test_novos_para_seleciona_e_exclui_ja_enviados():
    anuncios = [
        ANUNCIO,
        replace(ANUNCIO, id_externo="2"),
        replace(ANUNCIO, id_externo="3", aluguel_centavos=310_000),
        replace(ANUNCIO, id_externo="4", quartos=1),
        replace(ANUNCIO, id_externo="5"),
    ]
    pessoa = Pessoa(1, "Heitor", FILTRO)
    novos = novos_para(pessoa, anuncios, ja_enviados={("quintoandar", "2")})
    assert [a.id_externo for a in novos] == ["1", "5"]


def test_novos_para_nao_repete_anuncio_duplicado_na_rodada():
    pessoa = Pessoa(1, "Heitor", FILTRO)
    assert len(novos_para(pessoa, [ANUNCIO, ANUNCIO], ja_enviados=set())) == 1


def test_pessoas_com_filtros_diferentes_recebem_conjuntos_diferentes():
    casa = replace(ANUNCIO, id_externo="9", tipo=Tipo.CASA)
    heitor = Pessoa(1, "Heitor", FILTRO)
    ana = Pessoa(2, "Ana", replace(FILTRO, tipos=frozenset({Tipo.CASA})))
    assert [a.id_externo for a in novos_para(heitor, [ANUNCIO, casa], set())] == ["1"]
    assert [a.id_externo for a in novos_para(ana, [ANUNCIO, casa], set())] == ["9"]


def test_hash_filtros_estavel_e_sensivel_a_mudancas():
    mesmo = Filtro(
        bairros=frozenset({"funcionarios", "buritis"}),
        aluguel_max_centavos=300_000,
        quartos_min=2,
        tipos=frozenset({Tipo.APARTAMENTO}),
    )
    assert hash_filtros(FILTRO) == hash_filtros(mesmo)
    assert len(hash_filtros(FILTRO)) == 64
    for alterado in (
        replace(FILTRO, bairros=frozenset({"buritis"})),
        replace(FILTRO, aluguel_max_centavos=300_100),
        replace(FILTRO, quartos_min=3),
        replace(FILTRO, tipos=frozenset({Tipo.APARTAMENTO, Tipo.CASA})),
    ):
        assert hash_filtros(alterado) != hash_filtros(FILTRO)
