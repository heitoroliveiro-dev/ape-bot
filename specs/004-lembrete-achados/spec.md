# Feature Specification: Lembrete de achados

**Feature Branch**: `004-lembrete-achados`

**Created**: 2026-10-28

**Status**: Draft

**Input**: User description: "Lembrete de achados. Depois da 003, o robô passa a relembrar, uma única vez, imóveis já entregues que são achados: aluguel atual de até 70% do valor máximo da pessoa. O lembrete entra na fila da pessoa a partir de 32 horas depois da entrega original (na primeira rodada depois disso), respeita a janela 8h–22h e o espaçamento de 2 a 5 min, e sai com a mensagem 'Esse imóvel já tinha sido encontrado, você chegou a dar uma olhada? É um achado!!' seguida de quartos, bairro, valor e link, com os botões Abrir anúncio e Salvar como favorito. Regras: no máximo 1 lembrete por imóvel por pessoa; só se o imóvel ainda estiver anunciado (visto nas últimas 24 h); não relembra favoritado; não relembra pausada; confere filtros e os 70% na hora de enviar; não conta como recebido no resumo."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ser lembrado de um imóvel bem abaixo do orçamento (Priority: P1)

Com a entrega espaçada, a pessoa recebe dezenas de imóveis por dia e um imóvel muito barato pode
passar despercebido. Um dia e pouco depois, o robô manda de novo os que custam até 70% do valor
máximo dela, com uma mensagem que chama atenção para o achado, desde que o imóvel ainda esteja
anunciado e ela não o tenha salvado.

**Why this priority**: é a feature inteira; aumenta a chance de a pessoa não perder justamente
os imóveis mais vantajosos.

**Independent Test**: com uma pessoa de máximo R$ 3.000 que recebeu há mais de 32 h um imóvel de
R$ 2.000 ainda anunciado e um de R$ 2.500, rodar e verificar que só o de R$ 2.000 volta, uma vez,
no formato de lembrete.

**Acceptance Scenarios**:

1. **Given** uma pessoa com máximo de R$ 3.000 e um imóvel de R$ 2.000 entregue há 33 h e visto
   pelo robô na última rodada, **When** a rodada roda, **Then** o imóvel entra na fila dela e sai
   com "Esse imóvel já tinha sido encontrado, você chegou a dar uma olhada? É um achado!!",
   quartos, bairro, valor, link e os botões "Abrir anúncio" e "⭐ Salvar como favorito".
2. **Given** o mesmo imóvel entregue há 20 h, **When** a rodada roda, **Then** ele ainda não é
   relembrado.
3. **Given** um imóvel de R$ 2.200 (73% do máximo) entregue há 40 h, **When** a rodada roda,
   **Then** ele não é relembrado.
4. **Given** um imóvel já relembrado, **When** passam mais 32 h, **Then** ele não é relembrado de
   novo.
5. **Given** um imóvel de R$ 2.000 que a pessoa salvou como favorito, **When** passam 32 h,
   **Then** ele não é relembrado.
6. **Given** um imóvel de R$ 2.000 que o robô não vê há mais de 24 h, **When** passam 32 h,
   **Then** ele não é relembrado.
7. **Given** um lembrete na fila e a pessoa baixou o máximo para R$ 2.500 (o imóvel de R$ 2.000
   passou a ser 80% do máximo), **When** chegaria a vez dele, **Then** ele não é enviado.
8. **Given** a pessoa recebeu 10 imóveis e 2 lembretes nas últimas 24 h, **When** sai o resumo
   das 23h, **Then** ele diz "Você recebeu 10 imóveis".

### Edge Cases

- **Entrega à noite**: um imóvel entregue às 21h completa 32 h às 05h do segundo dia; o lembrete
  entra na rodada seguinte e sai a partir das 8h.
- **Preço mudou**: vale o aluguel atual do anúncio; se subiu acima de 70% do máximo, não relembra;
  se caiu para dentro, relembra.
- **Pessoa pausada**: não recebe lembrete; ao retomar, os imóveis ainda elegíveis podem ser
  relembrados na rodada seguinte.
