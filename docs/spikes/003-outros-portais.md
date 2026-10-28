# Spike 003 — Outros portais de BH (Chaves na Mão, Casa Mineira, Lugar Certo, Imovelweb)

> 28/10/2026 · Heitor Oliveiro · Apoio: Claude
> Resultado: **nenhum portal novo liberado para o robô.** Chaves na Mão é tecnicamente o melhor (MCP oficial),
> mas os termos proíbem coleta automatizada; Casa Mineira também proíbe robôs nos termos (item 1.4.2); Lugar
> Certo e Imovelweb fora. Revisão dos termos do Netimóveis (spike 002) no fim.
> Cliente: `curl` com `User-Agent: ape-bot/0.1 (uso pessoal; baixo volume)`, 2–3 s entre requisições; ~30
> requisições no total.

## 1. Chaves na Mão

### 1.1 robots.txt e canais para agentes
- `User-agent: *`: bloqueia **toda query string** (`Disallow: /*?*`), exceto `?pg=2` e `?relatedAds=true`;
  só a página 2 da listagem é liberada. `Content-Signal: ai-train=no, search=yes, ai-input=yes`.
- `Allow: /api/mcp` e `/.well-known/`. O `/llms.txt` diz: *"Para consultas amplas sobre anúncios, preços e
  disponibilidade, os agentes devem priorizar o MCP Server em vez de percorrer sequencialmente as páginas."*
- **MCP oficial** (`/.well-known/mcp/server-card.json`): `https://www.chavesnamao.com.br/api/mcp/`,
  streamable-http, **sem autenticação**, ferramenta `search_realty_listings`. Skills públicas em
  `/.well-known/agent-skills/index.json`.

### 1.2 O que o MCP entrega (testado)
- Filtros: `transaction` (`aluguel`), `propertyType` (`apartamento`, `casa`, `casa em condomínio`, `kitnet`…),
  `city`, `state`, `neighborhood`, `bedrooms` (= **N ou mais**), `minPrice`, `maxPrice`, área, amenidades.
- Paginação: `pageSize` fixo em 15, `page` 1–20 → **no máximo 300 resultados por consulta**.
- Resultado: `id`, `url` canônica, `priceBRL`, `propertyType` (`Apartamento`, `Casa / Sobrado`,
  `Casa / Sobrado em Condomínio`, `Kitnet / Stúdio`), `location.neighborhood/city/state`, `bedrooms`,
  `bathrooms`, `parkingSpots`, `areaM2`, `imageUrl`. **Sem dados do anunciante.** Sem data de publicação nem
  ordenação.
- `neighborhood` é **aproximado** ("Santa Efigênia" trouxe Santa Amélia, Santa Mônica…): exigiria refiltrar
  o bairro localmente.
- Estoque em BH (aluguel): **2.919 apartamentos e 1.190 casas** (Netimóveis: 1.074 e 277). Com os filtros
  somados das duas pessoas (2+ quartos, até R$ 3.000): 530 apartamentos, 188 casas, 2 kitnets. Apartamentos
  passam do teto de 300; seria preciso fatiar por faixa de preço (~50 chamadas por rodada no total).

### 1.3 Termos de uso (lidos em 28/10/2026, `/termos-de-uso/`)
Na lista de condutas proibidas:
> "Uso de bots, scripts automatizados, ferramentas de raspagem ou qualquer sistema que simule acesso humano
> para criar contas, publicar anúncios, **coletar dados ou interagir com a plataforma de forma automatizada,
> seja para uso pessoal ou comercial**. Comportamento identificado como automatizado, abusivo ou de spam
> resulta em bloqueio da conta e do dispositivo."

O MCP é oferecido para assistentes de IA responderem a uma pessoa (`ai-input=yes`), não para um robô que
consulta sozinho 7 vezes por dia e guarda os anúncios.

**Decisão:** não entra no robô sem **autorização por escrito** do Chaves na Mão. Caminhos:
1. Pedir autorização (uso pessoal/familiar, ~50 chamadas por rodada pelo MCP, 7 rodadas por dia, sem dados de
   anunciante). Se autorizarem, vira feature com o MCP como fonte (canal oficial, princípio III).
2. Uso interativo, que é o uso previsto: conectar o MCP do Chaves na Mão a um assistente de IA (por exemplo,
   como conector no Claude) e perguntar "apartamento 2 quartos até R$ 2.000 em BH, bairros X, Y".

## 2. Casa Mineira
- `robots.txt` (`*`) libera a busca; atrás de Cloudflare, mas **sem desafio** para cliente HTTP comum.
- `/aluguel/apartamento/centro_belo-horizonte_mg` → 200, 900 KB, 30 blocos JSON-LD com os imóveis e preços
  no HTML (sem JavaScript). URLs por bairro no sitemap (`sitemaps.casamineira.com.br`).
- É do mesmo grupo do Imovelweb e do QuintoAndar (Navent/QuintoAndar).
- **Termos** (lidos em 28/10/2026 pelo navegador, porque a página só renderiza com JavaScript;
  `help.casamineira.com.br/s/article/Termos-e-Condi%C3%A7%C3%B5es-de-Uso-CM`, versão de 25/06/2020). O item
  1.4.2 proíbe especificamente:
  > "O uso ou tentativa de uso de qualquer máquina, software, ferramenta, agente ou outro mecanismo para navegar
  > ou buscar neste Site que sejam diferentes das ferramentas de busca fornecidas pela CASA MINEIRA neste Site."

  **Decisão: fora.** É proibição expressa de robô, não zona cinzenta; só com autorização por escrito.

## 3. Lugar Certo (Estado de Minas)
- `robots.txt` com `Allow: /`, mas a home só renderiza com JavaScript e o índice de sitemaps de anúncios
  **não tem MG** (`sitemap_anuncio_mg.xml` → 404; há AL, BA, SP, RJ…). Sem estoque visível em BH. **Fora.**

## 4. Imovelweb
- Busca de aluguel em BH → **403 "Just a moment"** (Cloudflare). **Fora** (constituição III).

## 5. Revisão: termos do Netimóveis (spike 002)
Lidos em 28/10/2026 (`/termos-de-uso`). Não há proibição expressa de robôs, mas o item **3.4 "Meios para a
obtenção de Conteúdos"** diz:
> "O Usuário deverá abster-se de obter, ou tentar obter, informações, mensagens, gráficos, (...) e, em geral,
> qualquer tipo de material acessível através do Portal (...) empregando, para tanto, meios ou procedimentos
> diversos daqueles que possam ter sido disponibilizados ou indicados com este propósito nas páginas do Portal."

O robô lê as mesmas páginas públicas que um navegador, com `robots.txt` respeitado e baixo volume, mas um
cliente automatizado pode ser lido como "procedimento diverso". **Zona cinzenta:** a decisão de ligar
`NETIMOVEIS` é do dono. Opção mais segura: pedir autorização ao Netimóveis (contato no portal) antes de ligar.

## 6. Resumo

| Portal | Técnica | Termos | Situação |
|---|---|---|---|
| Netimóveis | ✅ HTML + JSON-LD, 1ª página | ⚠️ item 3.4 genérico | Implementado (005), **desligado**; decisão do dono |
| Chaves na Mão | ✅✅ MCP oficial, maior estoque | ❌ proíbe coleta automatizada | Só com autorização escrita; uso interativo é livre |
| Casa Mineira | ✅ HTML + JSON-LD | ❌ item 1.4.2 proíbe robôs | Fora (só com autorização escrita) |
| Lugar Certo | ❌ sem anúncios de MG | — | Fora |
| Imovelweb | ❌ desafio Cloudflare | — | Fora |
