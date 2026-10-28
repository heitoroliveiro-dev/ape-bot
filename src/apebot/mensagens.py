"""Textos enviados no Telegram (contracts/telegram.md). HTML do Telegram."""

from datetime import datetime
from html import escape

from apebot.modelos import HORARIOS_RODADA, Anuncio, Pessoa

HORARIOS_TEXTO = ", ".join(f"{h:02d}" for h in HORARIOS_RODADA[:-1]) + (
    f" e {HORARIOS_RODADA[-1]:02d}h"
)


def formatar_reais(centavos: int) -> str:
    return "R$ " + f"{centavos // 100:,}".replace(",", ".")


def _bairro_legivel(bairro_slug: str) -> str:
    return bairro_slug.replace("-", " ").title()


def confirmacao_start(pessoa: Pessoa) -> str:
    f = pessoa.filtro
    bairros = ", ".join(sorted(_bairro_legivel(b) for b in f.bairros))
    tipos = ", ".join(sorted(t.rotulo for t in f.tipos))
    return (
        f"Pronto, {escape(pessoa.nome)}! Vou te avisar de imóveis novos às {HORARIOS_TEXTO}.\n"
        f"Seus filtros: {escape(bairros)} · até {formatar_reais(f.aluguel_max_centavos)}"
        f" · {f.quartos_min}+ quartos · {escape(tipos)}"
    )


NAO_INFORMADO = "não informado"


def mensagem_imovel(anuncio: Anuncio) -> str:
    area = f"{anuncio.area_m2} m²" if anuncio.area_m2 else NAO_INFORMADO
    total = formatar_reais(anuncio.total_centavos) if anuncio.total_centavos else NAO_INFORMADO
    return (
        f"🏠 {anuncio.tipo.rotulo} · {escape(anuncio.bairro)}\n"
        f"{anuncio.quartos} quartos · {area}\n"
        f"Aluguel: {formatar_reais(anuncio.aluguel_centavos)} · Total: {total}\n"
        f"{escape(anuncio.url)}"
    )


def resposta_padrao() -> str:
    return f"Eu aviso os imóveis nos horários {HORARIOS_TEXTO}."


LIMITE_MENSAGEM = 4000
MAX_PARTES_RESUMO = 5
RESERVA_RODAPE = 30


def _linha_resumo(anuncio: Anuncio) -> str:
    return (
        f"• {escape(anuncio.bairro)} · {anuncio.quartos}q · "
        f"{formatar_reais(anuncio.aluguel_centavos)} · {escape(anuncio.url)}"
    )


def mensagens_resumo(anuncios: list[Anuncio]) -> list[str]:
    if not anuncios:
        return ["Ainda não achei imóveis com os seus filtros. Continuo procurando."]
    partes: list[str] = []
    atual = f"Encontrei {len(anuncios)} imóveis com os seus filtros:"
    usados = 0
    for anuncio in anuncios:
        linha = _linha_resumo(anuncio)
        if len(atual) + 1 + len(linha) > LIMITE_MENSAGEM - RESERVA_RODAPE:
            if len(partes) == MAX_PARTES_RESUMO - 1:
                break
            partes.append(atual)
            atual = linha
        else:
            atual = f"{atual}\n{linha}"
        usados += 1
    restantes = len(anuncios) - usados
    if restantes:
        atual = f"{atual}\n(+{restantes} imóveis)"
    partes.append(atual)
    return partes


def aviso_falha(rodadas: int, erro: str | None) -> str:
    return f"⚠️ ape-bot: {rodadas} rodadas seguidas com falha. Último erro: {escape(erro or '?')}"


def aviso_recuperacao(quando: datetime) -> str:
    return f"✅ ape-bot voltou a funcionar ({quando:%d/%m/%Y %H:%M})."


def aviso_configuracao(problemas: list[str]) -> str:
    return "⚙️ filtros.yaml:\n" + "\n".join(f"- {escape(p)}" for p in problemas)
