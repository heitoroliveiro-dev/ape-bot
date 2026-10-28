# Contrato: interação no Telegram

## Comandos aceitos
| Entrada | Chat autorizado | Chat não autorizado |
|---|---|---|
| `/start` | Registra (idempotente) e responde confirmação + filtros | Silêncio; log `chat_nao_autorizado` |
| Qualquer outra mensagem | Resposta curta: "Eu aviso os imóveis nos horários 06, 09, 12, 15, 18, 21 e 23h." | Silêncio |

## Mensagens enviadas (texto, HTML do Telegram, sem pré-visualização de link)

**Confirmação de `/start`**
```
Pronto, {nome}! Vou te avisar de imóveis novos às 06, 09, 12, 15, 18, 21 e 23h.
Seus filtros: {bairros} · até R$ {aluguel_max} · {quartos_min}+ quartos · {tipos}
```

**Imóvel novo** (uma por imóvel)
```
🏠 {Tipo} · {Bairro}
{quartos} quartos · {area} m²
Aluguel: R$ {aluguel} · Total: R$ {total}
{url}
```
Campos ausentes → "não informado".

**Resumo (primeira rodada / filtros alterados)** — até 5 mensagens de ≤ 4.000 caracteres
```
Encontrei {N} imóveis com os seus filtros:
• {Bairro} · {quartos}q · R$ {aluguel} · {url}
…
(+{K} imóveis)        ← só se não couber
```
Sem resultados: `Ainda não achei imóveis com os seus filtros. Continuo procurando.`

**Operador — falha** (após 3 rodadas com falha; repetido a cada 24 h)
```
⚠️ ape-bot: {N} rodadas seguidas com falha. Último erro: {erro_resumo}
```
**Operador — recuperação**
```
✅ ape-bot voltou a funcionar ({data_hora}).
```
**Operador — configuração** (na inicialização, se houver problemas)
```
⚙️ filtros.yaml: {lista de problemas}
```

Valores monetários formatados `R$ 2.700`; horários em America/Sao_Paulo.
