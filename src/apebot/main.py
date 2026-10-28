"""Composição e ponto de entrada: python -m apebot.main [--rodada-agora [--simular-falha]]."""

import argparse
import asyncio
import logging
import time
from datetime import time as horario
from functools import partial

from telegram.ext import Application, ContextTypes

from apebot.banco import Banco
from apebot.config import (
    Configuracao,
    Segredos,
    bairros_validos,
    carregar_filtros,
    carregar_segredos,
    problemas_gecko,
)
from apebot.fila import Fila, Mensagem
from apebot.fontes import olx, quintoandar, zap
from apebot.fontes.geckoapi import ClienteGecko
from apebot.fontes.resultado import ResultadoFonte
from apebot.mensagens import COMANDOS, aviso_configuracao
from apebot.modelos import FUSO, HORARIOS_RODADA, Pessoa
from apebot.rodada import Coletor, Rodada
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
    banco.sincronizar_pessoas(config.pessoas)
    return banco


async def _rodada_agora(
    banco: Banco, segredos: Segredos, config: Configuracao, fontes: Fontes
) -> None:
    if not await asyncio.to_thread(banco.pessoas_registradas):
        print(
            "Nenhuma pessoa registrada. Mande /start ao bot com ele no ar e rode de novo.",
            flush=True,
        )
        return
    fila = Fila(segredos.redis_url)
    try:
        status = await Rodada(banco, fila, config, fontes.coletores).executar()
        log.info("rodada_manual status=%s; aguardando o bot entregar a fila", status)
        limite = time.monotonic() + ESPERA_FILA_MAX_SEGUNDOS
        while await fila.tamanho() and time.monotonic() < limite:
            await asyncio.sleep(2)
        log.info("rodada_manual_fim fila_restante=%d", await fila.tamanho())
    finally:
        await fila.fechar()


def _rodar_bot(banco: Banco, segredos: Segredos, config: Configuracao, fontes: Fontes) -> None:
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
        await app.bot.set_my_commands(COMANDOS)
        tarefas.append(asyncio.create_task(Entregador(app, fila, banco).executar()))

    async def ao_encerrar(_: Application) -> None:
        for tarefa in tarefas:
            tarefa.cancel()
        await fila.fechar()

    async def rodada_agendada(_: ContextTypes.DEFAULT_TYPE) -> None:
        await Rodada(banco, fila, config, fontes.coletores).executar()

    app = (
        Application.builder()
        .token(segredos.telegram_token)
        .post_init(ao_iniciar)
        .post_shutdown(ao_encerrar)
        .build()
    )
    registrar_handlers(app, config, banco, fontes.ligadas, fontes.gecko)
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
    config.problemas.extend(problemas_gecko(segredos))
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
