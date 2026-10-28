---

description: "Task list for 001 — MVP QuintoAndar → Telegram"
---

# Tasks: MVP — avisos de imóveis do QuintoAndar no Telegram

**Input**: Design documents from `specs/001-mvp-quintoandar-telegram/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Exigidos pela constituição (princípio II) apenas para parse, filtro e formatação de
mensagens — escritos antes da implementação correspondente, devem falhar primeiro. Nenhum teste
acessa a internet.

**Organization**: Tasks agrupadas por user story. US2 (registro) vem antes de US1 porque, embora
ambas sejam P1, US1 só entrega mensagens a pessoas registradas.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1–US4 conforme spec.md

## Path Conventions

Projeto único: `src/apebot/`, `tests/`, `migrations/` na raiz do repositório.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: esqueleto do projeto e ambiente Docker

- [X] T001 Criar estrutura de pastas do plan.md: `src/apebot/__init__.py`, `src/apebot/fontes/__init__.py`, `src/apebot/dados/`, `migrations/`, `tests/__init__.py`
- [X] T002 Criar `pyproject.toml` (projeto `apebot`, Python `>=3.12`, layout `src/`; deps: `httpx`, `beautifulsoup4`, `python-telegram-bot[job-queue]`, `redis`, `PyMySQL`, `PyYAML`, `tzdata`; dev: `pytest`, `ruff`; config do ruff com `line-length = 100` e regras `E,F,I,UP,B`; `pytest` com `testpaths = ["tests"]`)
- [X] T003 [P] Criar `.gitignore` com `.env`, `filtros.yaml`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`, `.claude/settings.local.json`
- [X] T004 [P] Criar `.env.example` com `TELEGRAM_TOKEN=`, `MYSQL_HOST=mysql`, `MYSQL_PORT=3306`, `MYSQL_DATABASE=apebot`, `MYSQL_USER=apebot`, `MYSQL_PASSWORD=`, `MYSQL_ROOT_PASSWORD=`, `REDIS_URL=redis://redis:6379/0`, `FILTROS_PATH=/app/filtros.yaml`
- [X] T005 [P] Criar `filtros.yaml.example` exatamente com o exemplo de `contracts/filtros-yaml.md`
- [X] T006 [P] Criar `Dockerfile` (base `python:3.12-slim`, instala o pacote, usuário não root `apebot`, `WORKDIR /app`, `CMD ["python", "-m", "apebot.main"]`)
- [X] T007 Criar `docker-compose.yml` com serviços `app` (build local, `env_file: .env`, monta `./filtros.yaml:/app/filtros.yaml:ro`, `depends_on` mysql/redis com healthcheck), `mysql` (`mysql:8.4`, volume `mysql-dados`, healthcheck `mysqladmin ping`), `redis` (`redis:7`, `--appendonly yes`, volume `redis-dados`); todos com `restart: unless-stopped`
- [X] T008 [P] Gerar `src/apebot/dados/bairros_bh.txt`: um slug por linha, extraído de `tests/fixtures/quintoandar/bairros-bh-sitemap.txt` removendo o prefixo `https://www.quintoandar.com.br/alugar/imovel/` e o sufixo `-belo-horizonte-mg-brasil` (289 linhas)

**Checkpoint**: `docker compose build` passa; `pytest` roda (0 testes).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: modelos, configuração, banco, fila e esqueleto do bot usados por todas as stories

**⚠️ CRITICAL**: nenhuma story começa antes desta fase

