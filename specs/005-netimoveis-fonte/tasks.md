---

description: "Task list for 005 — Netimóveis como fonte de anúncios"
---

# Tasks: Netimóveis como fonte de anúncios

**Input**: Design documents from `specs/005-netimoveis-fonte/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: exigidos pela constituição (princípio II); escritos antes e falhando primeiro; sem rede,
Redis ou MySQL reais. Fixtures reais cortadas (research R9).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Criar `tests/fixtures/netimoveis/` com páginas reais **cortadas** (só `<title>` e os blocos `<script type="application/ld+json">`), baixadas uma única vez com `User-Agent: ape-bot/0.1 (uso pessoal; baixo volume)` e 2–5 s entre requisições: `funcionarios-apartamento-2q.html` (`/locacao/minas-gerais/belo-horizonte/bairros/funcionarios/apartamento?quartos=2`; total 31, 21 lidos, com cobertura e área privativa), `centro-kitchenette.html` (`…/bairros/centro/kitchenette`), `lourdes-casa-em-condominio.html` (`…/bairros/lourdes/casa-em-condominio`, sem `ItemList`) e `sem-jsonld.html` (cópia da de Lourdes sem nenhum bloco JSON-LD); anotar em `tests/fixtures/netimoveis/README.md` as URLs e a data

---

## Phase 2: Foundational (bloqueia as histórias)

- [X] T002 [P] Em `tests/test_modelos.py`: `Tipo.de_netimoveis` mapeia `apartamento`, `cobertura`, `area-privativa`, `andar-pilotis` → APARTAMENTO; `casa`, `casa-geminada`, `sobrado`, `duplex` → CASA; `casa-em-condominio` → CASA_CONDOMINIO; `kitchenette`, `studio`, `flat`, `loft` → KITNET; `loja`/`sala` → None; `Tipo.slug_netimoveis` é `apartamento`, `casa`, `casa-em-condominio`, `kitchenette`; `NOMES_FONTE["netimoveis"] == "Netimóveis"`
- [X] T003 Em `src/apebot/modelos.py`: adicionar `_SLUG_NETIMOVEIS`, `_DO_NETIMOVEIS`, as propriedades/classmethods `slug_netimoveis` e `de_netimoveis` (no padrão de `slug_url`/`de_zap`) e `"netimoveis": "Netimóveis"` em `NOMES_FONTE`

---

## Phase 3: User Story 1 - Receber imóveis do Netimóveis junto com os outros portais (Priority: P1) 🎯 MVP

**Goal**: com a fonte ligada, a rodada busca bairro × tipo no Netimóveis e os imóveis que batem com
os filtros entram na fila de cada pessoa.

**Independent Test**: quickstart 1 e 4 (itens 2, 3 e 5).

### Tests for User Story 1 ⚠️

- [X] T004 [P] [US1] Criar `tests/test_netimoveis.py` — parse: `extrair(html)` da fixture de Funcionários devolve `total=31`, 21 `Anuncio` com `fonte="netimoveis"`, `id_externo` só dígitos (fim da URL), `url` sem query string, `aluguel_centavos = price * 100`, `quartos = numberOfBedrooms`, `area_m2` de `floorSize.value` ("inteiro > 0, senão None"), `total_centavos` = aluguel + condomínio quando há "Condominium Fee" ("sem condomínio → None"), cobertura e área privativa como `Tipo.APARTAMENTO`, `bairro_slug="funcionarios"`; a de Centro/kitchenette devolve `Tipo.KITNET`; a de Lourdes devolve 0 anúncios e `total=0` sem erro; a `sem-jsonld.html` levanta `FormatoInvalido`
- [X] T005 [P] [US1] Em `tests/test_netimoveis.py` — descartes (itens montados em memória a partir de um item real da fixture): URL sem `-minas-gerais-belo-horizonte-` → `fora_da_cidade`; tipo `loja` → `tipo_nao_aceito`; bairro `bandeirantes-(pampulha)` aceito como `bandeirantes`; bairro inexistente no catálogo → `bairro_desconhecido`; sem `price` ou sem `numberOfBedrooms` → `incompleto`
- [X] T006 [P] [US1] Em `tests/test_netimoveis.py` — buscas: `combinacoes(pessoas)` = pares (bairro, tipo) únicos da união dos filtros, ordenados; `quartos_minimo(pessoas)` = menor `quartos_min`; `url_busca("centro", Tipo.APARTAMENTO, 2)` = `https://www.netimoveis.com/locacao/minas-gerais/belo-horizonte/bairros/centro/apartamento?quartos=2` e, com 0 quartos, sem `?quartos=`; nenhuma URL contém `pag=`, `preco`, `ordem=`, `/pesquisa/` ou `/api/`
- [X] T007 [P] [US1] Em `tests/test_netimoveis.py` — `coletar` com `httpx.MockTransport` (sem rede) e `asyncio.sleep` trocado por no-op: duas buscas ok viram `ResultadoFonte(fonte="netimoveis", status="ok", consultas=2)` com anúncios das duas; 404 conta como busca vazia (não é erro); todas 404 → `status="falha"`; `simular_falha=True` não acessa a rede e marca erro de acesso em todas
- [X] T008 [P] [US1] Em `tests/test_mensagens.py`: `texto_ajuda(["quintoandar", "netimoveis"])` lista "QuintoAndar, Netimóveis"; `texto_resumo` traz a linha `Netimóveis: N` depois de OLX; `mensagem_imovel` de um anúncio Netimóveis igual ao formato da 003

