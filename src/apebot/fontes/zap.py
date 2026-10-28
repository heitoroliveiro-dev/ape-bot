"""Zap Imóveis via GeckoAPI: consulta única na cidade e parse da listagem (research R2, R3, R12)."""

from typing import Any

from apebot.filtro import filtros_somados
from apebot.fontes.geckoapi import ClienteGecko, coletar_listagem
from apebot.fontes.resultado import (
    ResultadoFonte,
    bairro_do_catalogo,
    na_cidade,
    telefone_legivel,
    whatsapp_url,
)
from apebot.modelos import Anuncio, Contato, Pessoa, Tipo

FONTE = "zap"
QUARTOS_TETO = 4  # o "4" do Zap é "4 ou mais", como no site


def payload_zap(pessoas: list[Pessoa]) -> dict[str, Any]:
    """Uma consulta para todas as pessoas: filtros somados, nunca por bairro (constituição III)."""
    payload: dict[str, Any] = {
        "target": "zapimoveis.com.br",
        "type": "plp",
        "page": 1,
        "businessType": "rent",
        "state": "MG",
        "city": "Belo Horizonte",
    }
    somado = filtros_somados(pessoas)
    if somado is None:
        return payload
    payload["priceMax"] = somado.aluguel_max_centavos // 100
    if somado.quartos_min > 0:
        payload["bedrooms"] = list(range(min(somado.quartos_min, QUARTOS_TETO), QUARTOS_TETO + 1))
    payload["propertyTypes"] = [
        nome for tipo in Tipo if tipo in somado.tipos for nome in tipo.zap_property_types
    ]
    return payload


def extrair_zap(corpo: dict[str, Any], catalogo: frozenset[str]) -> ResultadoFonte:
    resultado = ResultadoFonte(fonte=FONTE)
    itens = (corpo.get("data") or {}).get("items")
    if not isinstance(itens, list):
        resultado.status, resultado.erro_de_formato = "falha", True
        resultado.erro = "formato: data.items ausente"
        return resultado
    for item in itens:
        motivo = _ler_item(item, catalogo, resultado) if isinstance(item, dict) else "incompleto"
        if motivo:
            resultado.descartados[motivo] += 1
    return resultado


def _ler_item(item: dict, catalogo: frozenset[str], resultado: ResultadoFonte) -> str | None:
    """Acrescenta o anúncio (e o contato) ao resultado; devolve o motivo do descarte, se houver."""
    if item.get("business") != "RENTAL":
        return "venda"
    endereco = item.get("address") or {}
    if not na_cidade(endereco.get("city"), endereco.get("state")):
        return "fora_da_cidade"
    tipos = item.get("unitTypes") or []
    tipo = Tipo.de_zap(str(tipos[0])) if tipos else None
    if tipo is None:
        return "tipo"
    bairro = endereco.get("neighborhood")
    bairro_slug = bairro_do_catalogo(bairro, catalogo)
    if bairro_slug is None:
        return "bairro_desconhecido"
    atributos = item.get("attributes") or {}
    precos = item.get("prices") or {}
    aluguel = _centavos(precos.get("rent"))
    quartos = _primeiro_inteiro(atributos.get("bedrooms"))
    id_externo, url = item.get("id"), item.get("url")
    if aluguel is None or quartos is None or not id_externo or not url:
        return "incompleto"

    condominio = _centavos(precos.get("condominium"))
    iptu = _centavos(precos.get("iptu"))
    area = _primeiro_inteiro(atributos.get("usableAreas"))
    anuncio = Anuncio(
        fonte=FONTE,
        id_externo=str(id_externo),
        tipo=tipo,
        bairro=str(bairro),
        bairro_slug=bairro_slug,
        quartos=quartos,
        area_m2=area if area else None,
        aluguel_centavos=aluguel,
        total_centavos=None if condominio is None else aluguel + condominio + (iptu or 0),
        url=str(url),
    )
    resultado.anuncios.append(anuncio)
    contato = _contato(item.get("advertiser"))
    if contato:
        resultado.contatos[anuncio.chave] = contato
    return None


def _contato(anunciante: Any) -> Contato | None:
    """Só em trânsito: vai para a mensagem, nunca para o banco (constituição 2.2.0)."""
    if not isinstance(anunciante, dict):
        return None
    nome = anunciante.get("name") or None
    telefones = anunciante.get("phoneNumbers") or []
    telefone = str(telefones[0]) if telefones else None
    whatsapp = anunciante.get("whatsAppNumber")
    contato = Contato(
        nome=str(nome) if nome else None,
        telefone=telefone_legivel(telefone) if telefone else None,
        whatsapp_url=whatsapp_url(str(whatsapp)) if whatsapp else None,
    )
    return contato if any((contato.nome, contato.telefone, contato.whatsapp_url)) else None


def _centavos(valor: Any) -> int | None:
    if isinstance(valor, bool) or not isinstance(valor, int | float) or valor < 0:
        return None
    return round(valor * 100)


def _primeiro_inteiro(valores: Any) -> int | None:
    if not isinstance(valores, list) or not valores:
        return None
    valor = valores[0]
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


async def coletar(
    cliente: ClienteGecko, pessoas: list[Pessoa], banco, catalogo: frozenset[str]
) -> ResultadoFonte:
    if not pessoas:  # ninguém ativo: não gasta crédito
        return ResultadoFonte(fonte=FONTE, status="desligada", erro="sem pessoas ativas")
    return await coletar_listagem(
        FONTE, cliente, payload_zap(pessoas), lambda bruto: extrair_zap(bruto, catalogo), banco
    )
