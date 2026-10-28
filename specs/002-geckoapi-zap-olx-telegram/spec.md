# Feature Specification: Zap e OLX via serviço pago e interação melhor no Telegram

**Feature Branch**: `002-geckoapi-zap-olx-telegram`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Fontes Zap e OLX via GeckoAPI e interação melhor no Telegram. O MVP 001 (QuintoAndar → banco → filtro por pessoa → fila → Telegram) está implementado; a constituição 2.2.0 permite a GeckoAPI para Zap e OLX (VivaReal excluído). Zap: 1 consulta por rodada, cidade inteira (Belo Horizonte/MG, aluguel), com os filtros somados das pessoas; 1 página (30 itens); a API não ordena por data nem informa data de publicação, então 'novo' é a primeira vez que o robô vê o anúncio. OLX: pronta, mas desligada até a API respeitar a localização. Filtro local de cidade/UF obrigatório, aceitando variações de escrita; itens de fora são descartados e contados. Cada anúncio guarda o link e a mensagem informa a origem. Contato do anunciante (nome, telefone, WhatsApp) aparece na mensagem quando a API devolver, só em trânsito, nunca gravado. Resposta bruta de cada consulta paga guardada sem dados de anunciante. Cada fonte paga ligada/desligada por configuração e chave; falha de uma fonte não derruba as outras. Telegram: botões 'Abrir anúncio' e 'WhatsApp'; comandos /filtros, /ajuda, /pausar, /retomar e /status; a mensagem padrão sugere /ajuda. Orçamento: 1.000 créditos por R$ 49,90; Zap = 7 créditos/dia."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receber imóveis do Zap com acesso direto ao anúncio e ao anunciante (Priority: P1)

A pessoa que procura imóvel já recebe os imóveis do QuintoAndar. Agora, nos mesmos horários, ela
também recebe os imóveis novos do Zap que atendem aos filtros dela. Cada mensagem diz de qual portal
o imóvel veio e traz um botão para abrir o anúncio. Quando o portal informa, a mensagem também traz
o nome do anunciante, o telefone e um botão para chamar no WhatsApp, para que ela vá direto ao
contato sem procurar no portal.

**Why this priority**: o Zap tem a maior oferta de aluguel em BH (cerca de 22 mil imóveis), e
avisar que um imóvel existe só ajuda se a pessoa conseguir chegar ao anúncio e ao anunciante.

**Independent Test**: com uma pessoa registrada e a fonte Zap ligada, disparar uma rodada contra uma
resposta conhecida do Zap e verificar que só os imóveis de BH que atendem aos filtros chegam, com
origem, botão do anúncio e, quando existir, contato e botão de WhatsApp.

**Acceptance Scenarios**:

1. **Given** uma pessoa registrada, já depois da primeira rodada, e a fonte Zap ligada, **When** a
   rodada recebe do Zap 2 imóveis novos que atendem aos filtros dela, **Then** ela recebe 2
   mensagens, cada uma identificada como "Zap", com tipo, bairro, quartos, área, aluguel, custo
   total e o botão "Abrir anúncio".
2. **Given** um imóvel do Zap cujo anunciante tem nome, telefone e WhatsApp, **When** ele é enviado,
   **Then** a mensagem mostra o nome e o telefone e tem um botão "WhatsApp" que abre a conversa com
   o número do anunciante.
3. **Given** um imóvel sem WhatsApp informado, **When** ele é enviado, **Then** a mensagem não tem o
   botão "WhatsApp" e o restante sai normalmente.
4. **Given** um imóvel do Zap já enviado a essa pessoa, **When** ele aparece de novo numa rodada
   seguinte, **Then** ele não é reenviado.
5. **Given** um imóvel do QuintoAndar, **When** ele é enviado, **Then** a mensagem é identificada
   como "QuintoAndar" e também tem o botão "Abrir anúncio".

---

### User Story 2 - Descobrir o que o robô faz e ver os próprios filtros (Priority: P1)

A pessoa não sabe de cor o que o robô aceita. Ela abre o menu de comandos do Telegram ou digita
qualquer coisa e é orientada a usar `/ajuda`, que explica os comandos e os horários das rodadas.
Com `/filtros`, ela vê os bairros, o aluguel máximo, os quartos mínimos e os tipos que o operador
configurou para ela. Com `/status`, ela vê quando foi a última rodada, quando será a próxima e se
algum portal está com problema.

**Why this priority**: sem isso, a pessoa depende do operador para entender por que recebeu, ou
deixou de receber, um imóvel.

**Independent Test**: de um chat autorizado, enviar `/ajuda`, `/filtros`, `/status` e um texto
qualquer, e verificar cada resposta; de um chat não autorizado, verificar o silêncio.

**Acceptance Scenarios**:

