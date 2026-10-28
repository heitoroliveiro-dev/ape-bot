# Feature Specification: Entrega espaçada, favoritos, resumo diário e filtros pelo Telegram

**Feature Branch**: `003-entrega-espacada-cadastro-telegram`

**Created**: 2026-10-28

**Status**: Draft

**Input**: User description: "Entrega espaçada, favoritos, resumo diário e cadastro/edição de filtros pelo Telegram. A 002 está implementada (QuintoAndar + Zap via GeckoAPI, OLX desligada; comandos /ajuda /filtros /status /pausar /retomar; filtros por pessoa no filtros.yaml; ao mudar filtros o robô manda uma lista-resumo com todos os imóveis, ex.: 64 do QuintoAndar de uma vez). (1) Depois de persistir a resposta das fontes e formar a fila, enviar cada imóvel numa mensagem própria, com intervalo aleatório de 2 a 5 minutos, no formato 'Veja o imóvel que encontrei: / X quartos no bairro Y / Valor: R$ x.xxx,xx / Link: ...' e botão 'Salvar como favorito'; a lista-resumo deixa de existir; envio só entre 8h e 22h, o que não couber fica para o dia seguinte, mais baratos primeiro. (2) Favoritos com /favoritos. (3) Resumo às 23h com última e próxima rodada, recebidos em 24 h por portal e créditos (para todas as pessoas). (4) Cadastro pelo /start com acesso em lista fechada: nome, tipos, quartos, bairros por regional e valor máximo, terminando em 'Perfeito, [nome]! ...'. (5) /filtros mostra os filtros e o botão 'Editar filtros', que refaz as perguntas; vale a partir da próxima rodada; sai 'fale com Heitor'. (6) Valor máximo normalizado para centavos, rejeitando letras, símbolos, zero, negativos e valores fora de faixa; exibido como 'R$ x.xxx,xx'."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receber os imóveis um a um, espaçados, durante o dia (Priority: P1)

Hoje, quando a pessoa entra ou muda de filtros, o robô despeja numa mensagem só uma lista com
dezenas de imóveis (64 do QuintoAndar numa rodada), e ela não consegue avaliar nenhum com calma.
Agora o robô guarda tudo o que encontrou e entrega um imóvel por vez, com 2 a 5 minutos (variados)
entre um e outro, só entre 8h e 22h. Cada mensagem diz quantos quartos, o bairro, o valor e o link,
e tem um botão para salvar como favorito. O que não couber no dia segue no dia seguinte, começando
pelos mais baratos.

**Why this priority**: é a dor que motivou a feature: a lista em bloco é ignorada, e a fonte paga
só aumenta o volume. Sem isso, os outros itens não mudam a experiência.

**Independent Test**: com uma pessoa ativa e 10 imóveis novos que atendem aos filtros dela, rodar e
verificar que chegam 10 mensagens individuais no formato combinado, cada uma de 2 a 5 minutos depois
da anterior, nenhuma fora das 8h–22h, em ordem crescente de valor.

**Acceptance Scenarios**:

1. **Given** uma pessoa ativa e 3 imóveis novos que atendem aos filtros dela, **When** a rodada
   termina dentro da janela de envio, **Then** ela recebe 3 mensagens separadas, a primeira em até
   5 minutos e as seguintes com intervalo de 2 a 5 minutos, nunca o mesmo intervalo fixo em todas.
2. **Given** um imóvel de 2 quartos no Prado com aluguel de R$ 2.450, **When** ele é entregue,
   **Then** a mensagem diz "Veja o imóvel que encontrei:", "2 quartos no bairro Prado",
   "Valor: R$ 2.450,00" e "Link:" com o endereço do anúncio, e tem os botões "Abrir anúncio" e
   "Salvar como favorito".
3. **Given** uma pessoa que acabou de se cadastrar ou de mudar os filtros e 64 imóveis disponíveis,
   **When** a próxima rodada roda, **Then** nenhuma lista em bloco é enviada: os 64 entram na fila
   dela e saem um a um.
4. **Given** imóveis na fila às 21h50, **When** dá 22h, **Then** o envio para e o restante sai a
   partir das 8h do dia seguinte, começando pelo de menor valor.
5. **Given** imóveis encontrados na rodada das 6h, **When** a rodada termina, **Then** nada é
   enviado antes das 8h.
