# Data Model: 003 — Entrega espaçada, favoritos, resumo diário e filtros pelo Telegram

Mudanças sobre os modelos da 001 e da 002. Dinheiro em centavos (`INT`); horários em UTC no banco,
exibidos em America/Sao_Paulo. Migração nova: `migrations/004_cadastro_entrega.sql`.

## MySQL

### pessoa (alterada)
| Campo | Tipo | Regra |
|---|---|---|
| nome | VARCHAR(80) | Agora é o nome escolhido no cadastro (R8): 1 a 40 caracteres limpos. A semente do arquivo só vale para quem ainda não tem cadastro |
| filtros | JSON NULL | **Novo.** `{"bairros": [slug…], "aluguel_max_centavos": int, "quartos_min": int, "tipos": [valor de Tipo…]}`. NULL = sem cadastro |
| cadastro_completo_em | DATETIME NULL | **Novo.** Preenchido ao fim do cadastro ou pela semente do arquivo |
| filtros_atualizados_em | DATETIME NULL | **Novo.** Última gravação de filtros (cadastro, edição ou semente) |
| filtros_hash | CHAR(64) NULL | **Sem uso** a partir da 003 (R4); fica na tabela para não precisar de migração destrutiva |

Validação de `filtros` (ao gravar, no `cadastro.py`, e ao ler, no `banco.py`): pelo menos 1 bairro
do catálogo, pelo menos 1 tipo, `quartos_min` ∈ {0, 1, 2, 3, 4}, `aluguel_max_centavos` ∈
[30 000, 5 000 000]. Lido inválido → pessoa fora da rodada e aviso ⚙️ ao operador.

**Estados** (derivados, sem coluna própria):

```text
autorizada (no arquivo) ──/start──▶ registrada ──cadastro──▶ ativa ⇄ pausada
                                      │                        ▲
                                      └─ semente do arquivo ───┘ (já ativa, se registrada)
removida do arquivo ──▶ inativa (dados mantidos)
```

Ativa = autorizada **e** `registrada_em` **e** `cadastro_completo_em` **e** `pausada_em IS NULL`.
Só pessoas ativas entram na rodada, nos filtros somados, no despachante e no resumo.

### conversa (nova)
| Campo | Tipo | Regra |
|---|---|---|
| chat_id | BIGINT PK, FK pessoa | Uma conversa aberta por pessoa |
| modo | ENUM('cadastro','edicao') | |
| etapa | VARCHAR(20) | `nome`, `tipos`, `quartos`, `regionais`, `bairros`, `valor`, `revisao` |
| rascunho | JSON | Respostas parciais, mais `regional` e `pagina` quando a etapa é `bairros` |
| atualizada_em | DATETIME | |

Transições ([contracts/telegram.md](contracts/telegram.md)):

```text
cadastro: nome → tipos → quartos → regionais ⇄ bairros → valor → (grava, apaga conversa)
edição:          tipos → quartos → regionais ⇄ bairros → valor → revisao → (Salvar: grava | Cancelar)
"Cancelar" (edição) em qualquer etapa → apaga a conversa, filtros intactos
```

A linha é apagada ao concluir ou cancelar. Um novo "Editar filtros" com uma edição aberta recomeça
a partir dos filtros salvos.

### envio (uso alterado, sem mudança de colunas)
| status | Significado na 003 |
|---|---|
| `pendente` | Na fila da pessoa (Redis) ou a caminho do Telegram |
| `entregue` | Entregue; `entregue_em` alimenta o resumo e o `/status` |
| `falhou` | Falha definitiva (3 tentativas ou chat bloqueado) |

Descartado por filtro no despacho (FR-006) ou por `/pausar` → **a linha `pendente` é apagada**, e o
imóvel volta a ser candidato numa rodada futura. Não há status "descartado".

### favorito (nova)
| Campo | Tipo | Regra |
|---|---|---|
| chat_id | BIGINT, FK pessoa | |
| fonte, id_externo | VARCHAR(20), VARCHAR(40), FK anuncio | |
| salvo_em | DATETIME | Ordena o `/favoritos` (mais recente primeiro) |

PK (chat_id, fonte, id_externo). Sem dado de anunciante (FR-014).

### resumo_diario (nova)
| Campo | Tipo | Regra |
|---|---|---|
| chat_id | BIGINT, FK pessoa | |
| dia | DATE | Dia em America/Sao_Paulo |
| enviado_em | DATETIME | |

PK (chat_id, dia): `INSERT IGNORE` garante um resumo por pessoa por dia (FR-017).

## Redis

| Chave | Tipo | Conteúdo | Vida |
|---|---|---|---|
| `apebot:envios` | LIST | Fila de entrega da 002 (`Mensagem` JSON); agora com `botoes` em linhas (R10) | Até o Entregador entregar |
| `apebot:pessoa:{chat_id}:fila` | ZSET | `member = "{fonte}\|{id_externo}"`, `score = aluguel_centavos` | Até o despacho, ou `/pausar` |
| `apebot:pessoa:{chat_id}:imoveis` | HASH | campo = member; valor = `ImovelNaFila` JSON | Igual ao ZSET (HDEL no despacho) |
| `apebot:pessoa:{chat_id}:proximo` | STRING | Epoch (s) a partir do qual pode sair o próximo imóvel | Sobrescrito a cada despacho; apagado no `/pausar` |

`ImovelNaFila` (JSON): `anuncio` (os campos de `Anuncio`, para conferir o filtro no despacho e
remontar o texto), `contato` (`nome`, `telefone`, `whatsapp_url`, ou `null`). O texto e os botões
são montados **no despacho**, para usar o nome de bairro e o formato do momento.

A **reconciliação** na subida (research R3) mantém o invariante: toda linha `pendente` de pessoa
ativa está em exatamente um destes lugares: ZSET da pessoa ou `apebot:envios`.

## Domínio (`modelos.py`)

| Tipo | Mudança |
|---|---|
| `Pessoa` | Inalterado (`chat_id`, `nome`, `filtro`); agora montado do MySQL |
| `Filtro` | Inalterado |
| `Bairro` | **Novo**, frozen: `slug`, `nome`, `regional` |
| `REGIONAIS` | **Novo**: as 9 regionais, na ordem do teclado, mais `Outros` no fim |

## Arquivos de dados

`src/apebot/dados/bairros_bh.csv` substitui `bairros_bh.txt`: `slug,nome,regional`, 283 linhas
(289 − 6 de fora de BH), gerado por `scripts/regionais_pbh.py` a partir de
`docs/referencias/pbh-bairros-regionais.pdf` (research R9). `pyproject.toml`:
`package-data` passa a incluir `dados/*.csv`.
