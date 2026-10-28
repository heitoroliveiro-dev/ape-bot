# ape-bot — Arquitetura (enxuta)

> Versão 1.3 · 28/10/2026 · Heitor Oliveiro · Apoio: Claude
> 1.1: reflete a feature `001-mvp-quintoandar-telegram` implementada (spec/plan em `specs/001-*`).
> 1.2: feature `002-geckoapi-zap-olx-telegram` (Zap via GeckoAPI, OLX pronta e desligada, comandos no Telegram).
> 1.3: escopo da feature `003-entrega-espacada-cadastro-telegram` (em especificação) e a justificativa em 2.1. As seções 3 a 6 continuam descrevendo o que já roda até a 003 ser entregue.
> Substitui a v0.4 (arquivada em `docs/historico/arquitetura-v0.4-completa.md`). Foco: projeto rápido.

## 1. O que é
Robô que coleta anúncios de aluguel em Belo Horizonte, guarda no MySQL e avisa no Telegram, para chats definidos, os imóveis novos que batem com o filtro de cada pessoa.

## 2. MVP

| Entra | Fica para depois |
|---|---|
| QuintoAndar (coletor próprio, superfícies públicas: `docs/spikes/001-fontes-de-dados.md`) | Alerta de queda de preço |
| Filtro por pessoa: bairros, preço máximo, quartos mínimos, tipo. **003:** guardado no MySQL; `filtros.yaml` só autoriza chats, define o operador e semeia quem ainda não tem cadastro | Deduplicação entre portais |
| Aviso de imóvel novo, sem repetir | Cadastro aberto ao público ou aprovação de pessoas pelo Telegram |
| Rodadas às 06, 09, 12, 15, 18, 21 e 23h (America/Sao_Paulo) | Limite diário de imóveis por pessoa |
| Aviso ao operador em falhas repetidas, por fonte | Nuvem gerenciada (Azure) |
| Zap via GeckoAPI (1 chamada por rodada); OLX pronta e desligada (`GECKO_FONTES`) | VivaReal (excluído: `notFound` e cobra crédito) |
| Mensagem com portal, botões "Abrir anúncio" e "WhatsApp" e contato do anunciante em trânsito | |
| Comandos `/ajuda`, `/filtros`, `/status`, `/pausar`, `/retomar` e menu do bot | |
| **003:** entrega espaçada, um imóvel por mensagem a cada 2–5 min (sorteado), só das 8h às 22h, mais baratos primeiro; sai o resumo em lista | |
| **003:** resumo diário às 23h, com recebidos por portal e créditos da GeckoAPI | |
| **003:** cadastro pelo `/start` e edição pelo `/filtros`, com botões; bairros escolhidos por regional da PBH | |
| **003:** favoritos (botão na mensagem e `/favoritos`) | |

### 2.1 Por que a 003 traz itens que estavam "para depois"

A v1.2 deixava para depois a configuração por botões, os favoritos e as regionais da PBH. A 003 traz os três (princípio I da constituição: o escopo é o desta tabela, e a mudança fica registrada aqui):

- **Volume.** Com o Zap, uma rodada passou a render dezenas de imóveis por pessoa (64 só do QuintoAndar na primeira rodada de um filtro). O resumo em lista com tudo de uma vez não é lido. Mandar um por vez, espaçado e só em horário comercial, faz cada imóvel ser avaliado; isso não exige peça nova, só a fila passar a ter uma vez por pessoa.
- **Dependência do operador.** Toda mudança de filtro passava por editar o `filtros.yaml` e reiniciar o robô. A edição pelo Telegram é a interação mais frequente depois de receber imóveis, e tirar o operador do caminho é o que deixa o robô usável por outras pessoas da família.
- **Regionais.** Elas deixam de ser um fim e viram o meio de escolher bairro: 289 bairros não cabem numa lista de botões, e as 9 regionais quebram a escolha em grupos de tamanho razoável. A tabela bairro → regional é fixa e versionada, gerada uma vez a partir da relação oficial de bairros por regional da Prefeitura; o robô não consulta a Prefeitura em funcionamento.
- **Favoritos.** Com um imóvel por mensagem, guardar os que interessam custa um botão e uma tabela, e substitui rolar a conversa atrás de um anúncio.
- **Resumo diário.** Com a entrega espalhada pelo dia, a pessoa perde a noção do volume; um resumo às 23h devolve essa visão sem a lista em bloco.

