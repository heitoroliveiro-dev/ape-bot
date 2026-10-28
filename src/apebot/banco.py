"""Acesso ao MySQL com SQL puro. Funções síncronas: chamar via asyncio.to_thread."""

import json
import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pymysql

from apebot.config import Segredos
from apebot.fontes.geckoapi import RespostaGecko
from apebot.modelos import Anuncio, Pessoa, Tipo

log = logging.getLogger(__name__)

Chave = tuple[str, str]


def agora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None, microsecond=0)


class Banco:
    def __init__(self, segredos: Segredos) -> None:
        self._parametros = dict(
            host=segredos.mysql_host,
            port=segredos.mysql_port,
            user=segredos.mysql_user,
            password=segredos.mysql_password,
            database=segredos.mysql_database,
            charset="utf8mb4",
            autocommit=True,
        )

    @contextmanager
    def _cursor(self) -> Iterator[pymysql.cursors.Cursor]:
        conexao = pymysql.connect(**self._parametros)
        try:
            with conexao.cursor() as cursor:
                yield cursor
        finally:
            conexao.close()

    # migrações -------------------------------------------------------------

    def aplicar_migracoes(self, pasta: Path) -> list[str]:
        with self._cursor() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS schema_migracao ("
                " versao VARCHAR(40) PRIMARY KEY, aplicada_em DATETIME NOT NULL)"
            )
            c.execute("SELECT versao FROM schema_migracao")
            aplicadas = {linha[0] for linha in c.fetchall()}
            novas = []
            for arquivo in sorted(Path(pasta).glob("[0-9][0-9][0-9]_*.sql")):
                versao = arquivo.stem
                if versao in aplicadas:
                    continue
                for comando in arquivo.read_text(encoding="utf-8").split(";"):
                    if comando.strip():
                        c.execute(comando)
                c.execute(
                    "INSERT INTO schema_migracao (versao, aplicada_em) VALUES (%s, %s)",
                    (versao, agora()),
                )
                novas.append(versao)
        return novas

    # pessoas ---------------------------------------------------------------

    def sincronizar_pessoas(self, pessoas: Iterable[Pessoa]) -> None:
        with self._cursor() as c:
            for p in pessoas:
                c.execute(
                    "INSERT INTO pessoa (chat_id, nome) VALUES (%s, %s)"
                    " ON DUPLICATE KEY UPDATE nome = VALUES(nome)",
                    (p.chat_id, p.nome),
                )

    def registrar_pessoa(self, chat_id: int) -> None:
        with self._cursor() as c:
            c.execute(
                "UPDATE pessoa SET registrada_em = %s WHERE chat_id = %s AND registrada_em IS NULL",
                (agora(), chat_id),
            )

    def pessoas_registradas(self) -> dict[int, str | None]:
        """chat_id → filtros_hash das pessoas que já enviaram /start."""
        with self._cursor() as c:
            c.execute("SELECT chat_id, filtros_hash FROM pessoa WHERE registrada_em IS NOT NULL")
            return {chat_id: filtros_hash for chat_id, filtros_hash in c.fetchall()}

    def atualizar_filtros_hash(self, chat_id: int, filtros_hash: str) -> None:
        with self._cursor() as c:
            c.execute(
                "UPDATE pessoa SET filtros_hash = %s WHERE chat_id = %s", (filtros_hash, chat_id)
            )

    # anúncios --------------------------------------------------------------

    def salvar_anuncios(self, anuncios: Iterable[Anuncio]) -> int:
        """Insere ou atualiza; devolve quantos anúncios eram inéditos."""
        momento = agora()
        novos = 0
        with self._cursor() as c:
            for a in anuncios:
                linhas = c.execute(
                    "INSERT INTO anuncio (fonte, id_externo, tipo, bairro, bairro_slug, quartos,"
                    " area_m2, aluguel_centavos, total_centavos, url,"
                    " primeiro_visto_em, ultimo_visto_em)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    " ON DUPLICATE KEY UPDATE aluguel_centavos = VALUES(aluguel_centavos),"
                    " total_centavos = VALUES(total_centavos),"
                    " ultimo_visto_em = VALUES(ultimo_visto_em)",
                    (
                        a.fonte,
                        a.id_externo,
                        a.tipo.value,
                        a.bairro,
                        a.bairro_slug,
                        a.quartos,
                        a.area_m2,
                        a.aluguel_centavos,
                        a.total_centavos,
                        a.url,
                        momento,
                        momento,
                    ),
                )
                if linhas == 1:
                    novos += 1
        return novos

    # respostas de fonte ----------------------------------------------------

    def salvar_resposta(self, resposta: RespostaGecko) -> bool:
        """Guarda a resposta bruta (já sem anunciante); False se o request_id já existia."""
        with self._cursor() as c:
            linhas = c.execute(
                "INSERT IGNORE INTO resposta_fonte (fonte, request_id, url, extraida_em,"
                " total_resultados, itens, corpo, recebida_em)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    resposta.fonte,
                    resposta.request_id,
                    resposta.url[:500],
                    resposta.extraida_em,
                    resposta.total_resultados,
                    resposta.itens,
                    json.dumps(resposta.corpo, ensure_ascii=False),
                    agora(),
                ),
            )
        return linhas == 1

    # envios ----------------------------------------------------------------

    def ja_enviados(self, chat_id: int) -> set[Chave]:
        with self._cursor() as c:
            c.execute("SELECT fonte, id_externo FROM envio WHERE chat_id = %s", (chat_id,))
            return {(fonte, id_externo) for fonte, id_externo in c.fetchall()}

    def criar_envios_pendentes(self, chat_id: int, chaves: Iterable[Chave]) -> list[Chave]:
        """Cria envios 'pendente'; devolve só os que não existiam (idempotente)."""
        inseridas = []
        momento = agora()
        with self._cursor() as c:
            for fonte, id_externo in chaves:
                linhas = c.execute(
                    "INSERT IGNORE INTO envio (chat_id, fonte, id_externo, criado_em)"
                    " VALUES (%s, %s, %s, %s)",
                    (chat_id, fonte, id_externo, momento),
                )
                if linhas:
                    inseridas.append((fonte, id_externo))
        return inseridas

    def marcar_envio(self, chat_id: int, chaves: Iterable[Chave], status: str) -> None:
        entregue_em = agora() if status == "entregue" else None
        with self._cursor() as c:
            for fonte, id_externo in chaves:
                c.execute(
                    "UPDATE envio SET status = %s, entregue_em = %s, tentativas = tentativas + 1"
                    " WHERE chat_id = %s AND fonte = %s AND id_externo = %s",
                    (status, entregue_em, chat_id, fonte, id_externo),
                )

    def pendentes_antigos(self, minutos: int) -> list[tuple[int, Anuncio]]:
        limite = agora() - timedelta(minutes=minutos)
        with self._cursor() as c:
            c.execute(
                "SELECT e.chat_id, a.fonte, a.id_externo, a.tipo, a.bairro, a.bairro_slug,"
                " a.quartos, a.area_m2, a.aluguel_centavos, a.total_centavos, a.url"
                " FROM envio e JOIN anuncio a USING (fonte, id_externo)"
                " WHERE e.status = 'pendente' AND e.criado_em < %s",
                (limite,),
            )
            return [(linha[0], _anuncio(linha[1:])) for linha in c.fetchall()]

    # rodadas e alertas -----------------------------------------------------

    def iniciar_rodada(self) -> int:
        with self._cursor() as c:
            c.execute("INSERT INTO rodada (iniciada_em) VALUES (%s)", (agora(),))
            return int(c.lastrowid)

    def finalizar_rodada(
        self, rodada_id: int, status: str, contagens: dict[str, int], erro_resumo: str | None
    ) -> None:
        with self._cursor() as c:
            c.execute(
                "UPDATE rodada SET terminada_em = %s, status = %s, paginas_ok = %s,"
                " paginas_erro = %s, anuncios_vistos = %s, anuncios_novos = %s,"
                " descartados = %s, enfileirados = %s, erro_resumo = %s WHERE id = %s",
                (
                    agora(),
                    status,
                    contagens.get("paginas_ok", 0),
                    contagens.get("paginas_erro", 0),
                    contagens.get("anuncios_vistos", 0),
                    contagens.get("anuncios_novos", 0),
                    contagens.get("descartados", 0),
                    contagens.get("enfileirados", 0),
                    (erro_resumo or "")[:500] or None,
                    rodada_id,
                ),
            )

    def ultimas_rodadas(self, n: int) -> list[tuple[str, str | None]]:
        """(status, erro_resumo) das n últimas rodadas terminadas, mais recente primeiro."""
        with self._cursor() as c:
            c.execute(
                "SELECT status, erro_resumo FROM rodada WHERE status IS NOT NULL"
                " ORDER BY id DESC LIMIT %s",
                (n,),
            )
            return list(c.fetchall())

    def alerta_aberto(self) -> tuple[int, datetime] | None:
        """(id, ultimo_aviso_em) do alerta aberto, se houver."""
        with self._cursor() as c:
            c.execute(
                "SELECT id, ultimo_aviso_em FROM alerta WHERE fechado_em IS NULL"
                " ORDER BY id DESC LIMIT 1"
            )
            linha = c.fetchone()
            return (int(linha[0]), linha[1]) if linha else None

    def abrir_alerta(self) -> int:
        momento = agora()
        with self._cursor() as c:
            c.execute(
                "INSERT INTO alerta (aberto_em, ultimo_aviso_em) VALUES (%s, %s)",
                (momento, momento),
            )
            return int(c.lastrowid)

    def registrar_aviso(self, alerta_id: int) -> None:
        with self._cursor() as c:
            c.execute("UPDATE alerta SET ultimo_aviso_em = %s WHERE id = %s", (agora(), alerta_id))

    def fechar_alerta(self, alerta_id: int) -> None:
        with self._cursor() as c:
            c.execute("UPDATE alerta SET fechado_em = %s WHERE id = %s", (agora(), alerta_id))


def _anuncio(linha: tuple) -> Anuncio:
    fonte, id_externo, tipo, bairro, bairro_slug, quartos, area, aluguel, total, url = linha
    return Anuncio(
        fonte=fonte,
        id_externo=id_externo,
        tipo=Tipo(tipo),
        bairro=bairro,
        bairro_slug=bairro_slug,
        quartos=quartos,
        area_m2=area,
        aluguel_centavos=aluguel,
        total_centavos=total,
        url=url,
    )