### Implementation for User Story 1

- [X] T009 [US1] Criar `src/apebot/fontes/netimoveis.py` no molde de `fontes/quintoandar.py` (mesmas constantes `USER_AGENT`, `TIMEOUT_SEGUNDOS`, `INTERVALO_SEGUNDOS=(2.0, 5.0)`, `BACKOFF_SEGUNDOS=(5, 15, 45)`, `STATUS_REPETIR`): `FONTE="netimoveis"`, `BASE`, `url_busca(bairro_slug, tipo, quartos)`, `combinacoes`, `quartos_minimo`, `extrair(html, catalogo) -> ResultadoBusca(total, lidos, anuncios, descartados)` lendo os blocos JSON-LD com `json.loads` (página sem `ItemList` mas com outro JSON-LD = vazia; sem nenhum JSON-LD ou `ItemList` malformado = `FormatoInvalido`), regex da URL do imóvel `/imovel/locacao-(?P<tipo>.+)-minas-gerais-belo-horizonte-(?P<bairro>.+)/(?P<id>\d+)$`, bairro sem sufixo `-(…)` passado por `bairro_do_catalogo` (de `fontes/resultado.py`); `follow_redirects=False`
- [X] T010 [US1] Em `src/apebot/fontes/netimoveis.py`: `coletar(pessoas, catalogo, simular_falha=False) -> ResultadoFonte` buscando em sequência com intervalo aleatório 2–5 s e backoff em 429/5xx; 404 = busca vazia (log `info`); página de desafio (403 ou HTML com "Just a moment"/"Attention Required") = erro de acesso; `status = status_rodada(...)` e `falha` se todas as buscas forem 404; descartes somados; log `pagina_com_erro` como no QuintoAndar
- [X] T011 [US1] Em `src/apebot/mensagens.py`: `ORDEM_FONTES = ("quintoandar", "zap", "olx", "netimoveis")`
- [X] T012 [US1] Em `src/apebot/main.py` › `Fontes`: quando `segredos.netimoveis`, acrescentar `Coletor("netimoveis", partial(netimoveis.coletar, catalogo=catalogo, simular_falha=simular_falha))` e `"netimoveis"` em `self.ligadas`; senão `Coletor("netimoveis", partial(_desligada, "netimoveis"))` (depende de T014)

**Checkpoint**: com `NETIMOVEIS=ligado`, uma rodada registra `fonte_fim fonte=netimoveis` e põe imóveis na fila.

---

## Phase 4: User Story 2 - Acompanhar a saúde da fonte e desligá-la sem deploy (Priority: P2)

**Goal**: `/status` mostra o Netimóveis; alerta por fonte vale para ele; `NETIMOVEIS` liga e desliga.

**Independent Test**: quickstart 3 e 5; testes de status e alerta abaixo.

### Tests for User Story 2 ⚠️

