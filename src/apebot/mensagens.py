"""Textos enviados no Telegram (contracts/telegram.md da 001 e da 002). HTML do Telegram."""

from datetime import UTC, datetime, timedelta
from html import escape

from apebot.config import nome_bairro
from apebot.modelos import (
    FUSO,
    HORARIOS_RODADA,
    NOMES_FONTE,
    Anuncio,
    Contato,
    Filtro,
    Pessoa,
    Tipo,
)

HORARIOS_TEXTO = ", ".join(f"{h:02d}" for h in HORARIOS_RODADA[:-1]) + (
    f" e {HORARIOS_RODADA[-1]:02d}h"
)


def formatar_reais(centavos: int) -> str:
    """Sempre com centavos: R$ 3.000,00 (FR-029 da 003)."""
    reais, resto = divmod(centavos, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{resto:02d}"


def _local(momento_utc: datetime) -> datetime:
    """Horários do banco são UTC sem fuso; exibidos em São Paulo."""
    return momento_utc.replace(tzinfo=UTC).astimezone(FUSO)


# Menu do Telegram (contracts/telegram.md da 002).
COMANDOS = [
    ("ajuda", "Como o robô funciona"),
    ("filtros", "Ver meus filtros"),
    ("status", "Última rodada e portais"),
    ("pausar", "Pausar os avisos"),
    ("retomar", "Voltar a receber avisos"),
]
TEXTO_PAUSADO = "⏸️ Avisos pausados. Use /retomar quando quiser voltar."
TEXTO_RETOMADO = "▶️ Avisos retomados. Na próxima rodada eu volto a te mandar o que encontrar."
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


def linhas_filtro(filtro: Filtro) -> list[str]:
    """Bloco "Seus filtros -" do /filtros e da revisão da edição (contracts/telegram.md da 003)."""
    bairros = ", ".join(sorted(nome_bairro(b) for b in filtro.bairros))
    tipos = ", ".join(t.rotulo for t in Tipo if t in filtro.tipos)
    if filtro.quartos_min:
        quartos = f"com {filtro.quartos_min}+ quartos"
    else:
        quartos = "com qualquer número de quartos"
    return [
        "Seus filtros -",
        f"Bairros: {escape(bairros)}",
        f"Valores até {formatar_reais(filtro.aluguel_max_centavos)}",
        f"{escape(tipos)} {quartos}",
    ]


def texto_filtros(pessoa: Pessoa, pausada_em: datetime | None) -> str:
    avisos = "ativos" if pausada_em is None else f"pausados desde {_local(pausada_em):%d/%m %H:%M}"
    return "\n".join([*linhas_filtro(pessoa.filtro), f"Avisos: {avisos}"])


def boas_vindas(nome: str) -> str:
    return (
        f"Perfeito, {escape(nome)}! Vou te ajudar a encontrar um imóvel com sua cara para alugar! "
        "Durante o dia vou te enviar o que achar por aqui, fique atento(a)."
    )


def filtros_salvos(proxima: datetime) -> str:
    return f"Filtros salvos! Eles valem a partir da próxima rodada ({proxima:%H:%M})."


EDICAO_CANCELADA = "Edição cancelada. Seus filtros continuam os mesmos."
CADASTRO_ABERTO = "Termine o cadastro primeiro: /start"


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


def portal(fonte: str) -> str:
    return NOMES_FONTE.get(fonte, fonte)


def _quartos_no_bairro(anuncio: Anuncio) -> str:
    bairro = escape(nome_bairro(anuncio.bairro_slug))
    if anuncio.quartos == 0:
        return f"{anuncio.tipo.rotulo} no bairro {bairro}"
    plural = "quarto" if anuncio.quartos == 1 else "quartos"
    return f"{anuncio.quartos} {plural} no bairro {bairro}"


def mensagem_imovel(anuncio: Anuncio, contato: Contato | None = None) -> str:
    """Um imóvel por mensagem (contracts/telegram.md da 003); contato só quando em trânsito."""
    linhas = [
        "Veja o imóvel que encontrei:",
        _quartos_no_bairro(anuncio),
        f"Valor: {formatar_reais(anuncio.aluguel_centavos)}",
        f"Link: {escape(anuncio.url)}",
    ]
    if contato and contato.nome:
        linhas.append(f"👤 {escape(contato.nome)}")
    if contato and contato.telefone:
        linhas.append(f"📞 {escape(contato.telefone)}")
    return "\n".join(linhas)


SALVAR_FAVORITO = "⭐ Salvar como favorito"


def botoes_imovel(anuncio: Anuncio, contato: Contato | None = None) -> list[list[dict[str, str]]]:
    """Linhas de botões: {"t": rótulo, "u": url} ou {"t": rótulo, "c": callback_data}."""
    linha = [{"t": "Abrir anúncio", "u": anuncio.url}]
    if contato and contato.whatsapp_url:
        linha.append({"t": "WhatsApp", "u": contato.whatsapp_url})
    favorito = {"t": SALVAR_FAVORITO, "c": f"f:{anuncio.fonte}:{anuncio.id_externo}"}
    return [linha, [favorito]]


def resposta_padrao() -> str:
    return f"Eu aviso os imóveis às {HORARIOS_TEXTO}. Envie /ajuda para ver os comandos."


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
