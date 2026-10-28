# Quickstart: validar a 003

## Pré-requisitos
- A 002 no ar (`docker compose up -d`) e você registrado com `/start`.
- Um segundo chat do Telegram (de outra pessoa ou de outra conta) para testar o cadastro do zero.
- `pdftotext` (poppler-utils), só para gerar de novo a tabela de regionais.

## Validar sem internet (testes)
```bash
.venv/bin/pytest -q && .venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
```
Esperado: tudo verde. Cobre leitura de valor e nome, transições do cadastro e da edição, ordem e
janela do despachante, sorteio do intervalo, refiltragem no despacho, reconciliação depois de
reiniciar, catálogo com regionais, textos do contrato e resumo.

## Tabela de regionais
```bash
python scripts/regionais_pbh.py docs/referencias/pbh-bairros-regionais.pdf > src/apebot/dados/bairros_bh.csv
git diff --stat src/apebot/dados/
```
Esperado: 283 linhas de dados; nenhum slug `*-sp-brasil` ou `*-justinopolis`; os 21 bairros do
seu filtro numa das 9 regionais ([research R9](research.md)).

## Subir
1. No `.env`, só para validar: `ENTREGA_INTERVALO=5-10` ([contracts/configuracao.md](contracts/configuracao.md)).
2. Em `filtros.yaml`, acrescente o segundo chat só com `chat_id` (sem `filtros`).
3. `docker compose up -d --build` (aplica a migração 004 e semeia o seu cadastro a partir do arquivo).

## Cenários de aceite

| # | Ação | Esperado | Spec |
|---|---|---|---|
| 1 | No segundo chat: `/start` e responda tudo | Perguntas e botões de [contracts/telegram.md](contracts/telegram.md); no fim, a mensagem "Perfeito, {nome}!…" | US3 |
| 2 | Cadastro: no meio, `docker compose restart app` e depois `/start` | Volta na mesma etapa, com as respostas anteriores | FR-023 |
| 3 | Na etapa valor: `3k`, `-3000`, `3000.50`, `3 000`, `100`, depois `3.000,00` | Recusa com o exemplo nas 5 primeiras; aceita a última | FR-020, SC-006 |
| 4 | No seu chat: `/filtros` | Formato "Seus filtros -" com botão Editar; sem "fale com Heitor" | FR-025 |
| 5 | Editar filtros → mude o valor → Salvar; `/filtros` | Valor novo; "valem a partir da próxima rodada" | US2 |
| 6 | Editar filtros → Cancelar no meio | Filtros iguais aos de antes | FR-026 |
| 7 | `docker compose exec app python -m apebot.main --rodada-agora` (entre 8h e 22h) | Mensagens uma a uma no formato novo, de 5 a 10 s entre elas, em ordem crescente de valor; nenhuma lista em bloco | US1, FR-007 |
| 8 | Durante o 7: `docker compose restart app` | Continua do ponto em que parou; nada repetido. `SELECT status, COUNT(*) FROM envio WHERE chat_id = … GROUP BY status;` antes e depois | FR-005, SC-008 |
| 9 | Durante o 7: Editar filtros e baixe o valor para menos que os próximos da fila | Os que ficaram acima do valor não chegam | FR-006 |
| 10 | Tocar em "⭐ Salvar como favorito" em 2 imóveis, de novo em 1; `/favoritos` | Botão alterna; lista só o que ficou | US5 |
| 11 | Rodada manual depois das 22h (ou `date` do container ajustado) | Imóveis ficam na fila (`/status`: "Na sua fila: N"); nada sai até as 8h | FR-003 |
| 12 | Esperar a rodada das 23h (ou chamar `enviar_resumos` pelo shell do container) | Um resumo por pessoa ativa, com contagem por portal e créditos; reiniciar e repetir não manda outro | US4, FR-017 |
| 13 | `/pausar` com itens na fila; rodada manual; `/retomar`; rodada manual | Nada durante a pausa; depois volta um a um | Edge Cases |
| 14 | `SELECT COUNT(*) FROM favorito f JOIN anuncio a USING (fonte, id_externo) WHERE …` com telefone visto | Nenhuma coluna com dado de anunciante em `favorito`, `conversa` ou `pessoa` | SC-009 |
| 15 | Voltar `ENTREGA_INTERVALO` ao padrão e observar um dia | Intervalos de 2 a 5 min; nada antes das 8h nem depois das 22h | SC-001 |
