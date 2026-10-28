"""Conversa do cadastro (/start) e da edição de filtros (research R6 a R8 da 003).

Regra pura, sem Telegram: `processar(estado, texto|dados)` devolve o novo estado e a resposta,
com o teclado descrito como dados. O estado fica no MySQL (tabela conversa) entre um toque e outro.
Botões levam `c:{etapa}:{ação}[:{arg}]`; um toque de etapa que já passou não muda nada.
"""

import re
import unicodedata
from dataclasses import dataclass, field, replace

from apebot.config import catalogo_bairros
from apebot.filtro import QUARTOS_OPCOES, VALOR_MAX_CENTAVOS, VALOR_MIN_CENTAVOS
from apebot.mensagens import EDICAO_CANCELADA, formatar_reais, linhas_filtro
from apebot.modelos import REGIONAIS, Filtro, Pessoa, Tipo

POR_PAGINA = 24
TAMANHO_NOME = 40
PARTICULAS = {"da", "de", "do", "das", "dos", "e"}

TEXTO_NOME = "Oi! Eu procuro imóveis para alugar em BH e te aviso por aqui. Como devo te chamar?"
NOME_INVALIDO = "Me diga um nome com letras, de até 40 caracteres."
TEXTO_TIPOS = "Você busca quais tipos de imóveis? Marque um ou mais e toque em Continuar."
TEXTO_QUARTOS = "Quantos quartos, no mínimo?"
TEXTO_VALOR = "Qual valor máximo de aluguel? Exemplos: 2500, 2.500 ou R$ 2.500,00"
VALOR_INVALIDO = (
    "Não entendi esse valor. Escreva só o número, como 2500 ou 2.500,00, entre R$ 300 e R$ 50.000."
)
USE_OS_BOTOES = "Use os botões para responder. 👇"
JA_PASSOU = "Essa pergunta já passou."
CONTINUAR = "Continuar ▶"
CANCELAR = "✖ Cancelar"
ROTULO_QUARTOS = {0: "Tanto faz", 4: "4 ou mais"}

_VALOR = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$")
_PREFIXO_REAIS = re.compile(r"^r\$\s*", re.IGNORECASE)


@dataclass(frozen=True)
class Botao:
    texto: str
    dados: str


@dataclass
class Resposta:
    texto: str | None  # None: só o aviso do toque, sem mexer na mensagem
    teclado: list[list[Botao]] = field(default_factory=list)
    editar: bool = False  # True: edita a mensagem do botão em vez de mandar outra
    aviso: str | None = None  # texto curto do answerCallbackQuery


@dataclass(frozen=True)
class Estado:
    modo: str  # cadastro | edicao
    etapa: str  # nome | tipos | quartos | regionais | bairros | valor | revisao
    rascunho: dict


@dataclass
class Resultado:
    estado: Estado | None
    resposta: Resposta | None
    acao: str = "seguir"  # seguir | gravar | cancelar
    nome: str | None = None
    filtro: Filtro | None = None


# --- validações -------------------------------------------------------------------------------


def ler_valor(texto: str) -> int | None:
    """Valor digitado → centavos; None fora do formato ou da faixa R$ 300 a R$ 50.000."""
    m = _VALOR.match(_PREFIXO_REAIS.sub("", texto.strip()))
    if not m:
        return None
    centavos = int(m.group(1).replace(".", "")) * 100 + int((m.group(2) or "0").ljust(2, "0"))
    return centavos if VALOR_MIN_CENTAVOS <= centavos <= VALOR_MAX_CENTAVOS else None


def limpar_nome(texto: str) -> str | None:
    """Tira controle, símbolos, emojis e <>&; colapsa espaços; capitaliza; 1 a 40 caracteres."""
    limpo = "".join(
        " "
        if unicodedata.category(c)[0] == "C"
        or unicodedata.category(c) in ("So", "Sk")
        or c in "<>&"
        else c
        for c in texto
    )
    limpo = " ".join(limpo.split())[:TAMANHO_NOME].strip()
    if not any(c.isalpha() for c in limpo):
        return None
    palavras = limpo.split(" ")
    return " ".join(
        p.lower() if i and p.lower() in PARTICULAS else p[:1].upper() + p[1:].lower()
        for i, p in enumerate(palavras)
    )


# --- início e retomada ------------------------------------------------------------------------


def iniciar_cadastro() -> Resultado:
    estado = Estado("cadastro", "nome", _rascunho_vazio())
    return Resultado(estado, reapresentar(estado))


def iniciar_edicao(pessoa: Pessoa) -> Resultado:
    f = pessoa.filtro
    rascunho = _rascunho_vazio() | {
        "nome": pessoa.nome,
        "tipos": sorted(t.value for t in f.tipos),
        "quartos": f.quartos_min,
        "bairros": sorted(f.bairros),
        "valor": f.aluguel_max_centavos,
        "valor_atual": f.aluguel_max_centavos,
    }
    estado = Estado("edicao", "tipos", rascunho)
    return Resultado(estado, reapresentar(estado))


