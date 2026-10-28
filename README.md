# ape-bot

Robô de Telegram que procura imóveis para alugar em Belo Horizonte (QuintoAndar e Zap) nas rodadas
das 06, 09, 12, 15, 18, 21 e 23h e manda para cada pessoa, um por vez, das 8h às 22h, os que batem
com os filtros dela (bairros por regional, aluguel máximo, quartos mínimos, tipo). Às 23h sai um
resumo do dia.

## Configurar
1. Crie o bot no @BotFather e copie o token.
2. `cp .env.example .env` e preencha `TELEGRAM_TOKEN`, `MYSQL_PASSWORD` e `MYSQL_ROOT_PASSWORD`.
3. `cp filtros.yaml.example filtros.yaml` e liste o operador e os `chat_id`s autorizados
   (formato em `specs/003-entrega-espacada-cadastro-telegram/contracts/configuracao.md`).
   Seu `chat_id`: mande uma mensagem ao bot e procure `chat_nao_autorizado chat_id=` no log.
4. Opcional: `ENTREGA_INTERVALO=5-10` no `.env` só para testar a entrega espaçada em segundos
   (padrão `120-300`).

## Rodar
```bash
docker compose up -d --build      # sobe app, MySQL e Redis (reinício automático)
docker compose logs -f app
docker compose exec app python -m apebot.main --rodada-agora   # rodada na hora
```
Cada pessoa manda `/start` e responde o cadastro (nome, tipos, quartos, bairros, valor). Depois,
muda os filtros sozinha pelo `/filtros` → "Editar filtros". Autorizou alguém novo no
`filtros.yaml`? `docker compose restart app`.

Tabela de bairros e regionais (só se o catálogo mudar):
```bash
.venv/bin/python scripts/regionais_pbh.py docs/referencias/pbh-bairros-regionais.pdf > src/apebot/dados/bairros_bh.csv
```

## Railway
O `railway.json` sobe o bot pelo `Dockerfile`, com 1 réplica e reinício sempre.

1. No Railway: **New Project → Deploy from GitHub repo** → `ape-bot` (branch com este README).
2. No mesmo projeto: **+ New → Database → MySQL** e **+ New → Database → Redis**. Confira se
   os dois têm volume (aba *Volumes*); sem volume, os dados somem a cada reinício.
3. Variáveis do serviço do bot (**Variables**; segredos digitados por você):
   | Variável | Valor |
   |---|---|
   | `TELEGRAM_TOKEN`, `GECKO_API_KEY` | os do `.env` |
   | `GECKO_FONTES` | `zap` |
   | `MYSQL_HOST` / `MYSQL_PORT` | `${{MySQL.MYSQLHOST}}` / `${{MySQL.MYSQLPORT}}` |
   | `MYSQL_DATABASE` | `${{MySQL.MYSQLDATABASE}}` |
   | `MYSQL_USER` / `MYSQL_PASSWORD` | `${{MySQL.MYSQLUSER}}` / `${{MySQL.MYSQLPASSWORD}}` |
   | `REDIS_URL` | `${{Redis.REDIS_URL}}` |
   | `FILTROS_YAML` | o conteúdo inteiro do `filtros.yaml` (o arquivo não vai para o git) |
4. **Pare o bot do notebook antes do primeiro deploy** (`docker compose stop app`): dois
   processos com o mesmo token disputam as mensagens do Telegram.
5. Depois do deploy, nos logs: `migracoes_aplicadas` e `Application started`. Teste o QuintoAndar
   a partir do IP do Railway: no serviço do bot, **⋯ → Shell** (ou `railway ssh`) e
   `python -m apebot.main --rodada-agora`; as 63 páginas precisam passar.

Levar os dados do notebook (cadastros feitos pelo `/start`, favoritos, envios) é opcional:
`docker compose exec mysql mysqldump -u root -p apebot > apebot.sql` e importar no MySQL do
Railway pela URL pública dele (`MYSQL_PUBLIC_URL`), antes de subir o bot.

## Testes
```bash
docker compose run --rm app pytest     # ou: .venv/bin/pytest
docker compose run --rm app ruff check src tests
```

## Documentação
- Arquitetura: `docs/arquitetura.md` · Constituição: `.specify/memory/constitution.md`
- Features: `specs/001-*` (MVP), `specs/002-*` (Zap/OLX e comandos) e `specs/003-*` (entrega espaçada, cadastro, favoritos e resumo)
