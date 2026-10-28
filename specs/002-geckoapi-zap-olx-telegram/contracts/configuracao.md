# Contrato: configuração (002)

O `filtros.yaml` não muda (`specs/001-mvp-quintoandar-telegram/contracts/filtros-yaml.md`).

## Variáveis novas no `.env` (e no `.env.example`, sem valor)
| Variável | Padrão | Regra |
|---|---|---|
| `GECKO_API_KEY` | vazio | Vazio → nenhuma fonte paga é chamada; aviso único ao operador na inicialização |
| `GECKO_FONTES` | `zap` | Lista separada por vírgula entre `zap` e `olx`. Valor desconhecido → aviso e ignorado. `olx` só deve ser ligada quando a GeckoAPI respeitar a localização |

`vivareal` não é aceito (constituição 2.2.0).