def _rascunho_vazio() -> dict:
    return {
        "nome": None,
        "tipos": [],
        "quartos": None,
        "bairros": [],
        "valor": None,
        "regional": 0,
        "pagina": 0,
    }


def reapresentar(estado: Estado) -> Resposta:
    """A mensagem da etapa atual, montada do rascunho (também serve para retomar)."""
    return _TELAS[estado.etapa](estado)


# --- processamento ----------------------------------------------------------------------------


def processar(estado: Estado, texto: str | None = None, dados: str | None = None) -> Resultado:
    if dados is not None:
        return _botao(estado, dados)
    texto = texto or ""
    if estado.etapa == "nome":
        nome = limpar_nome(texto)
        if nome is None:
            return Resultado(estado, Resposta(NOME_INVALIDO))
        return _ir(estado, "tipos", nome=nome, editar=False)
    if estado.etapa == "valor":
        valor = ler_valor(texto)
        if valor is None:
            return Resultado(estado, Resposta(VALOR_INVALIDO, reapresentar(estado).teclado))
        return _depois_do_valor(replace(estado, rascunho=estado.rascunho | {"valor": valor}), False)
    tela = reapresentar(estado)
    return Resultado(estado, replace(tela, texto=f"{USE_OS_BOTOES}\n\n{tela.texto}"))


def _botao(estado: Estado, dados: str) -> Resultado:
    partes = dados.split(":")
    if len(partes) < 3 or partes[0] != "c" or partes[1] != estado.etapa:
        return Resultado(estado, Resposta(None, aviso=JA_PASSOU))
    acao, arg = partes[2], ":".join(partes[3:])
    r = estado.rascunho

    if acao == "cancelar" and estado.modo == "edicao":
        return Resultado(None, Resposta(EDICAO_CANCELADA, editar=True), acao="cancelar")

    if estado.etapa == "tipos":
        if acao == "t" and arg in {t.value for t in Tipo}:
            return _ficar(estado, tipos=sorted(set(r["tipos"]) ^ {arg}))
        if acao == "ok":
            if not r["tipos"]:
                return _ficar(estado, aviso="Marque pelo menos um tipo.")
            return _ir(estado, "quartos")
    elif estado.etapa == "quartos":
        if acao == "q" and arg.isdigit() and int(arg) in QUARTOS_OPCOES:
            return _ir(estado, "regionais", quartos=int(arg))
    elif estado.etapa == "regionais":
        if acao == "r" and arg.isdigit() and int(arg) < len(REGIONAIS):
            return _ir(estado, "bairros", regional=int(arg), pagina=0)
        if acao == "ok":
            if not r["bairros"]:
                return _ficar(estado, aviso="Marque pelo menos um bairro.")
            return _ir(estado, "valor")
    elif estado.etapa == "bairros":
        da_regional = [b.slug for b in _bairros_da(r["regional"])]
        if acao == "t" and arg in da_regional:
            return _ficar(estado, bairros=sorted(set(r["bairros"]) ^ {arg}))
        if acao == "p" and arg.isdigit() and int(arg) < _paginas(r["regional"]):
            return _ficar(estado, pagina=int(arg))
        if acao == "todos":
            return _ficar(estado, bairros=sorted(set(r["bairros"]) | set(da_regional)))
        if acao == "nenhum":
            return _ficar(estado, bairros=sorted(set(r["bairros"]) - set(da_regional)))
        if acao == "volta":
            return _ir(estado, "regionais")
    elif estado.etapa == "valor":
        if acao == "manter" and estado.modo == "edicao":
            return _depois_do_valor(estado, True)
    elif estado.etapa == "revisao":
        if acao == "salvar":
            return _gravar(estado, editar=True)
    return Resultado(estado, Resposta(None, aviso=JA_PASSOU))


def _ficar(estado: Estado, aviso: str | None = None, **mudancas) -> Resultado:
    novo = replace(estado, rascunho=estado.rascunho | mudancas)
    return Resultado(novo, replace(reapresentar(novo), editar=True, aviso=aviso))


def _ir(estado: Estado, etapa: str, editar: bool = True, **mudancas) -> Resultado:
    novo = Estado(estado.modo, etapa, estado.rascunho | mudancas)
    return Resultado(novo, replace(reapresentar(novo), editar=editar))


def _depois_do_valor(estado: Estado, editar: bool) -> Resultado:
    if estado.modo == "cadastro":
        return _gravar(estado, editar)
    return _ir(estado, "revisao", editar=editar)


def _filtro(rascunho: dict) -> Filtro:
    return Filtro(
        bairros=frozenset(rascunho["bairros"]),
        aluguel_max_centavos=rascunho["valor"],
        quartos_min=rascunho["quartos"],
        tipos=frozenset(Tipo(t) for t in rascunho["tipos"]),
    )


def _gravar(estado: Estado, editar: bool) -> Resultado:
    """O bot grava e responde (boas-vindas ou "Filtros salvos!", que dependem do relógio)."""
    r = estado.rascunho
    return Resultado(None, None, acao="gravar", nome=r["nome"], filtro=_filtro(r))


