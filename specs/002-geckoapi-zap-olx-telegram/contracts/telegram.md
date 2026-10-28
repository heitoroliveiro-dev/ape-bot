# Contrato: interação no Telegram (002)

Estende `specs/001-mvp-quintoandar-telegram/contracts/telegram.md`. HTML do Telegram, sem
pré-visualização de link. Chats não autorizados: silêncio em tudo.

## Menu de comandos (`set_my_commands`)
| Comando | Descrição no menu |
|---|---|
| `/ajuda` | Como o robô funciona |
| `/filtros` | Ver meus filtros |
| `/status` | Última rodada e portais |
| `/pausar` | Pausar os avisos |
| `/retomar` | Voltar a receber avisos |

## Comandos
| Entrada | Resposta (chat autorizado) |
|---|---|
| `/start` | Como na 001; se pausada, acrescenta a linha `Seus avisos estão pausados. Use /retomar para voltar.` |
| `/ajuda` | Texto **Ajuda** abaixo |
| `/filtros` | Texto **Filtros** abaixo |
| `/status` | Texto **Status** abaixo |
| `/pausar` | `⏸️ Avisos pausados. Use /retomar quando quiser voltar.` (idempotente) |
| `/retomar` | `▶️ Avisos retomados. Na próxima rodada eu te mando um resumo do que estiver disponível.` (idempotente) |
| Outra mensagem | `Eu aviso os imóveis às 06, 09, 12, 15, 18, 21 e 23h. Envie /ajuda para ver os comandos.` |

Operador sem filtros válidos: `/filtros` e `/pausar` respondem `Você está sem filtros válidos.`.

**Ajuda**
```
🤖 Eu procuro imóveis para alugar em BH e te aviso dos novos às 06, 09, 12, 15, 18, 21 e 23h.
Portais: {QuintoAndar, Zap}          ← só os ligados
/filtros — ver seus filtros
/status — última rodada e portais
/pausar — parar os avisos por um tempo
/retomar — voltar a receber
```

**Filtros**
```
Seus filtros: {bairros} · até R$ {aluguel_max} · {quartos_min}+ quartos · {tipos}
Avisos: {ativos | pausados desde DD/MM HH:MM}
Para mudar os filtros, fale com {nome do operador}.
```

**Status**
```
📊 Última rodada: DD/MM HH:MM · próxima: HH:MM
Você recebeu {N} imóveis nas últimas 24 h.
QuintoAndar: ✅ ok
Zap: ✅ ok | ⚠️ falha ({erro curto}) | ⏹️ desligado | 💳 sem crédito
OLX: ⏹️ desligado
💳 Créditos: {currentCredits} (gastos em 24 h: {last24Hours})   ← só para o operador
```
Sem rodada ainda: `Ainda não houve rodada.`. Saldo com erro: `💳 Créditos: saldo indisponível`.

## Mensagem de imóvel (uma por imóvel)
```
🏠 {Tipo} · {Bairro} · {Portal}
{quartos} quartos · {area} m²
Aluguel: R$ {aluguel} · Total: R$ {total}
👤 {nome do anunciante}               ← só se houver
📞 {telefone}                         ← só se houver
```
Botões (uma linha): `[Abrir anúncio → {url}]` `[WhatsApp → https://wa.me/55{número}]` (o
segundo só com WhatsApp válido, research R7). Campo ausente → "não informado". O link deixa de
ir no texto, porque está no botão.

Reenvio a partir do banco (pendente antigo): mesmo formato, sem 👤/📞 e sem WhatsApp.

## Resumo
Como na 001, com o portal em cada linha:
```
• {Bairro} · {quartos}q · R$ {aluguel} · {Portal} · {url}
```

## Operador
**Falha por fonte** (3 rodadas seguidas com falha naquela fonte; repete a cada 24 h)
```
⚠️ ape-bot: {Portal} com falha em {N} rodadas seguidas. Último erro: {erro_resumo}
```
**Recuperação**
```
✅ ape-bot: {Portal} voltou a funcionar ({data_hora}).
```
**Sem crédito** (imediato, uma vez por processo)
```
💳 ape-bot: a GeckoAPI recusou por falta de créditos. Zap/OLX parados até reiniciar o robô.
```
**Configuração** (na inicialização): como na 001, mais `GECKO_API_KEY ausente: Zap/OLX
desligados` e `GECKO_FONTES: valor desconhecido '{x}' ignorado`.
