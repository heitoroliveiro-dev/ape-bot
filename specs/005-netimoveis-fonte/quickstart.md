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

## Resultado da validação (28/10/2026)
- **1. Testes**: `pytest` 369 passando (20 em `tests/test_netimoveis.py`); `ruff check` e `ruff format --check` limpos.
- **2. Sonda local** (IP residencial, 2 requisições):
  - `python -m apebot.fontes.netimoveis` → `status=200 total=39 lidos=21 anuncios=21 descartados={}` e
    `netimoveis_corte bairro=centro tipo=apartamento total=39 lidos=21`.
  - `python -m apebot.fontes.netimoveis funcionarios apartamento` → `status=200 total=43 lidos=21 anuncios=21`.
- **3. Sonda no Railway** (28/10/2026, 17:52, `railway ssh`): `erro=acesso: HTTP 403`. O Netimóveis bloqueia
  o IP do datacenter (do IP residencial a mesma URL dá 200). **`NETIMOVEIS` fica `desligado` em produção**;
  coletar de outro IP para escapar do bloqueio seria contorno (constituição III). Caminho: pedir autorização
  ao Netimóveis; se liberarem o acesso, basta `NETIMOVEIS=ligado`.
