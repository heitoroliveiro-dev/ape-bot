import csv
import io
import os
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from apebot.modelos import REGIONAIS, Bairro, Filtro, Pessoa, Tipo, slug

FONTES_GECKO = ("zap", "olx")  # constituição 2.2.0: VivaReal excluído
ENTREGA_INTERVALO_PADRAO = (120, 300)  # segundos entre dois imóveis da mesma pessoa


class ConfiguracaoInvalida(Exception):
    """Erro no filtros.yaml que impede o robô de subir."""


@dataclass(frozen=True)
class Segredos:
    telegram_token: str
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str
    redis_url: str
    filtros_path: Path
    migrations_path: Path
    gecko_api_key: str = ""
    gecko_fontes: tuple[str, ...] = ()
    gecko_fontes_desconhecidas: tuple[str, ...] = ()
    entrega_intervalo: tuple[int, int] = ENTREGA_INTERVALO_PADRAO
    entrega_intervalo_invalido: str | None = None
    filtros_yaml: str = ""  # conteúdo do filtros.yaml (Railway, sem arquivo montado)


@dataclass
class Configuracao:
    """filtros.yaml: quem é autorizado e, para quem ainda não tem cadastro, os filtros iniciais."""

    operador_chat_id: int
    autorizados: dict[int, str | None]  # chat_id → nome no arquivo
    sementes: list[Pessoa] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)


def carregar_segredos() -> Segredos:
    def obrigatoria(nome: str) -> str:
        valor = os.environ.get(nome, "")
        if not valor:
            raise ConfiguracaoInvalida(f"variável de ambiente {nome} não definida")
        return valor

    return Segredos(
        telegram_token=obrigatoria("TELEGRAM_TOKEN"),
        mysql_host=os.environ.get("MYSQL_HOST", "mysql"),
        mysql_port=int(os.environ.get("MYSQL_PORT", "3306")),
        mysql_database=os.environ.get("MYSQL_DATABASE", "apebot"),
        mysql_user=obrigatoria("MYSQL_USER"),
        mysql_password=obrigatoria("MYSQL_PASSWORD"),
        redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        filtros_path=Path(os.environ.get("FILTROS_PATH", "filtros.yaml")),
        filtros_yaml=os.environ.get("FILTROS_YAML", ""),
        migrations_path=Path(os.environ.get("MIGRATIONS_PATH", "migrations")),
        gecko_api_key=os.environ.get("GECKO_API_KEY", "").strip(),
        **_fontes_gecko(os.environ.get("GECKO_FONTES", "zap")),
        **_entrega_intervalo(os.environ.get("ENTREGA_INTERVALO")),
    )


def _entrega_intervalo(texto: str | None) -> dict[str, Any]:
    if texto is None:
        return {}
    minimo, _, maximo = texto.strip().partition("-")
    if minimo.isdigit() and maximo.isdigit() and 1 <= int(minimo) <= int(maximo) <= 3600:
        return {"entrega_intervalo": (int(minimo), int(maximo))}
    return {"entrega_intervalo_invalido": texto}


def _fontes_gecko(texto: str) -> dict[str, tuple[str, ...]]:
    pedidas = [f.strip().lower() for f in texto.split(",") if f.strip()]
    return {
        "gecko_fontes": tuple(f for f in dict.fromkeys(pedidas) if f in FONTES_GECKO),
        "gecko_fontes_desconhecidas": tuple(f for f in pedidas if f not in FONTES_GECKO),
    }


def problemas_gecko(segredos: Segredos) -> list[str]:
    """Avisos ao operador na inicialização sobre a configuração das fontes pagas."""
    problemas = [
        f"GECKO_FONTES: valor desconhecido '{f}' ignorado"
        for f in segredos.gecko_fontes_desconhecidas
    ]
    if segredos.gecko_fontes and not segredos.gecko_api_key:
        problemas.append("GECKO_API_KEY ausente: Zap/OLX desligados")
    return problemas


def problemas_entrega(segredos: Segredos) -> list[str]:
    if segredos.entrega_intervalo_invalido is None:
        return []
    minimo, maximo = ENTREGA_INTERVALO_PADRAO
    return [
        f"ENTREGA_INTERVALO inválido '{segredos.entrega_intervalo_invalido}';"
        f" usando {minimo}-{maximo}"
    ]


def _ler_catalogo(texto: str) -> tuple[Bairro, ...]:
    bairros = tuple(
        Bairro(slug=linha["slug"], nome=linha["nome"], regional=linha["regional"])
        for linha in csv.DictReader(io.StringIO(texto))
    )
    vistos: set[str] = set()
    for bairro in bairros:
        if bairro.slug in vistos:
            raise ValueError(f"bairro repetido no catálogo: {bairro.slug}")
        if bairro.regional not in REGIONAIS:
            raise ValueError(f"regional desconhecida para {bairro.slug}: {bairro.regional}")
        vistos.add(bairro.slug)
    return bairros


