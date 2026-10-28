"""Acesso ao MySQL com SQL puro. Funções síncronas: chamar via asyncio.to_thread."""

import json
import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pymysql

from apebot.cadastro import Estado
from apebot.config import Segredos, bairros_validos
from apebot.filtro import filtro_de_json, filtro_para_json
from apebot.fontes.geckoapi import RespostaGecko
from apebot.fontes.resultado import ResultadoFonte
from apebot.modelos import Anuncio, Filtro, Pessoa, Tipo

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

    def semear_pessoas(
        self, autorizados: dict[int, str | None], sementes: Iterable[Pessoa]
    ) -> list[str]:
        """Cria os chats autorizados e grava a semente do arquivo em quem ainda não tem cadastro.

        O nome e os filtros passam a ser da pessoa (research R5 da 003): o arquivo não sobrescreve
        quem já tem cadastro. Devolve os avisos ao operador.
        """
        avisos = []
        momento = agora()
        with self._cursor() as c:
            for chat_id, nome in autorizados.items():
                c.execute(
                    "INSERT IGNORE INTO pessoa (chat_id, nome) VALUES (%s, %s)",
                    (chat_id, nome or str(chat_id)),
                )
            for p in sementes:
                semente = filtro_para_json(p.filtro)
                if filtro_de_json(semente, bairros_validos()) is None:
                    avisos.append(f"{p.nome}: filtros do arquivo fora das regras do cadastro")
                    continue
                c.execute("SELECT filtros FROM pessoa WHERE chat_id = %s", (p.chat_id,))
                (salvo,) = c.fetchone()
                if salvo is None:
                    c.execute(
                        "UPDATE pessoa SET nome = %s, filtros = %s, cadastro_completo_em = %s,"
                        " filtros_atualizados_em = %s WHERE chat_id = %s",
                        (p.nome, json.dumps(semente), momento, momento, p.chat_id),
                    )
                elif json.loads(salvo) != semente:
                    avisos.append(
                        f"{p.nome}: filtros do arquivo ignorados;"
                        " vale o que a pessoa salvou no Telegram"
                    )
        return avisos

    def pessoas_ativas(self, autorizados: Iterable[int]) -> list[Pessoa]:
        """Registradas, com cadastro completo, não pausadas e autorizadas no arquivo."""
        permitidos = set(autorizados)
        with self._cursor() as c:
            c.execute(
                "SELECT chat_id, nome, filtros FROM pessoa WHERE registrada_em IS NOT NULL"
                " AND cadastro_completo_em IS NOT NULL AND pausada_em IS NULL"
            )
            linhas = c.fetchall()
        pessoas = []
        for chat_id, nome, filtros in linhas:
            if chat_id not in permitidos:
                continue
            pessoa = _pessoa(chat_id, nome, filtros)
            if pessoa is None:
                log.warning("filtro_invalido chat_id=%s", chat_id)
            else:
                pessoas.append(pessoa)
        return pessoas

    def pessoa(self, chat_id: int) -> tuple[Pessoa | None, datetime | None, bool]:
        """(pessoa com filtro, pausada_em, cadastro completo) de um chat."""
        with self._cursor() as c:
            c.execute(
                "SELECT nome, filtros, pausada_em, cadastro_completo_em FROM pessoa"
                " WHERE chat_id = %s",
                (chat_id,),
            )
            linha = c.fetchone()
        if linha is None:
            return None, None, False
        nome, filtros, pausada_em, completo_em = linha
        completo = completo_em is not None
        return (_pessoa(chat_id, nome, filtros) if completo else None), pausada_em, completo

    def salvar_filtros(self, chat_id: int, nome: str, filtro: Filtro) -> None:
        momento = agora()
        with self._cursor() as c:
            c.execute(
                "UPDATE pessoa SET nome = %s, filtros = %s, filtros_atualizados_em = %s,"
                " cadastro_completo_em = COALESCE(cadastro_completo_em, %s) WHERE chat_id = %s",
                (nome, json.dumps(filtro_para_json(filtro)), momento, momento, chat_id),
            )

    # conversa do cadastro e da edição ---------------------------------------------------

    def conversa(self, chat_id: int) -> Estado | None:
        with self._cursor() as c:
            c.execute("SELECT modo, etapa, rascunho FROM conversa WHERE chat_id = %s", (chat_id,))
            linha = c.fetchone()
        if linha is None:
            return None
        modo, etapa, rascunho = linha
        return Estado(modo=modo, etapa=etapa, rascunho=json.loads(rascunho))

    def salvar_conversa(self, chat_id: int, estado: Estado) -> None:
        with self._cursor() as c:
            c.execute(
                "INSERT INTO conversa (chat_id, modo, etapa, rascunho, atualizada_em)"
                " VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE modo = VALUES(modo),"
                " etapa = VALUES(etapa), rascunho = VALUES(rascunho),"
                " atualizada_em = VALUES(atualizada_em)",
                (
                    chat_id,
                    estado.modo,
                    estado.etapa,
                    json.dumps(estado.rascunho, ensure_ascii=False),
                    agora(),
                ),
            )

    def apagar_conversa(self, chat_id: int) -> None:
        with self._cursor() as c:
            c.execute("DELETE FROM conversa WHERE chat_id = %s", (chat_id,))

    def registrar_pessoa(self, chat_id: int) -> None:
        with self._cursor() as c:
            c.execute(
                "UPDATE pessoa SET registrada_em = %s WHERE chat_id = %s AND registrada_em IS NULL",
                (agora(), chat_id),
            )

    def pausar(self, chat_id: int) -> None:
        with self._cursor() as c:
            c.execute(
                "UPDATE pessoa SET pausada_em = %s WHERE chat_id = %s AND pausada_em IS NULL",
                (agora(), chat_id),
            )

    def retomar(self, chat_id: int) -> None:
        with self._cursor() as c:
            c.execute(
                "UPDATE pessoa SET pausada_em = NULL WHERE chat_id = %s AND pausada_em IS NOT NULL",
                (chat_id,),
            )

    def pausada_em(self, chat_id: int) -> datetime | None:
        with self._cursor() as c:
            c.execute("SELECT pausada_em FROM pessoa WHERE chat_id = %s", (chat_id,))
            linha = c.fetchone()
            return linha[0] if linha else None

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

    def pendentes_de(self, chat_id: int) -> list[Anuncio]:
        """Imóveis decididos para a pessoa e ainda não entregues (reconciliação, research R3)."""
        with self._cursor() as c:
            c.execute(
                "SELECT a.fonte, a.id_externo, a.tipo, a.bairro, a.bairro_slug, a.quartos,"
                " a.area_m2, a.aluguel_centavos, a.total_centavos, a.url"
                " FROM envio e JOIN anuncio a USING (fonte, id_externo)"
                " WHERE e.chat_id = %s AND e.status = 'pendente'",
                (chat_id,),
            )
            return [_anuncio(linha) for linha in c.fetchall()]

    def apagar_pendente(self, chat_id: int, chave: Chave) -> None:
        """O imóvel volta a ser candidato numa rodada futura (descartado por filtro)."""
        with self._cursor() as c:
            c.execute(
                "DELETE FROM envio WHERE chat_id = %s AND fonte = %s AND id_externo = %s"
                " AND status = 'pendente'",
                (chat_id, *chave),
            )

    def apagar_pendentes(self, chat_id: int) -> None:
        with self._cursor() as c:
            c.execute("DELETE FROM envio WHERE chat_id = %s AND status = 'pendente'", (chat_id,))

    # lembrete de achados (004) ----------------------------------------------------------

    def achados_para(self, chat_id: int, limite_centavos: int) -> list[Anuncio]:
        """Entregues há 32 h ou mais, nunca relembrados, vistos nas últimas 24 h, fora dos
        favoritos e com aluguel até o limite (research R1 da 004)."""
        momento = agora()
        with self._cursor() as c:
            c.execute(
                "SELECT a.fonte, a.id_externo, a.tipo, a.bairro, a.bairro_slug, a.quartos,"
                " a.area_m2, a.aluguel_centavos, a.total_centavos, a.url"
                " FROM envio e JOIN anuncio a USING (fonte, id_externo)"
                " LEFT JOIN favorito f ON f.chat_id = e.chat_id AND f.fonte = e.fonte"
                " AND f.id_externo = e.id_externo"
                " WHERE e.chat_id = %s AND e.status = 'entregue' AND e.lembrado_em IS NULL"
                " AND e.entregue_em <= %s AND a.ultimo_visto_em >= %s"
                " AND a.aluguel_centavos <= %s AND f.chat_id IS NULL",
                (
                    chat_id,
                    momento - timedelta(hours=32),
                    momento - timedelta(hours=24),
                    limite_centavos,
                ),
            )
            return [_anuncio(linha) for linha in c.fetchall()]

    def marcar_lembrado(self, chat_id: int, chaves: Iterable[Chave]) -> None:
        momento = agora()
        with self._cursor() as c:
            for fonte, id_externo in chaves:
                c.execute(
                    "UPDATE envio SET lembrado_em = %s"
                    " WHERE chat_id = %s AND fonte = %s AND id_externo = %s",
                    (momento, chat_id, fonte, id_externo),
                )

    def e_favorito(self, chat_id: int, chave: Chave) -> bool:
        with self._cursor() as c:
            c.execute(
                "SELECT 1 FROM favorito WHERE chat_id = %s AND fonte = %s AND id_externo = %s",
                (chat_id, *chave),
            )
            return c.fetchone() is not None

    # favoritos ----------------------------------------------------------------------------

    def alternar_favorito(self, chat_id: int, chave: Chave) -> bool:
        """Salva ou remove; devolve se ficou salvo. A PK impede favorito duplicado (FR-012)."""
        with self._cursor() as c:
            if c.execute(
                "INSERT IGNORE INTO favorito (chat_id, fonte, id_externo, salvo_em)"
                " VALUES (%s, %s, %s, %s)",
                (chat_id, *chave, agora()),
            ):
                return True
            c.execute(
                "DELETE FROM favorito WHERE chat_id = %s AND fonte = %s AND id_externo = %s",
                (chat_id, *chave),
            )
            return False

    def favoritos(self, chat_id: int) -> list[Anuncio]:
        with self._cursor() as c:
            c.execute(
                "SELECT a.fonte, a.id_externo, a.tipo, a.bairro, a.bairro_slug, a.quartos,"
                " a.area_m2, a.aluguel_centavos, a.total_centavos, a.url"
                " FROM favorito f JOIN anuncio a USING (fonte, id_externo)"
                " WHERE f.chat_id = %s ORDER BY f.salvo_em DESC, f.fonte, f.id_externo",
                (chat_id,),
            )
            return [_anuncio(linha) for linha in c.fetchall()]

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

    def registrar_fonte(self, rodada_id: int, resultado: ResultadoFonte) -> None:
        with self._cursor() as c:
            c.execute(
                "INSERT INTO rodada_fonte (rodada_id, fonte, status, consultas, anuncios_vistos,"
                " descartados, fora_da_cidade, erro_resumo)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    rodada_id,
                    resultado.fonte,
                    resultado.status,
                    resultado.consultas,
                    len(resultado.anuncios),
                    sum(resultado.descartados.values()),
                    resultado.descartados["fora_da_cidade"],
                    (resultado.erro or "")[:500] or None,
                ),
            )

    def seguidas_com_falha(self, fonte: str, n: int = 50) -> int:
        """Rodadas seguidas com falha na fonte, da mais recente para trás (sem 'desligada')."""
        with self._cursor() as c:
            c.execute(
                "SELECT status FROM rodada_fonte WHERE fonte = %s AND status <> 'desligada'"
                " ORDER BY rodada_id DESC LIMIT %s",
                (fonte, n),
            )
            estados = [linha[0] for linha in c.fetchall()]
        return next((i for i, s in enumerate(estados) if s != "falha"), len(estados))

    def alerta_aberto(self, fonte: str) -> tuple[int, datetime] | None:
        """(id, ultimo_aviso_em) do alerta aberto desta fonte, se houver."""
        with self._cursor() as c:
            c.execute(
                "SELECT id, ultimo_aviso_em FROM alerta WHERE fonte = %s AND fechado_em IS NULL"
                " ORDER BY id DESC LIMIT 1",
                (fonte,),
            )
            linha = c.fetchone()
            return (int(linha[0]), linha[1]) if linha else None

    def abrir_alerta(self, fonte: str) -> int:
        momento = agora()
        with self._cursor() as c:
            c.execute(
                "INSERT INTO alerta (fonte, aberto_em, ultimo_aviso_em) VALUES (%s, %s, %s)",
                (fonte, momento, momento),
            )
            return int(c.lastrowid)

    # consultas do /status -------------------------------------------------

    def ultima_rodada(self) -> datetime | None:
        with self._cursor() as c:
            c.execute("SELECT MAX(terminada_em) FROM rodada")
            linha = c.fetchone()
            return linha[0] if linha else None

    def ultima_rodada_iniciada(self) -> datetime | None:
        with self._cursor() as c:
            c.execute("SELECT MAX(iniciada_em) FROM rodada")
            linha = c.fetchone()
            return linha[0] if linha else None

    def estados_fonte(self) -> dict[str, tuple[str, str | None]]:
        """fonte → (status, erro_resumo) da última rodada em que a fonte aparece."""
        with self._cursor() as c:
            c.execute(
                "SELECT rf.fonte, rf.status, rf.erro_resumo FROM rodada_fonte rf"
                " JOIN (SELECT fonte, MAX(rodada_id) AS ultima FROM rodada_fonte GROUP BY fonte) u"
                " ON rf.fonte = u.fonte AND rf.rodada_id = u.ultima"
            )
            return {fonte: (status, erro) for fonte, status, erro in c.fetchall()}

    def recebidos_por_fonte_24h(self, chat_id: int) -> dict[str, int]:
        with self._cursor() as c:
            c.execute(
                "SELECT fonte, COUNT(*) FROM envio"
                " WHERE chat_id = %s AND status = 'entregue' AND entregue_em >= %s"
                " GROUP BY fonte",
                (chat_id, agora() - timedelta(hours=24)),
            )
            return {fonte: int(n) for fonte, n in c.fetchall()}

    def recebidos_24h(self, chat_id: int) -> int:
        return sum(self.recebidos_por_fonte_24h(chat_id).values())

    def registrar_resumo(self, chat_id: int, dia: date) -> bool:
        """True se é o primeiro resumo da pessoa nesse dia (FR-017 da 003)."""
        with self._cursor() as c:
            linhas = c.execute(
                "INSERT IGNORE INTO resumo_diario (chat_id, dia, enviado_em) VALUES (%s, %s, %s)",
                (chat_id, dia, agora()),
            )
        return linhas == 1

    def registrar_aviso(self, alerta_id: int) -> None:
        with self._cursor() as c:
            c.execute("UPDATE alerta SET ultimo_aviso_em = %s WHERE id = %s", (agora(), alerta_id))

    def fechar_alerta(self, alerta_id: int) -> None:
        with self._cursor() as c:
            c.execute("UPDATE alerta SET fechado_em = %s WHERE id = %s", (agora(), alerta_id))


def _pessoa(chat_id: int, nome: str, filtros: str | None) -> Pessoa | None:
    filtro = filtro_de_json(json.loads(filtros), bairros_validos()) if filtros else None
    return Pessoa(chat_id=chat_id, nome=nome, filtro=filtro) if filtro else None


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
