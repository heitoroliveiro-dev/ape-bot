# Contrato: configuração (003)

## `filtros.yaml`
Passa a ser a **lista de autorizados**. Os filtros no arquivo são opcionais e servem só de semente
para quem ainda não tem cadastro (research R5).

```yaml
operador_chat_id: 8522143832      # obrigatório; precisa estar em pessoas

pessoas:
  - chat_id: 8522143832           # obrigatório, inteiro, único
    nome: Heitor                  # opcional (semente)
    filtros:                      # opcional (semente); mesmo formato da 001
      bairros: [prado, barroca]
      aluguel_max: 3000
      quartos_min: 2
      tipos: [apartamento, casa]
  - chat_id: 123456789            # autorizado; faz o cadastro pelo /start
```

| Situação | Comportamento |
|---|---|
| `chat_id` ausente, repetido ou não inteiro; operador fora de `pessoas` | Erro na subida (como na 001) |
| `filtros` ausente | Pessoa autorizada sem semente; cadastro pelo `/start` |
| `filtros` inválido (bairro desconhecido, valor ≤ 0 etc.) | Aviso ⚙️ como hoje; a pessoa **continua autorizada** e pode fazer o cadastro |
| `filtros` válido e a pessoa sem cadastro no banco | Semente: grava nome, filtros e cadastro completo na subida |
| `filtros` diferente do salvo para quem já tem cadastro | Aviso ⚙️ `{nome}: filtros do arquivo ignorados; vale o que a pessoa salvou no Telegram` |
| `chat_id` removido do arquivo | Deixa de receber tudo; dados mantidos |
| Bairro do arquivo que saiu do catálogo (6 de fora de BH) | Aviso ⚙️ `bairro não reconhecido`, como hoje |

## Variáveis no `.env` (e no `.env.example`)
| Variável | Padrão | Regra |
|---|---|---|
| `ENTREGA_INTERVALO` | `120-300` | **Nova.** Segundos entre dois imóveis da mesma pessoa, `min-max`, inteiros entre 1 e 3600, com min ≤ max. Inválido → aviso ⚙️ e padrão. Usar outro valor só para validar (quickstart) |

As variáveis da 002 (`GECKO_API_KEY`, `GECKO_FONTES`) não mudam.
