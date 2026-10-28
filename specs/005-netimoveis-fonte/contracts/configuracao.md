# Contrato: configuração (005)

## Variável `NETIMOVEIS` (no `.env`, no `.env.example` e nas variáveis do serviço no Railway)

| Valor | Comportamento |
|---|---|
| ausente | Fonte desligada (padrão até ler os termos de uso e validar o IP do Railway) |
| `ligado` | Coletor do Netimóveis roda em toda rodada com pessoas ativas |
| `desligado` | Nenhuma página do Netimóveis é acessada; `rodada_fonte` registra `desligada` |
| outro valor | Aviso ⚙️ ao operador na subida: `NETIMOVEIS: valor desconhecido '{valor}'; Netimóveis desligado`; fica desligado |

Maiúsculas/minúsculas e espaços nas pontas são ignorados. A mudança vale no próximo início do
processo (no Railway, salvar a variável reinicia o serviço). `--simular-falha` não afeta o
Netimóveis além do que já faz com o QuintoAndar: com a flag, a fonte simula erro de acesso em todas as
buscas sem acessar a rede.

## Sonda

```bash
python -m apebot.fontes.netimoveis            # Centro / apartamento
python -m apebot.fontes.netimoveis savassi casa
```

Faz uma única busca e imprime `status=<HTTP> total=<n> lidos=<n> anuncios=<n> descartados={...}` ou
o erro. Não lê nem grava banco, Redis ou Telegram e funciona com `NETIMOVEIS` desligado. Saída 0 se
a busca respondeu, 1 se houve erro de acesso ou formato.
