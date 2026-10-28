"""Resultado comum das fontes e as travas que valem para todas (research R5–R8 da 002)."""

import re
from collections import Counter
from dataclasses import dataclass, field

from apebot.modelos import Anuncio, Contato, slug

Chave = tuple[str, str]

CIDADES_BH = frozenset({"belo-horizonte", "bh"})
UFS_MG = frozenset({"mg", "minas-gerais"})


@dataclass
class ResultadoFonte:
    fonte: str
    status: str = "ok"  # ok | falha | desligada | sem_credito
    anuncios: list[Anuncio] = field(default_factory=list)
    contatos: dict[Chave, Contato] = field(default_factory=dict)
    descartados: Counter[str] = field(default_factory=Counter)
    consultas: int = 0
    consultas_erro: int = 0
    erro: str | None = None
    erro_de_formato: bool = False
    aviso_operador: str | None = None  # enviado na hora (ex.: falta de crédito)


def status_rodada(paginas_ok: int, paginas_erro: int, erro_de_formato: bool) -> str:
    if erro_de_formato:
        return "falha"
    total = paginas_ok + paginas_erro
    if total and paginas_erro * 2 >= total:
        return "falha"
    return "ok"


def na_cidade(cidade: str | None, uf: str | None) -> bool:
    return slug(cidade or "") in CIDADES_BH and slug(uf or "") in UFS_MG


def bairro_do_catalogo(nome: str | None, catalogo: frozenset[str]) -> str | None:
    """Slug do catálogo de BH para o bairro do portal, aceitando o sufixo de região."""
    procurado = slug(nome or "")
    if not procurado:
        return None
    if procurado in catalogo:
        return procurado
    candidatos = [b for b in catalogo if b.startswith(procurado + "-")]
    return candidatos[0] if len(candidatos) == 1 else None


def _numero_nacional(numero: str | None) -> str | None:
    """DDD + número (10 ou 11 dígitos) de um telefone brasileiro válido; senão None."""
    digitos = re.sub(r"\D", "", numero or "")
    if len(digitos) in (12, 13) and digitos.startswith("55"):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        return None
    ddd, assinante = digitos[:2], digitos[2:]
    if "0" in ddd:
        return None
    if len(assinante) == 9 and assinante[0] != "9":
        return None
    if len(assinante) == 8 and assinante[0] not in "2345":
        return None
    return digitos


def whatsapp_url(numero: str | None) -> str | None:
    nacional = _numero_nacional(numero)
    return f"https://wa.me/55{nacional}" if nacional else None


def telefone_legivel(numero: str) -> str:
    nacional = _numero_nacional(numero)
    if nacional is None:
        return numero
    ddd, assinante = nacional[:2], nacional[2:]
    return f"({ddd}) {assinante[:-4]}-{assinante[-4:]}"
