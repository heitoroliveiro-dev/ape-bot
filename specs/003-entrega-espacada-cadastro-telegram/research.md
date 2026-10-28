# Research: 003 — Entrega espaçada, favoritos, resumo diário e filtros pelo Telegram

Base: código da 002 (`rodada.py`, `fila.py`, `telegram_bot.py`, `banco.py`, `config.py`), Redis 7
com AOF já ligado no Compose, e o PDF da PBH "Relação de bairros, regionais e territórios de
gestão compartilhada" (`docs/referencias/pbh-bairros-regionais.pdf`).

## R1. Onde fica a fila de cada pessoa
- **Decision**: uma fila **por pessoa no Redis**, ordenada por valor:
  - `apebot:pessoa:{chat_id}:fila`: ZSET com `member = "{fonte}|{id_externo}"` e
    `score = aluguel_centavos`;
  - `apebot:pessoa:{chat_id}:imoveis`: HASH com `campo = member` e valor = JSON da mensagem
    pronta (texto, botões, dados do anúncio para conferir o filtro e contato, se houver).

  A rodada faz `ZADD NX` e `HSETNX` (idempotente). A tabela `envio` continua sendo a verdade sobre o
  que já foi decidido para a pessoa: a linha nasce `pendente` quando o imóvel entra na fila dela, e
  `ja_enviados` continua barrando a repetição.
- **Rationale**: o ZSET dá "mais barato primeiro" sem ordenar nada à mão, e imóveis novos entram na
  ordem certa junto com os antigos (FR-004). O contato do anunciante continua só no Redis até a
  entrega, que é o "trânsito pela fila" da constituição (princípio III), mesmo que a espera agora
  dure horas. O AOF do Redis já existe, então a fila sobrevive a reinício (FR-005).
- **Alternatives**: (a) `envio` no MySQL como fila, com `ORDER BY aluguel`. Perde o contato, que
  não pode ir ao MySQL. (b) Manter a lista FIFO única `apebot:envios` e dormir de 2 a 5 min entre
  os itens. Bloqueia as outras pessoas e não ordena por valor.

## R2. Quem decide a hora de cada mensagem (despachante)
- **Decision**: uma tarefa assíncrona, o **despachante**, roda no mesmo processo do bot e acorda a
  cada 20 s. A cada volta:
  1. Fora de [08:00, 22:00) em America/Sao_Paulo, não faz nada (FR-003).
  2. Lê do MySQL as pessoas ativas (cadastro completo, autorizadas, não pausadas) com os filtros
     atuais.
  3. Para cada pessoa com `agora ≥ apebot:pessoa:{chat_id}:proximo` (chave Redis com timestamp;
     ausente = já pode), faz `ZPOPMIN` + `HGET`/`HDEL`. Se o imóvel não atende mais ao filtro
     (FR-006), apaga a linha `pendente` em `envio` (ele volta a ser candidato) e tenta o próximo da
     fila na mesma volta. Se atende, coloca a mensagem em `apebot:envios`, a fila de entrega que já
     existe, e grava `proximo = agora + uniforme(120, 300) s`.
- O **Entregador** da 002 não muda: limite de taxa, `RetryAfter`, 3 tentativas, `Forbidden` e
  marcação `entregue`/`falhou` em `envio`. Respostas de comando, perguntas do cadastro, resumo e
  avisos ao operador continuam indo direto para `apebot:envios` ou como resposta ao update, sem
  espera (FR-010).
- **Rationale**: o despachante só escolhe *qual* e *quando*; a entrega continua passando pela fila
  Redis com limite de taxa e nova tentativa (princípio V). O sorteio por mensagem atende ao "nunca
  o mesmo intervalo fixo". Com o `proximo` no Redis, ninguém recebe uma rajada depois de reiniciar.
  Volta de 20 s: a primeira mensagem sai em até 20 s depois da rodada, e o intervalo real fica entre
  120 e 320 s, dentro de "2 a 5 min" com folga para arredondamento.
- **Intervalo configurável só para validação**: `ENTREGA_INTERVALO` (padrão `120-300`, em segundos)
  permite rodar o quickstart com `5-10`. Fora do intervalo 1–3600 → aviso ⚙️ e usa o padrão.