6. **Given** imóveis na fila de uma pessoa, **When** o robô reinicia, **Then** nenhum imóvel se
   perde nem é entregue duas vezes, e o espaçamento de 2 a 5 minutos continua valendo.
7. **Given** um imóvel na fila de uma pessoa que, antes da entrega, mudou os filtros e ele deixou
   de atender, **When** chegaria a vez dele, **Then** ele não é enviado.
8. **Given** um imóvel cujo anunciante tem WhatsApp informado pela fonte, **When** ele é entregue
   antes de o robô reiniciar, **Then** a mensagem também mostra o contato e o botão "WhatsApp".

---

### User Story 2 - Ver e editar os próprios filtros pelo /filtros (Priority: P1)

A pessoa quer mudar o valor máximo ou incluir um bairro e hoje precisa pedir ao operador. Agora o
`/filtros` mostra os filtros dela de forma legível, com um botão "Editar filtros" que refaz as
perguntas do cadastro já com as respostas atuais marcadas. Ao salvar, os novos filtros valem a
partir da próxima rodada.

**Why this priority**: tira o operador do caminho em toda mudança de busca, que é a interação mais
frequente depois de receber imóveis.

**Independent Test**: de um chat autorizado já cadastrado, enviar `/filtros`, tocar em "Editar
filtros", trocar o valor máximo e um bairro, salvar e verificar que a próxima rodada usa os filtros
novos e que `/filtros` mostra os valores novos.

**Acceptance Scenarios**:

1. **Given** uma pessoa cadastrada, **When** envia `/filtros`, **Then** recebe "Seus filtros -",
   a linha "Bairros:" com os bairros em ordem alfabética, "Valores até R$ X.XXX,XX", os tipos com
   "com X quartos", o estado dos avisos (ativos ou pausados) e o botão "Editar filtros"; a frase
   "Para mudar os filtros, fale com ..." não aparece mais.
2. **Given** uma pessoa que tocou em "Editar filtros", **When** percorre as perguntas, **Then** cada
   pergunta já vem com a resposta atual marcada, e ela pode manter tudo e mudar só o que quiser.
3. **Given** uma pessoa editando, **When** confirma no fim, **Then** recebe a confirmação com os
   filtros novos, e a rodada seguinte já busca e filtra por eles.
4. **Given** uma pessoa editando, **When** toca em "Cancelar" em qualquer etapa, **Then** os filtros
   anteriores continuam valendo, sem mudança.
5. **Given** uma pessoa que salvou filtros novos, **When** a próxima rodada roda, **Then** os
   imóveis disponíveis que atendem aos filtros novos e ainda não foram enviados a ela entram na
   fila e saem um a um (US1), e os que estavam na fila e não atendem mais são descartados.

---

### User Story 3 - Cadastro guiado pelo /start (Priority: P2)

O operador autoriza o chat de uma pessoa nova e não precisa mais escrever os filtros dela. Ao dar
`/start`, a pessoa é guiada por perguntas de escopo fechado: como deve ser chamada, quais tipos de
imóvel busca, quantos quartos no mínimo, quais bairros (escolhidos por regional) e qual o valor
máximo. No fim, o robô dá as boas-vindas e passa a procurar para ela.

**Why this priority**: as pessoas atuais já são migradas com os filtros que têm; o cadastro guiado
é o que permite incluir alguém novo sem o operador montar o filtro à mão.

**Independent Test**: autorizar um chat sem filtros, enviar `/start`, responder as perguntas e
verificar a mensagem final, os filtros gravados e a inclusão da pessoa na rodada seguinte.

**Acceptance Scenarios**:

1. **Given** um chat autorizado sem cadastro, **When** envia `/start`, **Then** o robô pergunta
   "Como devo te chamar?".
2. **Given** a pergunta do nome, **When** a pessoa responde "  maria   clara ", **Then** o nome é
   guardado como "Maria Clara" e o robô pergunta "Você busca quais tipos de imóveis?" com botões
   de múltipla escolha (Apartamento, Casa, Casa em condomínio, Kitnet/Studio) e um botão para
   continuar, que só funciona com pelo menos um tipo marcado.
3. **Given** os tipos escolhidos, **When** ela continua, **Then** o robô pergunta os quartos mínimos
   com botões (Tanto faz, 1, 2, 3, 4 ou mais).
