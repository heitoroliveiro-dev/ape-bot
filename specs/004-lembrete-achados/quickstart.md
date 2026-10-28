# Quickstart: validar a 004

```bash
.venv/bin/pytest -q && .venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
docker compose up -d --build app   # aplica a migração 005
```

| # | Ação | Esperado | Spec |
|---|---|---|---|
| 1 | Esperar 32 h depois de uma entrega (ou, só para validar, `UPDATE envio SET entregue_em = entregue_em - INTERVAL 33 HOUR WHERE chat_id = …`) e rodar `--rodada-agora` | Os imóveis até 70% do máximo, vistos na rodada, voltam com a mensagem de achado | US1, FR-001 |
| 2 | `SELECT COUNT(*) FROM envio WHERE lembrado_em IS NOT NULL` depois da entrega; rodar de novo | Nenhum lembrete repetido | FR-005 |
| 3 | Favoritar um achado antes do lembrete | Ele não volta | FR-001 |
| 4 | `/status` e resumo | Contagem de recebidos sem os lembretes | FR-006 |
