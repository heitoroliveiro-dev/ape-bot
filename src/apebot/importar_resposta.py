"""Importa respostas JSON da GeckoAPI para o MySQL: python -m apebot.importar_resposta ARQUIVO..."""

import argparse
import logging
import sys
from pathlib import Path

from apebot.banco import Banco
from apebot.config import carregar_segredos
from apebot.fontes.geckoapi import RespostaInvalida, ler_resposta

log = logging.getLogger("apebot")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(prog="apebot.importar_resposta")
    parser.add_argument("arquivos", nargs="+", type=Path)
    args = parser.parse_args()

    segredos = carregar_segredos()
    banco = Banco(segredos)
    novas = banco.aplicar_migracoes(segredos.migrations_path)
    if novas:
        log.info("migracoes_aplicadas versoes=%s", ",".join(novas))

    falhas = 0
    for arquivo in args.arquivos:
        try:
            resposta = ler_resposta(arquivo.read_text(encoding="utf-8"))
        except (OSError, RespostaInvalida) as erro:
            log.error("resposta_invalida arquivo=%s erro=%s", arquivo, erro)
            falhas += 1
            continue
        inserida = banco.salvar_resposta(resposta)
        log.info(
            "resposta_%s arquivo=%s fonte=%s request_id=%s itens=%d total=%s",
            "importada" if inserida else "repetida",
            arquivo.name,
            resposta.fonte,
            resposta.request_id,
            resposta.itens,
            resposta.total_resultados,
        )
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