4. **Given** os quartos escolhidos, **When** ela continua, **Then** o robô mostra as 9 regionais de
   BH como botões; ao tocar numa, vê os bairros dela para marcar e desmarcar, com a opção de marcar
   todos da regional, e pode voltar às regionais e seguir só com pelo menos um bairro marcado.
5. **Given** os bairros escolhidos, **When** ela continua, **Then** o robô pergunta "Qual valor
   máximo?" e aceita a resposta conforme as regras de valor (FR-020).
6. **Given** todas as respostas válidas, **When** o cadastro termina, **Then** o robô envia
   "Perfeito, [nome]! Vou te ajudar a encontrar um imóvel com sua cara para alugar! Durante o dia
   vou te enviar o que achar por aqui, fique atento(a)." e a pessoa entra na rodada seguinte.
7. **Given** uma pessoa que parou no meio do cadastro, **When** volta e envia `/start` ou qualquer
   mensagem, **Then** o robô retoma da pergunta em que ela parou, com as respostas anteriores
   preservadas.
8. **Given** uma pessoa que já tinha filtros no arquivo de configuração antes desta feature,
   **When** o robô sobe, **Then** ela já está cadastrada com esses filtros e não precisa refazer o
   cadastro; um novo `/start` mostra os filtros dela com o botão "Editar filtros".
9. **Given** um chat não autorizado, **When** envia `/start`, **Then** o robô não responde.

---

### User Story 4 - Resumo do dia às 23h (Priority: P2)

No fim do dia, a pessoa quer saber se o robô está funcionando e quanto ele achou, sem precisar
pedir. Depois da última rodada, às 23h, cada pessoa ativa recebe um resumo com a última e a próxima
rodada, quantos imóveis recebeu nas últimas 24 horas no total e por portal, e os créditos do serviço
pago.

**Why this priority**: com a entrega espaçada, a pessoa perde a noção do volume; o resumo devolve
essa visão, mas o produto funciona sem ele.

**Independent Test**: com uma pessoa ativa que recebeu 5 imóveis do QuintoAndar e 2 do Zap no dia,
deixar passar a rodada das 23h e verificar o texto do resumo.

**Acceptance Scenarios**:

1. **Given** uma pessoa ativa que recebeu 5 imóveis do QuintoAndar, 2 do Zap e nenhum da OLX nas
   últimas 24 horas, **When** a rodada das 23h termina, **Then** ela recebe
   "📊 Última rodada: DD/MM 23:00 · próxima: 06:00", "Você recebeu 7 imóveis nas últimas 24 h.",
   "QuintoAndar: 5", "Zap: 2", "OLX: 0" e "💳 Créditos: XX (gastos em 24 h: Y)".
2. **Given** que o saldo de créditos não pode ser consultado, **When** o resumo é montado, **Then**
   a linha diz que o saldo está indisponível e o resto do resumo sai normalmente.
3. **Given** uma pessoa pausada ou com cadastro incompleto, **When** dá 23h, **Then** ela não recebe
   o resumo.
4. **Given** uma pessoa que não recebeu nenhum imóvel no dia, **When** dá 23h, **Then** ela recebe
   o resumo com "Você recebeu 0 imóveis nas últimas 24 h.".

---

### User Story 5 - Salvar imóveis como favoritos (Priority: P3)

Entre dezenas de imóveis recebidos no dia, a pessoa quer separar os que pretende visitar. Ela toca
em "Salvar como favorito" na mensagem do imóvel e depois consulta a lista com `/favoritos`.

**Why this priority**: ajuda a organizar, mas a pessoa já consegue achar os imóveis rolando a
conversa.

**Independent Test**: salvar 2 imóveis, remover 1 e verificar que `/favoritos` lista só o outro,
com o link.

**Acceptance Scenarios**:

1. **Given** uma mensagem de imóvel, **When** a pessoa toca em "Salvar como favorito", **Then** o
   imóvel vira favorito dela, ela vê uma confirmação curta e o botão passa a indicar que é favorito
   e que tocar de novo remove.
2. **Given** um imóvel favorito, **When** ela toca no botão de novo, **Then** ele deixa de ser
   favorito e o botão volta a "Salvar como favorito".