- [X] T009 [P] Escrever testes de `slug()` e `Tipo` em `tests/test_modelos.py`: `slug("Santa Mônica") == "santa-monica"`, `slug("Funcionários") == "funcionarios"`; mapeamento `Tipo` ↔ slug de URL ↔ `type` do JSON conforme research R2 (`apartamento`/`Apartamento`, `casa`/`Casa`, `casacondominio`/`CasaCondominio`, `kitnet`/`StudioOuKitchenette`)
- [X] T010 Implementar `src/apebot/modelos.py`: `slug(texto)` (minúsculas, sem acento, não alfanumérico → hífen, sem hífens duplicados nas pontas); enum `Tipo` (`apartamento`, `casa`, `casa_condominio`, `kitnet`) com `slug_url` e `de_json(type)`; dataclass frozen `Anuncio(fonte, id_externo, tipo, bairro, bairro_slug, quartos, area_m2: int | None, aluguel_centavos: int, total_centavos: int | None, url)`; dataclass frozen `Filtro(bairros: frozenset[str], aluguel_max_centavos: int, quartos_min: int, tipos: frozenset[Tipo])`; dataclass frozen `Pessoa(chat_id, nome, filtro)`; constante `HORARIOS_RODADA = (6, 9, 12, 15, 18, 21, 23)` e `FUSO = ZoneInfo("America/Sao_Paulo")`
- [X] T011 [P] Escrever testes de configuração em `tests/test_config.py` cobrindo cada linha da tabela de validação de `contracts/filtros-yaml.md` (operador ausente/não listado → erro fatal; `chat_id` duplicado → erro fatal; bairro desconhecido → ignorado + problema; `aluguel_max <= 0` → pessoa ignorada; tipo inválido → ignorado; tipos vazio → pessoa ignorada; nenhum bairro válido → pessoa ignorada; nome "Funcionários" e slug "funcionarios" aceitos)
- [X] T012 Implementar `src/apebot/config.py`: `carregar_segredos()` lê variáveis do `.env.example`; `carregar_filtros(caminho, bairros_validos) -> Configuracao(operador_chat_id, pessoas: list[Pessoa], problemas: list[str])` com as regras de `contracts/filtros-yaml.md`; `aluguel_max` em reais convertido para centavos; `bairros_validos()` lê `src/apebot/dados/bairros_bh.txt`; exceção `ConfiguracaoInvalida` para erros fatais
- [X] T013 Criar `migrations/001_inicial.sql` com as tabelas de `data-model.md`: `pessoa(chat_id BIGINT PK, nome VARCHAR(80), registrada_em DATETIME NULL, filtros_hash CHAR(64) NULL)`; `anuncio(fonte VARCHAR(20), id_externo VARCHAR(40), tipo ENUM('apartamento','casa','casa_condominio','kitnet') NOT NULL, bairro VARCHAR(80), bairro_slug VARCHAR(80), quartos TINYINT NOT NULL, area_m2 SMALLINT NULL, aluguel_centavos INT NOT NULL, total_centavos INT NULL, url VARCHAR(255), primeiro_visto_em DATETIME, ultimo_visto_em DATETIME, PK(fonte,id_externo), INDEX(bairro_slug,tipo))`; `envio(chat_id, fonte, id_externo, status ENUM('pendente','entregue','falhou'), criado_em, entregue_em NULL, tentativas TINYINT DEFAULT 0, PK(chat_id,fonte,id_externo), FKs)`; `rodada(...)`; `alerta(...)`; `schema_migracao(versao VARCHAR(40) PK, aplicada_em DATETIME)` — charset `utf8mb4`
- [X] T014 Implementar `src/apebot/banco.py`: conexão PyMySQL a partir dos segredos (autocommit, `utf8mb4`), `aplicar_migracoes(pasta)` (aplica `NNN_*.sql` ainda não registrados em `schema_migracao`), e funções síncronas com SQL puro: `sincronizar_pessoas(pessoas)` (insere/atualiza nome, não apaga), `registrar_pessoa(chat_id)` (preenche `registrada_em` só se NULL), `pessoas_registradas()`, `atualizar_filtros_hash(chat_id, hash)`, `salvar_anuncios(anuncios) -> int novos` (upsert atualizando preço e `ultimo_visto_em`), `ja_enviados(chat_id) -> set[(fonte,id)]`, `criar_envios_pendentes(chat_id, ids) -> ids_inseridos` (`INSERT IGNORE`), `marcar_envio(chat_id, ids, status)`, `pendentes_antigos(minutos)`; todas usadas via `asyncio.to_thread` pelos chamadores
- [X] T015 Implementar `src/apebot/fila.py` (research R7): `Mensagem` dataclass (`chat_id`, `tipo` em `imovel|resumo|operador|texto`, `anuncio_ids: list[[fonte,id]]`, `texto`), serialização JSON; `enfileirar(m)` (RPUSH `apebot:envios`), `enfileirar_no_inicio(m)` (LPUSH), `consumir(timeout)` (BLPOP) usando `redis.asyncio`
- [X] T016 Implementar esqueleto de `src/apebot/telegram_bot.py` e `src/apebot/main.py`: `main.py` carrega segredos e filtros, aplica migrações, sincroniza pessoas, cria `Application` do python-telegram-bot com `logging` configurado (formato `chave=valor`), e roda `run_polling()`; se `Configuracao.problemas` não estiver vazio, enfileira mensagem `⚙️ filtros.yaml: ...` ao operador (FR-007)

