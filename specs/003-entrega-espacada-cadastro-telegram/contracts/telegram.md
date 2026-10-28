# Contrato: interação no Telegram (003)

Substitui as partes correspondentes de `specs/002-geckoapi-zap-olx-telegram/contracts/telegram.md`.
HTML do Telegram, sem prévia de link. Chats não autorizados: silêncio em tudo, inclusive em toques
de botão. Valores sempre como `R$ 1.234,56` (research R7).

## Menu de comandos (`set_my_commands`)
| Comando | Descrição no menu |
|---|---|
| `/ajuda` | Como o robô funciona |
| `/filtros` | Ver e editar meus filtros |
| `/favoritos` | Imóveis que salvei |
| `/status` | Última rodada e portais |
| `/pausar` | Pausar os avisos |
| `/retomar` | Voltar a receber avisos |

## Mensagem de imóvel (entrega espaçada)
```
Veja o imóvel que encontrei:
{q} quartos no bairro {Bairro}          ← "1 quarto"; com 0 quartos: "{Tipo} no bairro {Bairro}"
Valor: R$ {aluguel}
Link: {url}
👤 {nome do anunciante}                 ← só com contato em trânsito
📞 {telefone}                           ← idem
```
Teclado:
```
[Abrir anúncio → url] [WhatsApp → https://wa.me/55…]   ← WhatsApp só com número válido
[⭐ Salvar como favorito]                               ← callback f:{fonte}:{id_externo}
```
Depois de salvar, o botão vira `[✅ Favorito · toque para remover]`; depois de remover, volta ao
original. O toque responde com um aviso curto (`answerCallbackQuery`): `⭐ Salvo nos favoritos` /
`Removido dos favoritos`.

Ritmo: 1 por pessoa a cada 2–5 min sorteados, só de 08:00 a 21:59, do mais barato para o mais
caro. A mensagem-resumo em lista da 001/002 deixa de existir.

## Cadastro (`/start` de chat autorizado sem cadastro)

| Etapa | Mensagem do robô | Entrada aceita |
|---|---|---|
| nome | `Oi! Eu procuro imóveis para alugar em BH e te aviso por aqui. Como devo te chamar?` | Texto (R8). Inválido: `Me diga um nome com letras, de até 40 caracteres.` |
| tipos | `Você busca quais tipos de imóveis? Marque um ou mais e toque em Continuar.` | Botões, múltipla escolha: `Apartamento` `Casa` `Casa em condomínio` `Kitnet/Studio` (marcado: `✅ Apartamento`); `[Continuar ▶]`. Sem tipo marcado: aviso `Marque pelo menos um tipo.` |
| quartos | `Quantos quartos, no mínimo?` | Botões: `Tanto faz` `1` `2` `3` `4 ou mais` (escolha única; o toque já avança) |
| regionais | `Em quais bairros? Escolha uma regional para ver os bairros dela. Você já marcou {n} bairros.` | 9 botões de regional (+ `Outros`), cada um com `({marcados})` quando houver; `[Continuar ▶]` só com pelo menos 1 bairro marcado |
| bairros | `{Regional}: toque para marcar ou desmarcar. Página {p}/{t}.` | Até 24 bairros (2 por linha), `✅` nos marcados; `[◀]` `[▶]`; `[Marcar todos]`/`[Desmarcar todos]` da regional; `[↩ Regionais]` |
| valor | `Qual valor máximo de aluguel? Exemplos: 2500, 2.500 ou R$ 2.500,00` | Texto (R7). Inválido: `Não entendi esse valor. Escreva só o número, como 2500 ou 2.500,00, entre R$ 300 e R$ 50.000.` |
| fim | `Perfeito, {nome}! Vou te ajudar a encontrar um imóvel com sua cara para alugar! Durante o dia vou te enviar o que achar por aqui, fique atento(a).` | — |