3. **Given** favoritos salvos, **When** ela envia `/favoritos`, **Then** recebe a lista do mais
   recente para o mais antigo, cada um com quartos, bairro, valor, portal e link.
4. **Given** nenhum favorito, **When** ela envia `/favoritos`, **Then** recebe uma mensagem dizendo
   que ainda não há favoritos e como salvar um.
5. **Given** que a pessoa tocou duas vezes seguidas e rápido no botão, **When** os toques são
   processados, **Then** o estado final é consistente com o número de toques e não há favorito
   duplicado.

### Edge Cases

- **Volume acima da capacidade do dia**: a janela de 14 horas comporta por volta de 240 mensagens
  por pessoa; o excedente continua na fila nos dias seguintes. Como a fila é sempre ordenada do
  mais barato para o mais caro, um imóvel caro pode esperar mais de um dia; antes de enviar, o robô
  confere de novo se ele ainda atende aos filtros da pessoa.
- **Pessoa pausa com imóveis na fila**: nada é enviado enquanto estiver pausada; os imóveis que não
  saíram voltam a ser candidatos e entram na fila de novo na primeira rodada depois do `/retomar`.
- **Rodada nova com a fila ainda cheia**: os imóveis novos entram na mesma fila e ela é reordenada
  por valor; não existem duas filas paralelas para a mesma pessoa, e o intervalo de 2 a 5 minutos
  vale entre quaisquer duas mensagens de imóvel dela.
- **Mesmo imóvel em duas rodadas antes de ser entregue**: entra uma única vez na fila.
- **Telegram limita o envio ou falha**: a mensagem volta para a fila sem perder a vez e sem quebrar
  o espaçamento das demais pessoas.
- **Pessoa bloqueia o robô**: os envios para ela falham e ela deixa de receber resumo, sem afetar os
  outros.
- **Contato do anunciante após reinício**: imóvel que volta para a fila a partir dos dados guardados
  sai sem nome, telefone e botão de WhatsApp, só com o link.
- **Nome inválido**: vazio, só espaços, só símbolos ou emojis, ou com mais de 40 caracteres depois
  de limpo: o robô explica a regra e pergunta de novo.
- **Texto digitado quando a etapa espera botão** (tipos, quartos, bairros): o robô lembra de usar os
  botões e repete a pergunta.
- **Botão de uma pergunta antiga**: tocar num botão de uma etapa já concluída ou de um cadastro já
  terminado não altera nada; o robô responde que aquela pergunta já passou.
- **Comandos no meio do cadastro**: `/ajuda` responde normalmente; `/filtros`, `/favoritos`,
  `/pausar` e `/status` pedem para terminar o cadastro primeiro; `/start` retoma de onde parou.
- **Edição iniciada e abandonada**: os filtros antigos continuam valendo; um novo "Editar filtros"
  começa do zero a partir dos filtros salvos.
- **Bairro do arquivo de configuração que não existe no catálogo**: na migração, é ignorado e o
  operador é avisado, como já acontece hoje.
- **Imóvel favorito que saiu do portal**: continua na lista com o link original; o robô não verifica
  se o anúncio ainda existe.
- **Chat autorizado removido da configuração**: deixa de receber mensagens e resumo; os dados dele
  ficam guardados caso volte a ser autorizado.
- **Lista de favoritos longa**: é dividida em mais de uma mensagem, sem cortar um item no meio.

## Requirements *(mandatory)*

### Functional Requirements

**Entrega espaçada**

- **FR-001**: Depois de guardar o resultado das fontes e decidir o que cada pessoa deve receber, o
  sistema MUST colocar cada imóvel numa fila própria daquela pessoa, sem duplicar imóveis que já
  estão na fila ou que já foram entregues a ela.
- **FR-002**: O sistema MUST entregar no máximo uma mensagem de imóvel por vez para cada pessoa,
  com intervalo sorteado entre 2 e 5 minutos entre duas mensagens de imóvel consecutivas da mesma
  pessoa; pessoas diferentes recebem de forma independente.
- **FR-003**: Mensagens de imóvel MUST ser entregues só entre 8h e 22h (America/Sao_Paulo); fora
  dessa janela elas aguardam na fila.
- **FR-004**: A fila de cada pessoa MUST ser entregue em ordem crescente de valor do aluguel; a
  cada rodada, os imóveis novos entram na ordem junto com os que já aguardavam.