- **Alternatives**: `JobQueue.run_once` por pessoa, reagendado a cada envio. Os jobs do JobQueue
  ficam em memória e se perdem no reinício. Um job `run_repeating` faria o mesmo que a tarefa, mas
  a tarefa segue o padrão do `Entregador`, que já existe.

## R3. Reinício sem perder nem repetir
- **Decision**: na subida, antes do despachante, uma **reconciliação** por pessoa ativa:
  `pendentes(MySQL) − membros do ZSET − chaves em apebot:envios`. O que sobrar volta ao ZSET
  montado a partir do banco, **sem contato** (como o reenvio da 002). O `reenfileirar_pendentes` da
  002, que jogava todos os pendentes antigos direto em `apebot:envios`, **sai**: com a fila
  espaçada, todo pendente é "antigo", e ele causaria uma rajada.
- Item tirado do ZSET e perdido antes de entrar em `apebot:envios` (queda no meio da volta): ainda
  está `pendente` no MySQL e volta na próxima reconciliação. Item que já estava em `apebot:envios`:
  não é duplicado, porque a reconciliação desconta as chaves da lista de entrega.
- **Rationale**: SC-008 (nada repetido, nada sumido). O MySQL é a referência; o Redis só guarda a
  ordem e o contato.

## R4. O que entra na fila numa rodada (fim da lista-resumo)
- **Decision**: `Rodada._enfileirar_para` deixa de ter "modo resumo". Para cada pessoa ativa:
  `novos_para(pessoa, anúncios da rodada, ja_enviados)` → `criar_envios_pendentes` → `ZADD` +
  `HSET`. Saem `hash_filtros`, `filtros_hash`, `mensagens_resumo` e a regra "não manda resumo com
  coleta em falha": todos os imóveis vão um a um (FR-007), e um imóvel visto numa rodada com falha
  parcial é tão bom quanto qualquer outro.
- "Todos os disponíveis" continua significando "vistos nesta rodada": o QuintoAndar busca todos os
  bairros × tipos das pessoas ativas, e o Zap traz 30 itens por rodada. Depois de editar os filtros,
  a rodada seguinte já coleta os bairros novos (a rodada lê os filtros do MySQL na hora de começar,
  FR-027).
- **Pausa**: `/pausar` apaga a fila Redis da pessoa (ZSET, HASH e `proximo`) e as linhas `pendente`
  dela em `envio`. Os imóveis voltam a ser candidatos e entram de novo na primeira rodada depois de
  `/retomar` (Edge Cases da spec). O despachante já ignora quem está pausado, então a limpeza só
  evita que contatos antigos fiquem parados no Redis.
- **Alternatives**: buscar candidatos no MySQL (`anuncio.ultimo_visto_em` nas últimas 24 h) em vez
  de só nesta rodada. Mais completo para o Zap, mas muda a regra de "novo" da 001/002; fica para
  depois.

## R5. Filtros e cadastro no MySQL, `filtros.yaml` como lista de autorizados
- **Decision**:
  - `pessoa` ganha `filtros JSON NULL` (`{"bairros": [...], "aluguel_max_centavos": n,
    "quartos_min": n, "tipos": [...]}`), `cadastro_completo_em DATETIME NULL` e
    `filtros_atualizados_em DATETIME NULL`. O nome passa a ser o que a pessoa escolheu.
  - `filtros.yaml`: `operador_chat_id` e `pessoas[].chat_id` continuam obrigatórios; `nome` e
    `filtros` ficam opcionais. A validação dos filtros do arquivo continua, mas um erro neles vira
    problema ⚙️ e a pessoa continua autorizada (pode fazer o cadastro).
  - `sincronizar_pessoas` na subida: insere chat_ids novos; para quem tem `filtros IS NULL` e
    filtros válidos no arquivo, grava filtros, nome e `cadastro_completo_em` (semente única). Quem
    já tem cadastro e tem filtros diferentes no arquivo → aviso ⚙️ "filtros do arquivo ignorados
    para {nome}: o cadastro no Telegram vale". O `ON DUPLICATE KEY UPDATE nome` da 001 sai, porque
    o nome agora é da pessoa.
  - Pessoa ativa = autorizada no arquivo **e** `registrada_em` **e** `cadastro_completo_em` **e**
    `pausada_em IS NULL`. Um chat removido do arquivo deixa de ser ativo, mas os dados ficam.
  - `Rodada`, despachante, resumo, `/filtros` e `filtros_somados` leem `Pessoa` do MySQL
    (`banco.pessoas_ativas(autorizados)`), não mais de `config.pessoas`.
