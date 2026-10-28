# Implementation Plan: Lembrete de achados

**Branch**: `004-lembrete-achados` | **Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-lembrete-achados/spec.md`

## Summary

A cada rodada, depois dos imóveis novos, o robô procura para cada pessoa ativa os imóveis já
entregues há 32 h ou mais, nunca relembrados, com aluguel atual até 70% do máximo dela, ainda
vistos nas últimas 24 h e fora dos favoritos, e coloca na mesma fila da pessoa marcados como
lembrete. O despachante reconfere e manda com o texto de achado; o entregador grava
`envio.lembrado_em`. Detalhes em [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: as da 003; nenhuma nova

**Storage**: MySQL 8.4 (migração 005: `envio.lembrado_em`); Redis (campo `lembrete` no JSON do
imóvel na fila da pessoa)

**Testing**: pytest sem rede: regra do achado, rodada enfileira lembretes, despacho reconfere,
entregador marca `lembrado_em`, texto

**Target Platform**: Linux, Docker Compose

**Project Type**: serviço de longa duração

**Performance Goals**: uma consulta a mais por pessoa ativa por rodada

**Constraints**: no máximo 1 lembrete por imóvel por pessoa; mesmas regras de janela e ritmo da 003

**Scale/Scope**: até 5 pessoas; ~1 em 5 imóveis entregues vira lembrete

## Constitution Check

| Princípio | Verificação | Status |
|---|---|---|
| I. Simples Primeiro | Reaproveita rodada, fila da pessoa, despachante e entregador; uma coluna nova; sem módulo novo | ✅ |
| II. Testes Onde Quebra | Testes da regra do achado (dinheiro em centavos, arredondamento), da rodada, do despacho e do entregador | ✅ |
| III. Coleta Respeitosa | Nenhuma coleta nova; "ainda anunciado" usa o que as rodadas já viram, sem chamada de detalhe; lembrete sem contato | ✅ |
| IV. Segredos e Acesso | Só pessoas ativas e autorizadas | ✅ |
| V. Operação Confiável | Lembrete passa pela fila de entrega com limite de taxa; log `lembrete_enfileirado` e `lembrete_descartado` | ✅ |

**Pós-design**: sem violações.

## Project Structure

```text
src/apebot/
├── filtro.py        # + limite_achado, e_achado (70%)
├── banco.py         # + achados_para, e_favorito, marcar_lembrado
├── fila.py          # FilaPessoa: campo lembrete
├── rodada.py        # + enfileira lembretes depois dos novos
├── mensagens.py     # + mensagem_lembrete
└── telegram_bot.py  # Despachante e Entregador tratam tipo "lembrete"
migrations/005_lembrete.sql
tests/ (test_filtro, test_rodada, test_despacho, test_mensagens, test_entregador)
```

**Structure Decision**: tudo nos módulos da 003; nenhuma estrutura nova.

## Complexity Tracking

Sem violações a justificar.
