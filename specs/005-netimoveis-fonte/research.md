# Research: Netimóveis como fonte (005)

Base: spike `docs/spikes/002-netimoveis.md` (28/10/2026) e verificações adicionais do mesmo dia,
com cliente HTTP comum, `User-Agent: ape-bot/0.1 (uso pessoal; baixo volume)` e 2–3 s entre
requisições.

## R1 — Superfície e URL da busca
- **Decisão**: `https://www.netimoveis.com/locacao/minas-gerais/belo-horizonte/bairros/{bairro}/{tipo}?quartos={N}`,
  só a 1ª página, sem seguir redirecionamentos para fora de `/locacao/`.
- **Racional**: caminho público liberado no `robots.txt`; `quartos=` não é bloqueado e aparece no
  sitemap do próprio portal (`sitemap-filtro-quartos_*.xml`). `?quartos=2` devolve imóveis de 2 a 6
  quartos, ou seja, "N ou mais".
- **Alternativas rejeitadas**: paginação (`pag=`), preço (`precoMin/precoMax`) e ordenação (`ordem=`)
  são bloqueados; `/pesquisa/` e `/api/` também. Busca na cidade inteira (`/locacao/.../belo-horizonte/{tipo}`)
  traria só 21 de ~1.074 apartamentos.

## R2 — Onde estão os dados
- **Decisão**: ler os blocos `<script type="application/ld+json">` da página. O bloco `ItemList` tem
  `numberOfItems` (total da busca) e `itemListElement[].item` (`RealEstateListing`) com:
  `url` (id e slugs), `offers.price` (aluguel, inteiro em reais), `offers.itemOffered.numberOfBedrooms`,
  `floorSize.value` (m²) e `additionalProperty` "Condominium Fee" (às vezes ausente).
- **Busca vazia**: a página vem **sem** `ItemList`, mas com `WebPage` e `BreadcrumbList` (visto em
  Lourdes/casa-em-condominio e Penha/apartamento). Isso é "0 resultados", não erro.
- **Formato inválido**: nenhum bloco JSON-LD, ou `ItemList` sem a estrutura esperada → `FormatoInvalido`.
- **Racional**: JSON-LD é feito para buscadores (schema.org), é estável e não exige JavaScript; o
  HTML dos cartões muda mais.
- **Alternativas rejeitadas**: Playwright (desnecessário: os dados vêm no HTML); página de detalhe
  (fora do escopo; uma requisição por imóvel).

## R3 — Tipo, bairro e cidade a partir da URL do imóvel
- **Decisão**: a URL do imóvel tem o formato
  `/imovel/locacao-{tipo_portal}-minas-gerais-belo-horizonte-{bairro_portal}/{id}`. Extrair com
  regex ancorada em `-minas-gerais-belo-horizonte-`; quem não casar é descartado como
  `fora_da_cidade` (trava local de cidade da 002).
- **Mapa de tipos** (contagem de anúncios de locação em BH no sitemap entre parênteses):

  | Tipo do portal | Tipo do robô | Busca usada |
  |---|---|---|
  | `apartamento` (914), `cobertura` (99), `area-privativa` (43), `andar-pilotis` (204) | `APARTAMENTO` | `apartamento` (traz cobertura e área privativa junto) |
  | `casa` (203), `casa-geminada` (7), `sobrado` (2), `duplex` (1) | `CASA` | `casa` |
  | `casa-em-condominio` (1) | `CASA_CONDOMINIO` | `casa-em-condominio` |
  | `kitchenette` (26), `studio` (3), `flat` (7), `loft` (2) | `KITNET` | `kitchenette` |
  | comerciais (`loja`, `sala`, `galpao`, …) | — | descartados como `tipo_nao_aceito` |

  O tipo vem da URL do imóvel, não da busca, porque a busca de apartamento traz coberturas e áreas
  privativas.
