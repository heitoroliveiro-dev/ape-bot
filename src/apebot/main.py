"""Composição e ponto de entrada: python -m apebot.main [--rodada-agora [--simular-falha]]."""

import argparse
import asyncio
import logging
import time
from datetime import datetime
from functools import partial

from telegram.ext import Application

from apebot.banco import Banco
from apebot.config import (
    Configuracao,
    Segredos,
    bairros_validos,
    carregar_configuracao,
    carregar_segredos,
    problemas_entrega,
    problemas_gecko,
    problemas_netimoveis,
)
from apebot.fila import Fila, FilaPessoa, Mensagem
from apebot.fontes import netimoveis, olx, quintoandar, zap
from apebot.fontes.geckoapi import ClienteGecko
from apebot.fontes.resultado import ResultadoFonte
from apebot.mensagens import COMANDOS, aviso_configuracao
from apebot.modelos import FUSO, HORARIOS_RODADA, Pessoa
from apebot.rodada import Coletor, Rodada, enviar_resumos, rodada_devida
from apebot.telegram_bot import Despachante, Entregador, registrar_handlers

log = logging.getLogger("apebot")

ESPERA_FILA_MAX_SEGUNDOS = 600
HORA_RESUMO = 23
INTERVALO_AGENDADOR = 60
TENTATIVAS_BANCO = 30


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="apebot")
    parser.add_argument(
        "--rodada-agora",
        action="store_true",
        help="executa uma rodada, espera a fila esvaziar e encerra",
    )
    parser.add_argument(
        "--simular-falha",
        action="store_true",
        help="com --rodada-agora: força erro de acesso em todas as páginas",
    )
    return parser.parse_args()


class Fontes:
    """Coletores da rodada e o que o /status e o /ajuda precisam saber deles."""

    def __init__(self, segredos: Segredos, banco: Banco, simular_falha: bool = False) -> None:
        catalogo = bairros_validos()
        self.gecko = ClienteGecko(segredos.gecko_api_key) if segredos.gecko_api_key else None
        self.ligadas = ["quintoandar"]
        self.coletores = [
            Coletor("quintoandar", partial(quintoandar.coletar, simular_falha=simular_falha))
        ]
        for nome, modulo in (("zap", zap), ("olx", olx)):
            # simulação de falha não gasta crédito: as fontes pagas ficam desligadas
            if self.gecko is not None and nome in segredos.gecko_fontes and not simular_falha:
                coletar = partial(_coletar_paga, modulo, self.gecko, banco, catalogo)
                self.ligadas.append(nome)
            else:
                coletar = partial(_desligada, nome)
            self.coletores.append(Coletor(nome, coletar))
        if segredos.netimoveis:
            coletar = partial(netimoveis.coletar, catalogo=catalogo, simular_falha=simular_falha)
            self.ligadas.append("netimoveis")
        else:
            coletar = partial(_desligada, "netimoveis")
        self.coletores.append(Coletor("netimoveis", coletar))
        log.info("fontes_ligadas %s", ",".join(self.ligadas))


async def _coletar_paga(
    modulo, gecko: ClienteGecko, banco: Banco, catalogo: frozenset[str], pessoas: list[Pessoa]
) -> ResultadoFonte:
    return await modulo.coletar(gecko, pessoas, banco, catalogo)


async def _desligada(fonte: str, _pessoas: list[Pessoa]) -> ResultadoFonte:
    return ResultadoFonte(fonte=fonte, status="desligada")


def _preparar_banco(segredos: Segredos, config: Configuracao) -> Banco:
    banco = Banco(segredos)
    for tentativa in range(1, TENTATIVAS_BANCO + 1):
        try:
            novas = banco.aplicar_migracoes(segredos.migrations_path)
            break
        except Exception as erro:
            if tentativa == TENTATIVAS_BANCO:
                raise
            log.warning("banco_indisponivel tentativa=%d erro=%s", tentativa, erro)
            time.sleep(2)
    if novas:
        log.info("migracoes_aplicadas versoes=%s", ",".join(novas))
    config.problemas.extend(banco.semear_pessoas(config.autorizados, config.sementes))
    return banco


