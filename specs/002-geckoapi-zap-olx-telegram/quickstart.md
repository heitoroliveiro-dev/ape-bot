# Quickstart: validar a 002

## Pré-requisitos
- MVP 001 no ar (`docker compose up -d`) e você registrado com `/start`.
- API key da GeckoAPI (dashboard → Conta). Cada rodada com o Zap ligado gasta **1 crédito**.

## Configurar
1. No `.env`: `GECKO_API_KEY=...` e `GECKO_FONTES=zap` ([contracts/configuracao.md](contracts/configuracao.md)).
2. `docker compose up -d --build` (aplica a migração 003 na subida).

## Validar sem internet (testes)
```bash
.venv/bin/pytest -q && .venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
```
Esperado: tudo verde. Parse do Zap e da OLX com as fixtures reais, trava de cidade, bairro,
WhatsApp, contato fora do banco, filtros somados, alerta por fonte, pausa e textos.

## Cenários de aceite

| # | Ação | Esperado | Spec |
|---|---|---|---|
| 1 | Abrir o bot e tocar no menu `/` | 5 comandos com descrição | FR-018 |
| 2 | `/ajuda`, `/filtros`, texto qualquer | Textos de [contracts/telegram.md](contracts/telegram.md); o texto livre sugere `/ajuda` | US2 |
| 3 | `docker compose exec app python -m apebot.main --rodada-agora` | Mensagens com portal e botões; imóvel do Zap com 👤/📞 e botão WhatsApp quando houver | US1 |
| 4 | Tocar em "Abrir anúncio" e "WhatsApp" | Abre o anúncio certo e a conversa com o número do anunciante | SC-003 |
| 5 | `SELECT fonte, status, consultas, anuncios_vistos, fora_da_cidade FROM rodada_fonte ORDER BY rodada_id DESC LIMIT 3;` | `quintoandar ok`, `zap ok` com 1 consulta, `olx desligada` | FR-001, FR-004 |
| 6 | Painel da GeckoAPI → Uso | +1 crédito por rodada | SC-001 |
| 7 | `SELECT COUNT(*) FROM resposta_fonte WHERE corpo LIKE '%{telefone visto na mensagem}%';` e o mesmo em `anuncio` | 0 | FR-009, FR-016, SC-004 |
| 8 | `/pausar`, rodada manual, `/retomar`, rodada manual | Nada durante a pausa; depois, resumo com no máximo 5 mensagens | US3, SC-006 |
| 9 | `/status` (operador e outra pessoa) | Última e próxima rodada, recebidos em 24 h, portais; o operador vê também os créditos | FR-021 |
| 10 | `GECKO_API_KEY` vazio + `docker compose restart app` + rodada manual | Aviso ⚙️ na subida; QuintoAndar normal; `zap desligada` | FR-006 |
| 11 | `GECKO_FONTES=zap,olx` só para teste (gasta 1 crédito a mais) | OLX: itens fora de BH descartados em `fora_da_cidade`, nenhum enviado | FR-007, SC-002 |

## Resultado da validação (2026-10-28, `/speckit-implement`)

| Item | Resultado |
|---|---|
| `pytest` / `ruff check` / `ruff format --check` | ✅ 188 testes, sem rede |
| Migração 003 no MySQL real | ✅ `pausada_em`, `alerta.fonte`, `anuncio.url` 500, `rodada_fonte` |
| Cenário 5 (rodada manual com `GECKO_FONTES=` vazio, sem crédito) | ✅ rodada 6: `quintoandar ok` (63 páginas, 11 novos, resumo entregue), `zap desligada`, `olx desligada` |
| Cenário 10 (sem chave) | ✅ na subida sem `GECKO_API_KEY`: aviso ⚙️ entregue ao operador; só QuintoAndar ligado |
| Defeito do MVP achado e corrigido | QuintoAndar devolve 4 a 5 de 63 páginas sem a lista (`error: true`); antes derrubava a rodada (`formato`) e bloqueava o resumo. Agora: 1 nova tentativa e conta como erro de acesso |
| Cenários 1–4, 6–9, 11 | ⏳ dependem do Telegram do operador e, os do Zap, de 1 crédito por rodada (T041) |