- **Rationale**: SQL puro e uma coluna JSON (MySQL 8.4) evitam uma tabela filha só para bairros;
  ninguém consulta "quem quer o bairro X" no banco. Ler os filtros no início de cada rodada dá a
  regra "vale a partir da próxima rodada" sem trava extra.
- **Alternatives**: tabela `pessoa_bairro` (mais joins, sem uso); continuar com o YAML e reescrever
  o arquivo a partir do bot (montado `:ro`, e daria conflito com a edição manual do operador).

## R6. Conversa do cadastro e da edição
- **Decision**: máquina de estados própria em `src/apebot/cadastro.py`, **pura** (sem Telegram):
  recebe `(estado, entrada)` e devolve `(novo estado, resposta)`, em que a resposta tem texto e
  teclado descritos como listas. O estado fica no MySQL, na tabela `conversa` (chat_id, modo
  `cadastro|edicao`, etapa, rascunho JSON, `atualizada_em`). O `telegram_bot.py` só traduz updates
  (mensagem de texto ou `CallbackQuery`) para entradas e as respostas para `reply_text` ou
  `edit_message_text`.
- **Etapas**: `nome → tipos → quartos → regionais ⇄ bairros(regional, página) → valor → fim`. A
  edição começa em `tipos`, com o rascunho preenchido pelos filtros atuais, e confirma em
  `revisao` ("Salvar" / "Cancelar"). O cadastro grava ao receber um valor válido.
- **Retomada** (FR-023): `/start`, ou qualquer texto, com uma conversa aberta reapresenta a etapa
  atual a partir do rascunho.
- **Botões velhos**: o `callback_data` leva a etapa (`c:{etapa}:{ação}[:{arg}]`). Toque com etapa
  diferente da atual, ou sem conversa aberta → `answer("Essa pergunta já passou.")`, sem mudar
  nada.
- **Tamanho do `callback_data`** (limite de 64 bytes): o maior slug do catálogo, depois de tirar
  os de fora de BH, é `distrito-industrial-do-jatoba` (29 caracteres), então
  `c:bairros:t:{slug}` fica em no máximo 41 bytes. Regionais pelo índice 0–8.
  Página de bairros: 24 botões (2 por linha), com `◀`/`▶`, "Marcar todos"/"Desmarcar todos" e
  "Voltar às regionais". O toque edita a própria mensagem (`edit_message_reply_markup`) para não
  encher a conversa.
- **Rationale**: PTB tem `ConversationHandler` + `PicklePersistence`, mas isso exige um arquivo
  pickle num volume novo e mistura a regra de negócio com o framework. A máquina pura é testável sem
  Telegram (princípio II, onde quebra: validação e transições) e reaproveita o MySQL.
- **Alternatives**: `ConversationHandler` com persistência (arquivo novo, estado fora do banco,
  difícil de testar); estado em `context.user_data` (perde no reinício, viola FR-023).

## R7. Valor máximo: leitura e formato
- **Decision**: `ler_valor(texto) -> int | None` (centavos), em `cadastro.py`:
  1. `strip()`; tira um prefixo `R$` opcional (sem diferenciar maiúsculas) e os espaços depois dele.
  2. O resto precisa casar inteiro com
     `^(\d{1,3}(\.\d{3})+|\d+)(,\d{1,2})?$`: o ponto só aparece em grupos de 3 depois do primeiro
     grupo, e a vírgula, com 1 ou 2 dígitos. Sem sinal, sem espaço interno, sem letra.
  3. centavos = inteiro × 100 + fração ("5" → 50, "50" → 50, "05" → 5).
  4. Fora de [30 000, 5 000 000] centavos (R$ 300 a R$ 50.000) → `None`, com motivo "fora da
     faixa".

  | Entrada | Resultado |
  |---|---|
  | `3000`, `3.000`, `3.000,00`, `R$ 3.000`, `r$3000` | 300000 |
  | `3000,50`, `3000,5` | 300050 |
  | `12.500` | 1250000 |
  | `3k`, `três mil`, `-3000`, `0`, `3000.50`, `3 000`, `3.00`, `30.00,0`, `100`, `999999` | recusa |

