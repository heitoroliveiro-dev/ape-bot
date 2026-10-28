# Implementation Plan: Netimóveis como fonte de anúncios

**Branch**: `005-netimoveis-fonte` | **Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-netimoveis-fonte/spec.md`

## Summary

Novo coletor `fontes/netimoveis.py`, no formato `ResultadoFonte` e no mesmo molde do QuintoAndar:
para cada par (bairro, tipo) da união dos filtros das pessoas ativas, uma busca pública
`/locacao/minas-gerais/belo-horizonte/bairros/{bairro}/{tipo}?quartos={N}` (só a 1ª página), com
intervalo de 2–5 s e backoff. Os dados vêm dos blocos JSON-LD da página (`ItemList` →
`RealEstateListing`): id, tipo e bairro pela URL do imóvel, aluguel, quartos, área e condomínio.
Busca vazia = página sem `ItemList`; corte da 1ª página vai para o log. A fonte entra na composição
de `main.Fontes`, no `NOMES_FONTE`/`ORDEM_FONTES` (status, ajuda, resumo) e é ligada pela variável
`NETIMOVEIS` (padrão desligado). Sem migração: `fonte` já é texto livre em todas as tabelas. Uma
sonda (`python -m apebot.fontes.netimoveis`) valida o acesso a partir do IP do Railway.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `httpx` e `beautifulsoup4` (já no projeto); nada novo. Playwright não é
necessário (dados no HTML, research R2).

**Storage**: MySQL (sem mudança de esquema; `anuncio`, `envio`, `rodada_fonte`, `alerta` já têm
`fonte VARCHAR(20)`), Redis (filas por pessoa, sem mudança).

**Testing**: `pytest` com fixtures reais cortadas em `tests/fixtures/netimoveis/`; sem internet.

**Target Platform**: container Linux no Railway (1 réplica, restart ALWAYS, MySQL e Redis como
serviços do Railway); localmente via Docker Compose.

**Project Type**: serviço único (bot de Telegram + agendador + coletores).

**Performance Goals**: ~100 buscas por rodada em ~6–7 min; rodada inteira (QuintoAndar + Zap +
Netimóveis) bem abaixo de 2 h.

**Constraints**: constituição III (só `robots.txt` permitido, 2–5 s entre requisições, backoff,
nenhum contorno de proteção, nenhum dado de anunciante); dinheiro em centavos.

**Scale/Scope**: 2 pessoas, ~50 bairros, 4 tipos; ~1.350 imóveis residenciais de BH no portal.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Como o plano atende | OK |
|---|---|---|
| I. Simples Primeiro | Um módulo novo em `fontes/`, no mesmo molde do QuintoAndar; reaproveita `ResultadoFonte`, `status_rodada`, `bairro_do_catalogo`, alerta e fila; sem migração | ✅ |
| II. Testes Onde Quebra | Parse e mapeamentos testados com fixtures reais cortadas; nenhum teste acessa a internet; aluguel e condomínio em centavos | ✅ |
| III. Coleta Respeitosa | Só `/locacao/...` permitido; sem `pag=`, `precoMin/Max`, `ordem=`, `/pesquisa/`, `/api/`; intervalo 2–5 s e backoff 429/5xx; desafio antirrobô = erro de acesso, sem contorno; JSON-LD é superfície pública da página, não API interna; nenhum dado de anunciante lido | ✅ |
| IV. Segredos e Acesso | Sem segredo novo; liga/desliga por variável de ambiente | ✅ |
| V. Operação Confiável | Falha isolada por busca e por fonte; `rodada_fonte` e alerta por fonte; log de corte; status da rodada continua do QuintoAndar | ✅ |
| Restrições técnicas | Só `httpx` + `beautifulsoup4`; Playwright não entra | ✅ |

Re-check pós-design: sem violações; Complexity Tracking vazio.

## Project Structure

### Documentation (this feature)

```text
specs/005-netimoveis-fonte/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── configuracao.md   # variável NETIMOVEIS
│   └── telegram.md       # nome do portal no /status, /ajuda, mensagem e resumo
└── tasks.md              # /speckit-tasks
```

### Source Code (repository root)

```text
src/apebot/
├── fontes/
│   ├── netimoveis.py      # NOVO: url_busca, combinacoes, extrair (JSON-LD), coletar, sonda (__main__)
│   └── resultado.py       # reuso: ResultadoFonte, status_rodada, bairro_do_catalogo
├── modelos.py             # NOMES_FONTE += netimoveis; mapa tipo do portal → Tipo; slug de busca por Tipo
├── config.py              # Segredos.netimoveis + aviso de valor inválido
├── mensagens.py           # ORDEM_FONTES += netimoveis
└── main.py                # Fontes: Coletor("netimoveis", ...) ligado ou _desligada

tests/
├── fixtures/netimoveis/   # NOVO: páginas reais cortadas (research R9)
├── test_netimoveis.py     # NOVO: parse, tipos, bairros, vazio, corte, formato inválido, status
├── test_config.py         # NETIMOVEIS ligado/desligado/inválido
└── test_mensagens.py      # Netimóveis em /status, /ajuda e resumo
```

**Structure Decision**: projeto único existente; a fonte nova fica em `src/apebot/fontes/`, ao lado de
`quintoandar.py`, `zap.py` e `olx.py`.

## Complexity Tracking

Nenhuma violação a justificar.