- **Bairro**: o slug do portal é o mesmo do catálogo na grande maioria (170 de 202 bairros de BH do
  portal batem exatamente; todos os bairros pedidos hoje pelas duas pessoas que existem no portal
  batem). Os demais têm sufixo de regional entre parênteses (`bandeirantes-(pampulha)`): remover
  `-(…)` e passar por `bairro_do_catalogo` (já existente em `fontes/resultado.py`). Sem
  correspondência → descartado como `bairro_desconhecido`.
- **Bairro diferente do buscado**: nas amostras todos os itens eram do bairro buscado; se vier outro
  bairro do catálogo, o imóvel é aceito com o bairro do item (o filtro por pessoa decide).

## R4 — Bairros que o portal não tem
- **Achado**: 7 bairros das pessoas não aparecem no sitemap do portal (Comiteco, Fazendinha, Marçola,
  Novo São Lucas, Penha, Santa Rita de Cássia, Vila Barragem Santa Lúcia). A busca deles responde 200
  com a página vazia (R2), não 404.
- **Decisão**: tratar como busca vazia; sem lista fixa de bairros do portal. 404 também conta como
  vazia (log `info`). Se **todas** as buscas da rodada voltarem 404, a fonte fica `falha` (provável
  mudança de URL).

## R5 — Volume, intervalo e duração
- **Decisão**: uma busca por par (bairro, tipo) da união dos filtros das pessoas ativas, com
  `quartos` = menor mínimo entre elas (omitido quando 0). Intervalo aleatório de 2–5 s e backoff
  5/15/45 s em 429/5xx, como no QuintoAndar.
- **Estimativa**: hoje ~50 bairros × 1–2 tipos ≈ 100 buscas ≈ 6–7 min por rodada, somados aos ~6 min
  do QuintoAndar. Bem abaixo do intervalo mínimo de 2 h entre rodadas.
- **Corte da 1ª página**: `numberOfItems > len(itemListElement)` → log `netimoveis_corte bairro= tipo=
  total= lidos=` (ex.: Funcionários/apartamento 2+ quartos, 31 → 21).

## R6 — Liga/desliga
- **Decisão**: variável `NETIMOVEIS` com `ligado` ou `desligado`; **padrão `desligado`**. Valor
  desconhecido → aviso ao operador na subida e fica desligado. Vale após reinício (no Railway, mudar a
  variável já reinicia o serviço).
- **Racional**: antes de ligar em produção faltam a leitura dos termos de uso e o teste a partir do IP
  do Railway; ligar por padrão faria o primeiro deploy acessar o portal antes disso.
- **Alternativas rejeitadas**: reaproveitar `GECKO_FONTES` (é da fonte paga, com outra semântica);
  lista genérica `FONTES` (mexe nas fontes existentes sem necessidade agora).

## R7 — Sonda para o IP do Railway
- **Decisão**: `python -m apebot.fontes.netimoveis` faz **uma** busca (Centro/apartamento) e imprime
  status HTTP, total e quantidade lida, sem tocar em banco ou fila. Roda no shell do serviço no
  Railway para validar o acesso do datacenter antes de ligar a fonte.
- **Racional**: `--rodada-agora` faria a rodada inteira, inclusive a chamada paga do Zap.

## R8 — Status da rodada e alertas
- **Decisão**: `status_rodada` como nas outras fontes (falha se formato inválido ou se metade ou mais
  das buscas falharem). O status geral da rodada continua vindo só do QuintoAndar. Alerta por fonte já
  existente (`decidir_alerta`) vale para `netimoveis` sem mudança.
- Página de desafio antirrobô (HTML com "Just a moment", "Attention Required" ou status 403) conta
  como erro de **acesso**, nunca é contornada.

## R9 — Fixtures
- **Decisão**: salvar páginas reais **cortadas** (só `<title>` e os blocos JSON-LD) em
  `tests/fixtures/netimoveis/`: `funcionarios-apartamento-2q.html` (corte 31 → 21, cobertura e área
  privativa), `centro-kitchenette.html` (kitnet), `lourdes-casa-em-condominio.html` (vazia),
  `sem-jsonld.html` (formato inválido, sintética a partir de uma real).
- **Racional**: as páginas inteiras têm ~1 MB; o parser só lê o JSON-LD.