- **Lembrete que não saiu** (pausa limpou a fila, reinício perdeu a fila): o imóvel continua
  elegível até ser de fato entregue como lembrete.
- **Lembrete que falhou de vez** (pessoa bloqueou o robô, 3 tentativas): conta como lembrado e não
  tenta de novo.
- **Imóvel favoritado depois de entrar na fila de lembrete**: não é enviado.
- **Imóvel do Zap**: o Zap traz poucos itens por rodada, então um imóvel do Zap ainda anunciado pode
  não ser visto de novo em 24 h e, nesse caso, não é relembrado. Aceito: é melhor não relembrar do
  que relembrar um imóvel que talvez já saiu.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Um imóvel MUST ser relembrado a uma pessoa quando, ao mesmo tempo: foi entregue a
  ela há 32 h ou mais; nunca foi relembrado a ela; o aluguel atual é de até 70% do valor máximo
  atual dela (arredondado para baixo em centavos); continua atendendo aos filtros atuais dela; o
  robô o viu nas últimas 24 h; não está nos favoritos dela; e ela está ativa (não pausada).
- **FR-002**: Os imóveis elegíveis MUST ser procurados a cada rodada, depois de os imóveis novos
  entrarem na fila, e colocados na mesma fila da pessoa, seguindo a mesma ordem por valor, a
  mesma janela das 8h às 22h e o mesmo espaçamento de 2 a 5 minutos.
- **FR-003**: Na hora do envio, o robô MUST conferir de novo os filtros atuais, os 70%, os
  favoritos e se a pessoa está ativa; se algo não bater, o lembrete é descartado sem ser enviado.
- **FR-004**: A mensagem MUST ser: "Esse imóvel já tinha sido encontrado, você chegou a dar uma
  olhada? É um achado!!", seguida das mesmas linhas da mensagem de imóvel (quartos no bairro,
  valor, link) e dos botões "Abrir anúncio" e "⭐ Salvar como favorito". Sem contato do anunciante.
- **FR-005**: Cada imóvel MUST ser relembrado no máximo uma vez por pessoa; um lembrete conta como
  feito quando é entregue ou quando falha de vez.
- **FR-006**: Lembretes MUST NOT entrar na contagem "Você recebeu X imóveis" nem nas contagens por
  portal do resumo e do `/status`.

### Key Entities

- **Envio**: a entrega de um imóvel a uma pessoa (da 001/003); ganha a informação de quando o
  imóvel foi relembrado, se foi.
- **Lembrete**: um imóvel já entregue que volta à fila da pessoa, marcado para sair com o texto de
  achado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Nenhum imóvel é relembrado duas vezes à mesma pessoa (verificado depois de 7 dias).
- **SC-002**: Todo lembrete enviado é de um imóvel com aluguel até 70% do máximo da pessoa naquele
  momento, entregue há pelo menos 32 h e visto pelo robô nas 24 h anteriores.
- **SC-003**: Nenhum lembrete é enviado para imóvel favoritado ou para pessoa pausada.
- **SC-004**: Com o filtro atual do dono (máximo R$ 3.000), cerca de 1 em cada 5 imóveis entregues
  volta como lembrete (14 de 76 na amostra de 28/10), sem passar de 2 a 5 minutos entre mensagens.

## Assumptions

- O limite de 70% e o prazo de 32 h são fixos nesta versão (decisão do dono); mudar exige nova
  versão.
- "Ainda anunciado" é aproximado por "visto pelo robô nas últimas 24 h", porque o robô não consulta
  o anúncio individualmente (constituição III proíbe chamadas de detalhe nas fontes pagas).
- O lembrete é montado a partir dos dados guardados; o contato do anunciante não existe mais nessa
  hora e não aparece.
- Os imóveis entregues antes desta feature (por exemplo, os 76 de 28/10) também podem ser
  relembrados, seguindo as mesmas regras.
- Fora do escopo: limite de lembretes por dia, comparação com o preço médio do bairro, lembrete de
  imóveis acima de 70%.
