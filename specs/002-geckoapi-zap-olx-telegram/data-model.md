# Data Model: 002 — Zap e OLX via GeckoAPI e interação no Telegram

Mudanças sobre o modelo da 001 (`specs/001-mvp-quintoandar-telegram/data-model.md`). Dinheiro em
centavos (`INT`); horários em UTC no banco e exibidos em America/Sao_Paulo. Migração nova:
`migrations/003_fontes_e_pausa.sql`. A tabela `resposta_fonte` (migração 002) já existe.

## pessoa (alterada)
| Campo | Tipo | Regra |
|---|---|---|
| pausada_em | DATETIME NULL | **Novo.** Preenchido por `/pausar`; NULL = avisos ativos |

Estados: `registrada/ativa` ⇄ `registrada/pausada`. `/retomar` limpa `pausada_em` **e**
`filtros_hash` (força o resumo na próxima rodada, R9). Só pessoas registradas e ativas entram na
rodada e nos filtros somados das fontes pagas.

## anuncio (alterada)
| Campo | Tipo | Regra |
|---|---|---|
| fonte | VARCHAR(20) | `quintoandar`, `zap` ou `olx` |
| id_externo | VARCHAR(40) | `id` do portal (Zap: `id`, não `externalId`; OLX: `id`) |
| bairro_slug | VARCHAR(80) | Slug do catálogo de BH (R6) |
| url | **VARCHAR(500)** | Link público do anúncio no portal (alargado; URLs do Zap chegam a ~150 caracteres) |
| total_centavos | INT NULL | Zap: aluguel + condomínio (+ IPTU) (R12); OLX: idem a partir de `properties` |

Sem campo de anunciante (constituição III).

## rodada_fonte (nova)
| Campo | Tipo | Regra |
|---|---|---|
| rodada_id | BIGINT FK rodada | |
| fonte | VARCHAR(20) | `quintoandar`, `zap`, `olx` |
| status | ENUM('ok','falha','desligada','sem_credito') | R8 |
| consultas | SMALLINT | Páginas (QuintoAndar) ou chamadas (pagas) |
| anuncios_vistos | INT | Itens que passaram nas travas |
| descartados | INT | Total descartado |
| fora_da_cidade | INT | R5 |
| erro_resumo | VARCHAR(500) NULL | Sem dado de anunciante |

PK (rodada_id, fonte). Uma linha por fonte conhecida em toda rodada, inclusive `desligada`.

## alerta (alterada)
| Campo | Tipo | Regra |
|---|---|---|
| fonte | VARCHAR(20) NOT NULL DEFAULT 'quintoandar' | **Novo.** Alerta aberto por fonte |

"Seguidas com falha" = linhas de `rodada_fonte` daquela fonte, da mais recente para trás,
ignorando `desligada`, até a primeira que não seja `falha`. Os alertas antigos ficam como
`quintoandar`.

## rodada (sem mudança de schema)
`status` continua refletindo o QuintoAndar (`status_rodada`); as fontes pagas ficam em
`rodada_fonte`. `descartados` passa a somar todas as fontes.

## resposta_fonte (migração 002, já aplicada)
Uma linha por chamada paga com sucesso (`request_id` único), corpo JSON **sem** anunciante.
`notFound` e erros não têm `data` e ficam só no `erro_resumo` de `rodada_fonte`.

## Em memória (não persistido)
- **Contato**: `nome: str | None`, `telefone: str | None`, `whatsapp_url: str | None`. Vive
  só durante a rodada (`dict[chave, Contato]`) e dentro da `Mensagem` na fila até a entrega.
- **Mensagem** (fila Redis): ganha `botoes: list[list[str]]` (pares `[rótulo, url]`). Serializada
  em JSON como as demais.
- **ResultadoFonte**: `fonte`, `status`, `anuncios`, `contatos`, `descartados: Counter`
  (`fora_da_cidade`, `tipo`, `bairro_desconhecido`, `incompleto`), `consultas`, `erro`.
