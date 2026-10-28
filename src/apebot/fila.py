"""Fila de mensagens para o Telegram, em Redis (RPUSH / BLPOP)."""

import json
from dataclasses import asdict, dataclass, field

import redis.asyncio as redis

CHAVE_FILA = "apebot:envios"
TIMEOUT_CONSUMO_SEGUNDOS = 5
# Precisa ser maior que a espera do BLPOP; senão o cliente desiste antes do servidor responder.
SOCKET_TIMEOUT_SEGUNDOS = 15


@dataclass
class Mensagem:
    chat_id: int
    tipo: str  # imovel | resumo | operador | texto
    texto: str
    anuncio_ids: list[tuple[str, str]] = field(default_factory=list)
    tentativas: int = 0
    # linhas de botões: {"t": rótulo, "u": url} ou {"t": rótulo, "c": callback_data}
    botoes: list[list[dict[str, str]]] = field(default_factory=list)

    def para_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def de_json(cls, bruto: str | bytes) -> "Mensagem":
        dados = json.loads(bruto)
        dados["anuncio_ids"] = [tuple(chave) for chave in dados.get("anuncio_ids", [])]
        return cls(**dados)


class Fila:
    def __init__(self, url: str) -> None:
        self._redis = redis.from_url(
            url, socket_timeout=SOCKET_TIMEOUT_SEGUNDOS, health_check_interval=30
        )

    async def enfileirar(self, mensagem: Mensagem) -> None:
        await self._redis.rpush(CHAVE_FILA, mensagem.para_json())

    async def enfileirar_no_inicio(self, mensagem: Mensagem) -> None:
        await self._redis.lpush(CHAVE_FILA, mensagem.para_json())

    async def consumir(self, timeout: int = TIMEOUT_CONSUMO_SEGUNDOS) -> Mensagem | None:
        item = await self._redis.blpop([CHAVE_FILA], timeout=timeout)
        return Mensagem.de_json(item[1]) if item else None

    async def tamanho(self) -> int:
        return int(await self._redis.llen(CHAVE_FILA))

    async def fechar(self) -> None:
        await self._redis.aclose()
