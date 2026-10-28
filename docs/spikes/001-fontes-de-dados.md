# Spike 001 — Fontes de dados (QuintoAndar e OLX)

> 27/10/2026 · Heitor Oliveiro · Apoio: Claude
> Resultado: **QuintoAndar viável com ressalvas** · **OLX inviável sem burlar proteção (fora do MVP)**
> Fixtures: `tests/fixtures/quintoandar/`

## 1. QuintoAndar

### 1.1 robots.txt (lido em 27/10/2026)
`User-agent: *` com `Allow: /`. Bloqueios relevantes: `/busca`, `/favoritos`, `/alertas`, `*/indisponivel*`, `/classificado*`, `/imovel/*/detalhes-*`, e os parâmetros `?filters=true`, `?search_id=`, `?redirect`, `?portfolio_ref=`, `?agent_search_mode=` nas URLs de busca. Publica `Sitemap: /sitemap-v3.xml`.

### 1.2 Superfícies permitidas que servem ao robô

| Superfície | URL | O que entrega | Limite |
|---|---|---|---|
| Sitemap de anúncios | `/sitemap-v3-listings-part-000N.xml` (7 partes de até 50 mil URLs) | Todos os anúncios do Brasil. O slug traz tipo, quartos, bairro e cidade: `/imovel/892842625/alugar/apartamento-2-quartos-carlos-prates-belo-horizonte` | Atualizado **uma vez por dia** (todos os `lastmod` = dia anterior) |
| Página de busca por cidade/bairro | `/alugar/imovel/{bairro}-belo-horizonte-mg-brasil` (289 bairros de BH no sitemap) | JSON `__NEXT_DATA__` com 24 imóveis e o total (ex.: Funcionários 499, Buritis 379, BH 3.636) | Só a **1ª página**, ordenada por relevância. As demais vêm de uma API interna, que **não** será usada (princípio de coleta respeitosa) |
| Filtros por caminho | `/alugar/imovel/{local}/{apartamento\|casa\|casacondominio\|kitnet}/{N}-quartos` | Mesmo formato, recorte menor | Mesmo limite de 24 |
| Página do imóvel | `/imovel/{id}` | `rentPrice`, `totalCost`, `condoPrice`, `iptu`, `bedrooms`, `area`, `status` (`"publicado"`) | Uma requisição por imóvel |

### 1.3 Campos (DoD)
ID ✔ · tipo ✔ (`Apartamento`, `Casa`, `CasaCondominio`, `StudioOuKitchenette`) · bairro ✔ (`neighbourhood`) · quartos ✔ · área ✔ · aluguel ✔ (`rentPrice`) · total ✔ (`totalCost` = aluguel + condomínio + IPTU + taxas) · condomínio ✔ · IPTU ✔ · link ✔ · status ✔.

### 1.4 Estratégia de coleta proposta
1. **Diária (madrugada):** baixar as 7 partes do sitemap de anúncios (~3,5 MB) e extrair os de aluguel em BH. IDs que não existiam no dia anterior são **novos**. O slug já permite um pré-filtro (tipo, quartos, bairro) contra a união das buscas dos usuários.
2. **A cada rodada (7 por dia):** visitar as páginas de bairro dos bairros escolhidos pelos usuários (uma requisição por bairro, intervalo de alguns segundos). Pega novidades que aparecem nas 24 primeiras antes do sitemap do dia seguinte.
3. **Detalhe:** buscar `/imovel/{id}` só para os candidatos que passaram no pré-filtro, para obter preço e encargos.
4. **Favoritos (a cada 30 min):** `/imovel/{id}`. Status diferente de `publicado`, ou redirecionamento para `*/indisponivel*` (detectado pelo `Location`, **sem seguir** a URL bloqueada), gera o aviso de "imóvel não encontrado".

**Volume estimado:** dezenas de requisições por rodada. Bem abaixo de qualquer uso abusivo.

