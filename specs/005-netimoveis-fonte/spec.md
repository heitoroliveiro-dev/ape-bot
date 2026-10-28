# Feature Specification: Netimóveis como fonte de anúncios

**Feature Branch**: `005-netimoveis-fonte`

**Created**: 2026-10-28

**Status**: Draft

**Input**: User description: "Netimóveis como nova fonte de anúncios (feature 005), a partir do spike docs/spikes/002-netimoveis.md. O robô passa a coletar imóveis para alugar em Belo Horizonte no Netimóveis, a cada rodada, sem custo de crédito e sem contornar nenhuma proteção: só páginas públicas permitidas pelo robots.txt (busca por bairro e tipo com ?quartos=N, só a 1ª página, até 21 imóveis por página; proibidos /pesquisa/, /api/, pag=, precoMin/precoMax, ordem=). Os dados vêm do JSON-LD: id, tipo, bairro, quartos, área, aluguel, condomínio quando houver, link. Uma busca por bairro × tipo da união dos filtros das pessoas ativas, com o menor mínimo de quartos, intervalo de alguns segundos entre requisições (~100 por rodada). Preço, quartos, tipo e bairro continuam filtrados localmente; bairros do portal são mapeados para o catálogo de bairros de BH e os desconhecidos são descartados e contados. Quando a busca tiver mais de 21 resultados, registrar no log. A fonte entra no registro por fonte, no alerta por fonte, no /status e na /ajuda, e pode ser ligada/desligada por configuração; a falha dela não derruba as outras nem muda o status da rodada. Os imóveis do Netimóveis seguem o mesmo fluxo da 003/004. Contexto de produção: a partir de hoje (28/10/2026) o robô roda no Railway, sempre ligado; a coleta precisa funcionar a partir do IP do datacenter do Railway, e a fonte deve poder ser desligada por variável de ambiente sem novo deploy de código. Fora de escopo: sitemap diário, página de detalhe (IPTU), deduplicação entre portais."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receber imóveis do Netimóveis junto com os outros portais (Priority: P1)

Hoje a pessoa recebe imóveis do QuintoAndar e do Zap. Com filtros apertados (por exemplo, a
parente: 39 bairros da região Centro-Sul, 2 quartos, até R$ 2.000), a primeira rodada achou só 7
imóveis. O Netimóveis reúne imobiliárias tradicionais de BH, com estoque diferente; a cada rodada o
robô passa a buscar também lá, nos bairros e tipos que as pessoas pediram, e os imóveis que batem
com os filtros de cada uma entram na mesma fila, com o mesmo formato de mensagem e o mesmo
espaçamento.

**Why this priority**: é a feature inteira; aumenta o número de imóveis relevantes sem custo de
crédito.

**Independent Test**: com uma pessoa ativa que pede apartamento de 2+ quartos até R$ 2.000 no
Centro e na Floresta, rodar uma rodada e verificar que imóveis do Netimóveis desses bairros, dentro
do valor, entram na fila dela e saem como mensagem de imóvel com o portal Netimóveis.

**Acceptance Scenarios**:

1. **Given** uma pessoa ativa que pede apartamento, 2+ quartos, até R$ 2.000, no Centro, **When** a
   rodada roda e o Netimóveis mostra no Centro um apartamento de 2 quartos por R$ 1.650, **Then**
   ele entra na fila da pessoa e sai com quartos, bairro, valor, link e os botões de sempre.
2. **Given** o mesmo cenário com um apartamento de 2 quartos por R$ 2.150, **When** a rodada roda,
   **Then** ele não entra na fila (acima do máximo).
3. **Given** um imóvel do Netimóveis já entregue à pessoa, **When** ele aparece de novo numa rodada
   seguinte, **Then** não é entregue de novo (pode voltar só como lembrete de achado, pelas regras
   da 004).
4. **Given** duas pessoas ativas, uma pedindo Centro e outra Savassi, **When** a rodada roda,
   **Then** o robô busca os dois bairros uma vez cada (por tipo), e cada pessoa só recebe o que bate
   com os próprios filtros.
5. **Given** a pessoa favorita um imóvel do Netimóveis, **When** abre `/favoritos`, **Then** ele
   aparece com o portal Netimóveis; e no resumo das 23h ele conta em "Netimóveis".

---

### User Story 2 - Acompanhar a saúde da fonte e desligá-la sem deploy (Priority: P2)

O dono (operador) precisa saber se o Netimóveis está funcionando, especialmente agora que o robô
roda num datacenter (Railway), cujo IP pode ser tratado diferente do IP de casa. O `/status`
mostra o estado do Netimóveis como mostra o dos outros portais; se a fonte falhar em várias rodadas
seguidas, o operador recebe o alerta por fonte; e ele consegue desligar ou religar a fonte mudando
só a configuração do ambiente.