1. **Given** uma pessoa autorizada, **When** ela abre o menu de comandos do bot, **Then** vê
   `/ajuda`, `/filtros`, `/status`, `/pausar` e `/retomar`, cada um com uma descrição curta.
2. **Given** uma pessoa autorizada, **When** envia `/ajuda`, **Then** recebe a lista de comandos,
   os horários das rodadas e os portais consultados.
3. **Given** uma pessoa autorizada, **When** envia `/filtros`, **Then** recebe os filtros dela no
   mesmo formato da confirmação do `/start`, e se os avisos estão ativos ou pausados.
4. **Given** uma pessoa autorizada, **When** envia `/status`, **Then** recebe a data e a hora da
   última rodada, a próxima rodada, quantos imóveis ela recebeu nas últimas 24 horas e, para cada
   portal, se está funcionando, desligado ou com falha.
5. **Given** uma pessoa autorizada, **When** envia um texto que não é comando, **Then** recebe uma
   resposta curta sugerindo `/ajuda`.
6. **Given** um chat não autorizado, **When** envia qualquer comando, **Then** o bot não responde.

---

### User Story 3 - Pausar e retomar os avisos (Priority: P2)

A pessoa já está visitando imóveis, ou viajou, e não quer receber avisos por um tempo. Ela envia
`/pausar` e o robô para de mandar imóveis para ela, sem que o operador precise mexer na
configuração. Quando quer voltar, envia `/retomar`.

**Why this priority**: evita que a pessoa bloqueie o bot ou peça ao operador para removê-la, mas o
produto funciona sem isso.

**Independent Test**: pausar uma pessoa, rodar com imóveis que atendem aos filtros dela, verificar
que nada chega; retomar, rodar de novo e verificar que ela volta a receber.

**Acceptance Scenarios**:

1. **Given** uma pessoa com avisos ativos, **When** envia `/pausar`, **Then** recebe a confirmação
   e nenhuma mensagem de imóvel enquanto estiver pausada.
2. **Given** uma pessoa pausada, **When** envia `/retomar`, **Then** recebe a confirmação, e a
   próxima rodada envia um resumo com os imóveis disponíveis que atendem aos filtros e ainda não
   foram enviados a ela.
3. **Given** uma pessoa pausada, **When** o robô reinicia, **Then** ela continua pausada.
4. **Given** uma pessoa já pausada, **When** envia `/pausar` de novo, **Then** recebe a mesma
   confirmação, sem erro.

---

### User Story 4 - Operador controla as fontes pagas e o gasto (Priority: P2)

O operador paga por consulta ao Zap e à OLX. Ele quer ligar e desligar cada portal pela
configuração, ter certeza de que o robô faz no máximo uma consulta por portal por rodada, saber
quando uma fonte paga falha repetidamente ou fica sem créditos, e conferir depois o que cada
consulta devolveu. A OLX fica pronta, mas desligada, até o serviço pago respeitar a localização.

**Why this priority**: sem controle, o crédito acaba sem aviso ou é gasto com resultados de fora de
BH.

**Independent Test**: com o Zap ligado e a OLX desligada, rodar e verificar uma única consulta ao
Zap, nenhuma à OLX, a resposta guardada sem dados de anunciante e, numa resposta com imóveis de
outros estados, os itens descartados e contados.

**Acceptance Scenarios**:

1. **Given** o Zap ligado e a OLX desligada, **When** a rodada roda, **Then** o robô faz exatamente
   uma consulta ao Zap e nenhuma à OLX.
2. **Given** que a chave do serviço pago não está configurada, **When** a rodada roda, **Then**
   nenhuma fonte paga é consultada, o QuintoAndar segue normalmente e o operador é avisado uma vez
   ao iniciar o robô.
3. **Given** uma resposta com 50 imóveis, dos quais 47 fora de Belo Horizonte, **When** a rodada a
   processa, **Then** só os 3 de BH seguem para o filtro das pessoas, e os 47 aparecem como
   descartados por localização no registro da rodada.
4. **Given** qualquer consulta paga, **When** a resposta chega, **Then** ela fica guardada para
   conferência, sem nome, telefone ou e-mail de anunciante.
5. **Given** que o serviço pago responde "créditos insuficientes", **When** a rodada roda, **Then**
   o operador é avisado na mesma rodada, e as fontes pagas não são consultadas de novo até o robô
   ser reiniciado.
6. **Given** que uma fonte paga falha em 3 rodadas seguidas, **When** a terceira termina, **Then** o
   operador recebe um aviso que nomeia a fonte, mesmo que o QuintoAndar esteja funcionando.

### Edge Cases

- O mesmo imóvel anunciado no QuintoAndar e no Zap: é tratado como dois anúncios e pode chegar duas
  vezes (deduplicação entre portais continua fora do escopo).