- **FR-005**: A fila e a posição de cada pessoa MUST sobreviver a reinícios do robô, sem perder nem
  repetir imóveis e sem disparar várias mensagens de uma vez na volta.
- **FR-006**: Antes de entregar um imóvel, o sistema MUST conferir que a pessoa continua ativa e que
  o imóvel ainda atende aos filtros atuais dela; se não atender, o imóvel sai da fila sem ser
  enviado nem contado como entregue.
- **FR-007**: A mensagem-resumo em lista (primeira rodada, mudança de filtros ou retomada) MUST
  deixar de existir: nesses casos, todos os imóveis disponíveis seguem a entrega espaçada.
- **FR-008**: A mensagem de imóvel MUST ter, nesta ordem: "Veja o imóvel que encontrei:",
  "X quartos no bairro Y", "Valor: R$ x.xxx,xx" (aluguel) e "Link: " com o endereço público do
  anúncio, e os botões "Abrir anúncio" (com o mesmo endereço) e "Salvar como favorito".
- **FR-009**: Quando a fonte tiver devolvido o contato do anunciante e ele ainda estiver em
  trânsito, a mensagem MUST mostrar também nome e telefone e o botão "WhatsApp" quando houver número
  válido; o contato continua sem ser gravado de forma permanente (constituição, princípio III).
- **FR-010**: Mensagens que não são de imóvel (resumo diário, respostas a comandos, avisos ao
  operador, perguntas do cadastro) MUST NOT esperar o intervalo de 2 a 5 minutos nem a janela das
  8h–22h.

**Favoritos**

- **FR-011**: O botão "Salvar como favorito" MUST marcar o imóvel como favorito da pessoa e, tocado
  de novo, desmarcar; o rótulo do botão MUST refletir o estado atual.
- **FR-012**: Um imóvel MUST aparecer no máximo uma vez nos favoritos de uma pessoa, mesmo com
  toques repetidos ou simultâneos.
- **FR-013**: `/favoritos` MUST listar os favoritos da pessoa, do mais recente para o mais antigo,
  com quartos, bairro, valor, portal e link, dividindo em várias mensagens quando necessário.
- **FR-014**: Os favoritos MUST guardar só a referência ao imóvel e a data em que foi salvo, nunca
  dados do anunciante.

**Resumo diário**

- **FR-015**: Depois da rodada das 23h, o sistema MUST enviar a cada pessoa ativa (cadastro completo
  e avisos não pausados) o resumo: "📊 Última rodada: DD/MM HH:MM · próxima: HH:MM", "Você recebeu
  X imóveis nas últimas 24 h.", uma linha por portal (QuintoAndar, Zap e OLX) com a quantidade
  entregue a ela nas últimas 24 horas e "💳 Créditos: XX (gastos em 24 h: Y)".
- **FR-016**: A linha de créditos MUST aparecer para todas as pessoas que recebem o resumo; se o
  saldo não puder ser consultado, MUST dizer que está indisponível; se nenhuma fonte paga estiver
  configurada, a linha MUST ser omitida.
- **FR-017**: O resumo diário MUST ser enviado uma única vez por pessoa por dia, mesmo que o robô
  reinicie perto das 23h.

**Cadastro e edição de filtros**

- **FR-018**: O acesso MUST continuar restrito aos chats autorizados pelo operador na configuração;
  chats não autorizados continuam ignorados em todos os comandos, botões e mensagens.
- **FR-019**: Um chat autorizado sem cadastro MUST ser guiado, ao enviar `/start`, pelas perguntas
  nesta ordem: nome, tipos de imóvel, quartos mínimos, bairros e valor máximo.
- **FR-020**: O valor máximo digitado MUST ser convertido para centavos inteiros seguindo estas
  regras:
  - aceita dígitos, opcionalmente precedidos de "R$", com espaços nas pontas ou entre "R$" e o
    número;
  - o ponto só é aceito como separador de milhar, em grupos de exatamente 3 dígitos ("3.000",
    "12.500");
  - a vírgula é o separador de centavos, com 1 ou 2 dígitos depois dela ("3000,5" = R$ 3.000,50);
  - qualquer outra letra, símbolo, sinal de menos, número com ponto decimal ("3000.50") ou espaço no
    meio do número é recusado;
  - o valor MUST ficar entre R$ 300,00 e R$ 50.000,00.

  Em caso de recusa, o robô MUST explicar o formato esperado, dar um exemplo e perguntar de novo,
  sem perder as respostas anteriores.
