---

description: "Task list for 003 — Entrega espaçada, favoritos, resumo diário e filtros pelo Telegram"
---

# Tasks: Entrega espaçada, favoritos, resumo diário e filtros pelo Telegram

**Input**: Design documents from `specs/003-entrega-espacada-cadastro-telegram/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: exigidos pela constituição (princípio II) nos pontos que quebram: leitura de valor
(dinheiro em centavos, `int`) e nome, transições da conversa, despacho e reconciliação, catálogo
gerado do PDF e textos do contrato. Os testes são escritos antes da implementação correspondente e
precisam falhar primeiro. Nenhum teste acessa rede, Redis ou MySQL reais (fakes como em
`tests/test_rodada.py`).

**Organization**: por user story (spec.md). A Phase 2 muda a origem das pessoas (MySQL em vez de
`filtros.yaml`) e o catálogo de bairros, sem mudar o comportamento visível. US1 (entrega espaçada)
é o MVP desta feature.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: US1–US5 conforme spec.md

## Path Conventions

Projeto único: `src/apebot/`, `tests/`, `migrations/`, `scripts/` na raiz do repositório.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: schema, configuração e tabela de regionais

- [X] T001 Criar `migrations/004_cadastro_entrega.sql` (data-model.md): `ALTER TABLE pessoa ADD COLUMN filtros JSON NULL, ADD COLUMN cadastro_completo_em DATETIME NULL, ADD COLUMN filtros_atualizados_em DATETIME NULL`; `CREATE TABLE conversa (chat_id BIGINT PRIMARY KEY, modo ENUM('cadastro','edicao') NOT NULL, etapa VARCHAR(20) NOT NULL, rascunho JSON NOT NULL, atualizada_em DATETIME NOT NULL, CONSTRAINT fk_conversa_pessoa FOREIGN KEY (chat_id) REFERENCES pessoa (chat_id)) DEFAULT CHARSET = utf8mb4`; `CREATE TABLE favorito (chat_id BIGINT NOT NULL, fonte VARCHAR(20) NOT NULL, id_externo VARCHAR(40) NOT NULL, salvo_em DATETIME NOT NULL, PRIMARY KEY (chat_id, fonte, id_externo), CONSTRAINT fk_favorito_pessoa FOREIGN KEY (chat_id) REFERENCES pessoa (chat_id), CONSTRAINT fk_favorito_anuncio FOREIGN KEY (fonte, id_externo) REFERENCES anuncio (fonte, id_externo)) DEFAULT CHARSET = utf8mb4`; `CREATE TABLE resumo_diario (chat_id BIGINT NOT NULL, dia DATE NOT NULL, enviado_em DATETIME NOT NULL, PRIMARY KEY (chat_id, dia), CONSTRAINT fk_resumo_pessoa FOREIGN KEY (chat_id) REFERENCES pessoa (chat_id)) DEFAULT CHARSET = utf8mb4`. Não remover `pessoa.filtros_hash` (fica sem uso)
- [X] T002 [P] Acrescentar `ENTREGA_INTERVALO=120-300` ao `.env.example` (contracts/configuracao.md)
- [X] T003 [P] Criar `scripts/regionais_pbh.py` (fora do pacote, research R9): recebe o caminho do PDF, roda `pdftotext -layout` via `subprocess`, lê as linhas com a regex `^\s*(.+?)\s{2,}(BARREIRO|CENTRO-SUL|LESTE|NORDESTE|NOROESTE|NORTE|OESTE|PAMPULHA|VENDA NOVA)\s+([A-Z]{1,2}\d+)\s*$` (487 bairros), casa cada slug de `src/apebot/dados/bairros_bh.txt` pelo `apebot.modelos.slug` do nome oficial, depois pela tabela de apelidos do R9 (`aparecida-7a-secao`→"APARECIDA SÉTIMA SEÇÃO", `nova-suica`→"NOVA SUISSA", `incofindencia`→"INCONFIDÊNCIA", `bandeirantes-pampulha`→"BANDEIRANTES", `cabana`→"CABANA DO PAI TOMÁS", `maria-tereza`→"MARIA TERESA", `sao-jorge`→"SÃO JORGE I", `tupi`→"TUPI A", `novo-das-industrias`→"BAIRRO NOVO DAS INDÚSTRIAS", `parque-sao-joao-batista`→"SÃO JOÃO BATISTA", `miramar-barreiro`→"MIRAMAR", e os prefixos `conjunto-`, `chacara-`, `jardim-`, `vila-` removidos quando o resto bate), depois pelo sufixo (`santa-cruz-barreiro`→Barreiro, `sao-pedro-venda-nova`→Venda Nova); exclui `chacara-belo-horizonte-taubate-sp-brasil`, `jardim-belo-horizonte-campinas-sp-brasil`, `jardim-belo-horizonte-indaiatuba-sp-brasil`, `vila-belo-horizonte-sao-paulo-sp-brasil`, `hawai-justinopolis`, `katia-justinopolis`; o restante vai para `Outros` com nome = slug em título. Escreve em stdout o CSV `slug,nome,regional` (nome oficial em título, com acento: "Alto Caiçaras"; regional em título: "Centro-Sul", "Venda Nova"), ordenado por slug, e em stderr as contagens (direto, apelido, sufixo, excluídos, Outros)
- [X] T004 Gerar `src/apebot/dados/bairros_bh.csv` com `python scripts/regionais_pbh.py docs/referencias/pbh-bairros-regionais.pdf > src/apebot/dados/bairros_bh.csv` (283 linhas de dados), conferir à mão as linhas de apelido e sufixo, apagar `src/apebot/dados/bairros_bh.txt` e trocar `package-data` em `pyproject.toml` para `apebot = ["dados/*.csv"]`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: catálogo com regionais, pessoas e filtros no MySQL, `filtros.yaml` como lista de
autorizados, valor com centavos, fila com botões em linhas

**⚠️ CRITICAL**: nenhuma story começa antes desta fase

- [X] T005 [P] Escrever `tests/test_catalogo.py`: `catalogo_bairros()` tem 283 itens `Bairro(slug, nome, regional)`; toda `regional` está em `REGIONAIS` (9 regionais na ordem `Barreiro, Centro-Sul, Leste, Nordeste, Noroeste, Norte, Oeste, Pampulha, Venda Nova`, mais `Outros` no fim); nenhum slug contém `-sp-brasil` ou `justinopolis`; os 21 slugs do `filtros.yaml` atual (`barro-preto, alto-barroca, alto-caicaras, barroca, caicaras, carlos-prates, castelo, centro, cidade-nova, cidade-jardim, colegio-batista, fernao-dias, funcionarios, grajau, gutierrez, lagoinha, prado, santa-tereza, santa-efigenia, santa-ines, uniao`) existem e nenhum está em `Outros`; `nome_bairro("alto-caicaras") == "Alto Caiçaras"`; `bairros_validos()` é o `frozenset` dos slugs; slug repetido no CSV levanta erro
- [X] T006 Em `src/apebot/modelos.py`: dataclass frozen `Bairro(slug: str, nome: str, regional: str)` e `REGIONAIS: tuple[str, ...]` conforme T005. Em `src/apebot/config.py`: `catalogo_bairros() -> tuple[Bairro, ...]` lendo `dados/bairros_bh.csv` com `csv.DictReader` (cache com `functools.cache`), `bairros_validos()` derivado dele e `nome_bairro(slug) -> str` (slug desconhecido → slug em título)
- [X] T007 [P] Escrever em `tests/test_filtro.py`: `filtro_para_json(f)` e `filtro_de_json(d)` fazem ida e volta (bairros e tipos ordenados no JSON: `{"bairros": [...], "aluguel_max_centavos": n, "quartos_min": n, "tipos": [...]}`); `filtro_de_json` devolve `None` com 0 bairros, 0 tipos, bairro fora do catálogo, `quartos_min` fora de {0,1,2,3,4} ou `aluguel_max_centavos` fora de [30000, 5000000]; remover `test_hash_filtros_estavel_e_sensivel_a_mudancas`
- [X] T008 Em `src/apebot/filtro.py`: implementar `filtro_para_json` e `filtro_de_json(dados, catalogo: frozenset[str]) -> Filtro | None` (T007) e as constantes `VALOR_MIN_CENTAVOS = 30_000`, `VALOR_MAX_CENTAVOS = 5_000_000`, `QUARTOS_OPCOES = (0, 1, 2, 3, 4)`; `hash_filtros` só sai na US1 (T024), junto com o modo resumo que o usa
- [X] T009 [P] Escrever em `tests/test_config.py` (contracts/configuracao.md): pessoa só com `chat_id` é autorizada e não vira semente; pessoa com filtros inválidos continua em `config.autorizados` e gera problema; pessoa com filtros válidos vira `config.sementes` (Pessoa); `nome` ausente → `None` em `autorizados`; `ENTREGA_INTERVALO` `"5-10"` → `(5, 10)`, ausente → `(120, 300)`, `"300-120"`, `"0-10"`, `"abc"`, `"10-4000"` → `(120, 300)` e problema `ENTREGA_INTERVALO inválido '{x}'; usando 120-300`. Ajustar os testes que usam `config.pessoas`
- [X] T010 Em `src/apebot/config.py`: `Configuracao` passa a ter `operador_chat_id`, `autorizados: dict[int, str | None]` (chat_id → nome do arquivo), `sementes: list[Pessoa]` e `problemas`; `carregar_filtros` aceita pessoa sem `filtros` e não descarta a pessoa quando o filtro é inválido (só não vira semente); `Segredos.entrega_intervalo: tuple[int, int]` lido de `ENTREGA_INTERVALO` com a validação de T009 (problema entra pelo mesmo caminho de `problemas_gecko`)
- [X] T011 Em `src/apebot/banco.py` (research R5): `semear_pessoas(autorizados, sementes) -> list[str]` (insere chat_id novo com nome do arquivo ou `str(chat_id)`; para `filtros IS NULL` com semente, grava `nome`, `filtros`, `cadastro_completo_em` e `filtros_atualizados_em`; para quem já tem filtros diferentes da semente, devolve o aviso `{nome}: filtros do arquivo ignorados; vale o que a pessoa salvou no Telegram`), substituindo `sincronizar_pessoas` (sem mais `ON DUPLICATE KEY UPDATE nome`); `pessoas_ativas(autorizados) -> list[Pessoa]` (registrada, `cadastro_completo_em` preenchido, `pausada_em IS NULL`, chat_id em `autorizados`; filtro via `filtro_de_json`, inválido → fora e log `filtro_invalido chat_id=`); `pessoa(chat_id) -> tuple[Pessoa | None, datetime | None, bool]` (pessoa com filtro, `pausada_em`, cadastro completo); `salvar_filtros(chat_id, nome, filtro)` (grava filtros JSON, nome, `filtros_atualizados_em` e, se nulo, `cadastro_completo_em`); remover `atualizar_filtros_hash` e o `filtros_hash` de `pessoas_registradas` (se sem uso, remover a função)
- [X] T012 [P] Atualizar `tests/test_mensagens.py`: `formatar_reais(300000) == "R$ 3.000,00"`, `formatar_reais(245050) == "R$ 2.450,50"`, `formatar_reais(99) == "R$ 0,99"`; os textos existentes de status e filtros com centavos; o bairro exibido vem de `nome_bairro` ("Alto Caiçaras", não "Alto Caicaras")
- [X] T013 Em `src/apebot/mensagens.py`: `formatar_reais` sempre com centavos (FR-029); trocar `_bairro_legivel` por `config.nome_bairro`
- [X] T014 [P] Atualizar `tests/test_fila.py`: `Mensagem.botoes` é `list[list[dict]]`, com botão de URL `{"t": rótulo, "u": url}` e de callback `{"t": rótulo, "c": dados}`; ida e volta em JSON preserva as linhas; JSON antigo sem `botoes` → `[]`
- [X] T015 Em `src/apebot/fila.py`: `botoes: list[list[dict[str, str]]]`; em `src/apebot/telegram_bot.py`, `_teclado` monta uma linha de `InlineKeyboardButton` por lista (URL com `"u"`, `callback_data` com `"c"`); `mensagem_imovel`/`botoes_imovel` atuais adaptados ao formato novo (o formato do texto muda só na US1)
- [X] T016 Trocar a origem das pessoas: `src/apebot/rodada.py` (`_coletar_e_enfileirar` usa `banco.pessoas_ativas(config.autorizados)`), `src/apebot/telegram_bot.py` (`autorizados = set(config.autorizados) | {operador}`; `/filtros`, `/pausar`, `/retomar`, `/start` usam `banco.pessoa(chat_id)`; nome do operador sai de `config.autorizados`) e `src/apebot/main.py` (`_preparar_banco` chama `semear_pessoas` e manda os avisos para `config.problemas`; `--rodada-agora` checa `pessoas_ativas`). Ajustar `BancoFalso` em `tests/test_rodada.py` (`pessoas_ativas` devolve `[PESSOA]`)

**Checkpoint**: `pytest` e `ruff` verdes; a migração 004 sobe; o seu cadastro é semeado do arquivo;
uma rodada manual se comporta como na 002 (inclusive o resumo da primeira rodada, que só sai na
US1).

---

## Phase 3: User Story 1 - Receber os imóveis um a um, espaçados, durante o dia (Priority: P1) 🎯 MVP

**Goal**: cada imóvel numa mensagem, de 2 a 5 min entre mensagens da mesma pessoa, só das 8h às
22h, do mais barato para o mais caro, sem lista em bloco, sem perder nem repetir em reinício.

**Independent Test**: com `ENTREGA_INTERVALO=5-10` e 10 imóveis novos para uma pessoa, rodar e ver
10 mensagens no formato do contrato, em ordem crescente de valor, espaçadas; reiniciar no meio e não
repetir nem perder nenhuma (quickstart 7–9).

### Tests for User Story 1 ⚠️

- [X] T017 [P] [US1] Escrever `tests/test_despacho.py` com as regras puras de `src/apebot/telegram_bot.py` (ou de onde ficarem, research R2/R3): `dentro_da_janela(datetime 07:59 SP) is False`, `08:00 → True`, `21:59 → True`, `22:00 → False`, com horário UTC convertido para America/Sao_Paulo; `sortear_intervalo((120, 300), random.Random(1))` sempre em [120, 300] e com mais de um valor distinto em 50 sorteios; `faltando_na_fila(pendentes={a,b,c,d}, na_fila={a}, em_entrega={b}) == {c, d}`
- [X] T018 [P] [US1] Em `tests/test_despacho.py`, testar `Despachante.uma_volta(agora)` com `FilaPessoaFalsa` (dict em memória com a semântica de ZSET/HASH), `FilaFalsa` e `BancoFalso`: fora da janela não despacha nada; pessoa com 3 imóveis (R$ 2.500, R$ 1.800, R$ 2.000) despacha o de R$ 1.800 e grava `proximo = agora + intervalo`; segunda volta antes do `proximo` não despacha; imóvel que não atende mais ao filtro (aluguel acima do novo máximo) é descartado (`banco.apagar_pendente` chamado) e o próximo da fila sai na mesma volta; duas pessoas despacham de forma independente; pessoa que não está em `pessoas_ativas` não despacha
- [X] T019 [P] [US1] Atualizar `tests/test_mensagens.py` (contracts/telegram.md): `mensagem_imovel` de 2 quartos no Prado, R$ 2.450 → `"Veja o imóvel que encontrei:\n2 quartos no bairro Prado\nValor: R$ 2.450,00\nLink: {url}"`; 1 quarto → "1 quarto"; 0 quartos kitnet → "Kitnet/Studio no bairro …"; com contato → linhas 👤/📞 depois do link; `botoes_imovel` → `[[Abrir anúncio(u), WhatsApp(u)?], [⭐ Salvar como favorito(c="f:{fonte}:{id}")]]`; `len("f:quintoandar:" + "x" * 40) <= 64`; remover os testes de `mensagens_resumo`
- [X] T020 [P] [US1] Atualizar `tests/test_rodada.py`: a rodada não enfileira mais em `apebot:envios` mensagens de imóvel nem de resumo; para cada imóvel novo que atende ao filtro chama `FilaPessoa.adicionar(chat_id, anuncio, contato)` uma vez; imóvel já em `ja_enviados` não entra; a regra "não manda resumo com coleta em falha" sai

### Implementation for User Story 1

- [X] T021 [US1] Em `src/apebot/fila.py` (data-model.md, Redis): classe `FilaPessoa` sobre o mesmo cliente Redis, com chaves `apebot:pessoa:{chat_id}:fila` (ZSET, `member = "{fonte}|{id_externo}"`, `score = aluguel_centavos`), `apebot:pessoa:{chat_id}:imoveis` (HASH com `ImovelNaFila` JSON: `anuncio` + `contato` ou `null`) e `apebot:pessoa:{chat_id}:proximo` (epoch em segundos); métodos `adicionar(chat_id, anuncio, contato) -> bool` (`ZADD NX` + `HSETNX`), `retirar_mais_barato(chat_id) -> tuple[Anuncio, Contato | None] | None` (`ZPOPMIN` + `HGET` + `HDEL`), `membros(chat_id) -> set[tuple[str, str]]`, `tamanho(chat_id) -> int`, `limpar(chat_id)`, `proximo(chat_id) -> float | None`, `marcar_proximo(chat_id, epoch)`; e `Fila.chaves_em_entrega() -> set[tuple[int, str, str]]` (`LRANGE` de `apebot:envios`, só mensagens `tipo == "imovel"`)
- [X] T022 [US1] Em `src/apebot/banco.py`: `pendentes_de(chat_id) -> list[Anuncio]` (`envio` `pendente` JOIN `anuncio`), `apagar_pendente(chat_id, chave)` e `apagar_pendentes(chat_id)` (só `status = 'pendente'`); remover `pendentes_antigos`
- [X] T023 [US1] Em `src/apebot/mensagens.py`: `mensagem_imovel(anuncio, contato=None)` e `botoes_imovel(anuncio, contato=None)` conforme T019 (nome do bairro via `nome_bairro(anuncio.bairro_slug)`; prévia de link continua desligada); remover `mensagens_resumo`, `_linha_resumo` e as constantes do resumo
- [X] T024 [US1] Em `src/apebot/rodada.py` (research R4): `Rodada` recebe `FilaPessoa`; `_enfileirar_para(pessoa, anuncios)` = `novos_para` → `criar_envios_pendentes` → `FilaPessoa.adicionar` com o contato em memória, log `imovel_enfileirado chat_id= quantidade=`; remover o modo resumo, `hash_filtros` e o parâmetro `status`; `contagens["enfileirados"]` = imóveis colocados nas filas
- [X] T025 [US1] Em `src/apebot/telegram_bot.py` (research R2/R3): funções `dentro_da_janela`, `sortear_intervalo`, `faltando_na_fila` e a classe `Despachante(app, fila, fila_pessoa, banco, autorizados, intervalo)` com `uma_volta(agora)` (T018: monta `Mensagem(tipo="imovel", texto=mensagem_imovel, botoes=botoes_imovel, anuncio_ids=[chave])`, enfileira em `apebot:envios`, log `imovel_despachado` / `imovel_descartado_filtro` sem texto nem contato), `reconciliar()` (para cada pessoa ativa: `pendentes_de` − `membros` − `chaves_em_entrega` → `adicionar` sem contato; log `reconciliacao chat_id= recolocados=`) e `executar()` (reconcilia uma vez e repete `uma_volta` a cada 20 s; erro numa pessoa vira `log.exception` e segue para as outras; erro de Redis espera 5 s, como o `Entregador`). Remover `Entregador.reenfileirar_pendentes`
- [X] T026 [US1] Em `src/apebot/telegram_bot.py`: `/pausar` também chama `FilaPessoa.limpar(chat_id)` e `banco.apagar_pendentes(chat_id)` (research R4); `/retomar` deixa de limpar `filtros_hash` em `src/apebot/banco.py` e responde `▶️ Avisos retomados. Na próxima rodada eu volto a te mandar o que encontrar.` (`TEXTO_RETOMADO` em `src/apebot/mensagens.py`)
- [X] T027 [US1] Em `src/apebot/main.py`: criar `FilaPessoa` e passá-la à `Rodada` (agendada e `--rodada-agora`); subir o `Despachante` no `ao_iniciar`, depois do `Entregador`, com `segredos.entrega_intervalo`; `--rodada-agora` termina depois de esvaziar `apebot:envios` e imprime `Imóveis na fila das pessoas: {n}. O bot entrega um por vez, das 8h às 22h.`

**Checkpoint**: quickstart 7, 8, 9, 11 e 13 passam; nenhuma lista em bloco.

---

## Phase 4: User Story 2 - Ver e editar os próprios filtros pelo /filtros (Priority: P1)

**Goal**: `/filtros` legível com "Editar filtros", que refaz tipos → quartos → bairros por
regional → valor com as respostas atuais, Salvar/Cancelar, valendo na próxima rodada.

**Independent Test**: `/filtros` → Editar → mudar valor e um bairro → Salvar → `/filtros` mostra os
novos, e a rodada seguinte usa os novos; Cancelar no meio não muda nada (quickstart 3–6).

### Tests for User Story 2 ⚠️

- [ ] T028 [P] [US2] Escrever `tests/test_cadastro.py` com a tabela de `ler_valor` do research R7: aceita `3000`, `3.000`, `3.000,00`, `R$ 3.000`, `r$3000` → 300000; `3000,50` e `3000,5` → 300050; `12.500` → 1250000; recusa (`None`) `3k`, `três mil`, `-3000`, `0`, `3000.50`, `3 000`, `3.00`, `30.00,0`, `100`, `999999`, `""`
- [ ] T029 [P] [US2] Em `tests/test_cadastro.py`, transições da edição (research R6, data-model.md `conversa`): `iniciar_edicao(filtro)` começa em `tipos` com o rascunho igual ao filtro; tocar tipo alterna; `Continuar` sem tipo → mesma etapa e aviso "Marque pelo menos um tipo."; quartos avança para `regionais`; regional abre `bairros` página 1; `▶`/`◀` mudam de página (24 por página); "Marcar todos" marca só os da regional; `Continuar` sem bairro → aviso; valor inválido → mesma etapa e texto de erro do contrato; `Manter` usa o valor atual; valor válido → `revisao`; `Salvar` → resultado "gravar" com o `Filtro`; `Cancelar` em qualquer etapa → resultado "cancelar"; texto numa etapa de botões → "Use os botões da mensagem acima. 👆"; callback de etapa diferente da atual → "Essa pergunta já passou." sem mudança; todo `callback_data` gerado tem ≤ 64 bytes
- [ ] T030 [P] [US2] Em `tests/test_mensagens.py`: `texto_filtros` no formato de contracts/telegram.md ("Seus filtros -", "Bairros:" com nomes do catálogo em ordem alfabética, "Valores até R$ 3.000,00", "Apartamento, Casa com 2+ quartos" / "com qualquer número de quartos", "Avisos:") e sem "fale com"

### Implementation for User Story 2

- [ ] T031 [US2] Criar `src/apebot/cadastro.py` (research R6/R7): `ler_valor(texto) -> int | None`; dataclasses `Estado(modo, etapa, rascunho: dict)`, `Botao(texto, dados)`, `Resposta(texto, teclado: list[list[Botao]], editar: bool, aviso: str | None)` e `Resultado(estado | None, resposta, acao: "seguir" | "gravar" | "cancelar")`; `iniciar_edicao(pessoa) -> Resultado`; `processar(estado, entrada) -> Resultado`, com `entrada` texto ou `callback_data` `c:{etapa}:{ação}[:{arg}]`; teclados de tipos, quartos, regionais (9 + Outros, com contagem de marcados), bairros (24 por página, 2 por linha, `✅`, `◀`/`▶`, Marcar/Desmarcar todos, `↩ Regionais`), valor (`Manter` na edição) e revisão (`💾 Salvar`/`✖ Cancelar`); `✖ Cancelar` em todas as etapas da edição; textos exatamente como em contracts/telegram.md
- [ ] T032 [US2] Em `src/apebot/banco.py`: `conversa(chat_id) -> Estado | None`, `salvar_conversa(chat_id, estado)` (UPSERT com `atualizada_em`), `apagar_conversa(chat_id)`
- [ ] T033 [US2] Em `src/apebot/mensagens.py`: `texto_filtros(pessoa, pausada_em)` no formato do contrato (T030), usado no `/filtros`, no `/start` de quem já tem cadastro e na `revisao` (com "Confere?" no topo); textos `Filtros salvos! Eles valem a partir da próxima rodada ({HH:MM}).` e `Edição cancelada. Seus filtros continuam os mesmos.`
- [ ] T034 [US2] Em `src/apebot/telegram_bot.py`: `/filtros` responde `texto_filtros` com o botão `✏️ Editar filtros` (`e:inicio`); `CallbackQueryHandler` para `e:inicio` (apaga a conversa aberta, cria a de edição e envia a etapa) e para `c:*` (carrega a conversa, chama `cadastro.processar`, salva ou apaga, responde com `edit_message_text`/`edit_message_reply_markup` quando `editar` e `query.answer(aviso)`); texto livre com conversa aberta vai para `processar` antes da resposta padrão; ação "gravar" → `banco.salvar_filtros` e mensagem de salvo com `proxima_rodada`; log `filtros_salvos chat_id=` (sem valores)

**Checkpoint**: quickstart 3–6 passam; a rodada seguinte à edição usa os filtros novos.

---

## Phase 5: User Story 3 - Cadastro guiado pelo /start (Priority: P2)

**Goal**: chat autorizado sem cadastro faz nome → tipos → quartos → bairros → valor pelo
`/start`, retomável depois de reinício, e entra na rodada seguinte.

**Independent Test**: autorizar um chat só com `chat_id`, `/start`, responder tudo, ver a
mensagem "Perfeito, {nome}!…" e a pessoa na rodada seguinte; reiniciar no meio e retomar
(quickstart 1–2).

### Tests for User Story 3 ⚠️

- [ ] T035 [P] [US3] Em `tests/test_cadastro.py`, `limpar_nome` (research R8): `"  maria   clara "` → `"Maria Clara"`; `"joão da silva"` → `"João da Silva"`; `"Ana & <Bia>"` → `"Ana Bia"` (sem `<`, `>`, `&`); `"🙂🙂"`, `""`, `"   "`, `"123"` → `None`; 60 letras → corta em 40; caracteres de controle removidos
- [ ] T036 [P] [US3] Em `tests/test_cadastro.py`, transições do cadastro: `iniciar_cadastro()` começa em `nome` com o texto "Oi! … Como devo te chamar?"; nome inválido repete com o erro do contrato; nome válido vai para `tipos` (sem `✖ Cancelar` no modo cadastro); valor válido no fim → ação "gravar" com nome + `Filtro` e texto "Perfeito, {nome}! Vou te ajudar a encontrar um imóvel com sua cara para alugar! Durante o dia vou te enviar o que achar por aqui, fique atento(a)."; `reapresentar(estado)` devolve a etapa atual a partir do rascunho (retomada)

### Implementation for User Story 3

- [ ] T037 [US3] Em `src/apebot/cadastro.py`: `limpar_nome(texto) -> str | None` (T035), `iniciar_cadastro()`, etapa `nome`, modo `cadastro` (grava ao receber valor válido, sem `revisao`) e `reapresentar(estado) -> Resposta`
- [ ] T038 [US3] Em `src/apebot/telegram_bot.py`: `/start` → registra a pessoa; com conversa aberta, `reapresentar`; sem cadastro, `iniciar_cadastro` e salva a conversa; com cadastro, `texto_filtros` + `Editar filtros` (e o aviso de pausa, como na 002); "gravar" no modo cadastro → `banco.salvar_filtros(chat_id, nome, filtro)` e log `cadastro_concluido chat_id=`; com o cadastro aberto, `/filtros`, `/favoritos`, `/status`, `/pausar` e `/retomar` respondem `Termine o cadastro primeiro: /start` (`/ajuda` responde normalmente)

**Checkpoint**: quickstart 1–2 passam; o segundo chat recebe imóveis a partir da rodada seguinte.

---

## Phase 6: User Story 4 - Resumo do dia às 23h (Priority: P2)

**Goal**: depois da rodada das 23h, um resumo por pessoa ativa por dia, com recebidos em 24 h por
portal e créditos para todos.

**Independent Test**: pessoa com 5 entregues do QuintoAndar e 2 do Zap; chamar `enviar_resumos`
duas vezes no mesmo dia → um resumo no formato do contrato (quickstart 12).

### Tests for User Story 4 ⚠️

- [ ] T039 [P] [US4] Em `tests/test_mensagens.py`: `texto_resumo(ultima_rodada, proxima, por_fonte={"quintoandar": 5, "zap": 2}, creditos)` → as 6 linhas do contrato, com `OLX: 0`, "Você recebeu 7 imóveis", "1 imóvel" no singular; `creditos` texto de erro → `💳 Créditos: saldo indisponível`; `creditos=None` → sem a linha 💳; `texto_status` mostra a linha 💳 para qualquer pessoa e `Na sua fila: {n} imóveis (envio das 8h às 22h).`
- [ ] T040 [P] [US4] Em `tests/test_rodada.py`: `enviar_resumos(banco, fila, gecko, autorizados, agora)` com fakes: uma chamada a `gecko.creditos()` para todas as pessoas; só pessoas de `pessoas_ativas` recebem; `banco.registrar_resumo` devolvendo `False` (já enviado hoje) → nada enviado; `gecko=None` → resumo sem linha 💳; o dia usado é o de America/Sao_Paulo (23:30 SP de 28/10 = 02:30 UTC de 29/10 → dia 28/10)

### Implementation for User Story 4

- [ ] T041 [US4] Em `src/apebot/banco.py`: `recebidos_por_fonte_24h(chat_id) -> dict[str, int]` (`envio` `entregue` com `entregue_em >= agora - 24 h`, `GROUP BY fonte`) e `registrar_resumo(chat_id, dia) -> bool` (`INSERT IGNORE INTO resumo_diario`; True se inseriu); `recebidos_24h` passa a somar `recebidos_por_fonte_24h`
- [ ] T042 [US4] Em `src/apebot/mensagens.py`: `texto_resumo` (T039); `texto_status` com a linha 💳 para todos e a linha "Na sua fila"
- [ ] T043 [US4] Em `src/apebot/rodada.py`: `async def enviar_resumos(...)` (T040), mensagem `tipo="resumo"` direto em `apebot:envios` (fora da janela, FR-010), log `resumo_enviado chat_id=`; em `src/apebot/main.py`, o job da rodada das 23h chama `enviar_resumos` depois de `Rodada.executar()`, com status ok ou falha; em `src/apebot/telegram_bot.py`, `/status` consulta créditos para qualquer pessoa autorizada e passa `FilaPessoa.tamanho(chat_id)`

**Checkpoint**: quickstart 12 passa; `/status` mostra créditos e tamanho da fila.

---

## Phase 7: User Story 5 - Salvar imóveis como favoritos (Priority: P3)

**Goal**: o botão "⭐ Salvar como favorito" alterna o favorito, e `/favoritos` lista com link.

**Independent Test**: salvar 2, remover 1, `/favoritos` lista só o outro (quickstart 10).

### Tests for User Story 5 ⚠️

- [ ] T044 [P] [US5] Em `tests/test_mensagens.py`: `texto_favoritos([])` → texto de "ainda não tem favoritos"; com itens, cabeçalho `⭐ Seus favoritos ({n}):` e uma entrada `⭐ {q} quartos · {Bairro} · R$ {valor} · {Portal}\n{url}` por item, em blocos ≤ 4.000 caracteres sem cortar item; `trocar_botao_favorito(linhas, salvo=True)` troca só o botão `f:` por `✅ Favorito · toque para remover` e mantém `Abrir anúncio`/`WhatsApp`; `salvo=False` volta a `⭐ Salvar como favorito`

### Implementation for User Story 5

- [ ] T045 [US5] Em `src/apebot/banco.py`: `alternar_favorito(chat_id, chave) -> bool` (`INSERT IGNORE` com `salvo_em`; 0 linhas → `DELETE`; devolve se ficou salvo) e `favoritos(chat_id) -> list[Anuncio]` (`JOIN anuncio`, `ORDER BY salvo_em DESC`)
- [ ] T046 [US5] Em `src/apebot/mensagens.py`: `texto_favoritos` e `trocar_botao_favorito` (T044); acrescentar `("favoritos", "Imóveis que salvei")` a `COMANDOS` e mudar a descrição de `filtros` para `Ver e editar meus filtros`
- [ ] T047 [US5] Em `src/apebot/telegram_bot.py`: `CallbackQueryHandler` para `f:{fonte}:{id_externo}` → `alternar_favorito`, `query.answer("⭐ Salvo nos favoritos" | "Removido dos favoritos")` e `edit_message_reply_markup` com `trocar_botao_favorito` sobre `query.message.reply_markup`; `/favoritos` envia os blocos de `texto_favoritos`; log `favorito chat_id= salvo=`

**Checkpoint**: quickstart 10 passa.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T048 [P] Em `src/apebot/mensagens.py` e `tests/test_mensagens.py`: `texto_ajuda` e `resposta_padrao` exatamente como em contracts/telegram.md (entrega das 8h às 22h, resumo às 23h, `/favoritos`, "ver e editar")
- [ ] T049 [P] Atualizar `docs/arquitetura.md` seções 3 a 6 (fluxo com fila por pessoa, despachante e resumo; Telegram com cadastro, edição e favoritos; dados com `conversa`, `favorito`, `resumo_diario` e `pessoa.filtros`; estrutura com `cadastro.py`, `scripts/` e `bairros_bh.csv`) e tirar o "(em especificação)" do cabeçalho
- [ ] T050 [P] Atualizar `README.md`: `filtros.yaml` como lista de autorizados, cadastro pelo `/start`, `ENTREGA_INTERVALO` e como gerar de novo a tabela de regionais
- [ ] T051 Rodar `.venv/bin/pytest -q && .venv/bin/ruff check src tests scripts && .venv/bin/ruff format --check src tests scripts` e corrigir o que falhar
- [ ] T052 Executar os cenários do `quickstart.md` com `ENTREGA_INTERVALO=5-10` e registrar o resultado numa seção "Resultado da validação" no fim de `specs/003-entrega-espacada-cadastro-telegram/quickstart.md`; voltar `ENTREGA_INTERVALO` ao padrão

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências; T004 depende de T003
- **Foundational (Phase 2)**: depende do Setup; bloqueia todas as stories
- **US1 (Phase 3)**: depende da Phase 2
- **US2 (Phase 4)**: depende da Phase 2; independe da US1 (as duas editam `telegram_bot.py` e
  `mensagens.py`, então não rodam ao mesmo tempo nesses arquivos)
- **US3 (Phase 5)**: depende da US2 (`cadastro.py`, conversa no banco e o roteamento de callbacks)
- **US4 (Phase 6)**: depende da Phase 2; a linha "Na sua fila" usa `FilaPessoa` (T021)
- **US5 (Phase 7)**: depende da US1 (o botão de favorito está na mensagem de imóvel da US1)
- **Polish (Phase 8)**: depois das stories desejadas

### Within Each User Story

- Testes antes da implementação, falhando primeiro
- Regra pura (`cadastro.py`, funções do despachante, textos) → banco → fila → Telegram → main

### Parallel Opportunities

- T002 e T003 juntos
- T005, T007, T009, T012 e T014 juntos (arquivos de teste diferentes)
- Na US1: T017/T018 (mesmo arquivo, em sequência), T019 e T020 juntos
- Na US2: T028/T029 (mesmo arquivo) e T030 juntos
- US2 e US4 em paralelo depois da Phase 2, fora de `telegram_bot.py`/`mensagens.py`
- T048, T049 e T050 juntos

---

## Parallel Example: User Story 1

```bash
# Testes da US1 juntos:
Task: "tests/test_despacho.py — janela, intervalo e reconciliação (T017) e uma_volta (T018)"
Task: "tests/test_mensagens.py — mensagem e botões no formato novo (T019)"
Task: "tests/test_rodada.py — rodada enfileira por pessoa, sem resumo (T020)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2 (pessoas no MySQL e catálogo com regionais, sem mudar o que a pessoa vê)
2. Phase 3 (entrega espaçada)
3. **PARAR E VALIDAR**: testes verdes; quickstart 7, 8, 9, 11 e 13 com `ENTREGA_INTERVALO=5-10`

### Incremental Delivery

1. Setup + Foundational → semente do arquivo, catálogo com regionais
2. US1 → um imóvel por vez (MVP; resolve a lista de 64)
3. US2 → edição de filtros sem o operador
4. US3 → cadastro de gente nova
5. US4 → resumo das 23h
6. US5 → favoritos

---

## Notes

- Nenhum teste acessa a rede, o Redis ou o MySQL: fakes em memória, como em `tests/test_rodada.py`
- Nunca registrar em log o texto de mensagem, o nome digitado, o valor digitado nem o contato
- Até a US5, tocar no botão de favorito não faz nada (o Telegram mostra o carregando e some)
- Commit ao fim de cada fase