- Anúncio do Zap com tipo comercial (sala, galpão, ponto) ou de venda: descartado e contado.
- Bairro do Zap escrito de forma diferente do bairro do filtro (acento, caixa, sufixo de região
  como em "Bandeirantes" e "bandeirantes-pampulha"): é reconhecido; bairro sem correspondência é
  descartado e contado.
- Localização escrita de formas variadas ("Belo Horizonte", "belo horizonte", "BH", "Minas Gerais",
  "MG"): é reconhecida como BH/MG; cidade ou UF ausente conta como fora de BH.
- Imóvel sem condomínio informado: o custo total sai como "não informado".
- Telefone do anunciante em formato inesperado ou sem DDD: o telefone é exibido como veio, e o
  botão "WhatsApp" só aparece se o número tiver DDD e for válido.
- Mensagem que precisa ser reenviada depois de reiniciar o robô: sai a partir dos dados guardados,
  sem o contato do anunciante, só com o link.
- Pessoa pausada recebe `/start` de novo: continua pausada e recebe a confirmação de registro
  dizendo que os avisos estão pausados.
- Nenhuma pessoa registrada e ativa: as fontes pagas não são consultadas naquela rodada.
- O serviço pago demora ou cai: a consulta desiste depois de um tempo limite, a falha é registrada,
  e o restante da rodada segue.

## Requirements *(mandatory)*

### Functional Requirements

**Fontes pagas (Zap e OLX)**

- **FR-001**: O sistema MUST consultar o Zap no máximo uma vez por rodada, buscando aluguel em Belo
  Horizonte/MG na cidade inteira, com a primeira página de resultados.
- **FR-002**: A consulta ao Zap MUST levar os filtros somados das pessoas registradas e ativas: o
  maior aluguel máximo, o menor número mínimo de quartos e a união dos tipos aceitos; MUST NOT
  filtrar por bairro.
- **FR-003**: Um anúncio do Zap MUST ser considerado novo na primeira vez que o robô o vê.
- **FR-004**: O sistema MUST ter a OLX pronta, consultada no máximo uma vez por rodada, ordenada
  pelos mais recentes, mas desligada por configuração até o serviço pago respeitar a localização.
- **FR-005**: O VivaReal MUST NOT ser consultado.
- **FR-006**: Cada fonte paga MUST poder ser ligada ou desligada pelo operador na configuração; sem
  a chave do serviço pago, nenhuma fonte paga é consultada.