@cache
def catalogo_bairros() -> tuple[Bairro, ...]:
    """dados/bairros_bh.csv: slug do QuintoAndar, nome oficial e regional (research R9 da 003)."""
    texto = resources.files("apebot").joinpath("dados/bairros_bh.csv").read_text("utf-8")
    return _ler_catalogo(texto)


@cache
def bairros_validos() -> frozenset[str]:
    return frozenset(b.slug for b in catalogo_bairros())


@cache
def _nomes() -> dict[str, str]:
    return {b.slug: b.nome for b in catalogo_bairros()}


def nome_bairro(bairro_slug: str) -> str:
    return _nomes().get(bairro_slug) or bairro_slug.replace("-", " ").title()


def carregar_configuracao(segredos: Segredos, bairros: frozenset[str]) -> Configuracao:
    """FILTROS_YAML (conteúdo, para o Railway) tem prioridade sobre o arquivo em FILTROS_PATH."""
    if segredos.filtros_yaml.strip():
        return ler_filtros(segredos.filtros_yaml, bairros)
    return carregar_filtros(segredos.filtros_path, bairros)


def carregar_filtros(caminho: Path, bairros: frozenset[str]) -> Configuracao:
    return ler_filtros(Path(caminho).read_text(encoding="utf-8"), bairros)


def ler_filtros(texto: str, bairros: frozenset[str]) -> Configuracao:
    dados = yaml.safe_load(texto) or {}
    operador = dados.get("operador_chat_id")
    entradas = dados.get("pessoas") or []

    if not isinstance(operador, int):
        raise ConfiguracaoInvalida("operador_chat_id ausente ou não é inteiro")
    chat_ids = [e.get("chat_id") for e in entradas]
    if not all(isinstance(c, int) for c in chat_ids):
        raise ConfiguracaoInvalida("todo chat_id precisa ser inteiro")
    if len(set(chat_ids)) != len(chat_ids):
        raise ConfiguracaoInvalida("chat_id repetido em pessoas")
    if operador not in chat_ids:
        raise ConfiguracaoInvalida("operador_chat_id precisa estar em pessoas")

    problemas: list[str] = []
    autorizados = {e["chat_id"]: (str(e["nome"]) if e.get("nome") else None) for e in entradas}
    sementes = []
    for entrada in entradas:
        if not entrada.get("filtros"):
            continue  # só autorizada: faz o cadastro pelo /start
        pessoa = _pessoa(entrada, bairros, problemas)
        if pessoa is not None:
            sementes.append(pessoa)
    return Configuracao(
        operador_chat_id=operador, autorizados=autorizados, sementes=sementes, problemas=problemas
    )


def _pessoa(
    entrada: dict[str, Any], bairros: frozenset[str], problemas: list[str]
) -> Pessoa | None:
    nome = str(entrada.get("nome") or entrada["chat_id"])
    filtros = entrada.get("filtros") or {}

    aluguel_max = filtros.get("aluguel_max")
    if not _inteiro(aluguel_max) or aluguel_max <= 0:
        problemas.append(
            f"{nome}: aluguel_max inválido ({aluguel_max!r}); filtros do arquivo ignorados"
        )
        return None
    quartos_min = filtros.get("quartos_min", 0)
    if not _inteiro(quartos_min) or quartos_min < 0:
        problemas.append(
            f"{nome}: quartos_min inválido ({quartos_min!r}); filtros do arquivo ignorados"
        )
        return None

    slugs = set()
    for bairro in filtros.get("bairros") or []:
        if slug(str(bairro)) in bairros:
            slugs.add(slug(str(bairro)))
        else:
            problemas.append(f"{nome}: bairro não reconhecido '{bairro}', ignorado")
    if not slugs:
        problemas.append(f"{nome}: nenhum bairro válido; filtros do arquivo ignorados")
        return None

    tipos = set()
    for tipo in filtros.get("tipos") or []:
        try:
            tipos.add(Tipo(str(tipo)))
        except ValueError:
            problemas.append(f"{nome}: tipo inválido '{tipo}', ignorado")
    if not tipos:
        problemas.append(f"{nome}: nenhum tipo válido; filtros do arquivo ignorados")
        return None

    return Pessoa(
        chat_id=entrada["chat_id"],
        nome=nome,
        filtro=Filtro(
            bairros=frozenset(slugs),
            aluguel_max_centavos=aluguel_max * 100,
            quartos_min=quartos_min,
            tipos=frozenset(tipos),
        ),
    )


def _inteiro(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)