**Checkpoint**: `docker compose up` sobe, migrações aplicadas, pessoas do YAML gravadas, bot conectado.

---

## Phase 3: User Story 2 - Registrar-se no bot (Priority: P1)

**Goal**: chats autorizados se registram com `/start`; os demais são ignorados

**Independent Test**: `/start` de chat autorizado → confirmação com filtros; de chat não autorizado → silêncio + log `chat_nao_autorizado`; segundo `/start` não duplica

- [X] T017 [P] [US2] Escrever testes em `tests/test_mensagens.py` para `confirmacao_start(pessoa)` e `resposta_padrao()` com os textos exatos de `contracts/telegram.md` (valores `R$ 3.000`, tipos e bairros legíveis)
- [X] T018 [US2] Implementar `confirmacao_start` e `resposta_padrao` em `src/apebot/mensagens.py`, incluindo `formatar_reais(centavos) -> "R$ 2.700"`
- [X] T019 [US2] Em `src/apebot/telegram_bot.py`, implementar filtro de whitelist (chats = `pessoas[].chat_id`; não autorizado → nenhuma resposta e log `chat_nao_autorizado chat_id=...`), handler `/start` (chama `registrar_pessoa`, responde `confirmacao_start`) e handler de qualquer outra mensagem (responde `resposta_padrao`)

**Checkpoint**: US2 validável pelos cenários 1 e 2 do quickstart.

---

## Phase 4: User Story 1 - Receber imóveis novos que batem com meus filtros (Priority: P1) 🎯 MVP

**Goal**: 7 rodadas por dia coletam o QuintoAndar e entregam a cada pessoa os imóveis novos que atendem aos filtros dela, sem repetir

**Independent Test**: com pessoa registrada e já fora do modo resumo, `--rodada-agora` envia só imóveis que passam no filtro, um por mensagem, e repetir o comando não reenvia nada

### Testes (escrever antes; devem falhar)

- [X] T020 [P] [US1] Escrever `tests/test_quintoandar_parse.py` usando `tests/fixtures/quintoandar/listagem-bairro-tipo-buritis-apartamento.html`, `listagem-bairro-funcionarios.html` e `listagem-cidade-bh.html`: parse retorna 24 `Anuncio`s na ordem de `pages["0"]`; primeiro anúncio com campos esperados (conferir valores reais da fixture); preços em centavos (`rentPrice × 100`); `url == f"https://www.quintoandar.com.br/imovel/{id}"`; HTML sem `__NEXT_DATA__` ou com JSON sem `houses` → `FormatoInvalido`; imóvel sem `rentPrice`/`bedrooms`/`type`/`neighbourhood` → descartado e contado; `area`/`totalCost` ausentes → `None`; regra de bairro do research R4 (`bandeirantes-pampulha` aceita `neighbourhood` "Bandeirantes"; bairro diferente → descartado como fora do bairro)
- [X] T021 [P] [US1] Escrever testes de URL em `tests/test_quintoandar_parse.py`: `url_listagem("buritis", Tipo.apartamento) == "https://www.quintoandar.com.br/alugar/imovel/buritis-belo-horizonte-mg-brasil/apartamento"`; `combinacoes(pessoas)` retorna o conjunto distinto (bairro, tipo) da união dos filtros (FR-009)
- [X] T022 [P] [US1] Escrever `tests/test_filtro.py`: os cenários de aceite 1, 3 e 5 de US1 e FR-005/FR-006 — aceita quando bairro ∈ filtro, tipo ∈ filtro, quartos ≥ mínimo, aluguel ≤ máximo; rejeita aluguel R$ 3.100 com máximo R$ 3.000; ignora `total_centavos` na comparação; `novos_para(pessoa, anuncios, ja_enviados)` exclui já enviados; duas pessoas com filtros diferentes recebem conjuntos diferentes
- [X] T023 [P] [US1] Escrever testes de `mensagem_imovel(anuncio)` em `tests/test_mensagens.py` com o formato de `contracts/telegram.md`, incluindo "não informado" para área/total ausentes

### Implementação

