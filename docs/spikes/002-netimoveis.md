# Spike 002 — Netimóveis

> 28/10/2026 · Heitor Oliveiro · Apoio: Claude
> Resultado: **viável, mesmo modelo do QuintoAndar** (HTML público + JSON-LD, sem JavaScript, sem Cloudflare)
> Cliente: `curl` com `User-Agent: ape-bot/0.1 (uso pessoal; baixo volume)`, intervalo de 2–3 s; ~20 requisições no total

## 1. robots.txt (lido em 28/10/2026)
`User-agent: *` com `Allow: /`. Bloqueios relevantes: `/pesquisa/`, `/api/`, `/internal/` e os parâmetros
`pag=` (paginação), `precoMin=`, `precoMax=`, `areaMin=`, `areaMax=`, `ordem=`, `maisOpcoes=`, `banhos=`,
`vagas=`, além dos de campanha (`utm_*`, `gclid` etc.). `quartos=` **não** é bloqueado e aparece no próprio
sitemap. Publica `Sitemap: /sitemap.xml`. Nenhuma proteção antirrobô: `robots.txt`, busca e detalhe
responderam 200 ao cliente HTTP comum.

Consequência: **só a 1ª página** de cada busca (paginação é bloqueada) e **sem filtro de preço na URL**; o
preço é filtrado localmente, como já fazemos.

## 2. Superfícies permitidas que servem ao robô

| Superfície | URL | O que entrega | Limite |
|---|---|---|---|
| Busca por bairro e tipo | `/locacao/minas-gerais/belo-horizonte/bairros/{bairro}/{apartamento\|casa\|casa-em-condominio\|cobertura\|…}` | JSON-LD `ItemList` com o total (`numberOfItems`) e até **21** imóveis | Só a 1ª página; ordem de relevância (não há ordenação por data permitida) |
| Mesmo, com quartos | `…/{tipo}?quartos=N` | Recorte "N ou mais quartos" (conferido: `?quartos=2` trouxe 2 a 6 quartos) | Idem |
| Busca na cidade | `/locacao/minas-gerais/belo-horizonte/{tipo}` | Total da cidade: 1.074 apartamentos e 277 casas para alugar | Idem; serve só de referência |
| Sitemap de imóveis | `/sitemaps/sitemap-imoveis_{1..7}.xml` (~2 MB cada, 63 mil URLs, venda + locação) | Slug com transação, tipo, cidade e bairro: `/imovel/locacao-apartamento-minas-gerais-belo-horizonte-aeroporto/1188776` | Sem `lastmod` por imóvel; cobre ~85% da busca (914 de 1.074 apartamentos, 203 de 277 casas em BH) |
| Página do imóvel | `/imovel/{slug}/{id}` | JSON-LD `RealEstateListing`; condomínio e IPTU no HTML | Uma requisição por imóvel; sem data de publicação |

## 3. Campos (DoD)
Do JSON-LD da busca, sem precisar abrir o detalhe:
ID ✔ (fim da URL) · tipo ✔ (slug da URL e `itemOffered.@type`: `Apartment`, `House`…) · bairro ✔ (slug da URL) ·
quartos ✔ (`numberOfBedrooms`) · área ✔ (`floorSize.value`) · aluguel ✔ (`offers.price`) · condomínio ✔
(`additionalProperty` "Condominium Fee", às vezes ausente) · link ✔ · disponível ✔ (`availability: InStock`).
IPTU ✘ na busca (só no detalhe) · data de publicação ✘ em qualquer superfície · contato ✘ (não é necessário).

Bairros usam slugs próprios do portal (`santa-efigenia`, `sagrada-familia`, `funcionarios`); conferir contra o
catálogo `src/apebot/dados/bairros_bh.csv` e mapear as diferenças.

## 4. Estratégia de coleta proposta
1. **A cada rodada:** para cada bairro × tipo da união dos filtros das pessoas ativas, uma busca
   `…/bairros/{bairro}/{tipo}?quartos={mínimo}` (1ª página). Com os bairros de hoje (Larissa 39 + Heitor 21,
   com sobreposição) e 2 tipos: ~100 requisições por rodada, como o QuintoAndar (78 hoje), com intervalo de
   alguns segundos.
2. **Corte de 21:** a maioria dos bairros cabe numa página (Santa Efigênia 19, Sagrada Família 18, Floresta 13,
   Centro 23, Funcionários 31 com 2+ quartos). Quando `numberOfItems > 21`, registrar no log; os que ficarem de
   fora podem vir do sitemap (passo 3), se fizer falta.
3. **Opcional, diário:** baixar os 7 sitemaps (~14 MB), filtrar `locacao-` + BH + tipo + bairro e tratar IDs novos
   como candidatos; buscar o detalhe só desses. Só vale se o corte de 21 se mostrar um problema real.
4. Filtro de preço, quartos e tipo continua local (`filtro.aceita`). Preço do portal = aluguel; condomínio quando vier.

**Rendimento esperado para a Larissa** (amostra de 4 bairros dela, apartamento 2+ quartos, aluguel ≤ R$ 2.000):
4 imóveis (Floresta R$ 1.600; Centro R$ 1.400, R$ 1.650 e R$ 2.000). Inventário de imobiliárias tradicionais
de BH, diferente do QuintoAndar, então deve somar mais do que repetir.

## 5. Ressalvas
- **Sem paginação e sem data:** um imóvel novo que não entre nas 21 primeiras do bairro só aparece se a
  relevância o puser lá (ou pelo sitemap). Não dá para ordenar por recentes (`ordem=` bloqueado).
- **Duplicidade:** o mesmo imóvel pode estar no Netimóveis e no QuintoAndar ou Zap com IDs diferentes. A chave
  `(fonte, id_externo)` não deduplica entre portais; avaliar depois se incomoda.
- **Termos de uso ainda não lidos** (pendente: leitura humana, como no QuintoAndar).
- O formato do JSON-LD pode mudar. Mitigação: fixtures e teste de parse, como nas outras fontes.
- O JSON-LD é feito para buscadores (schema.org); usá-lo é ler a página pública, não uma API interna.

## 6. Próximo passo
Feature nova (`004-netimoveis`): coletor `fontes/netimoveis.py` no formato `ResultadoFonte`, mapa de bairros
para o catálogo, fixtures de uma busca e de um bairro com mais de 21, e a fonte ligada por configuração. Sem
custo de crédito.
