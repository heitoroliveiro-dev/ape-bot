# Research: 002 — Zap e OLX via GeckoAPI e interação no Telegram

Base: teste no Playground em 27/10/2026 (6 créditos), docs da GeckoAPI lidas no mesmo dia,
respostas reais em `resposta_fonte` (ids 1 e 2) e fixtures em `tests/fixtures/geckoapi/`.

## R1. Como chamar a GeckoAPI
- **Decision**: `POST https://api.geckoapi.com.br/v1/extract`, `Authorization: Bearer
  {GECKO_API_KEY}`, corpo JSON (contrato em [contracts/geckoapi.md](contracts/geckoapi.md)).
  Tempo limite de 90 s por chamada. Uma nova tentativa só em 5xx (a GeckoAPI estorna o crédito
  nesses casos); nenhuma nova tentativa em tempo esgotado, 4xx ou `notFound`.
- **Rationale**: no Playground a extração levou de 10 a 20 s, e uma tentativa terminou em "não
  foi possível conectar" sem cobrar. Repetir depois de tempo esgotado pode cobrar duas vezes, porque
  não sabemos se o servidor terminou a extração.
- **Erros**: `402 INSUFFICIENT_CREDITS` → estado `sem_credito` (R8); `429` → falha da rodada, sem
  nova tentativa; `data: null, notFound: true` → falha de formato ("sem resultados").
- **Alternatives**: SDK ou MCP da GeckoAPI (dependência extra sem ganho); chamar no Playground
  (manual).

## R2. Consulta ao Zap
- **Decision**: `target=zapimoveis.com.br`, `type=plp`, `page=1`, `businessType=rent`,
  `state=MG`, `city=Belo Horizonte`, `priceMax` = maior `aluguel_max` das pessoas ativas (reais),
  `bedrooms` = `[q, q+1, …, 4]` com `q` = menor `quartos_min` (omitido quando `q = 0`),
  `propertyTypes` = união dos tipos das pessoas, convertida pela tabela abaixo. Sem `sort` e sem
  `neighborhood`.
- **Tipos** (docs do Zap PLP, 27/10/2026: `apartment, house, two_story_house, condominium,
  penthouse, kitnet, flat, …`; resposta em `unitTypes` com `APARTMENT`, `HOME`, …):

  | Tipo do domínio | `propertyTypes` enviados | `unitTypes` aceitos na resposta |
  |---|---|---|
  | apartamento | `apartment`, `penthouse` | `APARTMENT`, `PENTHOUSE` |
  | casa | `house`, `two_story_house` | `HOME`, `TWO_STORY_HOUSE` |
  | casa_condominio | `condominium` | `CONDOMINIUM` |
  | kitnet | `kitnet`, `flat` | `KITNET`, `FLAT` |

  Outro `unitTypes` (terreno, comercial) → descartado e contado como `tipo`.
- **Rationale**: a doc lista os aliases e diz que vários tipos são combinados com OU. Os filtros
  somados mantêm 1 chamada (constituição 2.2.0) e reduzem a busca. O "4" em `bedrooms` segue o "4+"
  do site; imóvel de aluguel com 5 ou mais quartos é raro na faixa das pessoas.
- **Alternatives**: uma chamada por pessoa (multiplica o custo); por bairro (proibido); sem filtros
  (30 de 22 mil, quase tudo fora da faixa).

## R3. Novidade no Zap
- **Decision**: "novo" = `anuncio` inserido pela primeira vez (`primeiro_visto_em`), como no
  QuintoAndar. Não há ordenação local.
- **Rationale**: o item do Zap não tem data de publicação, e a API não ordena por data (o `sort`
  só vale para VivaReal, Chaves na Mão, OLX e Webmotors). Ordenar os 30 itens recebidos não muda
  quais itens chegam.

## R4. Consulta à OLX (pronta, desligada)
- **Decision**: `target=olx.com.br`, `type=plp`, `page=1`, `state=MG`, `region=Belo Horizonte e
  Regiao`, `city=Belo Horizonte`, `categoryPath=imoveis/aluguel`, `sort=date`, `priceMax` como no
  Zap. 50 itens por página, com `listedAt`.
- **Parse**: `price` (reais) → aluguel; em `properties[]`: `condominio`/`iptu` ("R$ 497") → reais;
  `size` ("230m²") → área; `rooms` ("3", "5 ou mais") → quartos; tipo por `re_types` e
  `real_estate_type` normalizados: contém "temporada" → descarta; "kitnet"/"studio"/"loft" →
  kitnet; "casa" + "condominio" → casa_condominio; "apartamento"/"cobertura"/"flat" →
  apartamento; "casa"/"sobrado" → casa; senão descarta. Localização em `location.city`,
  `location.state`, `location.neighborhood`. A OLX PLP não traz contato.
- **Rationale**: formato visto na resposta real (id 2). A OLX ignorou a localização pedida, tanto
  por campos quanto por URL, e devolveu 50 itens de fora de MG. Fica desligada até a correção.

## R5. Filtro local de cidade e UF
- **Decision**: `slug(cidade) ∈ {belo-horizonte, bh}` **e** `slug(uf) ∈ {mg, minas-gerais}`.
  Cidade ou UF ausente → fora. Descartado e contado como `fora_da_cidade`.
- **Rationale**: a constituição 2.2.0 exige a trava. O `slug()` existente já tira acento, caixa e
  espaços ("Belo Horizonte", "belo horizonte" e "BELO-HORIZONTE" viram `belo-horizonte`).