- [X] T024 [US1] Implementar parse em `src/apebot/fontes/quintoandar.py`: `url_listagem(bairro_slug, tipo)`, `combinacoes(pessoas)`, `extrair(html, bairro_slug) -> ResultadoParse(anuncios, descartados: dict[str,int])` com BeautifulSoup + `json.loads`, exceção `FormatoInvalido` (research R3/R4)
- [X] T025 [US1] Implementar acesso em `src/apebot/fontes/quintoandar.py`: `async buscar_paginas(combinacoes) -> list[ResultadoPagina]` com um `httpx.AsyncClient` (User-Agent `ape-bot/0.1 (uso pessoal; baixo volume)`, `follow_redirects=False`, timeout 20 s), requisições sequenciais com `asyncio.sleep(random.uniform(2, 5))` entre elas, 3xx e 4xx tratados como erro, 429/5xx com até 3 tentativas e backoff 5/15/45 s respeitando `Retry-After`; cada página retorna anúncios ou erro sem lançar (FR-010, FR-017)
- [X] T026 [US1] Implementar `src/apebot/filtro.py`: `aceita(filtro, anuncio)` e `novos_para(pessoa, anuncios, ja_enviados)` (FR-005, FR-006, FR-012, FR-013)
- [X] T027 [US1] Implementar `mensagem_imovel(anuncio)` em `src/apebot/mensagens.py` (FR-014)
- [X] T028 [US1] Implementar `src/apebot/rodada.py`: `async executar_rodada()` → busca combinações, salva anúncios (`salvar_anuncios`), para cada pessoa registrada seleciona novos, cria envios pendentes (`criar_envios_pendentes`) e enfileira uma `Mensagem` `imovel` por anúncio inserido; registra a linha em `rodada` com contagens (FR-011, FR-012, FR-018)
- [X] T029 [US1] Implementar o worker em `src/apebot/telegram_bot.py` (research R7): tarefa asyncio iniciada no `post_init` que consome a fila, envia com `parse_mode=HTML` e `disable_web_page_preview=True`, espaça ≥ 1,1 s por chat; sucesso → `marcar_envio(..., 'entregue')`; `RetryAfter` → aguarda e `enfileirar_no_inicio`; `Forbidden` → `falhou`; outros erros → até 3 tentativas e depois `falhou`; no início, reenfileira `pendentes_antigos(10)` (FR-016)
- [X] T030 [US1] Em `src/apebot/main.py`, agendar `executar_rodada` com `job_queue.run_daily` para cada hora de `HORARIOS_RODADA` em `FUSO`, com `job_kwargs={"max_instances": 1, "coalesce": True, "misfire_grace_time": 300}`, e adicionar a flag `--rodada-agora` que executa uma rodada, espera a fila esvaziar e encerra (FR-008)

**Checkpoint**: cenários 3 (sem resumo ainda: tratar como mensagens individuais) e 4 do quickstart; MVP entregável.

---

## Phase 5: User Story 3 - Primeira rodada sem inundar o chat (Priority: P2)

**Goal**: primeira rodada (ou após mudança de filtros) gera um resumo de no máximo 5 mensagens

**Independent Test**: pessoa nova com filtros que casam com 40 imóveis da fixture recebe um resumo com total 40 e uma linha por imóvel, não 40 mensagens

- [X] T031 [P] [US3] Escrever testes em `tests/test_mensagens.py` para `mensagens_resumo(anuncios) -> list[str]`: 0 anúncios → texto "Ainda não achei…"; 40 anúncios → primeira linha "Encontrei 40 imóveis…", uma linha por imóvel; 200 anúncios → no máximo 5 partes de ≤ 4.000 caracteres e linha final "(+K imóveis)" quando não couber (SC-007)
- [X] T032 [P] [US3] Escrever teste de `hash_filtros(filtro)` em `tests/test_filtro.py`: estável para o mesmo filtro (independe da ordem dos bairros/tipos) e diferente quando qualquer campo muda
- [X] T033 [US3] Implementar `mensagens_resumo` em `src/apebot/mensagens.py` e `hash_filtros` em `src/apebot/filtro.py` (research R9)
- [X] T034 [US3] Em `src/apebot/rodada.py`, quando `pessoa.filtros_hash` for NULL ou diferente de `hash_filtros(filtro)`, enfileirar mensagens `resumo` (com todos os `anuncio_ids` cobertos) em vez de `imovel`, e então `atualizar_filtros_hash` (FR-015)

**Checkpoint**: cenários 3 e 5 do quickstart.

---

## Phase 6: User Story 4 - Operador sabe quando algo quebra (Priority: P2)

