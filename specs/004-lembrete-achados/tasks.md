---

description: "Task list for 004 — Lembrete de achados"
---

# Tasks: Lembrete de achados

**Input**: Design documents from `specs/004-lembrete-achados/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: exigidos pela constituição (princípio II); escritos antes e falhando primeiro; sem rede,
Redis ou MySQL reais.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Criar `migrations/005_lembrete.sql`: `ALTER TABLE envio ADD COLUMN lembrado_em DATETIME NULL`

---

## Phase 2: User Story 1 - Ser lembrado de um imóvel bem abaixo do orçamento (Priority: P1) 🎯 MVP

**Goal**: imóveis entregues há 32 h ou mais, até 70% do máximo, ainda vistos e fora dos favoritos,
voltam uma vez com o texto de achado.

**Independent Test**: quickstart 1–4.

### Tests for User Story 1 ⚠️

- [X] T002 [P] [US1] Em `tests/test_filtro.py`: `limite_achado` de máximo 300000 → 210000; de 333333 → 233333 (arredonda para baixo); `e_achado` aceita aluguel 210000 e recusa 210001; recusa imóvel fora do bairro mesmo barato
- [X] T003 [P] [US1] Em `tests/test_mensagens.py`: `mensagem_lembrete(anuncio)` = "Esse imóvel já tinha sido encontrado, você chegou a dar uma olhada? É um achado!!\n" + as linhas de `mensagem_imovel(anuncio)` sem "Veja o imóvel que encontrei:"
- [X] T004 [P] [US1] Em `tests/test_rodada.py`: com `BancoFalso.achados_para` devolvendo dois anúncios (um ainda aceito pelo filtro e um fora do bairro), a rodada chama `FilaPessoa.adicionar(..., lembrete=True)` só para o aceito, depois dos imóveis novos
- [X] T005 [P] [US1] Em `tests/test_despacho.py`: lembrete na fila sai como `Mensagem(tipo="lembrete")` com o texto de achado e sem WhatsApp; lembrete acima de 70% do máximo atual ou favoritado (`banco.e_favorito` True) é descartado sem `apagar_pendente`; `FilaPessoaFalsa` guarda `(anuncio, contato, lembrete)`
- [X] T006 [P] [US1] Criar `tests/test_entregador.py`: com bot e banco falsos, `Entregador._entregar` de `tipo="lembrete"` chama `banco.marcar_lembrado(chat_id, chaves)` na entrega e no `Forbidden`, e nunca `marcar_envio`; de `tipo="imovel"` continua chamando `marcar_envio`

### Implementation for User Story 1

- [X] T007 [US1] Em `src/apebot/filtro.py`: `PERCENTUAL_ACHADO = 70`, `limite_achado(filtro) -> int` (`aluguel_max_centavos * 70 // 100`) e `e_achado(filtro, anuncio) -> bool` (`aceita` e aluguel ≤ limite)
- [X] T008 [US1] Em `src/apebot/banco.py`: `achados_para(chat_id, limite_centavos) -> list[Anuncio]` (research R1: `entregue`, `lembrado_em IS NULL`, `entregue_em <= agora − 32 h`, `ultimo_visto_em >= agora − 24 h`, aluguel ≤ limite, sem favorito); `e_favorito(chat_id, chave) -> bool`; `marcar_lembrado(chat_id, chaves)` (`UPDATE envio SET lembrado_em = agora`)
- [X] T009 [US1] Em `src/apebot/fila.py`: campo `lembrete` no JSON do imóvel (ausente = False); `FilaPessoa.adicionar(chat_id, anuncio, contato=None, lembrete=False)`; `retirar_mais_barato` devolve `(anuncio, contato, lembrete)`
- [X] T010 [US1] Em `src/apebot/mensagens.py`: `TEXTO_ACHADO` e `mensagem_lembrete(anuncio)` (contracts/telegram.md)
- [X] T011 [US1] Em `src/apebot/rodada.py`: depois de `_enfileirar_para`, `_enfileirar_achados(pessoa)` busca `achados_para(chat_id, limite_achado(filtro))`, filtra com `e_achado` e adiciona com `lembrete=True`; log `lembrete_enfileirado chat_id= quantidade=`
- [X] T012 [US1] Em `src/apebot/telegram_bot.py`: `Despachante._despachar` trata lembrete (reconfere `e_achado` e `e_favorito`; descarta com log `lembrete_descartado`; senão `Mensagem(tipo="lembrete")`); `Entregador._marcar` chama `marcar_lembrado` para `tipo == "lembrete"` (entregue ou falhou)

**Checkpoint**: `pytest` e `ruff` verdes; quickstart 1–4.

---

## Phase 3: Polish

- [X] T013 [P] Atualizar `docs/arquitetura.md` (tabela do MVP e seção 3: lembrete de achados) e o texto de `/ajuda` não muda
- [ ] T014 Rodar `pytest`, `ruff check` e `ruff format --check`; aplicar a migração com `docker compose up -d --build app` e validar o quickstart 1–4

## Dependencies

- T001 → T008; testes T002–T006 antes de T007–T012; T009 antes de T011/T012; T014 por último.
