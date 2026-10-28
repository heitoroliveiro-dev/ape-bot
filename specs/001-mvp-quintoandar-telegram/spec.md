# Feature Specification: MVP — avisos de imóveis do QuintoAndar no Telegram

**Feature Branch**: `001-mvp-quintoandar-telegram`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "MVP do ape-bot: robô de Telegram, sempre ligado, que avisa imóveis novos para alugar em Belo Horizonte a partir do QuintoAndar. Quem usa: o operador (Heitor) e pessoas autorizadas por ele. Cada pessoa envia /start uma vez para se registrar; apenas chats autorizados são aceitos. Cada pessoa tem seus filtros, definidos pelo operador: bairros, preço máximo do aluguel, quartos mínimos e tipos de imóvel. O robô roda às 06h, 09h, 12h, 15h, 18h, 21h e 23h (Brasília), busca no QuintoAndar, guarda os anúncios e envia a cada pessoa os imóveis novos que atendem aos filtros dela, sem repetir. A mensagem traz tipo, bairro, quartos, área, aluguel, custo total e link. Na primeira rodada, um resumo em vez de dezenas de mensagens. Só páginas públicas permitidas, com intervalo, sem login e sem contornar proteções. Falhas não derrubam o robô e, se repetidas, avisam o operador. Fora do escopo: Zap, VivaReal, OLX, e-mail, botões, favoritos, queda de preço, deduplicação entre portais."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receber imóveis novos que batem com meus filtros (Priority: P1)

A pessoa que procura imóvel já está registrada no bot e tem filtros definidos pelo operador (por
exemplo: bairros Buritis e Funcionários, aluguel até R$ 3.000, pelo menos 2 quartos, apartamento).
Ao longo do dia, nos horários fixos, ela recebe no Telegram uma mensagem para cada imóvel novo que
atende aos filtros, com os dados essenciais e o link para abrir o anúncio. Ela nunca recebe o mesmo
imóvel duas vezes.

**Why this priority**: é o valor central do produto — parar de abrir o portal várias vezes ao dia.

**Independent Test**: com uma pessoa registrada e filtros definidos, disparar uma rodada contra
respostas conhecidas do portal e verificar que só os imóveis que atendem aos filtros chegam ao
chat, cada um uma única vez, com todos os campos.

**Acceptance Scenarios**:

1. **Given** uma pessoa registrada com filtros e já tendo passado pela primeira rodada, **When** uma
   rodada encontra 3 imóveis novos que atendem aos filtros e 5 que não atendem, **Then** ela recebe
   exatamente 3 mensagens, uma por imóvel.
2. **Given** um imóvel já enviado a essa pessoa, **When** ele aparece de novo numa rodada seguinte,
   **Then** ele não é reenviado.
3. **Given** um imóvel com aluguel R$ 3.100 e filtro de aluguel máximo R$ 3.000, **When** a rodada o
   encontra, **Then** ele não é enviado, mesmo que outros campos atendam.
4. **Given** um imóvel enviado, **Then** a mensagem contém tipo, bairro, quartos, área, aluguel,
   custo total como o portal informa e o link do anúncio.
5. **Given** duas pessoas com filtros diferentes, **When** a mesma rodada roda, **Then** cada uma
   recebe só os imóveis que atendem aos próprios filtros.

---

### User Story 2 - Registrar-se no bot (Priority: P1)

A pessoa abre o bot no Telegram e envia `/start`. Se o operador a autorizou, o bot confirma o
registro e explica que ela vai receber os imóveis nos horários fixos. Se não foi autorizada, o bot
não responde nada.

**Why this priority**: sem registro, o robô não sabe para onde enviar; sem a restrição, qualquer
pessoa poderia usar o bot.

**Independent Test**: enviar `/start` de um chat autorizado e de um não autorizado e verificar a
confirmação no primeiro e o silêncio no segundo.

**Acceptance Scenarios**:

1. **Given** um chat autorizado pelo operador, **When** ele envia `/start`, **Then** recebe
   confirmação de registro e um resumo dos filtros configurados para ele.
2. **Given** um chat não autorizado, **When** ele envia `/start` ou qualquer outra mensagem,
   **Then** o bot não responde e não guarda nada sobre ele além de um registro no log.
3. **Given** um chat já registrado, **When** envia `/start` de novo, **Then** recebe a mesma
   confirmação, sem duplicar o registro nem reiniciar o histórico de envios.

---

### User Story 3 - Primeira rodada sem inundar o chat (Priority: P2)

Na primeira rodada depois do registro de uma pessoa (ou depois de o operador mudar os filtros
dela), podem existir dezenas de imóveis que já atendem aos filtros. Em vez de dezenas de mensagens,
ela recebe um resumo: quantos imóveis foram encontrados e uma lista compacta (uma linha por imóvel,
com bairro, quartos, aluguel e link). A partir da rodada seguinte, recebe uma mensagem por imóvel
novo.

**Why this priority**: sem isso, a primeira experiência é ruim, mas o produto funciona.

