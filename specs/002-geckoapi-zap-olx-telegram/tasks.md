---

description: "Task list for 002 — Zap e OLX via GeckoAPI e interação no Telegram"
---

# Tasks: Zap e OLX via serviço pago e interação melhor no Telegram

**Input**: Design documents from `specs/002-geckoapi-zap-olx-telegram/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: exigidos pela constituição (princípio II) para parse de fonte, filtro e formatação de
mensagens. São escritos antes da implementação correspondente e devem falhar primeiro. Nenhum
teste acessa a internet. Fixtures reais já versionadas em `tests/fixtures/geckoapi/`.

**Organization**: por user story (spec.md). A Phase 2 refatora a rodada para várias fontes sem
mudar o comportamento do QuintoAndar. US1 (Zap) é o MVP desta feature.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1–US4 conforme spec.md

## Path Conventions

Projeto único: `src/apebot/`, `tests/`, `migrations/` na raiz do repositório.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: schema e configuração novos

- [X] T001 Criar `migrations/003_fontes_e_pausa.sql` (data-model.md): `ALTER TABLE pessoa ADD COLUMN pausada_em DATETIME NULL`; `ALTER TABLE anuncio MODIFY url VARCHAR(500) NOT NULL`; `ALTER TABLE alerta ADD COLUMN fonte VARCHAR(20) NOT NULL DEFAULT 'quintoandar'`; `CREATE TABLE rodada_fonte (rodada_id BIGINT NOT NULL, fonte VARCHAR(20) NOT NULL, status ENUM('ok','falha','desligada','sem_credito') NOT NULL, consultas SMALLINT UNSIGNED NOT NULL DEFAULT 0, anuncios_vistos INT UNSIGNED NOT NULL DEFAULT 0, descartados INT UNSIGNED NOT NULL DEFAULT 0, fora_da_cidade INT UNSIGNED NOT NULL DEFAULT 0, erro_resumo VARCHAR(500) NULL, PRIMARY KEY (rodada_id, fonte), CONSTRAINT fk_rodada_fonte_rodada FOREIGN KEY (rodada_id) REFERENCES rodada (id)) DEFAULT CHARSET = utf8mb4`
- [X] T002 [P] Acrescentar `GECKO_API_KEY=` e `GECKO_FONTES=zap` ao `.env.example` (contracts/configuracao.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: modelos, travas comuns, fila com botões, rodada com várias fontes e estado por fonte

**⚠️ CRITICAL**: nenhuma story começa antes desta fase

- [X] T003 [P] Escrever testes em `tests/test_modelos.py`: `Tipo.de_zap("APARTMENT") is Tipo.APARTAMENTO`, `PENTHOUSE`→apartamento, `HOME`/`TWO_STORY_HOUSE`→casa, `CONDOMINIUM`→casa_condominio, `KITNET`/`FLAT`→kitnet, `"ALLOTMENT_LAND"`→`None`; `Tipo.APARTAMENTO.zap_property_types == ("apartment", "penthouse")` e equivalentes da tabela do research R2; `NOMES_FONTE["zap"] == "Zap"`
- [X] T004 Implementar em `src/apebot/modelos.py`: `Tipo.de_zap(unit_type) -> Tipo | None`, propriedade `Tipo.zap_property_types` (tabela R2), `NOMES_FONTE = {"quintoandar": "QuintoAndar", "zap": "Zap", "olx": "OLX"}` e dataclass frozen `Contato(nome: str | None, telefone: str | None, whatsapp_url: str | None)`
- [X] T005 [P] Escrever testes em `tests/test_fontes_resultado.py`: `na_cidade("Belo Horizonte","MG")`, `("belo horizonte","Minas Gerais")`, `("BH","mg")` → True; `("Contagem","MG")`, `("Belo Horizonte","SP")`, `(None,"MG")`, `("Belo Horizonte", None)` → False (R5); `bairro_do_catalogo("Gutierrez", catalogo)` → `"gutierrez"`, `("Bandeirantes", …)` → `"bandeirantes-pampulha"` quando é o único com esse prefixo, ambíguo ou ausente → `None` (R6); `whatsapp_url("31982984510")`, `("5531982984510")` e `("(31) 98298-4510")` → `"https://wa.me/5531982984510"`, `("982984510")`, `("0031…")` e `""` → `None`; `telefone_legivel("31982984510") == "(31) 98298-4510"`, `("3130454545") == "(31) 3045-4545"`, valor inválido volta como veio (R7)
- [X] T006 Criar `src/apebot/fontes/resultado.py`: dataclass `ResultadoFonte(fonte: str, status: str = "ok", anuncios: list[Anuncio], contatos: dict[tuple[str, str], Contato], descartados: Counter[str], consultas: int = 0, erro: str | None = None, erro_de_formato: bool = False)` com `status` em `ok|falha|desligada|sem_credito`; funções `na_cidade(cidade, uf)`, `bairro_do_catalogo(nome, catalogo: frozenset[str]) -> str | None`, `whatsapp_url(numero)`, `telefone_legivel(numero)` conforme T005
- [X] T007 [P] Escrever teste em `tests/test_fila.py`: `Mensagem(..., botoes=[["Abrir anúncio","https://x"]])` sobrevive a `para_json`/`de_json`; JSON antigo sem `botoes` vira `botoes == []`
- [X] T008 Acrescentar `botoes: list[list[str]] = field(default_factory=list)` à `Mensagem` em `src/apebot/fila.py` (compatível com mensagens antigas na fila)
- [X] T009 Adaptar `src/apebot/fontes/quintoandar.py`: nova `async def coletar(pessoas, simular_falha=False) -> ResultadoFonte` que chama `buscar_paginas(combinacoes(pessoas), simular_falha)` e consolida anúncios, descartados, `consultas` = páginas, `status` = `status_rodada(ok, erro, formato)` (mover `status_rodada` de `rodada.py` para `fontes/resultado.py`, mantendo o import em `rodada.py` para `tests/test_rodada.py`) e `erro` = último erro
- [X] T010 Acrescentar em `src/apebot/banco.py`: `registrar_fonte(rodada_id, resultado: ResultadoFonte)` (INSERT em `rodada_fonte` com `fora_da_cidade = descartados["fora_da_cidade"]`; `erro_resumo` truncado em 500); `seguidas_com_falha(fonte, n=50) -> int` (linhas de `rodada_fonte` da fonte, mais recente primeiro, ignorando `desligada`, contando `falha` até a primeira diferente); `alerta_aberto(fonte)`, `abrir_alerta(fonte)` com `fonte`; remover `ultimas_rodadas` se ficar sem uso
- [X] T011 [P] Escrever testes em `tests/test_rodada.py` para a regra pura de alerta por fonte: `deve_alertar(seguidas=3, aberto=None)` → abrir; `seguidas=2` → nada; aberto há 25 h → reavisar; aberto e status ok → recuperar (extrair a decisão de `_avaliar_alerta` para uma função pura `decidir_alerta(status, seguidas, aberto_em, agora)` que devolve `abrir|reavisar|recuperar|nada`)
- [X] T012 Refatorar `src/apebot/rodada.py`: a rodada recebe uma lista de coletores (`Callable[[list[Pessoa]], Awaitable[ResultadoFonte]]`); coleta cada um isoladamente (exceção → `ResultadoFonte(status="falha", erro=...)`, FR-010); grava `registrar_fonte` para cada resultado; `rodada.status` e o modo resumo continuam vindo do QuintoAndar; junta anúncios e `contatos` de todas as fontes; `contagens["descartados"]` soma todas; `_avaliar_alerta` passa a rodar por fonte com `decidir_alerta` e as mensagens por fonte de contracts/telegram.md (`aviso_falha(portal, n, erro)`, `aviso_recuperacao(portal, quando)`)
- [X] T013 Atualizar `src/apebot/mensagens.py` e `tests/test_mensagens.py`: `aviso_falha(portal, rodadas, erro)` → `⚠️ ape-bot: {Portal} com falha em {N} rodadas seguidas. Último erro: {erro}`; `aviso_recuperacao(portal, quando)` → `✅ ape-bot: {Portal} voltou a funcionar (DD/MM/AAAA HH:MM).`
- [X] T014 Em `src/apebot/config.py` e `tests/test_config.py`: `Segredos` ganha `gecko_api_key: str` (vazio permitido) e `gecko_fontes: tuple[str, ...]` lidos de `GECKO_API_KEY`/`GECKO_FONTES` (padrão `zap`; aceitos `zap`, `olx`; desconhecido, inclusive `vivareal`, é ignorado e vira problema `GECKO_FONTES: valor desconhecido '{x}' ignorado`); chave vazia com fontes pedidas vira problema `GECKO_API_KEY ausente: Zap/OLX desligados`; os problemas entram em `Configuracao.problemas` (aviso ⚙️ já existente)
- [X] T015 Atualizar `src/apebot/main.py`: montar a lista de coletores (QuintoAndar sempre; Zap/OLX conforme T014, ou um coletor que devolve `status="desligada"` quando a fonte está fora de `GECKO_FONTES` ou sem chave) e passá-la à `Rodada` nos dois modos (agendado e `--rodada-agora`)

**Checkpoint**: `pytest` verde; rodada manual só com QuintoAndar se comporta como antes e grava
`rodada_fonte` com `quintoandar ok`, `zap desligada` e `olx desligada`.

---

## Phase 3: User Story 1 - Zap com acesso direto ao anúncio e ao anunciante (Priority: P1) 🎯 MVP

**Goal**: imóveis novos do Zap chegam com portal, botão "Abrir anúncio" e, quando houver, nome,
telefone e botão "WhatsApp"; contato nunca vai para o MySQL

**Independent Test**: rodada com o coletor do Zap alimentado pela fixture → mensagens com portal,
botões e contato; `anuncio` e `resposta_fonte` sem nome nem telefone

### Tests for User Story 1 ⚠️

- [X] T016 [P] [US1] Escrever `tests/test_zap.py` com `tests/fixtures/geckoapi/zap-plp-aluguel-bh.json`: `extrair_zap(corpo, catalogo)` devolve 3 `Anuncio` com `fonte="zap"`, `id_externo="2919519749"` no primeiro, tipo apartamento, `bairro_slug="gutierrez"`, quartos 2, área 80, `aluguel_centavos=489000`, `total_centavos=(4890+564)*100`, `url` do item; contato do primeiro com `nome="Imobiliária Fictícia"`, telefone `(31) 0000-0000` como veio (inválido) e `whatsapp_url=None` (número fictício sem DDD válido); item com `business != "RENTAL"`, `unitTypes` comercial, cidade fora de BH, bairro fora do catálogo ou sem `prices.rent`/`bedrooms` → descartado em `venda`, `tipo`, `fora_da_cidade`, `bairro_desconhecido` e `incompleto` (montar esses casos copiando um item da fixture e alterando o campo)
- [X] T017 [P] [US1] Escrever em `tests/test_zap.py` os testes do payload: `payload_zap(pessoas)` com duas pessoas (aluguel até 3.000 e 2.500; quartos mínimos 2 e 1; tipos apartamento e casa) → `priceMax=3000`, `bedrooms=[1,2,3,4]`, `propertyTypes` = união da tabela R2 em ordem estável, `businessType="rent"`, `state="MG"`, `city="Belo Horizonte"`, `page=1`, sem `neighborhood` nem `sort`; `quartos_min=0` → sem `bedrooms`
- [X] T018 [P] [US1] Escrever em `tests/test_mensagens.py`: `mensagem_imovel(anuncio, contato)` segue contracts/telegram.md (linha `🏠 Apartamento · Gutierrez · Zap`, `👤`/`📞` só com contato, nome escapado em HTML, sem URL no texto); `botoes_imovel(anuncio, contato)` → `[["Abrir anúncio", url]]` mais `["WhatsApp", wa]` quando `contato.whatsapp_url`; resumo com `· {Portal} ·` em cada linha
- [X] T019 [P] [US1] Escrever em `tests/test_geckoapi.py` os testes do cliente com `httpx.MockTransport` (sem rede): 200 → resposta lida e `ler_resposta` aplicada; `notFound` → `ErroGecko("sem resultados")`; 402 → `SemCredito` e chamadas seguintes nem saem (`sem_credito` em memória); 500 seguido de 200 → sucesso com 2 requisições; 500 duas vezes → erro; tempo esgotado → erro sem nova tentativa; header `Authorization: Bearer {chave}`

### Implementation for User Story 1

- [X] T020 [US1] Implementar em `src/apebot/fontes/geckoapi.py` o `ClienteGecko(chave, transport=None)`: `async extrair(payload) -> tuple[RespostaGecko, dict]` (POST `/v1/extract`, tempo limite 90 s, uma nova tentativa só em 5xx; 402 → `SemCredito` e flag `sem_credito` que bloqueia chamadas seguintes; `notFound`/4xx/timeout → `ErroGecko`); devolve a `RespostaGecko` sem anunciante **e** o corpo bruto só para o parse, que não é guardado; `async creditos() -> dict` (GET `/v1/me/credits`, tempo limite 10 s); nunca registra corpo nem contato em log
- [X] T021 [US1] Criar `src/apebot/fontes/zap.py`: `payload_zap(pessoas)` (T017, usando `filtro.filtros_somados`) e `extrair_zap(corpo_bruto, catalogo) -> ResultadoFonte` (T016, contrato contracts/geckoapi.md, total por R12, contato por `advertiser.name`, `phoneNumbers[0]`, `whatsAppNumber` → `Contato` com `telefone_legivel` e `whatsapp_url`); `async coletar(cliente, pessoas, banco, catalogo) -> ResultadoFonte` (sem pessoas → `ResultadoFonte(status="ok", consultas=0)`; `SemCredito` → `status="sem_credito"`; `ErroGecko` → `falha`; sucesso → grava `banco.salvar_resposta` via `asyncio.to_thread` e devolve `consultas=1`)
- [X] T022 [US1] Implementar `filtros_somados(pessoas) -> Filtro | None` em `src/apebot/filtro.py` (maior aluguel máximo, menor quartos mínimos, união dos tipos e dos bairros; `None` sem pessoas) com testes em `tests/test_filtro.py`
- [X] T023 [US1] Atualizar `src/apebot/mensagens.py`: `mensagem_imovel(anuncio, contato=None)`, `botoes_imovel(anuncio, contato=None)` e linha do resumo com o portal (T018)
- [X] T024 [US1] Em `src/apebot/rodada.py`, `_enfileirar_para` passa `contatos.get(anuncio.chave)` para `mensagem_imovel`/`botoes_imovel` e preenche `Mensagem.botoes`; contatos ficam só no `dict` em memória da rodada
- [X] T025 [US1] Em `src/apebot/telegram_bot.py`: `_entregar` envia `reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(r, url=u) for r, u in m.botoes]])` quando houver botões; `reenfileirar_pendentes` monta `mensagem_imovel(anuncio)` e `botoes_imovel(anuncio)` sem contato
- [X] T026 [US1] Em `src/apebot/main.py`, ligar o coletor do Zap com `ClienteGecko(segredos.gecko_api_key)` e o catálogo de `config.bairros_validos()`; aviso imediato ao operador na primeira rodada com `sem_credito` (mensagem 💳 de contracts/telegram.md, uma vez por processo)

**Checkpoint**: US1 testável sozinha; rodada manual com chave real gasta 1 crédito e entrega
mensagens com botões.

---

## Phase 4: User Story 2 - Descobrir o que o robô faz e ver os próprios filtros (Priority: P1)

**Goal**: menu de comandos, `/ajuda`, `/filtros`, `/status` e resposta padrão orientando

**Independent Test**: de um chat autorizado, cada comando responde conforme contracts/telegram.md;
de um não autorizado, silêncio

### Tests for User Story 2 ⚠️

- [X] T027 [P] [US2] Escrever em `tests/test_mensagens.py`: `texto_ajuda(fontes_ligadas)` lista só os portais ligados e os 5 comandos; `texto_filtros(pessoa, pausada_em, nome_operador)` com "ativos" e com "pausados desde DD/MM HH:MM"; `texto_status(ultima_rodada, proxima, recebidos_24h, estados_fonte, creditos=None)` com cada estado (`ok`, `falha` com erro, `desligada`, `sem_credito`), "Ainda não houve rodada.", linha 💳 só quando `creditos` é dado e "saldo indisponível" quando é erro; `resposta_padrao()` termina sugerindo `/ajuda`; `proxima_rodada(agora)` às 23h30 → 06:00 do dia seguinte e às 10h → 12:00 (fuso de São Paulo)

### Implementation for User Story 2

- [X] T028 [US2] Implementar em `src/apebot/mensagens.py`: `COMANDOS` (pares comando/descrição do menu), `texto_ajuda`, `texto_filtros`, `texto_status`, `proxima_rodada` e a nova `resposta_padrao` (T027)
- [X] T029 [US2] Acrescentar em `src/apebot/banco.py`: `ultima_rodada() -> datetime | None` (terminada mais recente), `estados_fonte() -> dict[str, tuple[str, str | None]]` (última linha de `rodada_fonte` por fonte), `recebidos_24h(chat_id) -> int` (`envio` entregue com `entregue_em` nas últimas 24 h) e `pausada_em(chat_id) -> datetime | None`
- [X] T030 [US2] Em `src/apebot/telegram_bot.py`: handlers `/ajuda`, `/filtros`, `/status` (o operador também recebe `ClienteGecko.creditos()`, com erro tratado como "saldo indisponível"); `registrar_handlers` recebe as fontes ligadas e o cliente Gecko opcional
- [X] T031 [US2] Em `src/apebot/main.py`, no `ao_iniciar`: `await app.bot.set_my_commands(COMANDOS)`

**Checkpoint**: US2 testável sozinha (não depende de crédito)

---

## Phase 5: User Story 3 - Pausar e retomar os avisos (Priority: P2)

**Goal**: `/pausar` e `/retomar` persistentes; nada é enviado durante a pausa; ao retomar, resumo

**Independent Test**: pausar, rodar, conferir zero mensagens; retomar, rodar, conferir o resumo

- [X] T032 [US3] Acrescentar em `src/apebot/banco.py`: `pausar(chat_id)` (preenche `pausada_em` só se NULL), `retomar(chat_id)` (`pausada_em = NULL, filtros_hash = NULL`, R9) e fazer `pessoas_registradas()` devolver só as não pausadas (a rodada e os filtros somados passam a ignorar as pausadas)
- [X] T033 [US3] Em `src/apebot/telegram_bot.py`: handlers `/pausar` e `/retomar` com os textos de contracts/telegram.md (idempotentes); `/start` de pessoa pausada acrescenta a linha de pausa
- [X] T034 [P] [US3] Em `tests/test_mensagens.py`: textos de pausa/retomada e da confirmação do `/start` pausado

**Checkpoint**: US3 testável sozinha

---

## Phase 6: User Story 4 - Operador controla as fontes pagas e o gasto (Priority: P2)

**Goal**: OLX pronta e desligada, trava de localização comprovada, alerta por fonte e crédito

**Independent Test**: `extrair_olx` na fixture com localização ignorada descarta tudo em
`fora_da_cidade`; com `GECKO_FONTES=zap`, a OLX não é chamada

- [X] T035 [P] [US4] Escrever `tests/test_olx.py` com `tests/fixtures/geckoapi/olx-plp-aluguel-bh-localizacao-ignorada.json`: os 3 itens (SP e outros estados) são descartados como `fora_da_cidade` e nenhum vira `Anuncio`; um item da fixture com `location` trocada para Belo Horizonte/MG e bairro "Buritis" vira `Anuncio(fonte="olx")` com tipo por R4 (casa de condomínio → `casa_condominio`), aluguel `price*100`, total com `condominio` + `iptu` dos `properties`, área de `size`, quartos de `rooms` ("5 ou mais" → 5); `real_estate_type` com "temporada" → descartado em `tipo`; `payload_olx(pessoas)` igual ao de contracts/geckoapi.md
- [X] T036 [US4] Criar `src/apebot/fontes/olx.py`: `payload_olx`, `extrair_olx(corpo_bruto, catalogo) -> ResultadoFonte` (sem contato) e `coletar(...)` com as mesmas regras de erro do Zap (T021)
- [X] T037 [US4] Em `src/apebot/main.py`, ligar o coletor da OLX somente quando `olx` está em `GECKO_FONTES` e há chave; caso contrário, coletor `desligada`

**Checkpoint**: todas as stories funcionais

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T038 [P] Teste de privacidade em `tests/test_zap.py`: depois de `extrair_zap` + `ler_resposta`, nem os `Anuncio` (via `dataclasses.asdict`) nem a `RespostaGecko.corpo` contêm o nome ou os telefones do anunciante da fixture (SC-004)
- [X] T039 [P] Atualizar `docs/arquitetura.md`: MVP passa a incluir Zap (GeckoAPI) e OLX desligada; fluxo com os coletores; tabelas `rodada_fonte` e `pessoa.pausada_em`; comandos do Telegram; estrutura com `fontes/zap.py`, `fontes/olx.py`, `fontes/resultado.py`
- [X] T040 Rodar `.venv/bin/ruff check src tests`, `.venv/bin/ruff format --check src tests` e `.venv/bin/pytest -q`; depois `docker compose up -d --build` e os cenários 1, 2, 5, 9 e 10 de quickstart.md que não gastam crédito; registrar o resultado no fim de quickstart.md
- [ ] T041 Com autorização do operador (gasta 1 crédito): cenários 3, 4, 6 e 7 de quickstart.md com o Zap ligado; registrar o resultado

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup; bloqueia todas as stories
- **US1 (Phase 3)**: depende da Phase 2
- **US2 (Phase 4)**: depende da Phase 2 (`rodada_fonte` para o `/status`); independe da US1, exceto `ClienteGecko.creditos()` (T020) para a linha 💳 do operador
- **US3 (Phase 5)**: depende da Phase 2; independe de US1/US2 (T033 edita `telegram_bot.py`, então não roda junto de T030)
- **US4 (Phase 6)**: depende de T020 (cliente) e T006 (travas)
- **Polish (Phase 7)**: depois das stories desejadas

### Within Each User Story

- Testes antes da implementação, falhando primeiro
- Parse e payload → cliente → rodada → Telegram → main

### Parallel Opportunities

- T002 junto de T001
- T003, T005, T007 e T011 juntos (arquivos de teste diferentes)
- Na US1: T016, T017, T018 e T019 juntos; depois T020, T022 e T023 (arquivos diferentes)
- US2 e US3 em paralelo após a Phase 2, exceto as edições em `telegram_bot.py`
- T038 e T039 juntos

---

## Parallel Example: User Story 1

```bash
# Testes da US1 juntos:
Task: "tests/test_zap.py — extrair_zap com a fixture (T016)"
Task: "tests/test_zap.py — payload_zap com filtros somados (T017)"
Task: "tests/test_mensagens.py — mensagem e botões com contato (T018)"
Task: "tests/test_geckoapi.py — ClienteGecko com MockTransport (T019)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2 (rodada com várias fontes, sem mudar o QuintoAndar)
2. Phase 3 (Zap com botões e contato)
3. **PARAR E VALIDAR**: testes verdes, cenários sem crédito, depois 1 rodada com crédito (T041)

### Incremental Delivery

1. Setup + Foundational → QuintoAndar igual, com `rodada_fonte`
2. US1 → Zap no ar (MVP)
3. US2 → comandos e menu
4. US3 → pausa
5. US4 → OLX pronta e desligada, pronta para ligar quando a GeckoAPI corrigir

---

## Notes

- Nenhum teste acessa a rede: `ClienteGecko` aceita `transport` (`httpx.MockTransport`)
- Nunca registrar em log o corpo da resposta, o texto da mensagem nem o contato
- Commit ao fim de cada fase
