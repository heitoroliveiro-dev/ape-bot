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

## Testes
```bash
docker compose run --rm app pytest     # ou: .venv/bin/pytest
docker compose run --rm app ruff check src tests
```

## Documentação
- Arquitetura: `docs/arquitetura.md` · Constituição: `.specify/memory/constitution.md`
- Features: `specs/001-*` (MVP), `specs/002-*` (Zap/OLX e comandos) e `specs/003-*` (entrega espaçada, cadastro, favoritos e resumo)
