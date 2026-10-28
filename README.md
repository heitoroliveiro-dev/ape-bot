# ape-bot

Telegram bot that searches for rental properties in Belo Horizonte (QuintoAndar and Zap) in rounds
at 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 and 23:00, and sends each person, one at a time,
between 8:00 and 22:00, the listings that match their filters (neighborhoods by administrative
region, maximum rent, minimum bedrooms, property type). At 23:00 a daily summary goes out.

## Setup
1. Create the bot with @BotFather and copy the token.
2. `cp .env.example .env` and fill in `TELEGRAM_TOKEN`, `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`.
3. `cp filtros.yaml.example filtros.yaml` and list the operator and the authorized `chat_id`s
   (format in `specs/003-entrega-espacada-cadastro-telegram/contracts/configuracao.md`).
   Your `chat_id`: send a message to the bot and look for `chat_nao_autorizado chat_id=` in the log.
4. Optional: `ENTREGA_INTERVALO=5-10` in `.env` only to test the spaced-out delivery in seconds
   (default `120-300`).

## Run
```bash
docker compose up -d --build      # starts app, MySQL and Redis (automatic restart)
docker compose logs -f app
docker compose exec app python -m apebot.main --rodada-agora   # run a round right now
```
Each person sends `/start` and answers the sign-up questions (name, types, bedrooms,
neighborhoods, price). After that, they change their filters on their own via `/filtros` →
"Editar filtros" (Edit filters). Authorized someone new in `filtros.yaml`?
`docker compose restart app`.

Neighborhood and region table (only if the catalog changes):
```bash
.venv/bin/python scripts/regionais_pbh.py docs/referencias/pbh-bairros-regionais.pdf > src/apebot/dados/bairros_bh.csv
```

## Railway
`railway.json` deploys the bot from the `Dockerfile`, with 1 replica and always-restart.

1. In Railway: **New Project → Deploy from GitHub repo** → `ape-bot` (the branch with this README).
2. In the same project: **+ New → Database → MySQL** and **+ New → Database → Redis**. Check that
   both have a volume (*Volumes* tab); without a volume, the data is lost on every restart.
3. Bot service variables (**Variables**; secrets typed in by you):
   | Variable | Value |
   |---|---|
   | `TELEGRAM_TOKEN`, `GECKO_API_KEY` | the ones from `.env` |
   | `GECKO_FONTES` | `zap,olx` |
   | `NETIMOVEIS` | `off` by default (the portal returns 403 to Railway's IP; see step 6) |
   | `MYSQL_HOST` / `MYSQL_PORT` | `${{MySQL.MYSQLHOST}}` / `${{MySQL.MYSQLPORT}}` |
   | `MYSQL_DATABASE` | `${{MySQL.MYSQLDATABASE}}` |
   | `MYSQL_USER` / `MYSQL_PASSWORD` | `${{MySQL.MYSQLUSER}}` / `${{MySQL.MYSQLPASSWORD}}` |
   | `REDIS_URL` | `${{Redis.REDIS_URL}}` |
   | `FILTROS_YAML` | the entire contents of `filtros.yaml` (the file is not committed to git) |
4. **Stop the bot on the laptop before the first deploy** (`docker compose stop app`): two
   processes with the same token compete for Telegram messages.
5. After the deploy, check the logs for `migracoes_aplicadas` and `Application started`. Test
   QuintoAndar from Railway's IP: run `railway login`, `railway link` (select the project and bot
   service), then `railway ssh` (the first run registers your SSH key; run it again to open the
   shell) and `python -m apebot.main --rodada-agora`; all 63 pages must go through.
6. Netimóveis: after reading the portal's terms of use, run in the same shell
   `python -m apebot.fontes.netimoveis` (a single search, no database or Telegram). With
   `status=200` and `lidos` greater than zero, set `NETIMOVEIS` to `ligado` (the service restarts
   on its own). With a 403, a challenge or a timeout, leave it off: the bot does not bypass blocks.

Moving the data from the laptop (sign-ups made via `/start`, favorites, deliveries) is optional:
`docker compose exec mysql mysqldump -u root -p apebot > apebot.sql` and import it into Railway's
MySQL through its public URL (`MYSQL_PUBLIC_URL`), before starting the bot.

## Tests
```bash
docker compose run --rm app pytest     # or: .venv/bin/pytest
docker compose run --rm app ruff check src tests
```

## Documentation
- Architecture: `docs/arquitetura.md` · Constitution: `.specify/memory/constitution.md`
- Features: `specs/001-*` (MVP), `specs/002-*` (Zap/OLX and commands), `specs/003-*` (spaced-out delivery, sign-up, favorites and summary), `specs/004-*` (findings reminder) and `specs/005-*` (Netimóveis)
