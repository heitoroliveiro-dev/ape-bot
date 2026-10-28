"""OLX via GeckoAPI (research R4 da 002).

Localização só por `state` + `city`: com `region` (ou a URL `belo-horizonte-e-regiao/...`) a OLX
ignorava a cidade. Correção validada pelo suporte da GeckoAPI em 28/10/2026.
"""

import re
from typing import Any

from apebot.filtro import filtros_somados
from apebot.fontes.geckoapi import ClienteGecko, coletar_listagem
from apebot.fontes.resultado import ResultadoFonte, bairro_do_catalogo, na_cidade
from apebot.modelos import Anuncio, Pessoa, Tipo, slug

FONTE = "olx"


def payload_olx(pessoas: list[Pessoa]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "target": "olx.com.br",
        "type": "plp",
        "page": 1,
        "state": "MG",
        "city": "Belo Horizonte",
        "categoryPath": "imoveis/aluguel",
        "sort": "date",
    }
    somado = filtros_somados(pessoas)
    if somado is not None:
        payload["priceMax"] = somado.aluguel_max_centavos // 100
    return payload


def extrair_olx(corpo: dict[str, Any], catalogo: frozenset[str]) -> ResultadoFonte:
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
    local = item.get("location") or {}
    if not na_cidade(local.get("city"), local.get("state")):
        return "fora_da_cidade"
    propriedades = {
        p.get("name"): p.get("value") for p in item.get("properties") or [] if isinstance(p, dict)
    }
    tipo = _tipo(propriedades.get("category") or item.get("category"), propriedades)
    if tipo is None:
        return "tipo"
    bairro = local.get("neighborhood")
    bairro_slug = bairro_do_catalogo(bairro, catalogo)
    if bairro_slug is None:
        return "bairro_desconhecido"
    preco = item.get("price")
    aluguel = preco * 100 if isinstance(preco, int) and not isinstance(preco, bool) else None
    quartos = _inteiro(propriedades.get("rooms"))
    id_externo, url = item.get("id"), item.get("url")
    if aluguel is None or quartos is None or not id_externo or not url:
        return "incompleto"
    condominio = _inteiro(propriedades.get("condominio"))
    iptu = _inteiro(propriedades.get("iptu"))
    resultado.anuncios.append(
        Anuncio(
            fonte=FONTE,
            id_externo=str(id_externo),
            tipo=tipo,
            bairro=str(bairro),
            bairro_slug=bairro_slug,
            quartos=quartos,
            area_m2=_inteiro(propriedades.get("size")) or None,
            aluguel_centavos=aluguel,
            total_centavos=None
            if condominio is None
            else aluguel + (condominio + (iptu or 0)) * 100,
            url=str(url),
        )
    )
    return None


def _tipo(categoria: Any, propriedades: dict) -> Tipo | None:
    texto = slug(
        " ".join(
            str(v or "")
            for v in (categoria, propriedades.get("real_estate_type"), propriedades.get("re_types"))
        )
    )
    if "temporada" in texto:
        return None
    if any(p in texto for p in ("kitnet", "quitinete", "studio", "loft")):
        return Tipo.KITNET
    if "casa" in texto and "condominio" in texto:
        return Tipo.CASA_CONDOMINIO
    if any(p in texto for p in ("apartamento", "cobertura", "flat")):
        return Tipo.APARTAMENTO
    if "casa" in texto or "sobrado" in texto:
        return Tipo.CASA
    return None


def _inteiro(valor: Any) -> int | None:
    """'R$ 1.497' → 1497; '230m²' → 230; '5 ou mais' → 5."""
    if valor is None:
        return None
    digitos = re.match(r"\D*([\d.]+)", str(valor))
    return int(digitos.group(1).replace(".", "")) if digitos else None


async def coletar(
    cliente: ClienteGecko, pessoas: list[Pessoa], banco, catalogo: frozenset[str]
) -> ResultadoFonte:
    if not pessoas:
        return ResultadoFonte(fonte=FONTE, status="desligada", erro="sem pessoas ativas")
    return await coletar_listagem(
        FONTE, cliente, payload_olx(pessoas), lambda bruto: extrair_olx(bruto, catalogo), banco
    )
