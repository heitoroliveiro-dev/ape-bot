# Research: 004 — Lembrete de achados

Base: código da 003 (fila por pessoa, despachante, entregador, favoritos) e a amostra de 28/10
(14 de 76 imóveis da fila até 70% do máximo de R$ 3.000).

## R1. Quem é elegível
- **Decision**: a cada rodada, depois de enfileirar os imóveis novos, para cada pessoa ativa uma
  consulta traz os candidatos: `envio` com `status = 'entregue'`, `lembrado_em IS NULL`,
  `entregue_em <= agora − 32 h`, `anuncio.ultimo_visto_em >= agora − 24 h`,
  `anuncio.aluguel_centavos <= limite` e sem linha em `favorito`. Em Python, o candidato ainda
  passa por `aceita(filtro atual)`. `limite = aluguel_max_centavos * 70 // 100` (arredonda para
  baixo, FR-001), em `filtro.limite_achado`; a regra completa é `filtro.e_achado(filtro, anuncio)`.
- **Rationale**: a rodada já lê os filtros atuais e roda a cada 3 h, então "a partir de 32 h, na
  primeira rodada depois" sai de graça, sem tarefa nova. O `ultimo_visto_em` é atualizado a cada
  rodada em que o portal mostra o anúncio, e o aluguel guardado é o atual.
- **Alternatives**: o despachante procurar a cada 20 s (consulta no MySQL a cada volta, sem ganho
  real de precisão); um job separado (mais uma peça).

## R2. Fila
- **Decision**: o lembrete entra na mesma fila Redis da pessoa (ZSET pelo aluguel), com
  `"lembrete": true` no JSON do imóvel. `FilaPessoa.adicionar(..., lembrete=False)` e
  `retirar_mais_barato` passa a devolver `(anuncio, contato, lembrete)`. O membro continua
  `"{fonte}|{id_externo}"`; como só imóvel já entregue vira lembrete, não colide com imóvel novo, e
  o `ZADD NX` evita duplicar o mesmo lembrete de uma rodada para outra.
- **Rationale**: a mesma ordem, a mesma janela e o mesmo espaçamento (FR-002) sem nenhum código novo
  de ritmo.

## R3. Envio e "no máximo uma vez"
- **Decision**: no despacho, um lembrete é reconferido (`e_achado` com o filtro atual e
  `banco.e_favorito`); se não passar, é descartado sem mexer em `envio` (FR-003). Passando, vira
  `Mensagem(tipo="lembrete")` com `mensagem_lembrete(anuncio)` e `botoes_imovel(anuncio)`. O
  `Entregador`, para `tipo == "lembrete"`, grava `envio.lembrado_em` quando entrega **ou** quando
  falha de vez, e não mexe em `status`/`entregue_em` (FR-005, FR-006).
- **Rationale**: marcar só na entrega mantém elegível o lembrete que se perdeu (pausa limpou a
  fila, reinício). Como `status` e `entregue_em` não mudam, o resumo e o `/status` já não contam o
  lembrete, sem regra extra. A reconciliação da 003 só olha `pendente`, então não mexe em lembrete.
