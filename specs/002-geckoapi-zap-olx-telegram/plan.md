# Implementation Plan: Zap e OLX via serviço pago e interação melhor no Telegram

**Branch**: `002-geckoapi-zap-olx-telegram` | **Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-geckoapi-zap-olx-telegram/spec.md`

## Summary

A rodada passa a coletar de várias fontes. O QuintoAndar continua como está. O Zap entra com 1
chamada à GeckoAPI por rodada, na cidade inteira, com os filtros somados das pessoas ativas. A OLX
fica pronta, mas desligada. Os itens das fontes pagas passam pela trava de cidade/UF, pelo
mapeamento de tipo e pelo bairro do catálogo antes de virar `Anuncio`. O contato do anunciante só
acompanha a mensagem na fila. Cada fonte registra o próprio estado por rodada, e isso alimenta o
alerta por fonte e o `/status`. No Telegram entram botões de URL, menu de comandos, `/ajuda`,
`/filtros`, `/status`, `/pausar` e `/retomar`. Detalhes em [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: as da 001 (httpx, beautifulsoup4, python-telegram-bot[job-queue], redis,
PyMySQL, PyYAML, tzdata). Nenhuma nova: a GeckoAPI é chamada com `httpx`.

**Storage**: MySQL 8.4 (migração 003: `pessoa.pausada_em`, `anuncio.url` 500, `alerta.fonte`,
`rodada_fonte`); Redis 7 (fila, `Mensagem.botoes`)

**Testing**: pytest com fixtures reais do Zap e da OLX (já versionadas) e testes de unidade de
normalização, contato, filtros somados, alerta por fonte e textos; ruff

**Target Platform**: Linux, Docker Compose na máquina do operador

**Project Type**: serviço de longa duração (bot + agendador + worker num processo)

**Performance Goals**: chamada ao Zap ≤ 90 s (medido: 10 a 20 s); a rodada continua terminando em
poucos minutos

**Constraints**: ≤ 1 chamada paga por fonte por rodada (7 créditos/dia com o Zap); nenhum dado de
anunciante no MySQL nem nos logs; VivaReal proibido; filtro local de cidade/UF obrigatório

**Scale/Scope**: até 5 pessoas; 30 itens do Zap por rodada; 5 comandos novos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Verificação | Status |
|---|---|---|
| I. Simples Primeiro | Módulos novos dentro de `fontes/`; sem classe-base de fonte (uma função `coletar` por módulo, com o mesmo resultado); sem dependência nova | ✅ |
| II. Testes Onde Quebra | Parse do Zap e da OLX com as fixtures reais de 27/10; sem rede nos testes; dinheiro em centavos | ✅ |
| III. Coleta Respeitosa (2.2.0) | Só Zap e OLX pela API do fornecedor; 1 chamada por fonte por rodada; filtros somados, nunca por bairro; trava de cidade/UF; fonte ligável por `GECKO_FONTES`; OLX desligada; contato só em trânsito; `resposta_fonte` sem anunciante; VivaReal ausente | ✅ |
| IV. Segredos e Acesso | `GECKO_API_KEY` no `.env`; comandos novos passam pela mesma whitelist; saldo só para o operador | ✅ |
| V. Operação Confiável | Falha de uma fonte isolada (`ResultadoFonte.status`); log por fonte; alerta por fonte; 402 para as fontes pagas sem derrubar o robô | ✅ |

**Pós-design (Phase 1)**: reavaliado após data-model e contratos, sem violações. Risco aceito e
documentado: texto com contato no AOF do Redis até a reescrita (research R7), dentro do "trânsito
pela fila" da constituição.

## Project Structure

### Documentation (this feature)

```text
specs/002-geckoapi-zap-olx-telegram/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── telegram.md
│   ├── geckoapi.md
│   └── configuracao.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/apebot/
├── config.py            # + GECKO_API_KEY, GECKO_FONTES (validação e problemas)
├── modelos.py           # + Contato; Tipo.de_zap / Tipo.de_olx; NOMES_FONTE
├── fontes/
│   ├── resultado.py     # ResultadoFonte + travas comuns (cidade/UF, bairro do catálogo)
│   ├── quintoandar.py   # + coletar() → ResultadoFonte (envolve buscar_paginas)
│   ├── geckoapi.py      # + cliente (extract, créditos, 402/5xx/timeout), filtros somados
│   ├── zap.py           # payload + parse dos itens → Anuncio + Contato
│   └── olx.py           # payload + parse dos itens → Anuncio
├── filtro.py            # + filtros_somados(pessoas)
├── mensagens.py         # + portal, contato, botões, ajuda, filtros, status, avisos por fonte
├── banco.py             # + pausa, rodada_fonte, alerta por fonte, status, recebidos 24 h
├── fila.py              # + Mensagem.botoes
├── rodada.py            # várias fontes; contatos em memória; alerta por fonte
├── telegram_bot.py      # + comandos, menu, InlineKeyboard
└── main.py              # compõe as fontes ligadas; aviso de configuração
migrations/
└── 003_fontes_e_pausa.sql
tests/
├── fixtures/geckoapi/   # já existentes
├── test_zap.py
├── test_olx.py
├── test_fontes_resultado.py
├── test_mensagens.py    # + casos novos
├── test_filtro.py       # + filtros somados
└── test_rodada.py       # + seguidas por fonte
```

**Structure Decision**: continua um projeto único com módulos planos (constituição I). Zap e OLX
ficam em módulos próprios, porque o parse de cada portal é o ponto que mais quebra (princípio II).
As travas comuns ficam em `fontes/resultado.py`, para não duplicar a regra de cidade e bairro.

## Complexity Tracking

Sem violações a justificar.
