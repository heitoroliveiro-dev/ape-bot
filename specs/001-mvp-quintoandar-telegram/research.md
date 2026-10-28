# Research: 001 — MVP QuintoAndar → Telegram

Base: `docs/spikes/001-fontes-de-dados.md` e fixtures em `tests/fixtures/quintoandar/`.

## R1. Como consultar o QuintoAndar por filtro
- **Decision**: uma requisição por combinação distinta (bairro, tipo) da união dos filtros, na URL
  pública `https://www.quintoandar.com.br/alugar/imovel/{bairro-slug}-belo-horizonte-mg-brasil/{tipo-slug}`.
  Quartos e preço são filtrados localmente.
- **Rationale**: URL permitida pelo `robots.txt` e publicada no sitemap (partição
  `neighborhood-housetype`). Verificado em 27/10/2026: `buritis.../apartamento` → 200, sem
  redirect, 24 imóveis na página, todos do tipo e bairro pedidos. Equivale a "preencher a busca",
  sem formulário e sem XPath.
- **Alternatives**: `/busca` com formulário (bloqueado no robots); segmento `/{n}-quartos` no
  caminho (semântica "exatamente N" incerta e multiplica requisições); API interna (proibida pela
  constituição, princípio III).

## R2. Slugs de tipo e bairro
- **Decision**: tipos do domínio → slug da URL → valor `type` no JSON:
  `apartamento` → `apartamento` → `Apartamento`; `casa` → `casa` → `Casa`;
  `casa_condominio` → `casacondominio` → `CasaCondominio`; `kitnet` → `kitnet` → `StudioOuKitchenette`.
  Bairros: lista fechada dos 289 slugs de BH extraída do sitemap
  (`src/apebot/dados/bairros_bh.txt`, cópia de `tests/fixtures/quintoandar/bairros-bh-sitemap.txt`
  reduzida ao slug). No `filtros.yaml` o operador escreve o nome ("Santa Mônica") ou o slug; ambos
  são normalizados (minúsculas, sem acento, espaços → hífen) e validados contra a lista.
- **Rationale**: o portal é a fonte da verdade para os nomes que ele aceita; evita o problema de
  grafia PBH × portal no MVP.
- **Alternatives**: catálogo oficial PBH + apelidos (adiado; regionais fora do escopo).

## R3. Extração dos dados
- **Decision**: BeautifulSoup localiza `<script id="__NEXT_DATA__">`; `json.loads`; ler
  `props.pageProps.initialState.search.visibleHouses.pages["0"]` (ids na ordem) e
  `props.pageProps.initialState.houses[id]`. Campos: `id`, `type`, `neighbourhood`, `bedrooms`,
  `area`, `rentPrice`, `totalCost`. Link = `https://www.quintoandar.com.br/imovel/{id}`.
  Valores vêm em reais inteiros → converter para centavos (`× 100`).
- **Rationale**: dados estruturados, sem depender de layout/XPath. A página do imóvel
  (`/imovel/{id}`) não é necessária no MVP, porque a listagem já traz todos os campos da mensagem.
- **Formato quebrado**: ausência do script, JSON inválido ou caminho ausente → `FormatoInvalido`
  (conta como falha de formato na rodada). Imóvel sem `rentPrice`, `bedrooms`, `type` ou
  `neighbourhood` → descartado e contado; `area`/`totalCost` ausentes → "não informado".

## R4. Bairro do anúncio × bairro consultado
- **Decision**: o anúncio só entra para o bairro consultado se `slug(neighbourhood)` for igual ao
  slug do bairro, ou se o slug do bairro começar com `slug(neighbourhood) + "-"` (slugs
  desambiguados como `bandeirantes-pampulha`). Caso contrário, é descartado e contado como
  "fora do bairro".
- **Rationale**: protege contra o portal misturar bairros vizinhos na página.

## R5. Política de acesso
- **Decision**: cliente `httpx.AsyncClient` único, `follow_redirects=False` (3xx = falha; nunca
  segue para URL possivelmente bloqueada), timeout 20 s, User-Agent
  `ape-bot/0.1 (uso pessoal; baixo volume)`. Requisições sequenciais com `sleep` aleatório de
  2–5 s. Em 429/5xx: até 3 tentativas com backoff exponencial (5, 15, 45 s) respeitando
  `Retry-After` quando presente.
