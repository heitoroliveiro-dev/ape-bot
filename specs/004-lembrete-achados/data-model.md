# Data Model: 004 — Lembrete de achados

Migração nova: `migrations/005_lembrete.sql`.

## envio (alterada)
| Campo | Tipo | Regra |
|---|---|---|
| lembrado_em | DATETIME NULL | **Novo.** Quando o lembrete de achado foi entregue ou falhou de vez. NULL = nunca relembrado. Só faz sentido com `status = 'entregue'` |

## Redis
`apebot:pessoa:{chat_id}:imoveis`: o JSON do imóvel ganha `"lembrete": true|false` (ausente =
false, compatível com o que já está na fila).

## Fila de entrega
`Mensagem.tipo` ganha o valor `lembrete`.