# --- telas ------------------------------------------------------------------------------------


def _marcado(texto: str, sim: bool) -> str:
    return f"✅ {texto}" if sim else texto


def _rodape(estado: Estado, *botoes: Botao) -> list[list[Botao]]:
    linha = list(botoes)
    if estado.modo == "edicao":
        linha.append(Botao(CANCELAR, f"c:{estado.etapa}:cancelar"))
    return [linha] if linha else []


def _em_linhas(botoes: list[Botao], por_linha: int = 2) -> list[list[Botao]]:
    return [botoes[i : i + por_linha] for i in range(0, len(botoes), por_linha)]


def _tela_nome(estado: Estado) -> Resposta:
    return Resposta(TEXTO_NOME)


def _tela_tipos(estado: Estado) -> Resposta:
    marcados = set(estado.rascunho["tipos"])
    botoes = [Botao(_marcado(t.rotulo, t.value in marcados), f"c:tipos:t:{t.value}") for t in Tipo]
    return Resposta(
        TEXTO_TIPOS, _em_linhas(botoes) + _rodape(estado, Botao(CONTINUAR, "c:tipos:ok"))
    )


def _tela_quartos(estado: Estado) -> Resposta:
    atual = estado.rascunho["quartos"]
    botoes = [
        Botao(_marcado(ROTULO_QUARTOS.get(q, str(q)), q == atual), f"c:quartos:q:{q}")
        for q in QUARTOS_OPCOES
    ]
    return Resposta(TEXTO_QUARTOS, [botoes] + _rodape(estado))


def _bairros_da(indice: int):
    regional = REGIONAIS[indice]
    return sorted((b for b in catalogo_bairros() if b.regional == regional), key=lambda b: b.nome)


def _paginas(indice: int) -> int:
    return max(1, -(-len(_bairros_da(indice)) // POR_PAGINA))


def _tela_regionais(estado: Estado) -> Resposta:
    marcados = set(estado.rascunho["bairros"])
    botoes = []
    for indice, regional in enumerate(REGIONAIS):
        quantos = sum(1 for b in _bairros_da(indice) if b.slug in marcados)
        rotulo = f"{regional} ({quantos})" if quantos else regional
        botoes.append(Botao(rotulo, f"c:regionais:r:{indice}"))
    n = len(marcados)
    texto = (
        "Em quais bairros? Escolha uma regional para ver os bairros dela. "
        f"Você já marcou {n} {'bairro' if n == 1 else 'bairros'}."
    )
    return Resposta(texto, _em_linhas(botoes) + _rodape(estado, Botao(CONTINUAR, "c:regionais:ok")))


def _tela_bairros(estado: Estado) -> Resposta:
    indice, pagina = estado.rascunho["regional"], estado.rascunho["pagina"]
    marcados = set(estado.rascunho["bairros"])
    bairros = _bairros_da(indice)
    total = _paginas(indice)
    trecho = bairros[pagina * POR_PAGINA : (pagina + 1) * POR_PAGINA]
    teclado = _em_linhas(
        [Botao(_marcado(b.nome, b.slug in marcados), f"c:bairros:t:{b.slug}") for b in trecho]
    )
    navegacao = []
    if pagina > 0:
        navegacao.append(Botao("◀", f"c:bairros:p:{pagina - 1}"))
    if pagina < total - 1:
        navegacao.append(Botao("▶", f"c:bairros:p:{pagina + 1}"))
    if navegacao:
        teclado.append(navegacao)
    em_massa = []
    if not all(b.slug in marcados for b in bairros):
        em_massa.append(Botao("Marcar todos", "c:bairros:todos"))
    if any(b.slug in marcados for b in bairros):
        em_massa.append(Botao("Desmarcar todos", "c:bairros:nenhum"))
    teclado.append(em_massa)
    teclado += _rodape(estado, Botao("↩ Regionais", "c:bairros:volta"))
    texto = f"{REGIONAIS[indice]}: toque para marcar ou desmarcar. Página {pagina + 1}/{total}."
    return Resposta(texto, teclado)


def _tela_valor(estado: Estado) -> Resposta:
    if estado.modo == "edicao":
        atual = formatar_reais(estado.rascunho["valor_atual"])
        texto = f"{TEXTO_VALOR}\nAtual: {atual}. Envie um novo valor ou toque em Manter."
        return Resposta(texto, _rodape(estado, Botao("Manter", "c:valor:manter")))
    return Resposta(TEXTO_VALOR)


def _tela_revisao(estado: Estado) -> Resposta:
    texto = "\n".join(["Confere?", *linhas_filtro(_filtro(estado.rascunho))])
    return Resposta(texto, _rodape(estado, Botao("💾 Salvar", "c:revisao:salvar")))


_TELAS = {
    "nome": _tela_nome,
    "tipos": _tela_tipos,
    "quartos": _tela_quartos,
    "regionais": _tela_regionais,
    "bairros": _tela_bairros,
    "valor": _tela_valor,
    "revisao": _tela_revisao,
}