## R6. Bairro do Zap/OLX → bairro do filtro
- **Decision**: com `s = slug(bairro do portal)`, usar `s` se estiver no catálogo
  `dados/bairros_bh.txt`; senão, o único slug do catálogo que começa com `s + "-"` (ex.:
  `bandeirantes` → `bandeirantes-pampulha`); senão (nenhum ou mais de um) → descartado e contado
  como `bairro_desconhecido`.
- **Rationale**: as pessoas filtram pelos slugs do catálogo do QuintoAndar (`filtro.aceita` compara
  `anuncio.bairro_slug`). É a mesma regra de `bairro_confere`, só que na direção inversa.
- **Alternatives**: aceitar o slug do portal sem conferir (o bairro nunca casaria com o filtro e o
  anúncio sumiria em silêncio).

## R7. Contato do anunciante em trânsito
- **Decision**: a fonte devolve, junto do `Anuncio`, um `Contato(nome, telefone, whatsapp)`
  opcional, que fica em memória durante a rodada (`dict` por chave do anúncio). `mensagem_imovel`
  recebe o contato; o texto e os botões vão na `Mensagem` da fila Redis. Nada do contato vai para o
  MySQL nem para os logs. `resposta_fonte` continua passando por `sem_anunciante`.
- **WhatsApp**: só os dígitos; tira o prefixo `55` quando o número tem 12 ou 13 dígitos; aceita 10
  ou 11 dígitos com DDD entre 11 e 99 → `https://wa.me/55{dígitos}`. Fora disso, sem botão. O
  telefone aparece formatado `(31) 98298-4510` quando é válido, ou como veio.
- **Reenvio** (`pendentes_antigos`): monta a mensagem a partir do banco, sem contato e com o botão
  "Abrir anúncio".
- **Risco aceito**: o Redis roda com AOF, então o texto da mensagem fica no arquivo AOF até a
  próxima reescrita. A constituição 2.2.0 permite a passagem pela fila; o arquivo fica no volume
  local do Redis.

## R8. Estado das fontes, falhas e créditos
- **Decision**: nova tabela `rodada_fonte` com uma linha por fonte por rodada: `status` ∈ {`ok`,
  `falha`, `desligada`, `sem_credito`} mais as contagens. O alerta passa a ser por fonte:
  `alerta.fonte` e "3 rodadas seguidas com `falha` naquela fonte" (as linhas `desligada` não contam
  e não interrompem a sequência). As regras de repetição a cada 24 h e de recuperação continuam as
  do MVP. Para o QuintoAndar, a falha da fonte é o `status_rodada` atual (metade das páginas ou
  erro de formato).
- **Créditos**: `402` → o cliente GeckoAPI marca `sem_credito` em memória, não chama mais nenhuma
  fonte paga até reiniciar, e o operador recebe um aviso imediato (uma vez por processo).
- **Rationale**: o alerta global do MVP fica cego para o Zap (1 chamada contra dezenas de páginas
  do QuintoAndar). Gravar por fonte também alimenta o `/status` sem estado compartilhado em
  memória.

## R9. Pausa
- **Decision**: `pessoa.pausada_em DATETIME NULL`. `/pausar` preenche, `/retomar` limpa e zera
  `filtros_hash`. A rodada considera só pessoas registradas **e** não pausadas.
- **Rationale**: zerar o `filtros_hash` reaproveita o modo resumo do MVP: na próxima rodada,
  "hash anterior ≠ atual" → resumo (FR-023), sem lógica nova.

## R10. Telegram
- **Decision**: `set_my_commands` no `post_init` com `/ajuda`, `/filtros`, `/status`, `/pausar` e
  `/retomar` (descrições em [contracts/telegram.md](contracts/telegram.md)). Mensagem de imóvel
  com `InlineKeyboardMarkup` de botões de URL: "Abrir anúncio" e, se houver, "WhatsApp". A
  `Mensagem` da fila ganha `botoes: list[[rótulo, url]]`. O resumo continua em texto.
- **/status**: última rodada (`rodada`), próxima rodada (calculada de `HORARIOS_RODADA` no fuso de
  São Paulo), envios entregues à pessoa em 24 h (`envio`), estado de cada fonte (última linha de
  `rodada_fonte`, ou `desligada` pela configuração). Para o operador, também o saldo de
  `GET /v1/me/credits` (`currentCredits`, `creditsConsumed.last24Hours`), com tempo limite de
  10 s; se falhar, mostra "saldo indisponível".
- **Rationale**: o endpoint de conta fica fora do `/v1/extract`, e a doc não fala em cobrança; o
  primeiro uso confere isso comparando com o painel.

## R11. Configuração
- **Decision**: `.env` ganha `GECKO_API_KEY` (vazio = fontes pagas desligadas) e `GECKO_FONTES`
  (lista separada por vírgula, padrão `zap`; valores aceitos `zap`, `olx`; outro valor → aviso ao
  operador na inicialização e ignorado). O `filtros.yaml` não muda.
- **Rationale**: ligar ou desligar uma fonte é decisão de operação, como os segredos, e não de
  pessoa. Sem chave, o robô sobe normalmente (FR-006) e avisa o operador uma vez.

## R12. Custo total no Zap
- **Decision**: total = `prices.rent` + `prices.condominium`, mais `prices.iptu` quando informado.
  Sem `condominium` → total `None` ("não informado"). Valores em reais → centavos.
- **Rationale**: FR-017. O Zap não informa o total pronto como o QuintoAndar faz.
- **Risco**: se o IPTU do Zap for anual em algum anúncio, o total fica inflado. Fica para conferir
  na amostra de 30 mensagens do SC-003.