- `formatar_reais` passa a sempre mostrar centavos: `R$ 3.000,00`, `R$ 2.450,50` (FR-029). Muda o
  texto do `/status` e do `/filtros` da 002, que mostravam `R$ 3.000`.
- **Rationale**: "3000.50" é ambíguo no Brasil e "3.00" quase sempre é erro de digitação;
  recusar e mostrar o exemplo custa menos do que gravar um filtro errado.

## R8. Nome
- **Decision**: `limpar_nome(texto) -> str | None`: remove caracteres de controle (categoria
  Unicode `C*`) e `<>&`, colapsa espaços, `strip()`, corta em 40 caracteres e exige pelo menos uma
  letra (`str.isalpha` em algum caractere). Capitaliza cada palavra, menos as partículas `da`,
  `de`, `do`, `das`, `dos` e `e` no meio do nome. Emojis e símbolos são removidos (categorias `So`,
  `Sk`). Na saída, o texto continua passando por `html.escape`.
- "  maria   clara " → "Maria Clara"; "joão da silva" → "João da Silva"; "🙂🙂" → recusa.

## R9. Bairros, regionais e o catálogo
- **Decision**: `src/apebot/dados/bairros_bh.txt` vira `src/apebot/dados/bairros_bh.csv`, com as
  colunas `slug,nome,regional`:
  - `slug`: o do QuintoAndar, **sem mudança** (a URL de coleta e os filtros salvos dependem dele);
  - `nome`: o nome oficial do PDF, com acento ("Alto Caiçaras", "Nova Suissa"), para exibir; para
    os bairros do grupo "Outros", o slug com iniciais maiúsculas;
  - `regional`: uma das 9 (`Barreiro`, `Centro-Sul`, `Leste`, `Nordeste`, `Noroeste`, `Norte`,
    `Oeste`, `Pampulha`, `Venda Nova`) ou `Outros`.
- **Geração** (uma vez, fora do robô; `scripts/regionais_pbh.py`, fora do pacote): `pdftotext
  -layout` no PDF, regex `NOME  REGIONAL  TERRITÓRIO` → 487 bairros, cada um numa única regional;
  depois, casamento pelo `slug()` atual:
  1. 240 batem direto.
  2. ~22 por apelido explícito, numa tabela no próprio script: `aparecida-7a-secao` → Aparecida
     Sétima Seção; `nova-suica` → Nova Suissa; `incofindencia` → Inconfidência;
     `bandeirantes-pampulha` → Bandeirantes; `cabana` → Cabana do Pai Tomás; `maria-tereza` → Maria
     Teresa; `conjunto-*`, `chacara-*`, `jardim-*` e `vila-*` sem o prefixo, quando o resto bate;
     `sao-jorge` → São Jorge I/II/III; `tupi` → Tupi A/B (mesma regional);
     `novo-das-industrias` → Bairro Novo das Indústrias; `parque-sao-joao-batista` → São João
     Batista; `miramar-barreiro` → Miramar.
  3. Pelo sufixo de regional: `santa-cruz-barreiro` → Barreiro; `sao-pedro-venda-nova` → Venda
     Nova.
  4. **Saem do catálogo** (não são de BH): `chacara-belo-horizonte-taubate-sp-brasil`,
     `jardim-belo-horizonte-campinas-sp-brasil`, `jardim-belo-horizonte-indaiatuba-sp-brasil`,
     `vila-belo-horizonte-sao-paulo-sp-brasil`, `hawai-justinopolis`, `katia-justinopolis`.
  5. O restante (~19) → `Outros`.
- `bairros_validos()` continua devolvendo `frozenset[str]` de slugs (Zap, OLX e validação), e
  `catalogo_bairros()` devolve a lista de `Bairro(slug, nome, regional)` para o teclado e para os
  nomes exibidos.
- Um teste garante que todo slug do catálogo tem regional (ou `Outros`), que não há slug `*-sp-*`
  nem `*-justinopolis` e que os 21 bairros do `filtros.yaml` de hoje estão numa das 9 regionais.
