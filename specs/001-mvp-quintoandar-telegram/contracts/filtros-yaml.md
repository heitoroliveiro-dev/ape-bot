# Contrato: `filtros.yaml` (configuração do operador)

```yaml
operador_chat_id: 123456789          # recebe avisos de falha; precisa estar em pessoas

pessoas:
  - nome: Heitor
    chat_id: 123456789
    filtros:
      bairros: [Buritis, Funcionários, santa-monica]   # nome ou slug do portal
      aluguel_max: 3000                                # reais, inteiro > 0
      quartos_min: 2                                   # inteiro >= 0
      tipos: [apartamento, casa_condominio]            # apartamento | casa | casa_condominio | kitnet

  - nome: Ana
    chat_id: 987654321
    filtros:
      bairros: [Sion, Anchieta]
      aluguel_max: 2500
      quartos_min: 1
      tipos: [apartamento]
```

## Regras de validação (na inicialização)
| Regra | Se violada |
|---|---|
| `operador_chat_id` presente e igual a algum `pessoas[].chat_id` | Erro fatal: o processo não sobe |
| `chat_id` inteiro e único | Erro fatal |
| Bairro reconhecido na lista de BH do portal (após normalização) | Bairro ignorado + aviso ao operador |
| `aluguel_max` inteiro > 0; `quartos_min` inteiro ≥ 0 | Pessoa ignorada + aviso ao operador |
| `tipos` ⊆ {apartamento, casa, casa_condominio, kitnet}, não vazio | Tipo inválido ignorado + aviso; vazio → pessoa ignorada |
| Pessoa sem nenhum bairro válido | Pessoa ignorada + aviso |

Chats autorizados = `pessoas[].chat_id`. Alterar o arquivo exige reiniciar o `app`.