- **FR-021**: O nome MUST ser limpo (espaços nas pontas removidos, espaços repetidos reduzidos,
  caracteres de controle e marcação removidos, iniciais maiúsculas) e ter de 1 a 40 caracteres com
  pelo menos uma letra; caso contrário, o robô pergunta de novo.
- **FR-022**: Tipos, quartos e bairros MUST ser escolhidos só por botões, a partir das opções
  fechadas: tipos Apartamento, Casa, Casa em condomínio e Kitnet/Studio (pelo menos um); quartos
  Tanto faz, 1, 2, 3 e 4 ou mais; bairros do catálogo de BH agrupados pelas 9 regionais (Barreiro,
  Centro-Sul, Leste, Nordeste, Noroeste, Norte, Oeste, Pampulha e Venda Nova), com opção de marcar
  todos de uma regional e pelo menos um bairro no total.
- **FR-023**: O cadastro interrompido MUST ser retomado da etapa em que parou, com as respostas já
  dadas preservadas, inclusive depois de um reinício do robô.
- **FR-024**: Ao concluir o cadastro, o robô MUST enviar a mensagem de boas-vindas com o nome da
  pessoa e incluí-la a partir da rodada seguinte.
- **FR-025**: `/filtros` MUST mostrar "Seus filtros -", "Bairros:" (em ordem alfabética, com os nomes
  legíveis), "Valores até R$ X.XXX,XX", os tipos com "com X quartos", o estado dos avisos e o botão
  "Editar filtros".
- **FR-026**: "Editar filtros" MUST percorrer as mesmas perguntas do cadastro, a partir do tipo de
  imóvel, com as respostas atuais pré-marcadas (o nome continua o mesmo), e oferecer "Cancelar" em
  todas as etapas; os filtros só mudam quando a pessoa confirma no fim.
- **FR-027**: Filtros salvos MUST valer a partir da rodada seguinte, inclusive na busca somada das
  fontes pagas; uma rodada em andamento continua com os filtros antigos.
- **FR-028**: Os filtros e o nome de cada pessoa MUST passar a ser guardados pelo robô; o arquivo de
  configuração continua definindo quem é autorizado e o operador, e os filtros que ele tiver
  servem só para cadastrar, uma única vez, quem ainda não tem cadastro.
- **FR-029**: Valores em dinheiro MUST ser exibidos em todas as mensagens no formato "R$ x.xxx,xx".

**Menu e comandos**

- **FR-030**: O menu do bot MUST incluir `/favoritos` junto dos comandos atuais, e `/ajuda` MUST
  explicar a entrega espaçada (8h–22h), o resumo das 23h, os favoritos e a edição de filtros.
- **FR-031**: `/status` MUST mostrar a linha de créditos para qualquer pessoa autorizada, com as
  mesmas regras do resumo diário.

### Key Entities

- **Pessoa**: chat autorizado; agora com nome escolhido por ela, filtros próprios guardados pelo
  robô, estado do cadastro (incompleto ou completo) e estado dos avisos (ativos ou pausados).
- **Filtro**: bairros, valor máximo em centavos, quartos mínimos e tipos de uma pessoa; tem uma data
  de atualização para valer a partir da rodada seguinte.
- **Conversa em andamento**: etapa atual do cadastro ou da edição de uma pessoa e as respostas
  parciais; descartada ao concluir ou cancelar.
- **Envio agendado**: imóvel aguardando entrega a uma pessoa, com o valor usado na ordenação, o
  estado (aguardando, entregue, descartado, falhou) e o horário em que foi entregue.
- **Favorito**: ligação entre uma pessoa e um imóvel, com a data em que foi salvo.
- **Regional**: uma das 9 regionais de BH, que agrupa os bairros do catálogo para a escolha por
  botões.
- **Resumo diário**: registro de que o resumo do dia já foi enviado a uma pessoa.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 3 dias de operação, nenhuma pessoa recebe mais de uma mensagem de imóvel num
  intervalo menor que 2 minutos, e nenhuma mensagem de imóvel chega antes das 8h ou depois das 22h.