### 1.5 Ressalvas
- **Atraso de até 1 dia** para imóveis que não entram nas 24 primeiras do bairro. Para a usuária, a rodada das 06h traz o "lote do dia", e as demais trazem o que surgiu em destaque.
- Os 3.636 imóveis da busca de BH incluem 1.036 classificados (`/classificado*`, bloqueado). O sitemap cobre os transacionais. Classificados ficam fora.
- **Termos de uso ainda não lidos** (pendente: leitura humana).
- O formato do `__NEXT_DATA__` pode mudar sem aviso. Mitigação: fixtures e teste de parse (RNF04).

## 2. OLX
`robots.txt` respondeu **403 (Cloudflare "Attention Required")** a um cliente HTTP comum, inclusive de um segundo IP. Coletar exigiria contornar a proteção antirrobô (navegador automatizado, falsificação de impressão digital), o que contraria a constituição. **Decisão: OLX sai do MVP.** A porta `FonteDeAnuncios` continua pronta para uma segunda fonte. Candidatas a avaliar num próximo spike: Netimóveis (forte em BH), Zap/VivaReal.

## 2.1 VivaReal e Zap Imóveis (27/10/2026)
`robots.txt` dos dois respondeu **403 (Cloudflare "Attention Required", com captcha)**, igual à OLX. Os três são do mesmo grupo (OLX Brasil). Sem acesso nem ao robots.txt, não há superfície pública utilizável sem contornar a proteção.

## 2.2 "Feeds XML" de portais
- Os feeds XML do mercado (ex.: formato VRSync) são de **entrada**: a imobiliária envia o estoque para o portal. Não existe feed público de **saída** para consumidores.
- O equivalente de saída é o **sitemap**, e só o QuintoAndar o expõe para nós (seção 1.2).
- O actor da Apify [`makemakers/viva-real-scraper`](https://apify.com/makemakers/viva-real-scraper) não documenta o método de coleta. Cobre só o VivaReal, cobra por uso da plataforma, é mantido pela comunidade e tem nota 3,0 com 0 usuários mensais. Usá-lo terceiriza o contorno da proteção, sem eliminá-lo.
- **Alternativa sem raspagem:** os **alertas nativos** dos portais (busca salva com aviso por e-mail), lidos de uma caixa de e-mail dedicada e repassados ao Telegram. **A existência e o formato atuais desses alertas não foram confirmados** e precisam de verificação manual em cada portal.

## 3. Catálogo de bairros
- **QuintoAndar:** 289 bairros de BH (sitemap), com slugs próprios, ex.: `bandeirantes-pampulha`, `aparecida-7a-secao`, `savassi` (lista em `tests/fixtures/quintoandar/bairros-bh-sitemap.txt`).
- **PBH:** dataset [Bairro oficial](https://dados.pbh.gov.br/dataset/bairro-oficial) (CSV com `CODIGO`, `TIPO`, `NOME`, `GEOMETRIA`, snapshot mais recente encontrado de 2023). **Não traz a regional.** O mapeamento bairro → regional exige cruzar a geometria com o dataset de regionais. O portal da PBH bloqueou o acesso automatizado (403): os arquivos precisam ser baixados pelo navegador.

**Proposta:** catálogo oficial PBH (bairro + regional) gerado **uma vez** e versionado em CSV no repositório, mais uma tabela de **apelidos** (nome no portal → bairro oficial) mantida à mão. Anúncio sem correspondência é descartado e contado (RF14), e os nomes não reconhecidos aparecem no log da rodada e num resumo ao desenvolvedor para virar apelido.

## 4. Pendências
- [ ] Ler os termos de uso do QuintoAndar e registrar a decisão.
- [ ] Baixar pelo navegador os CSVs de bairros oficiais e regionais da PBH.
- [ ] Cruzar os 289 bairros do QuintoAndar com o catálogo oficial e medir o percentual sem correspondência.
- [ ] Medir quantos imóveis novos de aluguel em BH surgem por dia no sitemap (2 dias seguidos).
