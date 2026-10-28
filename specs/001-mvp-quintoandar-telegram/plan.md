# Implementation Plan: MVP — avisos de imóveis do QuintoAndar no Telegram

**Branch**: `001-mvp-quintoandar-telegram` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-mvp-quintoandar-telegram/spec.md`

## Summary

Bot de Telegram sempre ligado que, 7 vezes por dia (horário de Brasília), consulta as páginas
públicas do QuintoAndar por bairro + tipo, extrai o JSON embutido (`__NEXT_DATA__`), guarda os
anúncios no MySQL, aplica os filtros de cada pessoa e enfileira no Redis as mensagens dos imóveis
ainda não enviados; um worker entrega no Telegram respeitando o limite de taxa. Primeira rodada
vira resumo; falhas repetidas avisam o operador. Detalhes em [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: httpx, beautifulsoup4, python-telegram-bot[job-queue], redis (asyncio),
PyMySQL, PyYAML, tzdata

**Storage**: MySQL 8.4 (anúncios, envios, rodadas, alertas); Redis 7 (fila de envio, AOF)

**Testing**: pytest (parse com fixtures reais + filtro + formatação de mensagens), ruff

**Target Platform**: Linux, Docker Compose na máquina do operador

**Project Type**: serviço de longa duração (bot + agendador + worker num processo)

**Performance Goals**: rodada completa ≤ 3 min com até 30 combinações bairro×tipo; entrega ≤ 1 msg/s por chat

**Constraints**: só páginas públicas permitidas; 2–5 s entre requisições; sem login; sem
seguir redirects; horários em America/Sao_Paulo

**Scale/Scope**: até 5 pessoas; dezenas de requisições e mensagens por rodada

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Verificação | Status |
|---|---|---|
| I. Simples Primeiro | Um processo, módulos por responsabilidade, SQL puro, sem ORM/DDD | ✅ |
| II. Testes Onde Quebra | Parse com fixtures reais e filtro testados; sem rede nos testes; centavos `int` | ✅ |
| III. Coleta Respeitosa | URLs públicas permitidas (R1), sem login/API interna/contorno, 2–5 s, backoff, sem redirects, sem dados de anunciante | ✅ |
| IV. Segredos e Acesso | `.env` fora do git; whitelist = `pessoas[].chat_id`; não autorizado → silêncio | ✅ |
| V. Operação Confiável | Falha isolada por página/rodada (R10), log por rodada, fuso fixo (R6), fila Redis com taxa (R7) | ✅ |

**Pós-design (Phase 1)**: reavaliado após data-model e contratos — sem violações. A página
`/imovel/{id}` não é usada (menos requisições).

## Project Structure

### Documentation (this feature)

```text
specs/001-mvp-quintoandar-telegram/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── filtros-yaml.md
│   └── telegram.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/apebot/
├── __init__.py
├── config.py            # .env + filtros.yaml → objetos validados (contracts/filtros-yaml.md)
├── modelos.py           # Anuncio, Filtro, Tipo (dataclasses frozen), slug()
├── dados/bairros_bh.txt # 289 slugs de BH do sitemap do QuintoAndar
├── fontes/
│   ├── __init__.py
│   └── quintoandar.py   # montar URL, buscar (httpx, sleep, backoff), parse __NEXT_DATA__
├── filtro.py            # Filtro.aceita, seleção de novos por pessoa
├── mensagens.py         # textos de contracts/telegram.md, resumo em ≤ 5 partes
├── banco.py             # PyMySQL + SQL puro + migrações
├── fila.py              # Redis: enfileirar, consumir, reenfileirar pendentes
├── rodada.py            # orquestra: coleta → banco → filtro → fila → registro/alerta
├── telegram_bot.py      # /start, whitelist, worker de envio
└── main.py              # composição, agendamento (JobQueue), --rodada-agora
migrations/
└── 001_inicial.sql
tests/
├── fixtures/quintoandar/  # já existentes
├── test_quintoandar_parse.py
├── test_filtro.py
├── test_mensagens.py
└── test_config.py
Dockerfile
docker-compose.yml
.env.example
filtros.yaml.example
pyproject.toml
```

**Structure Decision**: projeto único em `src/apebot/`, módulos planos por responsabilidade
(constituição I). `mensagens.py` e `rodada.py` separados de `telegram_bot.py` para que a lógica
de texto e de seleção seja testável sem Telegram.

## Complexity Tracking

Sem violações a justificar.