- **SC-002**: Numa rodada com 64 imóveis novos para uma pessoa, ela recebe 64 mensagens
  individuais e nenhuma lista em bloco; todos são entregues em até 2 dias de janela.
- **SC-003**: Uma pessoa autorizada completa o cadastro pelo `/start` em menos de 3 minutos, sem
  ajuda do operador.
- **SC-004**: Uma pessoa cadastrada muda o valor máximo pelo `/filtros` em menos de 1 minuto, e a
  rodada seguinte já reflete a mudança.
- **SC-005**: Nos 7 dias seguintes à entrega, o operador não recebe nenhum pedido para mudar filtros.
- **SC-006**: Todos os valores de teste aceitos ("3000", "3.000", "3.000,00", "R$ 3.000",
  "3000,50") são gravados com o valor certo em centavos, e todos os recusados ("3k", "três mil",
  "-3000", "0", "3000.50", "3 000", "100", "999999") pedem o valor de novo sem gravar nada.
- **SC-007**: Todas as pessoas ativas recebem exatamente um resumo por dia, depois da rodada das
  23h, com as contagens por portal batendo com as mensagens de imóvel que ela recebeu.
- **SC-008**: Depois de reiniciar o robô com imóveis na fila, nenhum imóvel é entregue duas vezes e
  nenhum some sem ter sido entregue ou descartado por filtro.
- **SC-009**: Uma busca nos dados guardados por nomes e telefones de anunciantes vistos nas
  mensagens não encontra nenhum resultado, inclusive nos favoritos.

## Assumptions

- O "Valor" da mensagem e do filtro é o aluguel, como já é hoje no filtro; o custo total deixa de
  aparecer na mensagem de imóvel para seguir o formato pedido.
- O link vai no texto da mensagem, como pedido, e o botão "Abrir anúncio" da 002 continua (decisão
  do dono); a prévia do link continua desligada para a mensagem não ficar grande.
- O contato do anunciante (nome, telefone, WhatsApp) continua aparecendo quando a fonte devolve,
  abaixo do link, para não perder o que a 002 entregou; com a entrega espaçada, ele pode ficar em
  trânsito por mais tempo (até a entrega), o que a constituição permite enquanto não for gravado.
- O resumo diário sai depois que a rodada das 23h termina, por isso "Última rodada" mostra 23:00 e
  "próxima" mostra 06:00; ele é a única mensagem programada fora da janela das 8h–22h.
- A decisão de mostrar créditos a todas as pessoas é do dono do robô; a consulta de saldo não gasta
  créditos. Por coerência, o `/status` passa a mostrar a mesma linha para todos.
- Os bairros de cada regional vêm de uma tabela fixa, versionada no projeto, que liga os 289
  bairros do catálogo atual às 9 regionais. Ela é gerada uma vez, fora do robô, a partir da
  "Relação de bairros, regionais e territórios de gestão compartilhada" da Prefeitura (487 bairros,
  cada um numa única regional); só os bairros do catálogo cujo nome não bate com o oficial são
  revisados à mão, e os que não são de BH saem do catálogo. Bairros que ainda não tiverem regional
  ficam num grupo "Outros". O robô não consulta a Prefeitura em funcionamento.
- O arquivo de configuração continua sendo a forma de o operador autorizar chats; incluir alguém
  continua exigindo editar o arquivo e reiniciar o robô. Autorizar pelo Telegram fica fora do
  escopo.
- O intervalo de 2 a 5 minutos vale para cada pessoa separadamente; o limite de taxa geral do
  Telegram continua valendo por cima disso.
- Pessoas que já estão no arquivo com filtros completos são cadastradas automaticamente com nome e
  filtros do arquivo; a partir daí, o que valer é o que estiver guardado pelo robô, e mudanças nos
  filtros do arquivo para quem já tem cadastro são ignoradas (o operador é avisado).
- Esta feature traz para o escopo itens que `docs/arquitetura.md` lista como "fica para depois"
  (configuração pelo Telegram, favoritos e regionais da PBH); o documento é atualizado junto com o
  plano, como pede a constituição. Alerta de queda de preço e deduplicação entre portais continuam
  fora.
- Fora do escopo: cadastro aberto ao público, aprovação de pessoas novas pelo Telegram, mudar o nome
  pelo `/filtros`, limite diário de imóveis por pessoa, verificar se o anúncio favorito ainda
  existe.