**Why this priority**: sem isso, uma falha silenciosa da fonte nova passaria despercebida
(constituição V), e um bloqueio exigiria novo deploy de código para parar de insistir.

**Independent Test**: simular a fonte respondendo com erro de acesso em 3 rodadas seguidas e
verificar o alerta ao operador e o estado no `/status`; depois desligar a fonte pela configuração,
reiniciar e verificar que ela não é chamada e aparece como desligada.

**Acceptance Scenarios**:

1. **Given** o Netimóveis respondeu normalmente na última rodada, **When** o operador manda
   `/status`, **Then** a linha "Netimóveis" aparece como ok.
2. **Given** o Netimóveis falhou (bloqueio, erro do servidor ou formato inesperado) em 3 rodadas
   seguidas, **When** a terceira termina, **Then** o operador recebe o alerta da fonte, como já
   acontece com as outras; e quando a fonte voltar, recebe o aviso de recuperação.
3. **Given** o Netimóveis falhou numa rodada em que o QuintoAndar funcionou, **When** a rodada
   termina, **Then** a rodada é registrada como ok e os imóveis das outras fontes são entregues
   normalmente.
4. **Given** a fonte desligada na configuração do ambiente, **When** o robô reinicia e roda,
   **Then** nenhuma página do Netimóveis é acessada, o `/status` mostra "desligado" e a `/ajuda` não
   lista o Netimóveis entre os portais.

---

### User Story 3 - Saber quando a 1ª página cortou resultados (Priority: P3)

Como o robô só lê a primeira página de cada busca (a paginação é proibida pelo robots.txt), bairros
com muitos imóveis podem ter resultados fora do alcance. O operador quer saber onde isso acontece
para decidir se vale buscar de outro jeito no futuro (por exemplo, pelo sitemap).

**Why this priority**: não muda o que a pessoa recebe hoje; serve para medir uma limitação
conhecida.

**Independent Test**: com uma busca cujo total é maior que o número de imóveis na página, rodar e
verificar o registro do corte com bairro, tipo, total e quantidade lida.

**Acceptance Scenarios**:

1. **Given** a busca de apartamentos 2+ quartos em Funcionários com 31 resultados e 21 na página,
   **When** a rodada roda, **Then** fica registrado que a busca de Funcionários/apartamento cortou
   10 resultados.
2. **Given** uma busca com 13 resultados e 13 na página, **When** a rodada roda, **Then** nenhum
   corte é registrado.

### Edge Cases

- **Bloqueio a partir do datacenter**: se o Netimóveis passar a negar acesso ao IP do Railway (ou
  pedir verificação antirrobô), a fonte conta como falha, segue o alerta por fonte e não tenta
  contornar; o operador pode desligá-la pela configuração.
- **Muitas requisições seguidas com erro**: em respostas de excesso de requisições ou erro do
  servidor, o robô espera mais antes de tentar de novo (backoff) e não insiste indefinidamente na
  mesma rodada.
- **Página sem os dados estruturados** (layout mudou): a busca conta como erro de formato da fonte;
  as demais buscas da rodada continuam.
- **Bairro do portal fora do catálogo de BH** ou com nome diferente: mapeado para o catálogo quando
  houver correspondência; senão o imóvel é descartado e contado como bairro desconhecido.
- **Imóvel fora de BH** na página (por exemplo, bairro homônimo de outra cidade): descartado pela
  trava local de cidade.
- **Tipos parecidos**: cobertura e área privativa aparecem dentro da busca de apartamento e contam
  como apartamento; tipos que a pessoa não pode escolher (sala, loja, galpão, garagem) são
  descartados.
- **Imóvel sem preço** ou sem quartos: descartado como incompleto.
- **Nenhuma pessoa ativa**: a fonte não é chamada (como as demais).
- **Mesmo imóvel em dois portais**: pode chegar duas vezes, uma por portal (aceito nesta versão).
- **Rodada mais longa**: com ~100 buscas a alguns segundos de intervalo, a rodada leva alguns
  minutos a mais; a rodada seguinte não começa antes de a anterior terminar.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A cada rodada, com a fonte ligada e ao menos uma pessoa ativa, o robô MUST buscar no
  Netimóveis imóveis para alugar em Belo Horizonte para cada combinação de bairro × tipo da união
  dos filtros das pessoas ativas, com o menor número mínimo de quartos entre elas, lendo só a 1ª
  página de cada busca.
- **FR-002**: O robô MUST acessar só páginas públicas permitidas pelo `robots.txt` do Netimóveis;
  MUST NOT usar paginação, filtros de preço ou de área na URL, ordenação, as áreas de pesquisa e de
  API bloqueadas, nem qualquer contorno de proteção antirrobô.
- **FR-003**: Requisições ao Netimóveis MUST ter intervalo aleatório de 2 a 5 s entre si e espera
  maior (backoff) em respostas de excesso de requisições ou erro do servidor.