O acesso continua em lista fechada (princípio IV), e o gasto da GeckoAPI não muda: a chamada por portal continua sendo uma por rodada, com os filtros somados das pessoas ativas. O contato do anunciante pode passar mais tempo na fila Redis até ser entregue, mas continua sem ir ao MySQL (princípio III).

**Fora de vez:** anti-captcha e qualquer contorno de Cloudflare ou de outra proteção antirrobô feito pelo próprio robô.

**Exceção temporária (constituição 2.2.0, princípio III):** Zap e OLX entram pela API paga da GeckoAPI (`POST /v1/extract`, chave em `GECKO_API_KEY`, fontes em `GECKO_FONTES`), com no máximo 1 chamada de listagem por portal por rodada, na cidade inteira, com os filtros somados das pessoas ativas e sem chamadas de detalhe. Todo item passa por trava local de cidade/UF e pelo catálogo de bairros. O contato do anunciante vai só na mensagem (fila Redis) e nunca no MySQL. A fonte é desligada quando a busca do familiar terminar. Orçamento: refil de 1.000 créditos por R$ 49,90, e 1 portal × 7 rodadas = 210 créditos/mês.

## 3. Fluxo

```mermaid
flowchart LR
    agenda["Agendador<br/>(7 rodadas/dia)"] --> qa["Coletor QuintoAndar<br/>httpx + BeautifulSoup"]
    agenda --> zap["Coletor Zap / OLX<br/>GeckoAPI (1 chamada)"]
    zap --> trava["Trava cidade/UF<br/>+ catálogo de bairros"]
    trava --> db
    zap -. "contato em trânsito" .-> fila
    qa --> db[("MySQL<br/>anuncio, envio, rodada,<br/>rodada_fonte, alerta")]
    db --> filtro["Filtro por pessoa<br/>filtros.yaml"]
    filtro --> fila[["Redis<br/>fila de notificações"]]
    fila --> worker["Worker Telegram<br/>(respeita limite de envio)"]
    worker --> tg["Telegram<br/>chat_ids definidos"]
```

- **Telegram não envia por número de telefone.** Cada pessoa abre o bot e manda `/start` uma vez. O bot registra o `chat_id`, e o `filtros.yaml` associa filtros a esse `chat_id`. Só chats da lista recebem mensagens.
- **Redis:** fila entre "achou imóvel" e "enviou no Telegram". O worker controla o ritmo (cerca de 1 mensagem por segundo por chat) e tenta de novo em falha. Alternativa mais simples, se preferir um container a menos: fila em memória (`asyncio.Queue`).
- **Coleta:** uma requisição por combinação bairro × tipo dos filtros, na URL pública `/alugar/imovel/{bairro}-belo-horizonte-mg-brasil/{tipo}`; dados do JSON `__NEXT_DATA__`; anúncios de bairros vizinhos que o portal mistura na página são descartados.
- **Sleep:** 2 a 5 s aleatórios entre requisições ao mesmo portal, e backoff em 429/5xx. Sem seguir redirects.
- **Fontes isoladas:** cada fonte vira uma linha em `rodada_fonte` (`ok`, `falha`, `desligada`, `sem_credito`); a falha de uma não derruba as outras, e o alerta ao operador é por fonte. Página do QuintoAndar sem a lista carregada (falha passageira do portal) ganha uma nova tentativa e conta como erro de acesso, não de formato.
- **Telegram:** menu de comandos; `/pausar` grava `pessoa.pausada_em` e `/retomar` força um resumo na rodada seguinte; `/status` mostra a última rodada, as fontes e, para o operador, o saldo da GeckoAPI.
- **Processo único:** bot (`/start`), agendador (`JobQueue`) e worker da fila rodam no mesmo processo; Docker Compose com `restart: unless-stopped`.

