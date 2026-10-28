"""Textos enviados no Telegram (contracts/telegram.md da 001 a 003). HTML do Telegram."""

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
    ("filtros", "Ver e editar meus filtros"),
    ("favoritos", "Imóveis que salvei"),
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
        "🤖 Eu procuro imóveis para alugar em BH que combinam com os seus filtros.\n"
        "Te mando um imóvel por vez, das 8h às 22h, começando pelos mais baratos.\n"
        "Às 23h chega um resumo do dia.\n"
        f"Portais: {portais}\n"
        "/filtros — ver e editar seus filtros\n"
        "/favoritos — imóveis que você salvou\n"
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


def _imoveis(n: int) -> str:
    return f"{n} imóvel" if n == 1 else f"{n} imóveis"


def _cabecalho(ultima_rodada: datetime | None, proxima: datetime, recebidos: int) -> list[str]:
    if ultima_rodada is None:
        primeira = f"📊 Ainda não houve rodada. Próxima: {proxima:%H:%M}"
    else:
        ultima = _local(ultima_rodada)
        primeira = f"📊 Última rodada: {ultima:%d/%m %H:%M} · próxima: {proxima:%H:%M}"
    return [primeira, f"Você recebeu {_imoveis(recebidos)} nas últimas 24 h."]


def _linha_creditos(creditos: dict | str | None) -> list[str]:
    """`creditos`: dict de /v1/me/credits, texto de erro, ou None (sem GeckoAPI: não mostra)."""
    if isinstance(creditos, dict):
        saldo = creditos.get("currentCredits", "?")
        gastos = (creditos.get("creditsConsumed") or {}).get("last24Hours", "?")
        return [f"💳 Créditos: {saldo} (gastos em 24 h: {gastos})"]
    if creditos is not None:
        return ["💳 Créditos: saldo indisponível"]
    return []


def texto_status(
    ultima_rodada: datetime | None,
    proxima: datetime,
    recebidos_24h: int,
    estados: dict[str, tuple[str, str | None]],
    fontes_ligadas: list[str],
    creditos: dict | str | None = None,
    na_fila: int | None = None,
) -> str:
    linhas = _cabecalho(ultima_rodada, proxima, recebidos_24h)
    if na_fila is not None:
        linhas.append(f"Na sua fila: {_imoveis(na_fila)} (envio das 8h às 22h).")
    linhas += [f"{portal(f)}: {_estado(f, estados, fontes_ligadas)}" for f in ORDEM_FONTES]
    return "\n".join(linhas + _linha_creditos(creditos))


def texto_resumo(
    ultima_rodada: datetime | None,
    proxima: datetime,
    por_fonte: dict[str, int],
    creditos: dict | str | None,
) -> str:
    """Resumo depois da rodada das 23h (contracts/telegram.md da 003)."""
    linhas = _cabecalho(ultima_rodada, proxima, sum(por_fonte.values()))
    linhas += [f"{portal(f)}: {por_fonte.get(f, 0)}" for f in ORDEM_FONTES]
    return "\n".join(linhas + _linha_creditos(creditos))


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
        "🏡Veja o imóvel que encontrei:",
        _quartos_no_bairro(anuncio),
        f"💰Valor: {formatar_reais(anuncio.aluguel_centavos)}",
        f"Link: {escape(anuncio.url)}",
    ]
    if contato and contato.nome:
        linhas.append(f"👤 {escape(contato.nome)}")
    if contato and contato.telefone:
        linhas.append(f"📞 {escape(contato.telefone)}")
    return "\n".join(linhas)


SALVAR_FAVORITO = "⭐ Salvar como favorito"
FAVORITO_SALVO = "✅ Favorito · toque para remover"


def botoes_imovel(anuncio: Anuncio, contato: Contato | None = None) -> list[list[dict[str, str]]]:
    """Linhas de botões: {"t": rótulo, "u": url} ou {"t": rótulo, "c": callback_data}."""
    linha = [{"t": "Abrir anúncio", "u": anuncio.url}]
    if contato and contato.whatsapp_url:
        linha.append({"t": "WhatsApp", "u": contato.whatsapp_url})
    favorito = {"t": SALVAR_FAVORITO, "c": f"f:{anuncio.fonte}:{anuncio.id_externo}"}
    return [linha, [favorito]]


def trocar_botao_favorito(
    linhas: list[list[dict[str, str]]], salvo: bool
) -> list[list[dict[str, str]]]:
    """Troca só o rótulo do botão de favorito (callback f:…), mantendo os outros botões."""
    rotulo = FAVORITO_SALVO if salvo else SALVAR_FAVORITO
    return [
        [b | {"t": rotulo} if b.get("c", "").startswith("f:") else b for b in linha]
        for linha in linhas
    ]


LIMITE_MENSAGEM = 4000


def texto_favoritos(anuncios: list[Anuncio]) -> list[str]:
    """Blocos de até 4.000 caracteres, sem cortar um imóvel no meio (research R11 da 003)."""
    if not anuncios:
        return [
            'Você ainda não tem favoritos. Toque em "⭐ Salvar como favorito" numa mensagem'
            " de imóvel."
        ]
    blocos, atual = [], f"⭐ Seus favoritos ({len(anuncios)}):"
    for a in anuncios:
        quartos = _quartos_no_bairro(a).split(" no bairro ")[0]
        item = (
            f"⭐ {quartos} · {escape(nome_bairro(a.bairro_slug))} · "
            f"{formatar_reais(a.aluguel_centavos)} · {portal(a.fonte)}\n{escape(a.url)}"
        )
        if len(atual) + 1 + len(item) > LIMITE_MENSAGEM:
            blocos.append(atual)
            atual = item
        else:
            atual = f"{atual}\n{item}"
    return [*blocos, atual]


def resposta_padrao() -> str:
    return "Eu te mando os imóveis por aqui, das 8h às 22h. Envie /ajuda para ver os comandos."


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