**Independent Test**: registrar uma pessoa cujos filtros casam com 40 imóveis conhecidos, rodar e
verificar que ela recebe um resumo com os 40, e não 40 mensagens individuais.

**Acceptance Scenarios**:

1. **Given** uma pessoa na primeira rodada e 40 imóveis que atendem aos filtros, **When** a rodada
   termina, **Then** ela recebe um resumo com o total (40) e uma linha por imóvel, dividido em
   quantas mensagens forem necessárias, e os 40 passam a contar como enviados.
2. **Given** uma pessoa na primeira rodada e nenhum imóvel encontrado, **When** a rodada termina,
   **Then** ela recebe uma mensagem curta dizendo que nada foi encontrado ainda e que o robô
   continua procurando.
3. **Given** que o operador alterou os filtros de uma pessoa, **When** acontece a rodada seguinte,
   **Then** ela recebe um novo resumo apenas com imóveis ainda não enviados a ela.

---

### User Story 4 - Operador sabe quando algo quebra (Priority: P2)

O operador quer confiar que o robô está funcionando sem ficar olhando. Cada rodada fica registrada
(quantos imóveis vistos, novos, enviados, erros). Se o portal falhar ou mudar de formato em rodadas
seguidas, o operador recebe um aviso no Telegram.

**Why this priority**: o robô roda sem supervisão; uma falha silenciosa equivale a não ter robô.

**Independent Test**: simular respostas inválidas do portal em 3 rodadas seguidas e verificar que
o robô continua no ar, que cada rodada foi registrada e que o operador recebeu um aviso.

**Acceptance Scenarios**:

1. **Given** que o portal está fora do ar numa rodada, **When** a rodada roda, **Then** o robô não
   para, a falha fica registrada e a próxima rodada acontece normalmente.
2. **Given** 3 rodadas seguidas com falha, **When** a terceira termina, **Then** o operador recebe
   um aviso no Telegram com o motivo resumido.
3. **Given** que um aviso de falha já foi enviado, **When** as falhas continuam, **Then** o operador
   não recebe um aviso por rodada; recebe um novo aviso somente quando o robô voltar a funcionar
   (aviso de recuperação) ou se a falha persistir por mais de 24 horas.

### Edge Cases

- Uma pessoa autorizada que ainda não enviou `/start`: nada é enviado a ela, e os imóveis não
  contam como enviados; quando ela se registrar, a primeira rodada segue a User Story 3.
- Uma pessoa bloqueia o bot no Telegram: os envios para ela falham, a falha é registrada e não
  afeta o envio às demais.
- O Telegram recusa o envio por excesso de mensagens: o envio é reprogramado e o imóvel só conta
  como enviado depois de entregue.
- Anúncio sem algum campo (área ou custo total ausente): é enviado com o campo marcado como "não
  informado"; se faltar aluguel, quartos, tipo ou bairro, o anúncio não pode ser filtrado e é
  descartado e contado no registro da rodada.
- Um imóvel muda de preço depois de enviado: não é reenviado (queda de preço está fora do escopo).
- Um bairro configurado pelo operador não existe na lista de bairros de BH do portal: o operador
  é avisado ao iniciar o robô, e o bairro é ignorado.
- O robô fica desligado durante um horário de rodada: a rodada perdida não é recuperada; a próxima
  rodada encontra os imóveis normalmente.
- O operador remove a autorização de uma pessoa: ela deixa de receber mensagens a partir da rodada
  seguinte.

## Requirements *(mandatory)*

### Functional Requirements

**Acesso e registro**

- **FR-001**: O sistema MUST aceitar interação apenas de chats autorizados pelo operador e ignorar
  os demais sem responder.
- **FR-002**: Um chat autorizado MUST conseguir se registrar enviando `/start`, recebendo
  confirmação e o resumo dos filtros configurados para ele.
- **FR-003**: Um novo `/start` de um chat já registrado MUST NOT duplicar o registro nem apagar o
  histórico de envios.

**Filtros**

- **FR-004**: Cada pessoa MUST ter filtros próprios, definidos pelo operador: conjunto de bairros de
  Belo Horizonte, aluguel máximo, número mínimo de quartos e tipos aceitos (apartamento, casa, casa
  em condomínio, kitnet/studio).
- **FR-005**: Um imóvel atende aos filtros somente se estiver num dos bairros escolhidos, for de um
  dos tipos aceitos, tiver quartos ≥ mínimo e aluguel ≤ máximo.
- **FR-006**: A comparação de preço MUST usar o valor de aluguel informado pelo portal; o custo
  total é apenas informativo.
- **FR-007**: Ao iniciar, o sistema MUST validar os filtros configurados e avisar o operador sobre
  bairros não reconhecidos ou valores inválidos.

**Rodadas e coleta**

- **FR-008**: O sistema MUST executar uma rodada às 06h, 09h, 12h, 15h, 18h, 21h e 23h no horário
  de Brasília, independentemente do fuso do equipamento onde roda.
- **FR-009**: Em cada rodada, o sistema MUST consultar o QuintoAndar uma vez para cada combinação
  distinta de bairro e tipo presente nos filtros de todas as pessoas, sem repetir consultas
  iguais para pessoas diferentes.
