# Definições dos indicadores

Referência da implementação atual do Executivo. Nomes de campos seguem o dataset;
nomes de métricas seguem os contratos da API. Este catálogo define como conferir
as análises e não estabelece metas comerciais ou limites de risco preditivo.

## População e unidade de análise

| Domínio | População padrão | Unidade antes da agregação |
|---|---|---|
| `delivery` | `delivered`, com entrega efetiva e previsão preenchidas | Pedido distinto por grupo |
| `sales` | Pedidos `delivered` com itens | Item; pedidos contados distintamente por grupo |
| `reviews` | Pedidos com avaliações, em qualquer status | Avaliação identificada por `review_id` e `order_id`, por grupo |
| `dispatch` | Despacho preenchido e igual ou posterior à compra, em qualquer status | Pedido distinto por grupo |

`sales`, `reviews` e `dispatch` aceitam um filtro de status diferente. `delivery`
aceita apenas `delivered`. A rota simples de vendas considera sempre `delivered`.
Não se deve comparar contagens de domínios diferentes como se tivessem a mesma
população. Em `delivery`, `order_count` corresponde a `delivered_order_count` da
rota simples de atrasos por estado.

## Catálogo de métricas

Considere `N` como o número de pedidos elegíveis distintos no grupo; `L`, os
pedidos atrasados; `R`, as avaliações; e `B`, as avaliações com nota de 1 a 3.

| Campo | Domínio | Definição | Unidade |
|---|---|---|---|
| `order_count` | Todos | Pedidos distintos elegíveis no domínio e grupo | Pedidos |
| `item_count` | `sales` | Quantidade de linhas de itens elegíveis | Itens |
| `item_revenue` | `sales` | Soma de `order_items.price`, sem `freight_value` | BRL |
| `late_order_count` | `delivery` | Quantidade de pedidos cuja data efetiva supera a prevista (`L`) | Pedidos |
| `late_rate_percent` | `delivery` | `100 × L / N` | Percentual |
| `avg_late_days` | `delivery` | Média dos dias de atraso somente dos pedidos atrasados | Dias de calendário |
| `max_late_days` | `delivery` | Maior quantidade de dias de atraso no grupo | Dias de calendário |
| `total_late_days` | `delivery` | Soma dos dias de atraso no grupo | Dias de calendário acumulados |
| `review_count` | `reviews` | Quantidade de avaliações (`R`) | Avaliações |
| `avg_review_score` | `reviews` | Soma das notas dividida por `R` | Nota de 1 a 5 |
| `low_review_count` | `reviews` | Quantidade de avaliações com nota de 1 a 3 (`B`) | Avaliações |
| `low_review_rate_percent` | `reviews` | `100 × B / R`; não usa pedidos como denominador | Percentual |
| `avg_dispatch_days` | `dispatch` | Média de `(order_delivered_carrier_date − order_purchase_timestamp) / 24 horas` | Dias de 24 horas |
| `max_dispatch_days` | `dispatch` | Maior duração entre compra e despacho no grupo | Dias de 24 horas |

Dias de atraso são `max(data_entrega − data_prevista, 0)`, descartando as horas.
Entrega às 20h no mesmo dia prometido não é atraso. Entrega antecipada equivale
a zero dias de atraso. `avg_late_days` é nula quando não há atrasados; máximo e
total são zero se há entregas elegíveis e todas estão no prazo.

Valor dos itens não representa lucro, recebimento financeiro nem faturamento
fiscal. Com filtro de cancelamento, descreva como valor dos itens de pedidos
cancelados, sem tratá-lo como receita realizada. Avaliações referem-se ao pedido;
não identificam qual vendedor ou etapa motivou a nota.

## Dimensões, filtros e apresentação

| Campo | Significado e origem |
|---|---|
| `seller_id` | Identificador do vendedor associado ao item |
| `seller_state` | Estado do cadastro do vendedor; não comprova local físico do despacho |
| `destination_state` | Estado do cliente associado ao pedido, em `customers.customer_state` |
| `product_category` | Categoria original de `products.product_category_name`; pode ser nula |
| `purchase_month` | Mês da compra em `YYYY-MM`, sem conversão de fuso |
| `order_status` | Status registrado em `orders.order_status` |

Podem ser combinadas até duas dimensões. `group_by=[]` produz a análise global.
`start_date` e `end_date` sempre filtram a **compra**, inclusive os dias limites;
não filtram a data de entrega ou da avaliação. Sem período informado, a consulta
abrange todo o histórico elegível. Datas da origem não recebem fuso presumido.

`min_order_count` tem padrão 1 e filtra pedidos por grupo; em avaliações, não é
um mínimo de avaliações. Não representa confiança estatística. `limit` tem padrão
10 e máximo 50 e restringe os grupos retornados após agregação e ordenação.
Não calcule um total global somando somente os grupos de um ranking limitado.

Taxas, médias e durações de despacho são apresentadas com duas casas decimais;
valores `Decimal` são strings no JSON. A rota simples por estado ordena pela taxa
sem arredondamento; o plano flexível ordena pela métrica calculada arredondada.
Rankings com taxas muito próximas podem divergir. A harmonização está pendente
e deve ser considerada antes de exigir equivalência exata entre essas rotas.

Na explicação, o estado deve aparecer como **São Paulo (SP)**, por exemplo.
Filtros e evidências técnicas preservam as siglas. Nulos permanecem nulos; não
devem ser substituídos por valores inventados. Sem grupos elegíveis, retorna-se
`data=[]`, inclusive na análise global com amostra inferior ao mínimo.

## Pedidos com múltiplos vendedores ou categorias

Um pedido pode participar de vários grupos. Dentro de cada grupo, a contagem de
pedidos é distinta, e as avaliações são deduplicadas antes da agregação. Em
vendas, os valores pertencem aos itens de cada grupo. Isso evita multiplicação
de pedidos e avaliações pelo número de itens, mas não torna os grupos disjuntos.

Entrega e despacho são registrados no pedido. Assim, o indicador identifica
**vendedores associados a pedidos atrasados**; não comprova quem causou o atraso
ou quando cada vendedor despachou. Tempo até o despacho mede duração observada,
não descumprimento de SLA nem efeito causal sobre a entrega.

## Interpretação das perguntas

| Expressão | Critério padrão do prompt | Informação que deve acompanhar |
|---|---|---|
| “Quem vendeu mais?” | `order_count` por vendedor | Critério adotado; itens e valor são alternativas |
| “Maior atraso por vendedor” | `max_late_days` por vendedor | Máximo, média entre atrasados, quantidade, taxa e amostra |
| “Mais pedidos atrasados” / “concentração de atrasos” | `late_order_count` | Quantidade, população e período |
| “Maior percentual de atraso” | `late_rate_percent` | Numerador, denominador e eventual mínimo de amostra |
| “Mais tempo até despachar” | `max_dispatch_days`, se a pergunta indicar máximo | Distinguir máximo de média e duração de atraso contratual |

O critério de despacho na última linha é uma orientação para avaliação; ainda não
há convenção explícita equivalente no prompt. Se houver outra interpretação
plausível, a resposta deve explicitar a escolhida. Diferenças de taxa entre
períodos devem ser descritas em pontos percentuais quando calculadas por subtração.

Implementação: [planos](../src/intelligent_marketplace/services/analysis_plan.py),
[cálculos](../src/intelligent_marketplace/infrastructure/flexible_analytics.py) e
[consultas simples](../src/intelligent_marketplace/infrastructure/analytics_queries.py).
