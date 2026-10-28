# ape-bot Constitution

## Core Principles

### I. Simples Primeiro

- O escopo MUST ser o MVP descrito em `docs/arquitetura.md`; o que não está nele fica para depois.
- Sem camadas ou abstrações sem uso imediato: nada de DDD ou hexagonal formal. O código é
  organizado em módulos por responsabilidade: `fontes`, `filtro`, `banco`, `fila`, `telegram`.
- Qualquer complexidade além disso MUST ser justificada na tabela de Complexity Tracking do
  `plan.md`.

**Racional:** o objetivo é entregar rápido um robô que funcione.

### II. Testes Onde Quebra

- O parse de cada fonte e o filtro MUST ter testes `pytest`, com fixtures reais salvas em
  `tests/fixtures/`.
- Nenhum teste acessa a internet.
- Quando uma fonte mudar e quebrar o parse, a nova resposta MUST virar fixture com um teste que
  falha antes da correção.
- Dinheiro MUST ser representado em centavos (`int`), nunca `float`.

**Racional:** os portais mudam sem aviso; o parse é o ponto que mais quebra.

### III. Coleta Respeitosa

- Só podem ser usadas superfícies públicas permitidas pelo `robots.txt` ou canais oficiais do
  portal (por exemplo, e-mails de alerta da busca salva).
- É proibido: anti-captcha, contorno de Cloudflare ou de qualquer outra proteção antirrobô, e uso
  de API interna não documentada. URLs bloqueadas pelo `robots.txt` nunca são acessadas.
- Requisições ao mesmo portal MUST ter intervalo aleatório de 2 a 5 s e backoff em 429/5xx.
- Dados pessoais de anunciantes (nome, telefone, e-mail) MUST NOT ser armazenados (MySQL,
  incluindo respostas brutas, logs e arquivos).

**Exceção temporária — fonte paga de terceiros (GeckoAPI):** para portais que bloqueiam o acesso
direto, é permitido consumir a API documentada e paga da GeckoAPI para **Zap** e **OLX**. O
VivaReal fica excluído (devolve `notFound` para aluguel em BH e cobra o crédito). Condições:

- O robô MUST falar só com a API do fornecedor; nunca acessa o portal direto nem contorna
  proteção por conta própria.
- Uso pessoal/familiar e de baixo volume: no máximo 1 chamada de listagem por portal por rodada,
  com busca na cidade inteira; chamadas por bairro ou de detalhe (PDP) MUST NOT ser feitas. A
  busca da cidade pode levar os filtros somados das pessoas (maior preço máximo, menor número de
  quartos, união dos tipos).
- A API pode ignorar a localização pedida: todo item MUST passar por filtro local de cidade/UF
  antes de entrar no banco.
- A chave vem de `GECKO_API_KEY`, e cada fonte é ligada ou desligada por configuração; sem chave
  ou desligada, a fonte não é chamada e as demais seguem normalmente. A OLX fica desligada até a
  GeckoAPI respeitar a localização.
- Dados de anunciante que a API devolver MUST NOT ser armazenados.
- **Contato em trânsito:** nome, telefone e WhatsApp do anunciante PODEM aparecer na mensagem do
  Telegram enviada a uma pessoa autorizada, passando só pela fila Redis até a entrega. Reenvio
  feito a partir do banco sai sem contato, só com o link do anúncio.
- A fonte MUST ser desligada quando a busca do familiar terminar; esta exceção então é removida
  em nova emenda.

**Racional:** uso pessoal e de baixo volume, sem prejudicar os portais nem gerar risco legal. A
exceção existe porque a busca é de curto prazo e o custo é baixo; ela não autoriza contorno
feito pelo próprio robô. O contato é exibido porque o anúncio sem anunciante não leva a pessoa à
visita; ele já é público no portal e não fica guardado pelo robô.

### IV. Segredos e Acesso

- Tokens e senhas MUST vir de variáveis de ambiente; `.env` fica fora do git e `.env.example` é
  versionado sem valores.
- Só `chat_id`s autorizados recebem mensagens; os demais são ignorados.

**Racional:** o bot fica exposto na internet e guarda credenciais de banco e de e-mail.

### V. Operação Confiável

- A falha de uma fonte MUST NOT impedir as demais nem derrubar o processo.
- Cada rodada MUST registrar em log: fonte, quantidade coletada, nova, enviada e erros.
- Horários de negócio MUST ser interpretados em `America/Sao_Paulo`.
- O envio ao Telegram MUST passar pela fila Redis, com limite de taxa e nova tentativa em falha.

**Racional:** o robô roda sem supervisão; falha silenciosa equivale a não ter robô.

## Restrições Técnicas

- Python 3.12 · `httpx` · `beautifulsoup4` · `python-telegram-bot` · `redis` · `PyMySQL` com SQL
  puro.
- MySQL e Redis via Docker Compose, junto com a aplicação.
- Playwright só entra se uma fonte permitida exigir JavaScript para exibir os dados.
- Ferramentas: `ruff` e `pytest`.
- Fonte paga opcional: GeckoAPI (`POST /v1/extract`), chave em `GECKO_API_KEY`.

## Fluxo de Desenvolvimento

- Spec Kit no caminho curto: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement` → `/speckit-converge`. `/speckit-clarify` entra quando a spec tiver
  ambiguidade.
- Uma entrega está pronta quando `ruff` e `pytest` passam e `docs/arquitetura.md` reflete o que
  mudou.

## Governance

- Esta constituição prevalece sobre outras práticas do projeto.
- **Emendas:** aplicadas via `/speckit-constitution` e refletidas em `docs/arquitetura.md`.
- **Versionamento semântico:** MAJOR para remoção ou redefinição de princípio; MINOR para
  princípio ou seção nova; PATCH para esclarecimentos.
- **Conformidade:** o `plan.md` passa pelo Constitution Check; `/speckit-analyze`, quando usado,
  trata violação de princípio como crítica.

**Version**: 2.2.0 | **Ratified**: 2026-10-27 | **Last Amended**: 2026-10-27
