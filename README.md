# Intelligent Marketplace API

Backend da solução Intelligent Marketplace. Projeto independente do frontend
`intelligent-marketplace-web`.

A solução prevê três agentes: Logístico, Jornada do Cliente e Executivo, que também
atua como Orquestrador. Sua implementação será feita em etapas pequenas, com um
commit específico para cada entrega.

## Estado atual

API HTTP em Python com FastAPI e Uvicorn. Inclui configuração por ambiente,
conexão opcional ao PostgreSQL com SQLAlchemy, documentação OpenAPI e testes.
Inclui nove tabelas históricas, controle técnico da carga e importador dos CSVs.
Disponibiliza consultas de vendas por vendedor, atrasos por estado e planos
analíticos combináveis para vendas, atrasos, avaliações e tempo até o despacho.
O Executivo possui uma primeira capacidade de análise histórica via OpenAI Agents
SDK. Logístico, Jornada do Cliente e a orquestração entre agentes ainda não estão
implementados. Migrações e importação são executadas separadamente da API.

## Executar localmente

Pré-requisitos: Python 3.12 ou superior e [uv](https://docs.astral.sh/uv/).
Execute os comandos a partir da raiz deste repositório:

```sh
uv sync --locked
uv run uvicorn intelligent_marketplace.main:app --reload --host 127.0.0.1 --port 8000
```

O primeiro comando cria o ambiente `.venv` e instala as dependências nas versões
registradas em `uv.lock`. O modo `--reload` destina-se ao desenvolvimento local.

## Configuração por ambiente

A API funciona sem `.env`, utilizando os valores padrão. Para personalizar, copie
`.env.example` para `.env` na raiz do repositório, caso esse arquivo ainda não exista.
O `.env` é local e não entra no Git.

| Variável | Padrão | Finalidade |
|---|---|---|
| `APP_NAME` | `Intelligent Marketplace API` | Nome exibido na documentação |
| `APP_ENV` | `development` | Identificação do ambiente: `development`, `test` ou `production` |
| `DOCS_ENABLED` | `true` | Habilitar `/docs`, `/redoc` e `/openapi.json` |
| `DATABASE_URL` | Não configurada | URL `postgresql+psycopg://usuario:senha@host:porta/banco` |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `5` | Limite de conexão e espera pelo pool, de 1 a 30 segundos |
| `ANALYTICS_QUERY_TIMEOUT_SECONDS` | `5` | Limite por comando analítico no PostgreSQL, de 1 a 30 segundos |
| `OPENAI_API_KEY` | Não configurada | Chave secreta da API OpenAI |
| `OPENAI_MODEL` | Não configurado | Identificador do modelo com suporte a ferramentas disponível na conta |
| `AGENT_TIMEOUT_SECONDS` | `60` | Limite total da execução do agente, de 1 a 120 segundos |
| `API_ACCESS_KEY` | Não configurada | Chave própria de acesso, de 32 a 256 caracteres; obrigatória em `production` |
| `EXECUTIVE_REQUESTS_PER_MINUTE` | `6` | Limite de requisições autenticadas ao Executivo por minuto e processo |
| `EXECUTIVE_MAX_CONCURRENT` | `1` | Limite de execuções simultâneas do Executivo por processo |

As variáveis do processo prevalecem sobre o `.env`; valores não definidos usam o
padrão. O `.env` é procurado no diretório de execução, por isso inicie a API pela
raiz do repositório. Valores inválidos nas configurações reconhecidas impedem a
inicialização. Reinicie a API após alterar a configuração.

`APP_ENV=production` exige `API_ACCESS_KEY`; as demais opções de implantação
continuam explícitas. `DOCS_ENABLED=false` desabilita somente a documentação, mantendo
`/health` disponível. As configurações ficam em `core/config.py`.

| Endereço | Finalidade |
|---|---|
| `http://127.0.0.1:8000/health` | Disponibilidade do processo HTTP |
| `http://127.0.0.1:8000/health/ready` | Conexão disponível com o PostgreSQL |
| `http://127.0.0.1:8000/docs` | Documentação interativa da API |
| `http://127.0.0.1:8000/openapi.json` | Contrato OpenAPI para integrações futuras |

Resposta de `GET /health`:

```json
{"status": "ok"}
```

Esse endpoint confirma somente que a API está respondendo. Não representa
disponibilidade de banco, agentes ou outros serviços.

## PostgreSQL local

Com Docker Desktop em execução, suba somente o banco:

```sh
docker compose up -d postgres
```

O `compose.yaml` usa PostgreSQL 16, acessível apenas em `127.0.0.1:5432`, com
volume persistente. Usuário, senha e banco locais são `marketplace`; esses valores
destinam-se exclusivamente ao desenvolvimento local.

Defina no seu `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://marketplace:marketplace@localhost:5432/marketplace
DATABASE_CONNECT_TIMEOUT_SECONDS=5
```

Reinicie a API e consulte `/health/ready`. Com conexão disponível, a resposta será:

```json
{"status": "ready", "database": "connected"}
```

Sem `DATABASE_URL`, ou se o banco estiver indisponível, esse endpoint retorna
HTTP 503. `/health` continua respondendo sem depender do banco. A inicialização
não abre conexões nem cria tabelas; o acesso ocorre sob demanda.

O pool pertence à aplicação e é liberado no encerramento. As futuras rotas poderão
obter uma sessão por requisição através de `get_session`; os serviços precisarão
confirmar explicitamente suas transações. O fechamento da sessão descarta trabalho
não confirmado.

Para um banco hospedado, utilize credenciais próprias e os parâmetros TLS exigidos
pelo provedor. Senhas com caracteres reservados devem ser codificadas para URL.
Não publique a URL real. A configuração protege a representação da senha e os
erros HTTP de conexão não expõem detalhes do driver.

`/health/ready` verifica somente `SELECT 1`, não a existência dos schemas e tabelas.
O Executivo usa ferramentas delimitadas; não há execução de SQL gerado pela IA.

## Migrações e tabelas históricas

Com o PostgreSQL disponível e `DATABASE_URL` configurada, execute:

```sh
uv run alembic upgrade head
uv run alembic current
```

A revisão `0001` cria o schema `historical` e nove tabelas vazias. A revisão `0002`
acrescenta `historical.dataset_imports` para rastrear arquivos já carregados. O
controle das migrações fica em `public.alembic_version`. O usuário deve ter permissão
para criar schemas e tabelas. Reexecutar `upgrade head` não reaplica revisões já
registradas. A API não executa migrações automaticamente.

| Tabela em `historical` | Chave primária |
|---|---|
| `customers` | `customer_id` |
| `sellers` | `seller_id` |
| `products` | `product_id` |
| `orders` | `order_id` |
| `order_items` | `order_id`, `order_item_id` |
| `order_payments` | `order_id`, `payment_sequential` |
| `order_reviews` | `review_id`, `order_id` |
| `geolocation` | `geolocation_id` gerado pelo banco |
| `product_category_name_translation` | `product_category_name` |

Os campos do dataset mantêm seus nomes, inclusive `product_name_lenght` e
`product_description_lenght`. Datas sem fuso na origem são `TIMESTAMP WITHOUT TIME
ZONE`; não são convertidas implicitamente para UTC. Valores monetários utilizam
`NUMERIC(14,2)`, prefixos de CEP são texto e coordenadas utilizam `NUMERIC(24,20)`.
Campos ausentes na origem permanecem opcionais, sem preenchimento artificial.

Avaliações não usam somente `review_id` como chave: esse identificador se repete.
A combinação com `order_id` é única nos arquivos conferidos. Geolocalização recebe
um identificador técnico para preservar ocorrências repetidas, sem considerar o
prefixo de CEP único. A tradução de categoria não é uma chave estrangeira
obrigatória, assim como os prefixos de CEP não apontam para uma linha única.

As tabelas relacionam pedidos a clientes, itens a produtos e vendedores, e
pagamentos e avaliações a pedidos. Índices apoiam esses cruzamentos, consultas
por estado, cliente recorrente, categoria, status e datas. Não há exclusões em
cascata. Os registros operacionais dos agentes ficarão no schema `application`
em outra etapa; ele ainda não é criado.

Para revisar o SQL sem conectar ao banco:

```sh
uv run alembic upgrade head --sql
```

O comando gera o SQL no terminal e não exige `DATABASE_URL`. Para criar revisões
futuras, altere as definições em `infrastructure/models/historical.py`, gere uma
revisão com `alembic revision --autogenerate -m "descricao"` contra um banco de
desenvolvimento atualizado e revise o arquivo antes de aplicar. A revisão `0001`
contém sua própria definição congelada, independente de alterações nos modelos.

**Reversão:** `uv run alembic downgrade base` remove todas as tabelas históricas e
seus dados. Utilize somente quando a remoção for intencional. A reversão não usa
`CASCADE` para remover objetos inesperados.

## Importar o dataset

Forneça uma pasta com os nove CSVs originais. Os arquivos não precisam estar
dentro do repositório e não são copiados, alterados ou publicados no Git.

Primeiro, confira os arquivos sem acessar o banco:

```sh
uv run marketplace-import --source-dir CAMINHO_DOS_CSVS --validate-only
```

Depois, com `DATABASE_URL` configurada e as migrações aplicadas:

```sh
uv run alembic upgrade head
uv run marketplace-import --source-dir CAMINHO_DOS_CSVS
```

Substitua `CAMINHO_DOS_CSVS` pelo caminho da pasta. Use aspas se houver espaços.
`--batch-size` controla a quantidade de registros por lote (padrão 2000; máximo
10000). O relatório JSON informa tabela, linhas e situação:

- `validated`: arquivo conferido, sem acesso ao banco;
- `imported`: dados e controle de carga confirmados na transação;
- `skipped`: arquivo já carregado, com o mesmo checksum e contagem no banco.

O comando exige todos os arquivos abaixo e respeita a ordem das dependências:

| Arquivo de origem | Tabela de destino |
|---|---|
| `olist_customers_dataset.csv` | `historical.customers` |
| `olist_sellers_dataset.csv` | `historical.sellers` |
| `product_category_name_translation.csv` | `historical.product_category_name_translation` |
| `olist_products_dataset.csv` | `historical.products` |
| `olist_orders_dataset.csv` | `historical.orders` |
| `olist_order_items_dataset.csv` | `historical.order_items` |
| `olist_order_payments_dataset.csv` | `historical.order_payments` |
| `olist_order_reviews_dataset.csv` | `historical.order_reviews` |
| `olist_geolocation_dataset.csv` | `historical.geolocation` |

### Validação e preservação da origem

A leitura usa UTF-8 com suporte a BOM, preservando comentários com aspas, vírgulas
e quebras de linha. São verificados cabeçalhos, tipos, comprimentos, precisão
decimal, campos obrigatórios e chaves compostas repetidas. Valores vazios em
campos opcionais viram `NULL`; não são inventadas datas ou características.
Números inteiros escritos como `10.0` são aceitos sem arredondar valores como
`10.5`. Dinheiro e coordenadas usam `Decimal`, sem conversão intermediária para
`float`. Datas históricas mantêm o horário original, sem fuso presumido.

Erros de conversão identificam arquivo, linha e campo sem exibir o conteúdo do
registro. A validação interrompe no primeiro erro. `--validate-only` verifica os
arquivos, mas não garante integridade referencial entre eles; as chaves
estrangeiras são verificadas pelo PostgreSQL durante a carga.

### Reexecução e atomicidade

Cada tabela possui um registro técnico com checksum SHA-256 do arquivo, quantidade
de linhas e momento da importação. A mesma carga é ignorada na reexecução. Isso
preserva todas as ocorrências originais de geolocalização, inclusive linhas
idênticas, sem confundi-las com uma segunda execução do comando.

Um arquivo com bytes diferentes de uma carga anterior é bloqueado, mesmo que a
diferença seja apenas de formatação. Tabelas com dados e sem controle de carga, ou
com contagens divergentes, também são bloqueadas. Não há substituição automática,
`TRUNCATE` ou descarte silencioso de registros. Esse controle pressupõe que as
tabelas históricas não sejam editadas diretamente; ele não detecta alterações
manuais de conteúdo que mantenham a mesma quantidade de linhas.

A carga dos nove arquivos utiliza uma única transação. Lotes limitam o consumo de
memória, mas não são confirmados separadamente. Uma falha desfaz o trabalho da
execução, preservando cargas anteriores. Um bloqueio transacional impede duas
execuções simultâneas do importador no mesmo banco. O checksum é conferido antes e
depois da leitura para detectar alterações dos arquivos durante o processo.

O código de saída é `0` em sucesso, `2` em erro de arquivo/configuração e `1` em
falha de banco. Nenhuma carga é iniciada automaticamente ao subir a API.

## Consultas históricas

Após aplicar as migrações e importar os dados, consulte pela documentação `/docs`:

| Rota GET | Finalidade | Ordenação (`sort_by`) |
|---|---|---|
| `/api/v1/analytics/sellers` | Vendas por vendedor | `order_count` (padrão), `item_count`, `item_revenue` |
| `/api/v1/analytics/delivery-by-state` | Atrasos por estado de destino | `late_order_count` (padrão), `late_rate_percent` |

Ambas aceitam `start_date` e `end_date` no formato `YYYY-MM-DD`, filtrando a data
da compra, com limites inclusivos. `limit` tem padrão 10 e máximo 50. A resposta
inclui origem, definição do indicador, filtros aplicados e resultados. Ausência
de resultados retorna uma lista vazia; indisponibilidade do banco retorna 503.

**Vendas:** considera pedidos com status `delivered` e itens registrados. Conta
pedidos distintos por vendedor, itens e soma dos preços em BRL, excluindo frete.
O valor não representa lucro ou faturamento fiscal. Um pedido com vários
vendedores conta uma vez para cada vendedor participante; a soma dessas contagens
pode superar o total de pedidos do marketplace. Pagamentos e avaliações não
entram no cruzamento, evitando multiplicar valores.

**Atrasos:** considera pedidos `delivered` com datas de entrega e previsão
preenchidas. A entrega é atrasada quando seu dia de calendário supera o dia
prometido. A taxa divide os atrasados pelos pedidos elegíveis do estado e
multiplica por 100. A resposta informa esse denominador e arredonda a taxa para
duas casas; a ordenação usa a taxa sem arredondamento. `min_delivered_orders`
(padrão 1) permite excluir estados com amostras pequenas. Quantidade e taxa podem
produzir rankings diferentes. Datas históricas permanecem sem conversão de fuso.

Exemplos:

```text
/api/v1/analytics/sellers?sort_by=item_revenue&limit=5
/api/v1/analytics/delivery-by-state?sort_by=late_rate_percent&min_delivered_orders=100
/api/v1/analytics/delivery-by-state?start_date=2018-01-01&end_date=2018-12-31
```

Valores decimais são strings JSON para preservar precisão. As consultas usam
parâmetros validados, transações somente de leitura e timeout local por comando.
Não aceitam SQL fornecido pelo cliente. Essas rotas estabelecem definições
verificáveis para as ferramentas do Executivo. Uma chave compartilhada permite
proteger o acesso da demonstração; permissões próprias do usuário de banco ainda
devem ser configuradas no ambiente hospedado.

## Proteção inicial da API

Com `API_ACCESS_KEY` definida, envie-a no cabeçalho `X-API-Key` para consultas,
Executivo e `/health/ready`. `/health` permanece público e não consulta o banco.
No Swagger, use **Authorize**. A chave deve ser diferente de `OPENAI_API_KEY`;
nunca distribua a chave da OpenAI aos consumidores da API. Sem chave em ambiente
local, o acesso continua livre; em `production`, a aplicação recusa iniciar.

O Executivo autenticado aceita por padrão seis requisições por minuto, com uma
execução por vez. Excesso retorna HTTP 429 e `Retry-After`; uma falha libera a
vaga de execução, mas conta no limite da janela. São limites em memória de um
processo, reiniciados no redeploy/restart, não um controle financeiro ou por
usuário. Utilize um único worker na demonstração. Ainda não há contas individuais,
rate limit distribuído ou auditoria persistente. A documentação pode ser desligada
no deploy por `DOCS_ENABLED=false`.

Os testes analíticos verificam pedidos com múltiplos itens e vendedores, filtros,
taxas, denominadores e proteção contra escrita no PostgreSQL temporário.

### Análises compostas pela IA

`POST /api/v1/analytics/query` executa um plano analítico validado. O Executivo
também pode construir esse plano pela ferramenta `marketplace_analysis`, sem
depender de uma função diferente para cada pergunta. A IA escolhe o domínio,
métricas, agrupamentos e filtros; o backend compila e calcula a consulta em SQL.

| Domínio | Métricas disponíveis (além de `order_count`) |
|---|---|
| `delivery` | `late_order_count`, `late_rate_percent`, `avg_late_days`, `max_late_days`, `total_late_days` |
| `sales` | `item_count`, `item_revenue` |
| `reviews` | `review_count`, `avg_review_score`, `low_review_count`, `low_review_rate_percent` |
| `dispatch` | `avg_dispatch_days`, `max_dispatch_days` |

Até duas dimensões podem ser combinadas: `seller_id`, `seller_state`,
`destination_state`, `product_category`, `purchase_month`, `order_status`. Uma
lista vazia de dimensões retorna a análise global. Há filtros por vendedor,
estados de origem/destino, categoria, status e período de compra. O ranking pode
ser crescente ou decrescente por uma das métricas solicitadas, com até 50 grupos.
`min_order_count` restringe a amostra por grupo (padrão 1).

Exemplo: vendedores associados aos maiores atrasos individuais, em dias:

```json
{
  "domain": "delivery",
  "group_by": ["seller_id"],
  "metrics": ["max_late_days", "avg_late_days", "late_order_count", "late_rate_percent"],
  "sort_by": "max_late_days",
  "limit": 5
}
```

`order_count` é incluído em todos os planos para mostrar a amostra. Em `delivery`,
conta pedidos entregues com datas válidas; a média de dias considera somente os
atrasados. Em `sales`, conta pedidos com itens. Em `reviews`, conta pedidos com
avaliações, enquanto taxas e médias usam cada avaliação: notas de 1 a 3 são
consideradas baixas. Em `dispatch`, conta pedidos com despacho igual ou posterior
à compra e calcula dias de 24 horas entre compra e despacho. Médias sem
observações são nulas. Os status padrão são `delivered` em vendas e entregas,
e todos os status em avaliações e despacho; `delivery` sempre exige `delivered`.

As medidas de pedido e avaliação são deduplicadas antes das agregações por
vendedor/categoria. Um pedido multivendedor pode pertencer a vários grupos;
some grupos somente quando as populações forem disjuntas. Atraso ou avaliação
associados a um vendedor não comprovam responsabilidade: o dataset registra
entrega e despacho no nível do pedido, sem eventos de cada vendedor.

## Executivo: perguntas em linguagem natural

Configure `OPENAI_API_KEY` e `OPENAI_MODEL` no `.env`, além do banco já migrado e
carregado. O modelo é uma escolha explícita de configuração; não há modelo padrão
nem chamada externa na inicialização. Não publique sua chave no Git. A assinatura
do ChatGPT não configura automaticamente as credenciais desta aplicação.

Envie `POST /api/v1/executive/messages` com o corpo:

```json
{"question": "Qual estado concentrou mais entregas atrasadas em 2018?"}
```

O Executivo interpreta a pergunta, escolhe a ferramenta e seus filtros, recebe os
resultados calculados no PostgreSQL e elabora a resposta. `marketplace_analysis`
permite construir análises por vendedor, estado, categoria, mês ou status, nos
quatro domínios. `sales_by_seller` e `delays_by_state` também permanecem disponíveis
para consultas simples. Cada chamada abre sua própria sessão de leitura e a fecha
antes de devolver o resultado ao modelo. O acesso ao banco não bloqueia o loop
assíncrono da API.

A resposta contém `answer` (explicação), `evidence` (relatórios efetivamente
consultados e selecionados como suporte, com filtros/plano, origem e resultados)
e `model`. O modelo devolve internamente uma resposta estruturada com os IDs das
evidências utilizadas; o backend verifica as referências e devolve apenas esses
relatórios, sem incluir automaticamente consultas irrelevantes. As evidências são
coletadas pelo backend, não inventadas pelo modelo. A redação gerada continua
sujeita à avaliação; o teste automatizado não comprova a qualidade de um modelo
real. O agente pode fazer várias consultas para comparar períodos e rankings,
e reformular um plano inválido a partir do retorno da ferramenta. Campos ausentes
na origem, causalidade e previsões exigem evidências ou métodos adicionais.
Não há SQL livre: as combinações usam o catálogo de métricas e dimensões acima.

Cada requisição é independente, sem histórico de conversa ou memória persistente.
O prompt está versionado em `agents/executive/assistant.py`. Ele orienta o agente
a fundamentar números nas ferramentas, distinguir quantidade de taxa e reconhecer
que o dataset é histórico. Esta etapa não implementa previsões, monitoramento
operacional, ações logísticas nem comunicação entre os três agentes.

A execução limita-se a dez turnos do SDK e 1500 tokens de saída por chamada do
modelo, com timeout total configurável. O cliente não faz retries automáticos.
Tracing está desabilitado e as chamadas usam `store=false`. Perguntas e resultados
agregados das ferramentas são enviados à OpenAI; os CSVs completos não são enviados.
Chamadas reais utilizam a conta e os créditos da chave configurada.

Sem chave/modelo ou banco configurado, a rota retorna 503. Falhas do provedor ou
limite de turnos retornam 502; timeout total retorna 504, sem detalhes sensíveis.
Uma conexão configurada, mas indisponível, é detectada quando a ferramenta a usa.

Referências de implementação: [quickstart oficial](https://developers.openai.com/api/docs/quickstart),
[Agents SDK](https://openai.github.io/openai-agents-python/quickstart/) e
[configuração do SDK](https://openai.github.io/openai-agents-python/config/).

## Verificar

```sh
uv run pytest
```

Os testes verificam a resposta HTTP, o contrato do endpoint, a leitura das
configurações, a precedência das variáveis e a desativação da documentação.
Também cobrem configuração do banco, sessões, encerramento, chaves históricas e
geração do SQL de criação/reversão, validação dos CSVs e comportamento do comando.
Por padrão, não fazem chamadas a serviços externos.

Os testes do Executivo usam modelo local simulado: não consomem créditos nem
chamam a OpenAI. Com o banco de testes configurado, exercitam o Runner real do SDK,
as ferramentas, as consultas SQL e a resposta HTTP com evidências. Também
verificam configuração ausente, validação de entrada e erros sanitizados.

Para executar os testes de integração, configure `TEST_DATABASE_URL` para um
**banco exclusivo de testes**. Exemplo no PowerShell, após criar um banco vazio
chamado `marketplace_test` no PostgreSQL local:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://marketplace:marketplace@localhost:5432/marketplace_test"
uv run pytest -m integration
```

Um teste verifica `SELECT 1`; outro aplica e reverte a migração dentro de uma
transação que é descartada ao final, comparando o schema real com os modelos. O
segundo é ignorado se já houver schema histórico ou controle de migrações. Sem
`TEST_DATABASE_URL`, ambos são ignorados. Os demais testes não dependem do Docker.

Também há testes de integração do importador: primeira carga, reexecução,
preservação de duplicatas de origem, bloqueio de arquivo alterado e rollback por
referência inexistente. Eles usam arquivos sintéticos pequenos e descartam a
transação ao final. Requerem o mesmo banco exclusivo e vazio de testes; sem ele,
são ignorados. Nenhum teste depende dos CSVs externos para executar.

## Estrutura

```text
intelligent-marketplace-api/
├── docs/                         # Decisões e documentação do backend
├── migrations/                   # Revisões versionadas do banco
├── src/
│   └── intelligent_marketplace/
│       ├── main.py                # Criação da aplicação FastAPI
│       ├── importing/             # Leitura, validação e comando de importação
│       ├── agents/
│       │   ├── customer_journey/   # Jornada do Cliente
│       │   ├── executive/          # Executivo e Orquestrador
│       │   └── logistics/          # Logístico
│       ├── api/                    # Rotas HTTP, incluindo GET /health
│       ├── core/                   # Configurações compartilhadas
│       ├── infrastructure/         # Conexões e sessões em database.py
│       └── services/               # Casos de uso da aplicação
├── tests/                          # Testes do backend
├── .editorconfig
├── .env.example                    # Exemplo de configuração sem segredos
├── .gitattributes
├── .gitignore
├── compose.yaml                    # PostgreSQL para desenvolvimento local
├── alembic.ini                     # Ambiente de migrações, sem credenciais
├── pyproject.toml
├── uv.lock                         # Versões resolvidas das dependências
└── README.md
```

Logístico e Jornada do Cliente reservam responsabilidades para etapas posteriores.
O projeto não depende de arquivos fora desta pasta.

## Convenções

- Nomes de pacotes, módulos e campos em inglês, no padrão `snake_case`.
- Documentação em português.
- Identidade genérica, sem nomes de empresas reais em pacotes e serviços.
- Segredos e arquivos `.env` fora do versionamento.
- Cada passo deve informar escopo, verificação e commit correspondente.
- Mensagens de commit no formato `tipo(escopo): descrição`.

## Métricas, guardrails e validação

- [Definições dos indicadores](docs/metric-definitions.md): fórmulas, populações,
  denominadores, filtros e interpretação de pedidos multivendedor.
- [Mapa de guardrails](docs/guardrails.md): controles no backend, orientações de
  prompt, cobertura existente e lacunas pendentes.
- [Cenários de validação](docs/validation-scenarios.md): perguntas, resultados
  esperados, critérios de aceitação e registro de avaliações do modelo real.
- [Avaliação real de 22/11/2026](docs/evaluations/2026-11-22-review.md): duas rodadas
  de 14 perguntas sintéticas, falhas observadas, ajuste do prompt e reavaliação.
- [Primeiro fluxo do Agente Logístico](docs/logistics-operating-flow.md): entradas,
  acompanhamento, atuação da IA, saídas para o Executivo e ordem de implementação.

Os testes com modelo simulado verificam integração e contratos; a validação
semântica das respostas de um modelo real permanece uma etapa distinta.

## Publicação inicial

Destino escolhido: **Render Free** para a API e **Neon Free** para PostgreSQL.
Veja o [guia de publicação](docs/deploy-render-neon.md) para carga local, role de
leitura, variáveis secretas, criação do Blueprint e verificação pós-deploy.

`Dockerfile` usa o `uv.lock` e executa um único worker como usuário sem privilégios.
`render.yaml` seleciona explicitamente o plano gratuito, gera a chave de acesso
e deixa banco/OpenAI para preenchimento seguro no painel. `.env` e CSVs ficam
fora da imagem. Migrações e importação são etapas separadas da inicialização.

Para conferir a imagem local sem credenciais reais:

```sh
docker build -t intelligent-marketplace-api:local .
docker run --rm -p 127.0.0.1:10000:10000 intelligent-marketplace-api:local
```

Esse comando inicia em desenvolvimento, sem banco/modelo configurados, permitindo
verificar `/health`. Para simular o deploy protegido, configure `APP_ENV=production`
e `API_ACCESS_KEY` em um arquivo local ignorado e use `--env-file`; nunca coloque
credenciais reais na linha de comando ou na imagem.

## Próximo passo

Criar/configurar Neon e Render, aplicar a carga e verificar a primeira publicação
do Executivo. Depois, retomar os contratos de entrada/saída e a conferência factual
do snapshot do Agente Logístico, conforme seu fluxo documentado. As duas rodadas
exploratórias registradas do Executivo não demonstram robustez geral.
