"""Composição e ponto de entrada: python -m apebot.main [--rodada-agora [--simular-falha]]."""

import argparse
import asyncio
import logging
import time
from datetime import time as horario

from telegram.ext import Application, ContextTypes

from apebot.banco import Banco
from apebot.config import (
    Configuracao,
    Segredos,
    bairros_validos,
    carregar_filtros,
    carregar_segredos,
)
from apebot.fila import Fila, Mensagem
from apebot.mensagens import aviso_configuracao
from apebot.modelos import FUSO, HORARIOS_RODADA
from apebot.rodada import Rodada
from apebot.telegram_bot import Entregador, registrar_handlers

log = logging.getLogger("apebot")

ESPERA_FILA_MAX_SEGUNDOS = 600
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
    banco.sincronizar_pessoas(config.pessoas)
    return banco


async def _rodada_agora(
    banco: Banco, segredos: Segredos, config: Configuracao, simular_falha: bool
) -> None:
    fila = Fila(segredos.redis_url)
    try:
        status = await Rodada(banco, fila, config, simular_falha).executar()
        log.info("rodada_manual status=%s; aguardando o bot entregar a fila", status)
        limite = time.monotonic() + ESPERA_FILA_MAX_SEGUNDOS
        while await fila.tamanho() and time.monotonic() < limite:
            await asyncio.sleep(2)
        log.info("rodada_manual_fim fila_restante=%d", await fila.tamanho())
    finally:
        await fila.fechar()


def _rodar_bot(banco: Banco, segredos: Segredos, config: Configuracao) -> None:
    fila = Fila(segredos.redis_url)
    tarefas: list[asyncio.Task] = []

    async def ao_iniciar(app: Application) -> None:
        if config.problemas:
            await fila.enfileirar(
                Mensagem(
                    chat_id=config.operador_chat_id,
                    tipo="operador",
                    texto=aviso_configuracao(config.problemas),
                )
            )
        tarefas.append(asyncio.create_task(Entregador(app, fila, banco).executar()))

    async def ao_encerrar(_: Application) -> None:
        for tarefa in tarefas:
            tarefa.cancel()
        await fila.fechar()

    async def rodada_agendada(_: ContextTypes.DEFAULT_TYPE) -> None:
        await Rodada(banco, fila, config).executar()

    app = (
        Application.builder()
        .token(segredos.telegram_token)
        .post_init(ao_iniciar)
        .post_shutdown(ao_encerrar)
        .build()
    )
    registrar_handlers(app, config, banco)
    for hora in HORARIOS_RODADA:
        app.job_queue.run_daily(
            rodada_agendada,
            time=horario(hour=hora, tzinfo=FUSO),
            name=f"rodada_{hora:02d}h",
            job_kwargs={"max_instances": 1, "coalesce": True, "misfire_grace_time": 300},
        )
    log.info("rodadas_agendadas horarios=%s fuso=%s", HORARIOS_RODADA, FUSO.key)
    app.run_polling()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = _argumentos()
    segredos = carregar_segredos()
    config = carregar_filtros(segredos.filtros_path, bairros_validos())
    for problema in config.problemas:
        log.warning("filtros_problema %s", problema)
    banco = _preparar_banco(segredos, config)

    if args.rodada_agora:
        asyncio.run(_rodada_agora(banco, segredos, config, args.simular_falha))
    else:
        _rodar_bot(banco, segredos, config)


if __name__ == "__main__":
    main()
