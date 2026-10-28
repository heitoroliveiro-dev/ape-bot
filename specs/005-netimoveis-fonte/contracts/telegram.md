# Contrato: Telegram (005)

O nome exibido é **Netimóveis**. A ordem dos portais passa a ser QuintoAndar, Zap, OLX, Netimóveis.

## `/status`
Uma linha nova, no mesmo formato das outras fontes:

```
Netimóveis: ✅ ok
Netimóveis: ⚠️ falha (acesso: HTTP 403 …)
Netimóveis: ⏹️ desligado
Netimóveis: ⏳ aguardando a primeira rodada
```

## `/ajuda`
`Portais: QuintoAndar, Zap, Netimóveis` — o Netimóveis só aparece quando ligado.

## Mensagem de imóvel
Igual à da 003 (quartos no bairro, valor, link, botões "Abrir anúncio" e "⭐ Salvar como
favorito"); sem contato e sem botão de WhatsApp (o portal não é lido para contato). O link é a URL do
imóvel sem a query string.

## Resumo das 23h e `/favoritos`
`Netimóveis: N` entra na contagem por portal; favoritos do Netimóveis aparecem como os demais.

## Alertas ao operador
Os mesmos da 002 por fonte, com o nome Netimóveis: alerta após 3 rodadas seguidas com falha,
reaviso a cada 24 h e aviso de recuperação.