- [X] T013 [P] [US2] Em `tests/test_config.py`: `NETIMOVEIS` ausente → `segredos.netimoveis is False`; `ligado` (também ` Ligado `) → True; `desligado` → False; `talvez` → False e `problemas_netimoveis(segredos)` devolve `["NETIMOVEIS: valor desconhecido 'talvez'; Netimóveis desligado"]`
- [X] T014 [US2] Em `src/apebot/config.py`: `Segredos.netimoveis: bool = False` e `netimoveis_invalido: str | None = None` lidos de `NETIMOVEIS` em `carregar_segredos` (`ligado` | `desligado`, padrão `desligado`, sem diferenciar maiúsculas e espaços); `problemas_netimoveis(segredos)` com o aviso do contrato; em `src/apebot/main.py` › `main()`, somar `problemas_netimoveis(segredos)` a `config.problemas`
- [X] T015 [P] [US2] Em `tests/test_mensagens.py`: `texto_status` mostra `Netimóveis: ⏹️ desligado` quando fora de `fontes_ligadas`, `Netimóveis: ✅ ok` com estado ok e `Netimóveis: ⚠️ falha (acesso: …)` com falha
- [X] T016 [P] [US2] Em `tests/test_rodada.py`: rodada com coletores falsos em que o Netimóveis devolve `status="falha"` e o QuintoAndar `ok` termina com status `ok`, entrega os anúncios das outras fontes e registra `rodada_fonte` do Netimóveis como `falha`
- [X] T017 [US2] Em `.env.example`: `NETIMOVEIS=desligado` com comentário curto (ligar só depois de ler os termos de uso e da sonda no Railway); em `README.md`, a variável na seção de configuração/Railway

**Checkpoint**: alerta, status e liga/desliga cobertos.

---

## Phase 5: User Story 3 - Saber quando a 1ª página cortou resultados (Priority: P3)

**Goal**: log `netimoveis_corte` quando `total > lidos`.

**Independent Test**: quickstart 4 item 3; teste abaixo.

- [X] T018 [P] [US3] Em `tests/test_netimoveis.py`: com `caplog`, `coletar` sobre a fixture de Funcionários registra `netimoveis_corte bairro=funcionarios tipo=apartamento total=31 lidos=21`; sobre a de Centro/kitchenette não registra corte
- [X] T019 [US3] Em `src/apebot/fontes/netimoveis.py`: após cada busca com `total > lidos`, `log.info("netimoveis_corte bairro=%s tipo=%s total=%d lidos=%d", ...)`

---

## Phase 6: Polish & Cross-Cutting

- [X] T020 [P] Em `src/apebot/fontes/netimoveis.py`: sonda `if __name__ == "__main__"` — `python -m apebot.fontes.netimoveis [bairro] [tipo]` (padrão `centro apartamento`) faz **uma** busca e imprime `status=<HTTP> total=<n> lidos=<n> anuncios=<n> descartados={...}` ou o erro; sai 0 se a busca respondeu e 1 em erro de acesso ou formato; não toca banco, Redis nem Telegram
- [X] T021 [P] Atualizar `docs/arquitetura.md`: Netimóveis na tabela de fontes, no diagrama e na lista de módulos; variável `NETIMOVEIS`; remover a "candidata a avaliar" do spike 001 se citada
- [X] T022 Rodar `.venv/bin/pytest -q` e `.venv/bin/ruff check src tests` e `.venv/bin/ruff format --check src tests`; tudo verde
- [X] T023 Executar quickstart 2 (sonda local) e registrar o resultado numa seção "Resultado da validação" no fim de `specs/005-netimoveis-fonte/quickstart.md`; quickstart 3 (Railway) fica para o dono, junto com a leitura dos termos de uso

---

## Dependencies & Execution Order

- **Setup (T001)** → base das fixtures de US1/US3.
- **Foundational (T002–T003)** bloqueia US1 (parse usa `Tipo.de_netimoveis`).
- **US1 (T004–T012)**: T009 → T010; T012 depende de T014 (US2) para ler `segredos.netimoveis` — fazer T014 antes de T012.
- **US2 (T013–T017)**: independente do parse; T014 é pré-requisito de T012.
- **US3 (T018–T019)**: depende de T010.
- **Polish (T020–T023)**: depois das histórias.

## Parallel Opportunities

- T002 junto com T001.
- Testes T004–T008 em paralelo (arquivos/blocos diferentes), antes de T009.
- T013, T015, T016 em paralelo.
- T020 e T021 em paralelo.

## Implementation Strategy

1. MVP = Setup + Foundational + US1 + T014 (variável) → já dá para ligar e ver imóveis do Netimóveis.
2. US2 completa a operação (status, aviso de configuração, docs de deploy).
3. US3 mede o corte da 1ª página.
4. Sonda e validação; ligar em produção só depois dos termos de uso e da sonda no Railway.
