"""Filas no Redis: a de entrega ao Telegram (RPUSH / BLPOP) e a de imóveis de cada pessoa.

A fila da pessoa (research R1 da 003) guarda o imóvel e o contato do anunciante até o despacho,
ordenada pelo aluguel. O contato só existe aqui e na fila de entrega (constituição III).
"""

import json
from dataclasses import asdict, dataclass, field

import redis.asyncio as redis

from apebot.modelos import Anuncio, Contato, Tipo

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

    async def chaves_em_entrega(self) -> set[tuple[int, str, str]]:
        """(chat_id, fonte, id_externo) dos imóveis que já saíram da fila da pessoa."""
        chaves = set()
        for bruto in await self._redis.lrange(CHAVE_FILA, 0, -1):
            mensagem = Mensagem.de_json(bruto)
            if mensagem.tipo == "imovel":
                chaves.update((mensagem.chat_id, *chave) for chave in mensagem.anuncio_ids)
        return chaves

    async def fechar(self) -> None:
        await self._redis.aclose()


def _membro(chave: tuple[str, str]) -> str:
    return f"{chave[0]}|{chave[1]}"


def _imovel_json(anuncio: Anuncio, contato: Contato | None, lembrete: bool) -> str:
    dados = {
        "anuncio": asdict(anuncio) | {"tipo": anuncio.tipo.value},
        "contato": asdict(contato) if contato else None,
        "lembrete": lembrete,
    }
    return json.dumps(dados, ensure_ascii=False)


ImovelNaFila = tuple[Anuncio, Contato | None, bool]  # anúncio, contato em trânsito, é lembrete


def _imovel_de_json(bruto: str | bytes) -> ImovelNaFila:
    dados = json.loads(bruto)
    anuncio = Anuncio(**(dados["anuncio"] | {"tipo": Tipo(dados["anuncio"]["tipo"])}))
    contato = Contato(**dados["contato"]) if dados.get("contato") else None
    return anuncio, contato, bool(dados.get("lembrete"))


class FilaPessoa:
    """Imóveis à espera de cada pessoa, do mais barato para o mais caro (data-model.md da 003)."""

    def __init__(self, fila: Fila) -> None:
        self._redis = fila._redis

    @staticmethod
    def _chaves(chat_id: int) -> tuple[str, str, str]:
        base = f"apebot:pessoa:{chat_id}"
        return f"{base}:fila", f"{base}:imoveis", f"{base}:proximo"

    async def adicionar(
        self,
        chat_id: int,
        anuncio: Anuncio,
        contato: Contato | None = None,
        lembrete: bool = False,
    ) -> bool:
        fila, imoveis, _ = self._chaves(chat_id)
        membro = _membro(anuncio.chave)
        await self._redis.hsetnx(imoveis, membro, _imovel_json(anuncio, contato, lembrete))
        return bool(await self._redis.zadd(fila, {membro: anuncio.aluguel_centavos}, nx=True))

    async def retirar_mais_barato(self, chat_id: int) -> ImovelNaFila | None:
        fila, imoveis, _ = self._chaves(chat_id)
        while retirado := await self._redis.zpopmin(fila):
            membro = retirado[0][0]
            bruto = await self._redis.hget(imoveis, membro)
            await self._redis.hdel(imoveis, membro)
            if bruto is not None:
                return _imovel_de_json(bruto)
        return None

    async def membros(self, chat_id: int) -> set[tuple[str, str]]:
        fila, _, _ = self._chaves(chat_id)
        brutos = await self._redis.zrange(fila, 0, -1)
        membros = (b.decode() if isinstance(b, bytes) else b for b in brutos)
        return {tuple(m.split("|", 1)) for m in membros}

    async def tamanho(self, chat_id: int) -> int:
        return int(await self._redis.zcard(self._chaves(chat_id)[0]))

    async def limpar(self, chat_id: int) -> None:
        await self._redis.delete(*self._chaves(chat_id))

    async def proximo(self, chat_id: int) -> float | None:
        valor = await self._redis.get(self._chaves(chat_id)[2])
        return float(valor) if valor is not None else None

    async def marcar_proximo(self, chat_id: int, epoch: float) -> None:
        await self._redis.set(self._chaves(chat_id)[2], f"{epoch:.0f}")
