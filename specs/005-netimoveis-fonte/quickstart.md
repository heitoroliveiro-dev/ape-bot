# Quickstart: validar o Netimóveis (005)

## 1. Testes (sem internet)
```bash
.venv/bin/pytest -q tests/test_netimoveis.py
.venv/bin/pytest -q && .venv/bin/ruff check src tests
```
Esperado: parse das fixtures de `tests/fixtures/netimoveis/` (corte 31 → 21, kitnet, busca vazia,
formato inválido), mapa de tipos e bairros, `NETIMOVEIS` ligado/desligado/inválido e o nome
Netimóveis em `/status`, `/ajuda` e resumo.

## 2. Sonda local (1 requisição)
```bash
docker compose run --rm app python -m apebot.fontes.netimoveis
```
Esperado: `status=200 total=… lidos=… anuncios=…`.

## 3. Sonda no Railway (IP do datacenter)
No shell do serviço do app no Railway:
```bash
python -m apebot.fontes.netimoveis
```
- `status=200` com `lidos > 0` → pode ligar.
- 403, página de desafio ou timeout → **não ligar**; registrar no spike e manter desligado.

## 4. Ligar e acompanhar uma rodada
Pré-requisito: termos de uso do Netimóveis lidos e sonda do passo 3 ok.
1. Nas variáveis do serviço no Railway: `NETIMOVEIS=ligado` (o serviço reinicia).
2. Logs do serviço: `fontes_ligadas quintoandar,zap,netimoveis`.
3. Na próxima rodada: `fonte_fim fonte=netimoveis status=ok consultas=~100 anuncios=… descartados={…}`,
   eventualmente `netimoveis_corte bairro=funcionarios tipo=apartamento total=31 lidos=21`.
4. `/status` mostra `Netimóveis: ✅ ok`; `/ajuda` lista o Netimóveis.
5. Imóveis do Netimóveis chegam pela fila, espaçados, das 8h às 22h; resumo das 23h com `Netimóveis: N`.

## 5. Desligar sem deploy
`NETIMOVEIS=desligado` no Railway → próxima rodada sem `fonte=netimoveis` acessando a rede;
`rodada_fonte` com `desligada`; `/status` com `⏹️ desligado`.
