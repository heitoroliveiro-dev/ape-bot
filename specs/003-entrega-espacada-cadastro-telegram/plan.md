# Implementation Plan: Entrega espaçada, favoritos, resumo diário e filtros pelo Telegram

**Branch**: `003-entrega-espacada-cadastro-telegram` | **Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-entrega-espacada-cadastro-telegram/spec.md`

## Summary

A rodada deixa de mandar mensagens. Ela coloca cada imóvel novo numa fila **por pessoa** no Redis,
ordenada por valor e com o contato em trânsito. Um **despachante** no processo do bot tira um
imóvel por pessoa a cada 2–5 min sorteados, só das 8h às 22h. Antes de enviar, ele confere de novo
o filtro atual da pessoa e passa a mensagem para a fila de entrega da 002, que continua com o
limite de taxa e as novas tentativas. A lista-resumo sai.

Os filtros e o nome passam a ficar no MySQL. O `filtros.yaml` vira a lista de autorizados e a
semente de quem ainda não tem cadastro. O cadastro e a edição são uma máquina de estados pura
(`cadastro.py`), com o estado no MySQL, e a escolha de bairro é feita por regional. O catálogo de
bairros ganha nome oficial e regional a partir do PDF da PBH.

Entram também os favoritos (botão na mensagem e `/favoritos`), o resumo depois da rodada das 23h
(com créditos para todos) e o valor sempre como `R$ x.xxx,xx`. Detalhes em
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: as da 002 (httpx, beautifulsoup4, python-telegram-bot[job-queue],
redis, PyMySQL, PyYAML, tzdata). Nenhuma nova. `pdftotext` (poppler) só no script de geração
da tabela de regionais, fora do robô.

**Storage**: MySQL 8.4 (migração 004: colunas novas em `pessoa`; tabelas `conversa`, `favorito`
e `resumo_diario`); Redis 7 com AOF (fila por pessoa: ZSET + HASH + `proximo`;
`apebot:envios` como antes)

**Testing**: pytest sem rede: leitura de valor e nome, transições do cadastro e da edição,
despachante (janela, ordem, intervalo, refiltragem) com relógio e Redis falsos, reconciliação,
catálogo de regionais, textos do contrato e resumo; ruff

**Target Platform**: Linux, Docker Compose na máquina do operador

**Project Type**: serviço de longa duração (bot + agendador + entregador + despachante num
processo)

**Performance Goals**: despachante acorda a cada 20 s; a primeira mensagem sai em até 20 s depois
da rodada; uma volta do despachante com 5 pessoas termina em menos de 1 s

**Constraints**: ≤ 1 imóvel por pessoa a cada 120–300 s; nada de imóvel fora de 08:00–21:59
(America/Sao_Paulo); contato do anunciante só no Redis até a entrega; `callback_data` ≤ 64
bytes; nenhuma chamada paga a mais (a consulta de créditos não gasta)

**Scale/Scope**: até 5 pessoas; até ~240 imóveis por pessoa por dia de janela; 283 bairros em 9
regionais (+ Outros); 1 comando novo (`/favoritos`) e 2 fluxos de conversa

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Verificação | Status |
|---|---|---|
| I. Simples Primeiro | Escopo novo registrado em `docs/arquitetura.md` (v1.3, seção 2.1) antes do plano. Um módulo novo, `cadastro.py` (regra pura da conversa e validações); o despachante fica ao lado do `Entregador`, e a fila por pessoa em `fila.py`. Sem framework de conversa, sem dependência nova. Duas complexidades justificadas abaixo | ✅ |
| II. Testes Onde Quebra | Testes nos pontos que quebram: leitura do valor (dinheiro em centavos, `int`), nome, transições, despacho e reconciliação, catálogo gerado do PDF. Sem rede. Nenhuma fonte nova, então nenhuma fixture nova | ✅ |
| III. Coleta Respeitosa | Nenhuma coleta nova; a GeckoAPI continua com 1 chamada por fonte por rodada, com os filtros somados (agora lidos do MySQL). O contato fica só no Redis (fila da pessoa → fila de entrega) até a entrega, e o reenvio a partir do banco sai sem contato. `favorito`, `conversa` e `resumo_diario` não guardam dado de anunciante. O PDF da PBH foi baixado à mão pelo navegador (o portal bloqueia acesso automatizado; nenhum contorno foi feito) | ✅ |
| IV. Segredos e Acesso | Acesso continua em lista fechada (`filtros.yaml`); toques de botão passam pela mesma barreira de chat autorizado. Nenhum segredo novo. O saldo de créditos para todos é decisão do dono, não expõe chave | ✅ |
| V. Operação Confiável | Toda mensagem continua passando por `apebot:envios` (limite de taxa, `RetryAfter`, 3 tentativas). A janela e o dia do resumo são calculados em America/Sao_Paulo. Logs novos: `imovel_enfileirado`, `imovel_despachado`, `imovel_descartado_filtro`, `reconciliacao`, `resumo_enviado`. A falha do despachante numa pessoa não para as outras | ✅ |

**Pós-design (Phase 1)**: reavaliado depois do data-model e dos contratos, sem violações. Riscos
aceitos e documentados: (1) o contato pode ficar horas, ou dias se o volume passar da janela, no
AOF do Redis; continua sendo "trânsito pela fila", e `/pausar` limpa a fila da pessoa. (2) Sem
resumo no dia em que o robô estiver fora do ar às 23h e voltar depois da tolerância de 5 min
(research R12).

## Project Structure

### Documentation (this feature)

```text
specs/003-entrega-espacada-cadastro-telegram/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── telegram.md
│   └── configuracao.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/apebot/
├── cadastro.py          # NOVO: etapas, transições, teclados (dados), ler_valor, limpar_nome
├── config.py            # filtros.yaml como autorizados + semente; catalogo_bairros(); ENTREGA_INTERVALO
├── modelos.py           # + Bairro, REGIONAIS
├── dados/bairros_bh.csv # NOVO (substitui bairros_bh.txt): slug,nome,regional
├── banco.py             # pessoas_ativas, semente, filtros JSON, conversa, favorito, resumo_diario,
│                        #   pendentes por pessoa, apagar pendente, recebidos por fonte
├── fila.py              # + FilaPessoa (ZSET/HASH/proximo); Mensagem.botoes em linhas
├── rodada.py            # sem modo resumo: enfileira por pessoa; enviar_resumos()
├── mensagens.py         # textos do contrato 003; formatar_reais com centavos; nome do bairro
├── telegram_bot.py      # + CallbackQueryHandler (cadastro, edição, favorito), /favoritos;
│                        #   Despachante e reconciliação ao lado do Entregador
└── main.py              # lê pessoas do banco; resumo depois da rodada das 23h; sobe o despachante
migrations/
└── 004_cadastro_entrega.sql
scripts/
└── regionais_pbh.py     # NOVO, fora do pacote: PDF → bairros_bh.csv (roda uma vez)
docs/
├── arquitetura.md       # seções 3–6 atualizadas na entrega
└── referencias/pbh-bairros-regionais.pdf
tests/
├── test_cadastro.py     # NOVO: valor, nome, transições, botões velhos
├── test_despacho.py     # NOVO: janela, ordem, intervalo, refiltragem, reconciliação
├── test_catalogo.py     # NOVO: regionais, exclusões, bairros do filtro atual
├── test_config.py       # autorizados sem filtros; semente
├── test_mensagens.py    # textos novos
├── test_rodada.py       # sem resumo; enfileira por pessoa; resumo diário
└── test_filtro.py       # sem hash_filtros
```

**Structure Decision**: continua um projeto único com módulos planos (constituição I). O
`cadastro.py` existe porque a regra da conversa é o ponto que mais vai quebrar com a interação de
gente de verdade, e isolada do Telegram ela é testável (princípio II). O despachante fica no
`telegram_bot.py`, junto do `Entregador`, porque os dois são o lado "trabalhador" da fila.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Fila por pessoa (ZSET + HASH + `proximo`) e despachante, além da fila de entrega | Ordem por valor, intervalo independente por pessoa, janela de horário e contato em trânsito sobrevivendo a reinício (FR-002 a FR-006) | A lista FIFO única não ordena por valor e, dormindo 2–5 min, trava todas as pessoas; usar o MySQL como fila perde o contato, que não pode ir ao banco |
| Estado de conversa no MySQL com máquina de estados própria | Cadastro retomável depois de reiniciar (FR-023) e testável sem Telegram | `ConversationHandler` + `PicklePersistence` exige arquivo e volume novos, guarda estado fora do banco e mistura regra com framework; `user_data` em memória perde tudo no reinício |