- **FR-004**: De cada imóvel o robô MUST obter: identificador no portal, tipo, bairro, quartos,
  área, aluguel e link; e o condomínio quando a página trouxer.
- **FR-005**: Os bairros do portal MUST ser mapeados para o catálogo de bairros de BH; imóveis cujo
  bairro não tenha correspondência MUST ser descartados e contados como bairro desconhecido.
  Imóveis fora de BH, sem preço ou sem quartos, ou de tipo que a pessoa não pode escolher, MUST ser
  descartados e contados por motivo.
- **FR-006**: Preço máximo, quartos mínimos, tipos e bairros de cada pessoa MUST continuar sendo
  aplicados localmente, pessoa a pessoa, como nas outras fontes.
- **FR-007**: Os imóveis do Netimóveis MUST seguir o mesmo fluxo das outras fontes: não repetir o
  que a pessoa já recebeu, fila por pessoa do mais barato ao mais caro, entrega espaçada das 8h às
  22h, favoritos, resumo das 23h (com contagem por portal) e lembrete de achados.
- **FR-008**: Quando o total de resultados de uma busca for maior que a quantidade lida na página,
  o robô MUST registrar o corte com bairro, tipo, total e quantidade lida.
- **FR-009**: O resultado do Netimóveis em cada rodada MUST ser registrado por fonte (ok, falha ou
  desligada, com quantidade de buscas, de erros, de imóveis e de descartes por motivo) e entrar no
  alerta por fonte já existente (alerta após falhas seguidas, reaviso e aviso de recuperação).
- **FR-010**: Uma falha do Netimóveis (inteira ou de algumas buscas) MUST NOT impedir as outras
  fontes nem mudar o status da rodada, que continua vindo do QuintoAndar.
- **FR-011**: O Netimóveis MUST aparecer no `/status` (estado da fonte) e na `/ajuda` (lista de
  portais, quando ligado), e as mensagens de imóvel e o resumo MUST identificá-lo como "Netimóveis".
- **FR-012**: A fonte MUST poder ser ligada ou desligada por configuração do ambiente, valendo após
  reiniciar o robô, sem mudança de código; desligada, nenhuma página do Netimóveis é acessada.
- **FR-013**: Nada além dos dados do imóvel listados no FR-004 MUST ser armazenado; dados de
  anunciante não são coletados.

### Key Entities

- **Fonte Netimóveis**: nova fonte de anúncios, ao lado de QuintoAndar, Zap e OLX; tem estado por
  rodada (ok, falha, desligada) e alerta próprio.
- **Busca**: uma consulta por bairro × tipo, com mínimo de quartos; tem total de resultados e
  quantidade lida (para o registro de corte).
- **Anúncio**: o mesmo das outras fontes (portal, identificador, tipo, bairro, quartos, área,
  aluguel, condomínio quando houver, link), identificado por portal + identificador.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Com os filtros atuais das duas pessoas, cada rodada com a fonte ligada traz imóveis do
  Netimóveis que passam no filtro de pelo menos uma delas (na amostra do spike, 4 imóveis em 4
  bairros da parente), sem repetir nenhum já entregue.
- **SC-002**: Em 7 dias de produção, nenhuma requisição ao Netimóveis usa endereço ou parâmetro
  bloqueado pelo `robots.txt`, e o intervalo entre requisições nunca é menor que 2 s.
- **SC-003**: Uma falha do Netimóveis em 3 rodadas seguidas gera alerta ao operador em até 1 rodada
  depois da terceira falha, e nenhuma rodada fica sem imóveis das outras fontes por causa dela.
- **SC-004**: Desligar a fonte pela configuração faz a próxima rodada não acessar o Netimóveis, sem
  novo deploy de código.
- **SC-005**: Cada rodada continua terminando antes da rodada seguinte (intervalo mínimo de 2 h
  entre horários), com as fontes somadas.

## Assumptions

- O robô roda no Railway desde 28/10/2026, sempre ligado (1 réplica, reinício automático); a
  configuração de ambiente do Railway é o lugar para ligar e desligar a fonte, e um reinício aplica
  a mudança.
- O spike foi feito de um IP residencial; o acesso a partir do IP do datacenter do Railway é
  verificado na implantação. Se for negado, a fonte fica desligada (não se tenta contornar).
- O preço do portal é o aluguel; IPTU e total com encargos ficam fora (exigiriam a página de cada
  imóvel).
- Os termos de uso do Netimóveis serão lidos pelo dono antes de ligar a fonte em produção, como
  ficou pendente para o QuintoAndar.
- A ordem dos resultados é a do portal (relevância); não há ordenação por data permitida, e o
  portal não informa data de publicação.
- Fora do escopo: sitemap diário, página de detalhe (IPTU), deduplicação entre portais, paginação.