- **Rationale**: princípio III da constituição. Volume estimado: ≤ 30 requisições por rodada.

## R6. Agendamento e fuso
- **Decision**: `JobQueue.run_daily` para cada hora de `HORARIOS_RODADA = (6, 9, 12, 15, 18, 21, 23)`
  com `tzinfo=ZoneInfo("America/Sao_Paulo")`; pacote `tzdata` incluído para não depender do SO
  do container. Rodadas não sobrepõem (`job_kwargs={"max_instances": 1, "coalesce": True}`);
  rodada perdida com o processo parado não é recuperada (`misfire_grace_time` curto).
- **Alternatives**: cron + script (descartado pelo operador: bot sempre ligado).

## R7. Fila Redis e entrega
- **Decision**: lista Redis `apebot:envios` (RPUSH / BLPOP) com mensagens JSON
  `{chat_id, tipo: "imovel"|"resumo"|"operador", anuncio_ids, texto}`. Um worker (tarefa asyncio
  no mesmo processo do bot) consome, envia e:
  - sucesso → marca `envio.status = 'entregue'` para os anúncios da mensagem;
  - `RetryAfter` → espera o tempo pedido e reenfileira no início;
  - `Forbidden` (bot bloqueado) → `status = 'falhou'`, registra e segue;
  - outro erro → até 3 tentativas, depois `falhou`.
  Ritmo: ≥ 1,1 s entre mensagens para o mesmo chat e ≥ 0,05 s global.
- **Idempotência**: ao enfileirar, insere `envio(status='pendente')`; a chave única
  (chat_id, fonte, id_externo) impede duplicar. No início do processo, envios `pendente` com mais
  de 10 min são reenfileirados (recupera a fila após queda).
- **Rationale**: FR-013, FR-016; princípio V da constituição.

## R8. Banco
- **Decision**: MySQL 8.4 (container), PyMySQL, SQL puro em `src/apebot/banco.py`; chamadas
  síncronas executadas via `asyncio.to_thread`. Migrações: arquivos `migrations/NNN_*.sql`
  aplicados em ordem na inicialização, com controle na tabela `schema_migracao`.
- **Rationale**: simples; volume minúsculo dispensa driver assíncrono ou ORM.

## R9. Primeira rodada / resumo
- **Decision**: `pessoa.filtros_hash` guarda o hash (SHA-256 do YAML normalizado dos filtros da
  pessoa) usado no último envio. Se o hash atual difere (ou é nulo) → modo resumo. Resumo: linha
  1 com o total; depois uma linha por imóvel (`Bairro · Nq · R$ X · link`), quebrado em mensagens
  de até 4.000 caracteres, no máximo 5 mensagens; se não couber, as últimas linhas viram
  "+N imóveis" e todos contam como enviados (SC-007).
- **Rationale**: FR-015 sem estado extra.

## R10. Falhas e avisos ao operador
- **Decision**: rodada com falha = erro de formato em qualquer página **ou** ≥ 50% das páginas
  com erro de acesso. Tabela `rodada` guarda status. Após a rodada: se as 3 últimas falharam e não
  há alerta aberto → abre alerta e avisa o operador; se há alerta aberto e a rodada teve sucesso →
  fecha e avisa recuperação; se alerta aberto há > 24 h desde o último aviso → avisa de novo
  (tabela `alerta`).
- **Rationale**: FR-019, User Story 4.

## R11. Configuração e segredos
- **Decision**: `filtros.yaml` (montado no container, somente leitura) com operador, pessoas e
  filtros; validado na inicialização (PyYAML + validação manual); erros de bairro/valor geram aviso
  ao operador e a entrada inválida é ignorada (FR-007). Segredos em `.env`: `TELEGRAM_TOKEN`,
  `MYSQL_*`, `REDIS_URL`. Mudanças no YAML exigem reiniciar o container (aceitável no MVP).

## R12. Execução contínua
- **Decision**: Docker Compose com `app`, `mysql`, `redis`; `restart: unless-stopped`; volumes
  nomeados para MySQL e Redis (AOF ligado); container `app` com usuário não root. O Docker é
  habilitado no boot da máquina (`systemctl enable docker`).
- **Rationale**: FR-020.
