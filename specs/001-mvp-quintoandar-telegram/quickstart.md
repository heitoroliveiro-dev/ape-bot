# Quickstart: validar o MVP 001

## Pré-requisitos
- Docker + Docker Compose; `systemctl enable --now docker` (sobe no boot).
- Bot criado no @BotFather (token).
- Seu `chat_id`: mande qualquer mensagem ao bot e veja o log `chat_nao_autorizado chat_id=...`
  no primeiro `docker compose logs app`, ou use @userinfobot.

## Configurar
1. `cp .env.example .env` e preencher `TELEGRAM_TOKEN` e senhas do MySQL.
2. `cp filtros.yaml.example filtros.yaml` e preencher conforme
   [contracts/filtros-yaml.md](contracts/filtros-yaml.md).

## Validar sem internet (testes)
```bash
docker compose run --rm app pytest      # parse com fixtures + filtro
docker compose run --rm app ruff check .
```
Esperado: tudo verde; nenhum teste abre conexão de rede.

## Subir
```bash
docker compose up -d --build
docker compose logs -f app
```
Esperado no log: migrações aplicadas, filtros validados, 7 rodadas agendadas (horário de Brasília).

## Cenários de aceite
| # | Ação | Esperado | Spec |
|---|---|---|---|
| 1 | `/start` do seu chat | Confirmação + filtros | US2, FR-002 |
| 2 | `/start` de um chat fora do YAML | Silêncio; log `chat_nao_autorizado` | FR-001 |
| 3 | Rodada manual: `docker compose exec app python -m apebot.main --rodada-agora` | Primeira vez: resumo (≤ 5 mensagens) | US3, FR-015 |
| 4 | Repetir o comando 3 | Nada é reenviado | FR-013 |
| 5 | Mudar `aluguel_max` no YAML, `docker compose restart app`, rodar de novo | Novo resumo só com imóveis ainda não enviados | US3 cen. 3 |
| 6 | `docker compose restart app` | Volta sozinho; rodadas reagendadas | FR-020 |
| 7 | Simular falha: `--rodada-agora --simular-falha` 3× | Aviso ⚠️ ao operador na 3ª | FR-019 |
| 8 | `--rodada-agora` normal depois | Aviso ✅ de recuperação | FR-019 |
| 9 | Conferir rodadas: `SELECT * FROM rodada ORDER BY id DESC LIMIT 5;` | Contagens preenchidas | FR-018 |

## Resultado da validação (2026-10-27, `/speckit-implement`)

| Item | Resultado |
|---|---|
| `pytest` (local e dentro da imagem) | ✅ 67 testes, sem rede |
| `ruff check` / `ruff format --check` | ✅ |
| Imagem Docker | ✅ build ok; processo roda como `uid=1000(apebot)` |
| Rodada real (MySQL 8.4 + Redis 7 temporários, QuintoAndar ao vivo, 1 pessoa, Buritis × apartamento/casa) | ✅ 2 páginas 200; 30 anúncios; 18 descartados como fora do bairro (o portal completa a página de casas com bairros vizinhos); 1ª rodada → 1 resumo com 12 imóveis; 2ª rodada → 0 enfileirados (sem repetição); `filtros_hash` gravado; bairro inválido reportado em `problemas` |
| Cenários 1, 2, 5–8 (dependem do Telegram) | ⏳ pendentes: precisam de `TELEGRAM_TOKEN` e dos `chat_id`s reais |