## 4. Stack
Python 3.12 · `httpx` · `beautifulsoup4` · `python-telegram-bot` (com `JobQueue`) · `redis` · `PyMySQL` + SQL puro · `pytest` · `ruff` · Docker Compose (app + MySQL + Redis). Playwright só entra se uma fonte permitida exigir JavaScript; o QuintoAndar não exige (os dados vêm no `__NEXT_DATA__`).

## 5. Dados

Tabelas `pessoa`, `anuncio`, `envio` (status pendente/entregue/falhou; PK por pessoa + anúncio impede repetição), `rodada` e `alerta`. Detalhes em `specs/001-mvp-quintoandar-telegram/data-model.md`; DDL em `migrations/001_inicial.sql`.

`resposta_fonte` (`migrations/002_resposta_fonte.sql`) guarda a resposta JSON bruta da GeckoAPI, uma linha por `requestId`, **sem dados de anunciante** (`advertiser`, `seller`, telefones e e-mail são removidos antes de gravar; princípio III). Importação manual: `docker compose run --rm -v <pasta>:/importar:ro app python -m apebot.importar_resposta /importar/*.json`.

O preço é guardado como o portal informa, em centavos.

## 6. Estrutura

```
ape-bot/
├── src/apebot/
│   ├── fontes/quintoandar.py   # URL, coleta (httpx) + parse
│   ├── fontes/geckoapi.py      # cliente GeckoAPI, resposta sem anunciante, coleta genérica
│   ├── fontes/zap.py · olx.py  # payload com filtros somados + parse
│   ├── fontes/resultado.py     # ResultadoFonte, trava cidade/UF, bairro, WhatsApp
│   ├── importar_resposta.py    # JSON da GeckoAPI → resposta_fonte
│   ├── config.py · modelos.py  # .env, filtros.yaml, Anuncio/Filtro/Pessoa
│   ├── mensagens.py · rodada.py
│   ├── filtro.py               # regras do filtros.yaml
│   ├── banco.py                # MySQL
│   ├── fila.py                 # Redis
│   ├── telegram_bot.py         # comandos, botões, worker de envio
│   └── main.py                 # agendador e composição
├── tests/ (fixtures/ + testes de parse e filtro)
├── filtros.yaml.example
├── docker-compose.yml · Dockerfile · .env.example · pyproject.toml
└── docs/ (arquitetura.md, spikes/, historico/)
```

## 7. Testes
Só onde quebra: **parse** de cada fonte (com fixtures reais, sem internet) e **filtro**. O resto é validado rodando.

## 8. Pendências
1. OLX: ligar (`GECKO_FONTES=zap,olx`) só quando a GeckoAPI respeitar a localização; abrir chamado com os `request_id` de `resposta_fonte`.
2. Ler os termos de uso do QuintoAndar.
3. Onde roda: máquina própria, VPS barata ou VM na nuvem. O Docker Compose funciona em qualquer uma.
4. GeckoAPI (teste no Playground em 27/10/2026, 6 créditos): VivaReal devolveu `notFound` para aluguel em BH; Zap funciona (22.060 imóveis, 30 por página), mas não ordena por data nem informa data de publicação, e traz `advertiser` com telefones; OLX ordena por data (`listedAt`), mas ignorou a localização, por campos e por URL, e devolveu 50 itens de fora de MG. Nenhum portal atende ainda ao modelo "1 chamada por rodada". As duas respostas estão em `resposta_fonte`; fixtures cortadas em `tests/fixtures/geckoapi/`. Próximo passo: chamado no suporte da GeckoAPI sobre OLX/VivaReal antes de comprar o refil.
5. Tabela bairro → regional (003): fonte é o PDF da PBH "Relação de bairros, regionais e territórios de gestão compartilhada" (487 bairros, 9 regionais, sem Hipercentro; cópia em `docs/referencias/pbh-bairros-regionais.pdf`), baixado pelo navegador (o portal bloqueia acesso automatizado). 240 dos 289 bairros do catálogo batem direto pelo nome; os demais são resolvidos por apelido, revisados à mão ou saem do catálogo (6 não são de BH).
