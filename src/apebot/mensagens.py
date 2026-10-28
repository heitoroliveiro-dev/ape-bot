"""Textos enviados no Telegram (contracts/telegram.md da 001 e da 002). HTML do Telegram."""

from datetime import UTC, datetime, timedelta
from html import escape

from apebot.config import nome_bairro
from apebot.modelos import FUSO, HORARIOS_RODADA, NOMES_FONTE, Anuncio, Contato, Pessoa

HORARIOS_TEXTO = ", ".join(f"{h:02d}" for h in HORARIOS_RODADA[:-1]) + (
    f" e {HORARIOS_RODADA[-1]:02d}h"
)


def formatar_reais(centavos: int) -> str:
    """Sempre com centavos: R$ 3.000,00 (FR-029 da 003)."""
    reais, resto = divmod(centavos, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{resto:02d}"


def _linha_filtros(pessoa: Pessoa) -> str:
    f = pessoa.filtro
    bairros = ", ".join(sorted(nome_bairro(b) for b in f.bairros))
    tipos = ", ".join(sorted(t.rotulo for t in f.tipos))
    return (
        f"Seus filtros: {escape(bairros)} · até {formatar_reais(f.aluguel_max_centavos)}"
        f" · {f.quartos_min}+ quartos · {escape(tipos)}"
    )


def _local(momento_utc: datetime) -> datetime:
    """Horários do banco são UTC sem fuso; exibidos em São Paulo."""
    return momento_utc.replace(tzinfo=UTC).astimezone(FUSO)


def confirmacao_start(pessoa: Pessoa, pausada: bool = False) -> str:
    texto = (
        f"Pronto, {escape(pessoa.nome)}! Vou te avisar de imóveis novos às {HORARIOS_TEXTO}.\n"
        f"{_linha_filtros(pessoa)}"
    )
    if pausada:
        texto += "\nSeus avisos estão pausados. Use /retomar para voltar."
    return texto


# Menu do Telegram (contracts/telegram.md da 002).
COMANDOS = [
    ("ajuda", "Como o robô funciona"),
    ("filtros", "Ver meus filtros"),
    ("status", "Última rodada e portais"),
    ("pausar", "Pausar os avisos"),
    ("retomar", "Voltar a receber avisos"),
]
TEXTO_PAUSADO = "⏸️ Avisos pausados. Use /retomar quando quiser voltar."
TEXTO_RETOMADO = (
    "▶️ Avisos retomados. Na próxima rodada eu te mando um resumo do que estiver disponível."
)
SEM_FILTROS = "Você está sem filtros válidos."
ORDEM_FONTES = ("quintoandar", "zap", "olx")


def texto_ajuda(fontes_ligadas: list[str]) -> str:
    portais = ", ".join(portal(f) for f in ORDEM_FONTES if f in fontes_ligadas)
    return (
        f"🤖 Eu procuro imóveis para alugar em BH e te aviso dos novos às {HORARIOS_TEXTO}.\n"
        f"Portais: {portais}\n"
        "/filtros — ver seus filtros\n"
        "/status — última rodada e portais\n"
        "/pausar — parar os avisos por um tempo\n"
        "/retomar — voltar a receber"
    )


def texto_filtros(pessoa: Pessoa, pausada_em: datetime | None, nome_operador: str) -> str:
    avisos = "ativos" if pausada_em is None else f"pausados desde {_local(pausada_em):%d/%m %H:%M}"
    return (
        f"{_linha_filtros(pessoa)}\n"
        f"Avisos: {avisos}\n"
        f"Para mudar os filtros, fale com {escape(nome_operador)}."
    )


def proxima_rodada(agora: datetime) -> datetime:
    local = agora.astimezone(FUSO)
    for dias in (0, 1):
        dia = local.date() + timedelta(days=dias)
        for hora in HORARIOS_RODADA:
            momento = datetime(dia.year, dia.month, dia.day, hora, tzinfo=FUSO)
            if momento > local:
                return momento
    raise AssertionError("HORARIOS_RODADA vazio")


_ESTADO_FONTE = {
    "ok": "✅ ok",
    "desligada": "⏹️ desligado",
    "sem_credito": "💳 sem crédito",
}


def _estado(fonte: str, estados: dict[str, tuple[str, str | None]], ligadas: list[str]) -> str:
    if fonte not in ligadas:
        return "⏹️ desligado"
    if fonte not in estados:
        return "⏳ aguardando a primeira rodada"
    status, erro = estados[fonte]
    if status == "falha":
        return f"⚠️ falha ({escape((erro or '?')[:80])})"
    return _ESTADO_FONTE.get(status, status)


def texto_status(
    ultima_rodada: datetime | None,
    proxima: datetime,
    recebidos_24h: int,
    estados: dict[str, tuple[str, str | None]],
    fontes_ligadas: list[str],
    creditos: dict | str | None = None,
) -> str:
    """`creditos`: dict de /v1/me/credits (operador), texto de erro, ou None (não mostra)."""
    if ultima_rodada is None:
        linhas = [f"📊 Ainda não houve rodada. Próxima: {proxima:%H:%M}"]
    else:
        ultima = _local(ultima_rodada)
        linhas = [f"📊 Última rodada: {ultima:%d/%m %H:%M} · próxima: {proxima:%H:%M}"]
    linhas.append(f"Você recebeu {recebidos_24h} imóveis nas últimas 24 h.")
    linhas += [f"{portal(f)}: {_estado(f, estados, fontes_ligadas)}" for f in ORDEM_FONTES]
    if isinstance(creditos, dict):
        saldo = creditos.get("currentCredits", "?")
        gastos = (creditos.get("creditsConsumed") or {}).get("last24Hours", "?")
        linhas.append(f"💳 Créditos: {saldo} (gastos em 24 h: {gastos})")
    elif creditos is not None:
        linhas.append("💳 Créditos: saldo indisponível")
    return "\n".join(linhas)


NAO_INFORMADO = "não informado"


def portal(fonte: str) -> str:
    return NOMES_FONTE.get(fonte, fonte)


def mensagem_imovel(anuncio: Anuncio, contato: Contato | None = None) -> str:
    """O link vai no botão "Abrir anúncio" (botoes_imovel), não no texto."""
    area = f"{anuncio.area_m2} m²" if anuncio.area_m2 else NAO_INFORMADO
    total = formatar_reais(anuncio.total_centavos) if anuncio.total_centavos else NAO_INFORMADO
    linhas = [
        f"🏠 {anuncio.tipo.rotulo} · {escape(anuncio.bairro)} · {portal(anuncio.fonte)}",
        f"{anuncio.quartos} quartos · {area}",
        f"Aluguel: {formatar_reais(anuncio.aluguel_centavos)} · Total: {total}",
    ]
    if contato and contato.nome:
        linhas.append(f"👤 {escape(contato.nome)}")
    if contato and contato.telefone:
        linhas.append(f"📞 {escape(contato.telefone)}")
    return "\n".join(linhas)


def botoes_imovel(anuncio: Anuncio, contato: Contato | None = None) -> list[list[dict[str, str]]]:
    """Linhas de botões: {"t": rótulo, "u": url} ou {"t": rótulo, "c": callback_data}."""
    linha = [{"t": "Abrir anúncio", "u": anuncio.url}]
    if contato and contato.whatsapp_url:
        linha.append({"t": "WhatsApp", "u": contato.whatsapp_url})
    return [linha]


def resposta_padrao() -> str:
    return f"Eu aviso os imóveis às {HORARIOS_TEXTO}. Envie /ajuda para ver os comandos."


LIMITE_MENSAGEM = 4000
MAX_PARTES_RESUMO = 5
RESERVA_RODAPE = 30


def _linha_resumo(anuncio: Anuncio) -> str:
    return (
        f"• {escape(anuncio.bairro)} · {anuncio.quartos}q · "
        f"{formatar_reais(anuncio.aluguel_centavos)} · {portal(anuncio.fonte)} · "
        f"{escape(anuncio.url)}"
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


def aviso_falha(fonte: str, rodadas: int, erro: str | None) -> str:
    return (
        f"⚠️ ape-bot: {portal(fonte)} com falha em {rodadas} rodadas seguidas. "
        f"Último erro: {escape(erro or '?')}"
    )


def aviso_recuperacao(fonte: str, quando: datetime) -> str:
    return f"✅ ape-bot: {portal(fonte)} voltou a funcionar ({quando:%d/%m/%Y %H:%M})."


def aviso_sem_credito() -> str:
    return (
        "💳 ape-bot: a GeckoAPI recusou por falta de créditos. "
        "Zap/OLX parados até reiniciar o robô."
    )


def aviso_configuracao(problemas: list[str]) -> str:
    return "⚙️ filtros.yaml:\n" + "\n".join(f"- {escape(p)}" for p in problemas)