- **Rationale**: o PDF dá a regional sem cruzar polígonos; manter o slug do QuintoAndar evita
  migrar filtros e quebrar a coleta.

## R10. Mensagem de imóvel
- **Decision** (contrato em [contracts/telegram.md](contracts/telegram.md)):
  ```
  Veja o imóvel que encontrei:
  {quartos} quartos no bairro {nome do bairro}
  Valor: R$ {aluguel}
  Link: {url}
  👤 {nome}     ← só com contato em trânsito
  📞 {telefone} ← idem
  ```
  Botões: linha 1 `[Abrir anúncio]` (URL) `[WhatsApp]` (URL, só com número válido); linha 2
  `[⭐ Salvar como favorito]` (callback `f:{fonte}:{id_externo}`). "1 quarto" no singular; com 0
  quartos (kitnet sem informação), "Kitnet/Studio no bairro {nome}".
- `Mensagem.botoes` passa de `[[rótulo, url]]` para linhas de botões
  `[[{"t": rótulo, "u": url} | {"t": rótulo, "c": callback}]]`. A fila de entrega é esvaziada na
  migração (R3 reconstrói o que for de imóvel), então não há mensagem antiga no formato velho.
- **Rationale**: formato pedido pelo dono, com o "Abrir anúncio" mantido; o nome do bairro vem do
  catálogo (R9), não do texto livre do portal.

## R11. Favoritos
- **Decision**: tabela `favorito(chat_id, fonte, id_externo, salvo_em)`, PK nas três primeiras
  colunas. Alternância: `INSERT IGNORE`; se 0 linhas, `DELETE`. Devolve o novo estado, e o bot
  responde com `answer("⭐ Salvo nos favoritos")` / `answer("Removido dos favoritos")` e troca só o
  botão de favorito no teclado da própria mensagem (lido de `query.message.reply_markup`).
  `callback_data` `f:quintoandar:` + 40 caracteres = 55 bytes, dentro do limite.
- Toques simultâneos: a PK garante no máximo uma linha; o estado final segue a ordem em que o MySQL
  aplicou os comandos (FR-012).
- `/favoritos`: `JOIN anuncio`, do mais recente para o mais antigo, uma linha por imóvel
  `⭐ {q} quartos · {bairro} · R$ {valor} · {Portal}\n{url}`, dividido em blocos de até 4.000
  caracteres sem cortar item. Sem limite de quantidade; com 5 pessoas, não há volume.

## R12. Resumo diário
- **Decision**: o job da rodada das 23h, depois de `Rodada.executar()` (com ok ou falha), chama
  `enviar_resumos()`:
  - uma chamada a `gecko.creditos()` para todos (sem custo; erro → "saldo indisponível"; sem
    GeckoAPI configurada → linha omitida);
  - para cada pessoa ativa: `INSERT IGNORE INTO resumo_diario (chat_id, dia)`, com o `dia` em
    America/Sao_Paulo; só envia se a linha foi inserida (FR-017);
  - contagem por portal: `SELECT fonte, COUNT(*) FROM envio WHERE chat_id = ? AND status =
    'entregue' AND entregue_em >= agora - 24 h GROUP BY fonte`;
  - a mensagem vai direto para `apebot:envios` (fora da janela, FR-010).
- `/status` passa a mostrar a linha de créditos para todos (FR-031), com a mesma regra.
- Se o robô estiver fora do ar às 23h e voltar depois de passado o `misfire_grace_time` (300 s) da
  rodada, não há resumo naquele dia. Aceito: o resumo é informativo.
- **Alternatives**: job separado às 23:05 (pode sair antes da rodada terminar, com "Última rodada"
  errada).

## R13. Menu, ajuda e respostas
- Menu: `/ajuda`, `/filtros`, `/favoritos`, `/status`, `/pausar`, `/retomar`.
- Com o cadastro incompleto: `/filtros`, `/favoritos`, `/pausar`, `/retomar` e `/status` respondem
  "Termine o cadastro primeiro: /start"; `/ajuda` responde normalmente; texto livre alimenta a etapa
  atual.
- A resposta padrão ("Eu aviso os imóveis às 06, 09…") passa a falar da entrega durante o dia (8h às
  22h).
