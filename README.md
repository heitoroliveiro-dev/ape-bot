# ape-bot

Robô de Telegram que avisa imóveis novos para alugar em Belo Horizonte (QuintoAndar), filtrados
por pessoa (bairros, aluguel máximo, quartos mínimos, tipo), às 06, 09, 12, 15, 18, 21 e 23h.

## Configurar
1. Crie o bot no @BotFather e copie o token.
2. `cp .env.example .env` e preencha `TELEGRAM_TOKEN`, `MYSQL_PASSWORD` e `MYSQL_ROOT_PASSWORD`.
3. `cp filtros.yaml.example filtros.yaml` e preencha operador, pessoas e filtros
   (formato em `specs/001-mvp-quintoandar-telegram/contracts/filtros-yaml.md`).
   Seu `chat_id`: mande uma mensagem ao bot e procure `chat_nao_autorizado chat_id=` no log.

## Rodar
```bash
docker compose up -d --build      # sobe app, MySQL e Redis (reinício automático)
docker compose logs -f app
docker compose exec app python -m apebot.main --rodada-agora   # rodada na hora
```
Cada pessoa manda `/start` ao bot uma vez. Alterou o `filtros.yaml`? `docker compose restart app`.

## Testes
```bash
docker compose run --rm app pytest     # ou: .venv/bin/pytest
docker compose run --rm app ruff check src tests
```

## Documentação
- Arquitetura: `docs/arquitetura.md` · Constituição: `.specify/memory/constitution.md`
- Feature atual: `specs/001-mvp-quintoandar-telegram/` (spec, plan, tasks, quickstart)