**Goal**: rodadas registradas; 3 falhas seguidas avisam o operador; recuperação e reaviso de 24 h

**Independent Test**: `--rodada-agora --simular-falha` 3× → aviso ⚠️; rodada normal depois → aviso ✅; robô continua no ar

- [X] T035 [P] [US4] Escrever testes em `tests/test_mensagens.py` para `aviso_falha(n, erro)`, `aviso_recuperacao(quando)` e `status_rodada(paginas_ok, paginas_erro, erro_formato)` (falha se erro de formato em qualquer página ou ≥ 50% de páginas com erro — research R10)
- [X] T036 [US4] Implementar `aviso_falha`, `aviso_recuperacao` em `src/apebot/mensagens.py` e `status_rodada` em `src/apebot/rodada.py`
- [X] T037 [US4] Em `src/apebot/banco.py`, adicionar `ultimas_rodadas(n)`, `alerta_aberto()`, `abrir_alerta()`, `registrar_aviso(alerta_id)` e `fechar_alerta(alerta_id)`
- [X] T038 [US4] Em `src/apebot/rodada.py`, ao fim de cada rodada aplicar a regra de alerta (research R10): 3 últimas com falha e nenhum alerta aberto → abrir e avisar; alerta aberto e rodada ok → fechar e avisar recuperação; alerta aberto com `ultimo_aviso_em` > 24 h → avisar de novo; toda exceção inesperada da rodada é capturada, registrada em `rodada.erro_resumo` e não derruba o processo (FR-017, FR-019)
- [X] T039 [US4] Adicionar a flag `--simular-falha` em `src/apebot/main.py` (usada com `--rodada-agora`) que força erro de acesso em todas as páginas, para o cenário 7 do quickstart

**Checkpoint**: cenários 7, 8 e 9 do quickstart.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T040 [P] Criar `README.md` curto: o que é, como configurar (`.env`, `filtros.yaml`), como subir e rodar testes (apontando para `specs/001-mvp-quintoandar-telegram/quickstart.md`)
- [X] T041 [P] Atualizar `docs/arquitetura.md` com o que mudou no plano (URL bairro+tipo, sem página do imóvel, tabelas `rodada` e `alerta`)
- [X] T042 Rodar `ruff check .` e `ruff format --check .` e `pytest` sem rede; corrigir até ficar verde
- [ ] T043 Executar o quickstart completo (cenários 1–9) e registrar o resultado no fim de `specs/001-mvp-quintoandar-telegram/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)** → **Foundational (2)** → **US2 (3)** → **US1 (4)** → **US3 (5)** e **US4 (6)** (independentes entre si) → **Polish (7)**

### User Story Dependencies

- **US2**: só Foundational
- **US1**: Foundational + US2 (precisa de pessoas registradas para entregar)
- **US3**: US1 (substitui o tipo de mensagem na primeira rodada)
- **US4**: US1 (usa a rodada e o registro em `rodada`)

### Within Each User Story

- Testes antes da implementação e falhando primeiro
- `modelos` → `fontes`/`filtro`/`mensagens` → `rodada` → `telegram_bot`/`main`

### Parallel Opportunities

- Setup: T003, T004, T005, T006, T008
- Foundational: T009 e T011 (testes) em paralelo; T013 em paralelo com T010/T012
- US1: T020, T021, T022, T023 em paralelo; depois T024/T026/T027 (arquivos diferentes) em paralelo
- US3 e US4 podem ser feitas em paralelo após US1

## Parallel Example: User Story 1

```text
T020 tests/test_quintoandar_parse.py (parse)   | T022 tests/test_filtro.py
T021 tests/test_quintoandar_parse.py (URLs)    | T023 tests/test_mensagens.py
→ depois: T024 fontes/quintoandar.py | T026 filtro.py | T027 mensagens.py
→ depois: T025 → T028 → T029 → T030
```

## Implementation Strategy

### MVP First

1. Phases 1–2 → base rodando no Docker
2. Phase 3 (US2) → registro funcionando
3. Phase 4 (US1) → **parar e validar**: imóveis chegam no Telegram sem repetir — MVP utilizável
4. US3 e US4 → lapidação (primeira experiência e confiabilidade)
5. Polish → README, docs, quickstart completo

### Incremental Delivery

Cada fase termina num checkpoint validável pelo quickstart; o robô pode ficar no ar a partir do
fim da Phase 4.