- Texto enviado numa etapa de botões: `Use os botões da mensagem acima. 👆` e repete a etapa.
- Toque num botão de etapa que já passou: aviso `Essa pergunta já passou.`, sem mudança.
- `/start` ou texto com o cadastro aberto: reapresenta a etapa atual (retomada).
- `/start` de quem já tem cadastro: o texto **Filtros** abaixo, com o botão `Editar filtros`.
- `/filtros`, `/favoritos`, `/status`, `/pausar` e `/retomar` com o cadastro aberto:
  `Termine o cadastro primeiro: /start`.

## Filtros (`/filtros`)
```
Seus filtros -
Bairros: {Bairro A}, {Bairro B}, …          ← nomes do catálogo, em ordem alfabética
Valores até R$ {aluguel_max}
{Apartamento, Casa, Casa em condomínio} com {q}+ quartos   ← "com qualquer número de quartos" se 0
Avisos: {ativos | pausados desde DD/MM HH:MM}
```
Teclado: `[✏️ Editar filtros]` (callback `e:inicio`).

## Edição (`Editar filtros`)
Mesmas etapas e textos do cadastro, de **tipos** a **valor**, com as respostas atuais marcadas; na
etapa valor, a mensagem mostra também `Atual: R$ {aluguel_max}. Envie um novo valor ou toque em
Manter.`, com o botão `[Manter]`. Todas as mensagens têm `[✖ Cancelar]`.

| Etapa | Mensagem | Botões |
|---|---|---|
| revisao | O texto **Filtros** com os valores novos, encabeçado por `Confere?` | `[💾 Salvar]` `[✖ Cancelar]` |
| salvo | `Filtros salvos! Eles valem a partir da próxima rodada ({HH:MM}).` | — |
| cancelado | `Edição cancelada. Seus filtros continuam os mesmos.` | — |

## Favoritos (`/favoritos`)
```
⭐ Seus favoritos ({n}):
⭐ {q} quartos · {Bairro} · R$ {aluguel} · {Portal}
{url}
…
```
Mais recente primeiro; dividido em blocos de até 4.000 caracteres, sem cortar item. Sem favoritos:
`Você ainda não tem favoritos. Toque em "⭐ Salvar como favorito" numa mensagem de imóvel.`

## Resumo diário (depois da rodada das 23h, pessoas ativas)
```
📊 Última rodada: DD/MM HH:MM · próxima: HH:MM
Você recebeu {N} imóveis nas últimas 24 h.
QuintoAndar: {n}
Zap: {n}
OLX: {n}
💳 Créditos: {currentCredits} (gastos em 24 h: {last24Hours})
```
Saldo com erro: `💳 Créditos: saldo indisponível`. Sem GeckoAPI configurada: linha omitida.
"1 imóvel" no singular.

## Status (`/status`)
Como na 002, com a linha `💳 Créditos` para **todas** as pessoas (mesma regra do resumo) e uma
linha a mais: `Na sua fila: {n} imóveis (envio das 8h às 22h).`

## Ajuda (`/ajuda`)
```
🤖 Eu procuro imóveis para alugar em BH nas rodadas das 06, 09, 12, 15, 18, 21 e 23h.
Te mando um imóvel por vez, das 8h às 22h, começando pelos mais baratos.
Às 23h chega um resumo do dia.
Portais: {QuintoAndar, Zap}
/filtros — ver e editar seus filtros
/favoritos — imóveis que você salvou
/status — última rodada e portais
/pausar — parar os avisos por um tempo
/retomar — voltar a receber
```

## Outras respostas
| Entrada | Resposta |
|---|---|
| `/pausar` | `⏸️ Avisos pausados. Use /retomar quando quiser voltar.` (idempotente) |
| `/retomar` | `▶️ Avisos retomados. Na próxima rodada eu volto a te mandar o que encontrar.` |
| Texto livre, sem conversa aberta | `Eu te mando os imóveis por aqui, das 8h às 22h. Envie /ajuda para ver os comandos.` |

## Operador
Como na 002, mais os avisos ⚙️ de [configuracao.md](configuracao.md).