- **FR-007**: Todo anúncio de fonte paga MUST passar por uma verificação local de cidade e UF antes
  de ser guardado, reconhecendo variações de escrita (com ou sem acento, maiúsculas, "BH", "Minas
  Gerais", "MG"); os de fora são descartados e contados como "fora da cidade".
- **FR-008**: Anúncios de fonte paga que não sejam de aluguel residencial (apartamento, casa, casa
  em condomínio, kitnet/studio) MUST ser descartados e contados.
- **FR-009**: A resposta de cada consulta paga MUST ser guardada para conferência, sem nome,
  telefone, WhatsApp ou e-mail de anunciante.
- **FR-010**: Uma falha de fonte paga (tempo esgotado, erro do serviço, formato inesperado) MUST
  NOT impedir o QuintoAndar nem as demais fontes na mesma rodada.
- **FR-011**: Se o serviço pago responder "créditos insuficientes", o sistema MUST avisar o operador
  na mesma rodada e MUST NOT consultar fontes pagas de novo até ser reiniciado.
- **FR-012**: Se uma fonte falhar em 3 rodadas seguidas, o sistema MUST avisar o operador nomeando
  a fonte, seguindo as mesmas regras de repetição e recuperação do aviso de falha do MVP.

**Anúncio e mensagem**

- **FR-013**: Cada anúncio guardado MUST ter o link público do anúncio no portal e a fonte de
  origem.
- **FR-014**: Cada mensagem de imóvel MUST informar o portal de origem (QuintoAndar, Zap ou OLX) e
  ter um botão "Abrir anúncio" com o link do anúncio.
- **FR-015**: Quando a fonte devolver dados do anunciante, a mensagem MUST mostrar nome e telefone
  e, se houver WhatsApp válido, um botão "WhatsApp" que abre a conversa com esse número.
- **FR-016**: Os dados do anunciante MUST NOT ser gravados de forma permanente; eles existem só
  até a mensagem ser entregue, e o reenvio feito a partir dos dados guardados sai sem contato.
- **FR-017**: O custo total de um anúncio do Zap MUST ser o aluguel mais o condomínio, mais o IPTU
  quando informado; sem condomínio informado, o total sai como "não informado".

**Interação no Telegram**

- **FR-018**: O bot MUST publicar no Telegram o menu de comandos `/ajuda`, `/filtros`, `/status`,
  `/pausar` e `/retomar`, cada um com uma descrição curta.
- **FR-019**: `/ajuda` MUST listar os comandos, os horários das rodadas e os portais consultados.
- **FR-020**: `/filtros` MUST mostrar os filtros da pessoa e se os avisos estão ativos ou pausados.
- **FR-021**: `/status` MUST mostrar a última rodada (data e hora), a próxima rodada, quantos
  imóveis a pessoa recebeu nas últimas 24 horas e o estado de cada portal (funcionando, desligado
  ou com falha). Para o operador, MUST mostrar também o saldo de créditos do serviço pago.
- **FR-022**: `/pausar` MUST suspender os avisos de imóvel da pessoa, e `/retomar` MUST reativá-los;
  o estado MUST sobreviver a reinícios do robô.
- **FR-023**: Imóveis encontrados enquanto a pessoa está pausada MUST NOT ser enviados a ela nem
  contados como enviados; ao retomar, a próxima rodada MUST enviar um resumo, como na primeira
  rodada.
- **FR-024**: Uma mensagem que não seja comando MUST receber resposta curta sugerindo `/ajuda`.
- **FR-025**: Chats não autorizados MUST continuar sendo ignorados em todos os comandos novos.

### Key Entities

- **Fonte**: portal de onde vêm os anúncios (QuintoAndar, Zap, OLX); tem estado ligado/desligado
  e, nas pagas, um histórico de falhas por rodada.
- **Anúncio**: como no MVP, agora com a fonte de origem e o link público para todos os portais.
  Nunca guarda dados do anunciante.
- **Contato do anunciante**: nome, telefone e WhatsApp que acompanham o anúncio só até a entrega da
  mensagem; não é guardado.
- **Resposta da fonte paga**: o que o serviço pago devolveu numa consulta (data, portal,
  quantidade de itens, total informado), sem dados de anunciante, para conferência e para chamados
  ao fornecedor.
- **Pessoa**: como no MVP, agora com o estado dos avisos (ativos ou pausados).
- **Rodada**: como no MVP, agora com as contagens por fonte e os descartes por localização e por
  tipo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Com o Zap ligado e a OLX desligada, o robô consome no máximo 7 créditos por dia (uma
  consulta por rodada), conferido no painel do serviço pago em 3 dias seguidos.
- **SC-002**: Em 7 dias de operação, nenhuma pessoa recebe imóvel fora de Belo Horizonte.
- **SC-003**: 100% das mensagens de imóvel têm o botão que abre o anúncio correto (verificado em
  amostra de 30 mensagens), e toda mensagem cujo anunciante tem WhatsApp abre a conversa com o
  número certo.
- **SC-004**: Uma busca no banco por nomes e telefones de anunciantes vistos nas mensagens não
  encontra nenhum resultado.
- **SC-005**: Uma pessoa nova descobre e usa `/filtros` e `/pausar` sem ajuda do operador, partindo
  apenas do menu do bot ou de `/ajuda`.
- **SC-006**: Enquanto uma pessoa está pausada, ela recebe zero mensagens de imóvel; a primeira
  rodada depois de `/retomar` envia no máximo 5 mensagens.
- **SC-007**: Em rodadas em que a fonte paga falha, o QuintoAndar continua entregando os imóveis
  normalmente, e o operador é avisado em até 3 rodadas ou na mesma rodada, se faltar crédito.

## Assumptions

- O serviço pago é a GeckoAPI (constituição 2.2.0, exceção do princípio III); a chave fica no
  ambiente e o refil de 1.000 créditos custa R$ 49,90. Com só o Zap ligado, dura cerca de 140
  dias.
- A primeira página do Zap vem por relevância, não por data; a cobertura de imóveis novos é
  parcial e aceita. Os filtros somados reduzem a busca de cerca de 22 mil para algumas centenas de
  imóveis.
- Os bairros do Zap e da OLX são comparados com os bairros de BH já usados pelo QuintoAndar,
  aceitando o nome sem o sufixo de região.
- O telefone do anunciante é tratado como número brasileiro; o botão de WhatsApp usa o código do
  país 55.
- A primeira rodada depois desta feature para cada pessoa segue as regras atuais: imóveis do Zap
  que ainda não foram enviados entram numa mensagem de resumo, não em mensagens individuais.
- O resumo (primeira rodada ou depois de `/retomar`) continua em texto, com uma linha por imóvel e
  o link; os botões valem para as mensagens individuais.
- `/status` e `/filtros` só leem dados; nenhum comando novo consulta portais nem gasta créditos,
  exceto a consulta de saldo do operador, que não consome créditos.
- Fora do escopo: VivaReal, deduplicação entre portais, configuração dos filtros pelo Telegram,
  queda de preço e favoritos.
