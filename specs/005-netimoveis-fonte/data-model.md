# Data Model: Netimóveis (005)

Sem migração. Todas as tabelas que guardam fonte (`anuncio`, `envio`, `rodada_fonte`, `alerta`) já
usam `fonte VARCHAR(20)`; a nova fonte grava `netimoveis`.

## Anúncio (existente, `modelos.Anuncio`)

| Campo | Origem no Netimóveis | Regra |
|---|---|---|
| `fonte` | constante | `"netimoveis"` |
| `id_externo` | último segmento da URL do imóvel (`/{id}`) | só dígitos; senão `incompleto` |
| `tipo` | `{tipo_portal}` da URL, pelo mapa do research R3 | fora do mapa → `tipo_nao_aceito` |
| `bairro` / `bairro_slug` | `{bairro_portal}` da URL, sem `-(…)`, via `bairro_do_catalogo` | sem correspondência → `bairro_desconhecido` |
| `quartos` | `offers.itemOffered.numberOfBedrooms` | inteiro ≥ 0; ausente → `incompleto` |
| `area_m2` | `offers.itemOffered.floorSize.value` | inteiro > 0, senão `None` |
| `aluguel_centavos` | `offers.price` × 100 | inteiro > 0; ausente → `incompleto` |
| `total_centavos` | aluguel + condomínio ("Condominium Fee") quando houver | sem condomínio → `None` (IPTU fora) |
| `url` | URL do imóvel **sem a query string** | `https://www.netimoveis.com/imovel/...` |

Cidade: URL sem `-minas-gerais-belo-horizonte-` → `fora_da_cidade`.

Motivos de descarte contados em `ResultadoFonte.descartados`: `incompleto`, `fora_da_cidade`,
`tipo_nao_aceito`, `bairro_desconhecido`.

## Busca (em memória, por rodada)

| Campo | Descrição |
|---|---|
| `bairro_slug` | slug do catálogo, usado direto na URL |
| `tipo` | `Tipo` do robô; slug de busca: `apartamento`, `casa`, `casa-em-condominio`, `kitchenette` |
| `quartos_min` | menor mínimo entre as pessoas ativas; `0` → sem `?quartos=` |
| `total` | `ItemList.numberOfItems` (0 se não houver `ItemList`) |
| `lidos` | itens em `itemListElement` |
| `erro` / `erro_de_formato` | como em `quintoandar.ResultadoPagina` |

Corte: `total > lidos` → log `netimoveis_corte`.

## Resultado da fonte (existente, `ResultadoFonte`)

- `consultas` = número de buscas; `consultas_erro` = buscas com erro de acesso ou formato (busca vazia
  e 404 não são erro).
- `status` = `status_rodada(ok, erro, erro_de_formato)`; **e** `falha` quando todas as buscas
  voltaram 404 (research R4); `desligada` quando `NETIMOVEIS != ligado`.
- `contatos` sempre vazio (o portal não é lido para contato).

## Configuração (`config.Segredos`)

| Campo | Variável | Padrão | Inválido |
|---|---|---|---|
| `netimoveis` (`bool`) | `NETIMOVEIS` = `ligado` \| `desligado` | `desligado` | aviso ⚙️ ao operador; fica desligado |
