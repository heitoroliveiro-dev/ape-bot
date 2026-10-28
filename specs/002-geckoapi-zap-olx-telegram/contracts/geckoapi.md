# Contrato: GeckoAPI (consumido)

Base `https://api.geckoapi.com.br`, autenticação `Authorization: Bearer {GECKO_API_KEY}`.
Docs lidas em 27/10/2026; respostas reais em `tests/fixtures/geckoapi/`.

## POST /v1/extract — Zap
```json
{
  "target": "zapimoveis.com.br", "type": "plp", "page": 1,
  "businessType": "rent", "state": "MG", "city": "Belo Horizonte",
  "priceMax": 3000, "bedrooms": [2, 3, 4],
  "propertyTypes": ["apartment", "penthouse", "condominium"]
}
```
`priceMax`, `bedrooms` e `propertyTypes` vêm dos filtros somados (research R2) e são omitidos quando
não restringem nada.

**Campos lidos** (`data.items[]`, 30 por página):

| Campo | Uso |
|---|---|
| `id` | `id_externo` |
| `url` | link |
| `business` | precisa ser `RENTAL` |
| `unitTypes[0]` | tipo (R2) |
| `address.city`, `address.state` | trava de localização (R5) |
| `address.neighborhood` | bairro (R6) |
| `attributes.bedrooms[0]` | quartos (obrigatório) |
| `attributes.usableAreas[0]` | área |
| `prices.rent` | aluguel (obrigatório) |
| `prices.condominium`, `prices.iptu` | total (R12) |
| `advertiser.name`, `advertiser.phoneNumbers[0]`, `advertiser.whatsAppNumber` | contato em trânsito (R7); nunca gravado |

## POST /v1/extract — OLX (desligada)
```json
{
  "target": "olx.com.br", "type": "plp", "page": 1,
  "state": "MG", "region": "Belo Horizonte e Regiao", "city": "Belo Horizonte",
  "categoryPath": "imoveis/aluguel", "sort": "date", "priceMax": 3000
}
```
**Campos lidos** (`data.items[]`, 50 por página): `id`, `url`, `price`, `location.city`,
`location.state`, `location.neighborhood` e `properties[]` por `name`: `condominio`, `iptu`,
`size`, `rooms`, `re_types`, `real_estate_type` (R4). Sem contato.

## Envelope e erros
| Situação | Resposta | Tratamento |
|---|---|---|
| Sucesso | `200 {requestId, executionId, data: {source, url, extractedAt, totalResults, items[]}}` | Parse; grava em `resposta_fonte` |
| Sem resultado | `200 {data: null, notFound: true}` | Falha da fonte (cobra crédito) |
| Sem crédito | `402 INSUFFICIENT_CREDITS` | `sem_credito`; para as fontes pagas até reiniciar; avisa o operador |
| Taxa | `429` | Falha da fonte, sem nova tentativa |
| Servidor | `5xx` | Uma nova tentativa (crédito estornado); depois, falha |
| Tempo esgotado (90 s) | — | Falha, sem nova tentativa |
| Chave inválida | `401` | Falha; aviso ao operador pelas regras de alerta |

## GET /v1/me/credits (só `/status` do operador)
`200 {currentCredits, creditsConsumed: {last24Hours, last7Days, last30Days}, …}`. Tempo limite de
10 s.
