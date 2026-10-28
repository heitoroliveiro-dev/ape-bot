# Data Model: 001 — MVP QuintoAndar → Telegram

Dinheiro sempre em centavos (`INT`). Horários em UTC no banco; exibidos em America/Sao_Paulo.

## pessoa
| Campo | Tipo | Regra |
|---|---|---|
| chat_id | BIGINT PK | Vem do `filtros.yaml`; só existe se autorizado |
| nome | VARCHAR(80) | Do YAML |
| registrada_em | DATETIME NULL | Preenchido no primeiro `/start`; NULL = ainda não registrada |
| filtros_hash | CHAR(64) NULL | Hash dos filtros usados no último envio; diferente do atual → modo resumo |

Estados: `autorizada (registrada_em NULL)` → `/start` → `registrada`. Pessoa removida do YAML deixa
de receber (não é apagada).

## anuncio
| Campo | Tipo | Regra |
|---|---|---|
| fonte | VARCHAR(20) | `quintoandar` |
| id_externo | VARCHAR(40) | ID do portal |
| tipo | ENUM('apartamento','casa','casa_condominio','kitnet') | Obrigatório |
| bairro | VARCHAR(80) | Nome como o portal informa |
| bairro_slug | VARCHAR(80) | Slug do bairro consultado (R4) |
| quartos | TINYINT | Obrigatório, ≥ 0 |
| area_m2 | SMALLINT NULL | |
| aluguel_centavos | INT | Obrigatório, ≥ 0 |
| total_centavos | INT NULL | |
| url | VARCHAR(255) | `https://www.quintoandar.com.br/imovel/{id}` |
| primeiro_visto_em | DATETIME | |
| ultimo_visto_em | DATETIME | Atualizado a cada rodada que o vê (preço também é atualizado) |

PK (fonte, id_externo). Índice (bairro_slug, tipo).

## envio
| Campo | Tipo | Regra |
|---|---|---|
| chat_id | BIGINT FK pessoa | |
| fonte, id_externo | FK anuncio | |
| status | ENUM('pendente','entregue','falhou') | |
| criado_em | DATETIME | Ao enfileirar |
| entregue_em | DATETIME NULL | |
| tentativas | TINYINT | |

PK (chat_id, fonte, id_externo) — garante FR-013. Transições: `pendente → entregue`,
`pendente → falhou`. Imóvel "já enviado" = existe linha com qualquer status (não reenvia nem os que
falharam por bloqueio do bot).

## rodada
| Campo | Tipo | Regra |
|---|---|---|
| id | BIGINT PK AI | |
| iniciada_em, terminada_em | DATETIME | |
| status | ENUM('ok','falha') | Regra em research R10 |
| paginas_ok, paginas_erro | SMALLINT | |
| anuncios_vistos, anuncios_novos, descartados | INT | |
| enfileirados | INT | Total de mensagens enfileiradas |
| erro_resumo | VARCHAR(500) NULL | |

## alerta
| Campo | Tipo | Regra |
|---|---|---|
| id | BIGINT PK AI | |
| aberto_em | DATETIME | Após 3 rodadas com falha |
| ultimo_aviso_em | DATETIME | Reaviso após 24 h |
| fechado_em | DATETIME NULL | Primeira rodada ok depois da abertura |

No máximo um alerta com `fechado_em IS NULL`.

## schema_migracao
`versao VARCHAR(40) PK, aplicada_em DATETIME`.

## Objetos em memória (não persistidos)
- **Filtro** (do YAML): `bairros: frozenset[slug]`, `aluguel_max_centavos: int`,
  `quartos_min: int`, `tipos: frozenset[Tipo]`; método `aceita(anuncio) -> bool` (FR-005/FR-006).
- **Anuncio** (dataclass frozen) — resultado do parse, espelha a tabela.
