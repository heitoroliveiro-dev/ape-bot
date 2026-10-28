import os
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from apebot.modelos import Filtro, Pessoa, Tipo, slug

FONTES_GECKO = ("zap", "olx")  # constituição 2.2.0: VivaReal excluído


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


@dataclass
class Configuracao:
    operador_chat_id: int
    pessoas: list[Pessoa]
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
        migrations_path=Path(os.environ.get("MIGRATIONS_PATH", "migrations")),
        gecko_api_key=os.environ.get("GECKO_API_KEY", "").strip(),
        **_fontes_gecko(os.environ.get("GECKO_FONTES", "zap")),
    )


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


def bairros_validos() -> frozenset[str]:
    texto = resources.files("apebot").joinpath("dados/bairros_bh.txt").read_text("utf-8")
    return frozenset(linha.strip() for linha in texto.splitlines() if linha.strip())


def carregar_filtros(caminho: Path, bairros: frozenset[str]) -> Configuracao:
    dados = yaml.safe_load(Path(caminho).read_text(encoding="utf-8")) or {}
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
    pessoas = []
    for entrada in entradas:
        pessoa = _pessoa(entrada, bairros, problemas)
        if pessoa is not None:
            pessoas.append(pessoa)
    return Configuracao(operador_chat_id=operador, pessoas=pessoas, problemas=problemas)


def _pessoa(
    entrada: dict[str, Any], bairros: frozenset[str], problemas: list[str]
) -> Pessoa | None:
    nome = str(entrada.get("nome") or entrada["chat_id"])
    filtros = entrada.get("filtros") or {}

    aluguel_max = filtros.get("aluguel_max")
    if not _inteiro(aluguel_max) or aluguel_max <= 0:
        problemas.append(f"{nome}: aluguel_max inválido ({aluguel_max!r}); pessoa ignorada")
        return None
    quartos_min = filtros.get("quartos_min", 0)
    if not _inteiro(quartos_min) or quartos_min < 0:
        problemas.append(f"{nome}: quartos_min inválido ({quartos_min!r}); pessoa ignorada")
        return None

    slugs = set()
    for bairro in filtros.get("bairros") or []:
        if slug(str(bairro)) in bairros:
            slugs.add(slug(str(bairro)))
        else:
            problemas.append(f"{nome}: bairro não reconhecido '{bairro}', ignorado")
    if not slugs:
        problemas.append(f"{nome}: nenhum bairro válido; pessoa ignorada")
        return None

    tipos = set()
    for tipo in filtros.get("tipos") or []:
        try:
            tipos.add(Tipo(str(tipo)))
        except ValueError:
            problemas.append(f"{nome}: tipo inválido '{tipo}', ignorado")
    if not tipos:
        problemas.append(f"{nome}: nenhum tipo válido; pessoa ignorada")
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
