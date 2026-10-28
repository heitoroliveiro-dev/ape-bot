"""Respostas da GeckoAPI (constituição 2.1.0, exceção do princípio III).

Guarda a resposta de listagem sem os dados de anunciante, que o princípio III proíbe armazenar.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# Chaves com dados de anunciante (nome, telefone, e-mail) em qualquer nível da resposta.
CHAVES_DE_ANUNCIANTE = frozenset(
    {
        "advertiser",
        "seller",
        "sellerName",
        "sellerId",
        "phone",
        "phones",
        "phoneNumbers",
        "whatsAppNumber",
        "email",
        "contact",
        "contacts",
        "account",
    }
)


class RespostaInvalida(Exception):
    """O JSON não tem o formato de resposta da GeckoAPI."""


@dataclass(frozen=True)
class RespostaGecko:
    fonte: str
    request_id: str
    url: str
    extraida_em: datetime
    total_resultados: int | None
    itens: int
    corpo: dict[str, Any]


def sem_anunciante(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {
            chave: sem_anunciante(item)
            for chave, item in valor.items()
            if chave not in CHAVES_DE_ANUNCIANTE
        }
    if isinstance(valor, list):
        return [sem_anunciante(item) for item in valor]
    return valor


def ler_resposta(texto: str) -> RespostaGecko:
    try:
        corpo = json.loads(texto)
        dados = corpo["data"]
        request_id = str(corpo["requestId"])
        fonte = str(dados["source"])
        url = str(dados["url"])
        itens = dados["items"]
        extraida_em = datetime.fromisoformat(dados["extractedAt"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as erro:
        raise RespostaInvalida(f"formato inesperado: {erro!r}") from erro
    if not isinstance(itens, list):
        raise RespostaInvalida("data.items não é lista")

    total = dados.get("totalResults")
    return RespostaGecko(
        fonte=fonte,
        request_id=request_id,
        url=url,
        extraida_em=extraida_em.astimezone(UTC).replace(tzinfo=None, microsecond=0),
        total_resultados=total if isinstance(total, int) else None,
        itens=len(itens),
        corpo=sem_anunciante(corpo),
    )