- **FR-010**: O sistema MUST acessar apenas páginas públicas permitidas pelo portal, sem login,
  sem contornar proteções contra robôs, com intervalo aleatório entre 2 e 5 segundos entre acessos
  e espera crescente quando o portal pedir para desacelerar.
- **FR-011**: O sistema MUST guardar cada anúncio encontrado (identificador no portal, tipo,
  bairro, quartos, área, aluguel, custo total, link e quando foi visto pela primeira e pela última
  vez), sem nenhum dado pessoal de anunciantes.

**Envio**

- **FR-012**: Para cada pessoa registrada, o sistema MUST enviar os imóveis que atendem aos filtros
  dela e que ainda não foram enviados a ela.
- **FR-013**: O sistema MUST NOT enviar o mesmo imóvel duas vezes para a mesma pessoa.
- **FR-014**: Cada mensagem de imóvel MUST conter tipo, bairro, quartos, área, aluguel, custo total
  (como o portal informa) e link do anúncio.
- **FR-015**: Na primeira rodada de uma pessoa, ou na primeira após mudança dos filtros dela, o
  sistema MUST enviar um resumo (total + uma linha por imóvel com bairro, quartos, aluguel e link)
  em vez de mensagens individuais.
- **FR-016**: O envio MUST respeitar os limites de envio do Telegram; um imóvel só conta como
  enviado depois de a mensagem ser entregue.

**Confiabilidade e operação**

- **FR-017**: Uma falha de acesso ao portal, de leitura de formato ou de envio MUST NOT derrubar o
  robô nem impedir as próximas rodadas.
- **FR-018**: Cada rodada MUST ser registrada com horário, anúncios vistos, novos, descartados,
  enviados por pessoa e erros.
- **FR-019**: Após 3 rodadas seguidas com falha na coleta, o sistema MUST avisar o operador pelo
  Telegram, MUST avisar de novo quando a coleta voltar a funcionar, e MUST repetir o aviso se a
  falha persistir por mais de 24 horas — nunca um aviso por rodada.
- **FR-020**: O robô MUST voltar a funcionar sozinho depois de a máquina reiniciar, sem intervenção
  manual.

### Key Entities

- **Pessoa**: alguém autorizado a receber avisos; tem um chat no Telegram, um estado de registro
  (registrada ou não) e um conjunto de filtros. O operador também é uma pessoa e recebe os avisos
  de falha.
- **Filtro**: critérios de uma pessoa — bairros, aluguel máximo, quartos mínimos, tipos aceitos —
  e a data da última alteração (usada para decidir o resumo).
- **Anúncio**: oferta de aluguel no QuintoAndar, identificada pelo número do portal; guarda tipo,
  bairro, quartos, área, aluguel, custo total, link e datas em que foi visto.
- **Envio**: registro de que um anúncio foi entregue a uma pessoa, com data e hora; garante que
  não há repetição.
- **Rodada**: uma execução agendada, com horário, contagens e erros.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em 7 dias de operação, nenhuma pessoa recebe o mesmo imóvel duas vezes.
- **SC-002**: 100% das mensagens enviadas correspondem a imóveis que atendem aos filtros da pessoa
  (verificado por amostragem de 50 mensagens).
- **SC-003**: Um imóvel novo que aparece nas páginas consultadas chega à pessoa em até 3 horas
  durante a janela de rodadas (06h–23h).
- **SC-004**: Pelo menos 95% das rodadas agendadas em 7 dias são executadas e registradas (com a
  máquina ligada).
- **SC-005**: Diante de falha do portal, o operador é avisado em até 3 rodadas, e o robô volta a
  entregar imóveis na primeira rodada após o portal se recuperar, sem intervenção.
- **SC-006**: A pessoa consegue se registrar enviando uma única mensagem, sem instruções técnicas.
- **SC-007**: A primeira rodada de uma pessoa gera no máximo 5 mensagens, qualquer que seja a
  quantidade de imóveis encontrados (até 200).

## Assumptions

- A lista de chats autorizados e os filtros de cada pessoa são mantidos pelo operador num arquivo
  de configuração; configuração pelo próprio Telegram fica para uma feature futura.
- Os bairros válidos são os bairros de Belo Horizonte publicados pelo próprio QuintoAndar.
- O portal mostra um número limitado de imóveis por página pública consultada; imóveis fora dessa
  janela podem não ser vistos na mesma rodada. Cobertura total do portal não é objetivo do MVP.
- O valor de aluguel e o custo total são usados exatamente como o portal informa, sem recomposição.
- O robô roda numa máquina do operador que fica ligada; rodadas perdidas com a máquina desligada
  não são recuperadas.
- Quantidade de pessoas pequena (até 5) e volume baixo (dezenas de consultas por rodada).
- A leitura dos termos de uso do QuintoAndar é feita pelo operador antes de colocar o robô em uso
  contínuo.
- Fora do escopo: Zap, VivaReal, OLX; alertas por e-mail; configuração por botões; favoritos e
  queda de preço; deduplicação entre portais; regionais de BH.
