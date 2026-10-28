# Fixtures do Netimóveis

Páginas reais baixadas em 28/10/2026 (`User-Agent: ape-bot/0.1 (uso pessoal; baixo volume)`, 2–3 s entre
requisições) e **cortadas**: só o `<title>` e os blocos `<script type="application/ld+json">`, que é o que
o parser lê (research R9 da 005).

| Arquivo | URL | Conteúdo |
|---|---|---|
| `funcionarios-apartamento-2q.html` | `/locacao/minas-gerais/belo-horizonte/bairros/funcionarios/apartamento?quartos=2` | `numberOfItems` 31, 21 itens (corte da 1ª página), com cobertura e área privativa |
| `centro-kitchenette.html` | `/locacao/minas-gerais/belo-horizonte/bairros/centro/kitchenette` | 2 kitchenettes |
| `lourdes-casa-em-condominio.html` | `/locacao/minas-gerais/belo-horizonte/bairros/lourdes/casa-em-condominio` | busca vazia: sem `ItemList` |
| `sem-jsonld.html` | cópia da de Lourdes sem nenhum bloco JSON-LD | formato inválido (sintética) |