async def _rodada_agora(
    banco: Banco, segredos: Segredos, config: Configuracao, fontes: Fontes
) -> None:
    if not await asyncio.to_thread(banco.pessoas_ativas, config.autorizados):
        print(
            "Nenhuma pessoa ativa. Mande /start ao bot com ele no ar e rode de novo.",
            flush=True,
        )
        return
    fila = Fila(segredos.redis_url)
    fila_pessoa = FilaPessoa(fila)
    try:
        status = await Rodada(banco, fila, fila_pessoa, config, fontes.coletores).executar()
        log.info("rodada_manual status=%s; aguardando o bot entregar a fila", status)
        limite = time.monotonic() + ESPERA_FILA_MAX_SEGUNDOS
        while await fila.tamanho() and time.monotonic() < limite:
            await asyncio.sleep(2)
        log.info("rodada_manual_fim fila_restante=%d", await fila.tamanho())
        ativas = await asyncio.to_thread(banco.pessoas_ativas, config.autorizados)
        na_fila = sum([await fila_pessoa.tamanho(p.chat_id) for p in ativas])
        print(
            f"Imóveis na fila das pessoas: {na_fila}. O bot entrega um por vez, das 8h às 22h.",
            flush=True,
        )
    finally:
        await fila.fechar()


def _rodar_bot(banco: Banco, segredos: Segredos, config: Configuracao, fontes: Fontes) -> None:
    fila = Fila(segredos.redis_url)
    fila_pessoa = FilaPessoa(fila)
    tarefas: list[asyncio.Task] = []
    pulados: set[datetime] = set()

    async def ao_iniciar(app: Application) -> None:
        if config.problemas:
            await fila.enfileirar(
                Mensagem(
                    chat_id=config.operador_chat_id,
                    tipo="operador",
                    texto=aviso_configuracao(config.problemas),
                )
            )
        await app.bot.set_my_commands(COMANDOS)
        tarefas.append(asyncio.create_task(Entregador(app, fila, banco).executar()))
        despachante = Despachante(
            fila, fila_pessoa, banco, config.autorizados, segredos.entrega_intervalo
        )
        tarefas.append(asyncio.create_task(despachante.executar()))
        tarefas.append(asyncio.create_task(agendar_rodadas()))

    async def ao_encerrar(_: Application) -> None:
        for tarefa in tarefas:
            tarefa.cancel()
        await fila.fechar()

    async def rodada_agendada(momento: datetime) -> None:
        ultima = await asyncio.to_thread(banco.ultima_rodada_iniciada)
        devida = rodada_devida(momento, ultima)
        if devida is None:
            return
        if not await asyncio.to_thread(banco.pessoas_ativas, config.autorizados):
            if devida not in pulados:  # um log por horário, não um por minuto
                log.info("rodada_pulada_sem_pessoas horario=%s", devida.strftime("%H:%M"))
                pulados.add(devida)
            return
        atraso = (momento - devida).total_seconds()
        log.info("rodada_disparada horario=%s atraso=%.0fs", devida.strftime("%H:%M"), atraso)
        await Rodada(banco, fila, fila_pessoa, config, fontes.coletores).executar()
        if devida.hour == HORA_RESUMO:  # depois da rodada, ok ou falha
            await enviar_resumos(banco, fila, fontes.gecko, config.autorizados, datetime.now(FUSO))

    async def agendar_rodadas() -> None:
        # laço próprio no relógio de parede: o timer do APScheduler usa o relógio monotônico,
        # que para quando o PC suspende, e a rodada se perdia sem log
        while True:
            try:
                await rodada_agendada(datetime.now(FUSO))
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("agendador_erro")
            await asyncio.sleep(INTERVALO_AGENDADOR)

    app = (
        Application.builder()
        .token(segredos.telegram_token)
        .post_init(ao_iniciar)
        .post_shutdown(ao_encerrar)
        .build()
    )
    registrar_handlers(app, config, banco, fila_pessoa, fontes.ligadas, fontes.gecko)
    log.info("rodadas_agendadas horarios=%s fuso=%s", HORARIOS_RODADA, FUSO.key)
    app.run_polling()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = _argumentos()
    segredos = carregar_segredos()
    config = carregar_configuracao(segredos, bairros_validos())
    config.problemas.extend(
        problemas_gecko(segredos) + problemas_entrega(segredos) + problemas_netimoveis(segredos)
    )
    for problema in config.problemas:
        log.warning("filtros_problema %s", problema)
    banco = _preparar_banco(segredos, config)

    fontes = Fontes(segredos, banco, simular_falha=args.simular_falha)

    if args.rodada_agora:
        asyncio.run(_rodada_agora(banco, segredos, config, fontes))
    else:
        _rodar_bot(banco, segredos, config, fontes)


if __name__ == "__main__":
    main()
