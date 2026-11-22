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
Os agentes ainda não estão implementados. Migrações e importação são executadas
separadamente da API.

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

As variáveis do processo prevalecem sobre o `.env`; valores não definidos usam o
padrão. O `.env` é procurado no diretório de execução, por isso inicie a API pela
raiz do repositório. Valores inválidos nas configurações reconhecidas impedem a
inicialização. Reinicie a API após alterar a configuração.

`APP_ENV` identifica o ambiente e não aplica configurações de implantação
automaticamente. `DOCS_ENABLED=false` desabilita somente a documentação, mantendo
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
Nenhuma consulta dinâmica de IA foi liberada.

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

## Verificar

```sh
uv run pytest
```

Os testes verificam a resposta HTTP, o contrato do endpoint, a leitura das
configurações, a precedência das variáveis e a desativação da documentação.
Também cobrem configuração do banco, sessões, encerramento, chaves históricas e
geração do SQL de criação/reversão, validação dos CSVs e comportamento do comando.
Por padrão, não fazem chamadas a serviços externos.

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

Os diretórios de agentes e serviços reservam responsabilidades para etapas
posteriores. O projeto não depende de arquivos fora desta pasta.

## Convenções

- Nomes de pacotes, módulos e campos em inglês, no padrão `snake_case`.
- Documentação em português.
- Identidade genérica, sem nomes de empresas reais em pacotes e serviços.
- Segredos e arquivos `.env` fora do versionamento.
- Cada passo deve informar escopo, verificação e commit correspondente.
- Mensagens de commit no formato `tipo(escopo): descrição`.

## Próximo passo

Definir a camada de consultas e os indicadores antes de integrar a IA. Consultas
analíticas dinâmicas, modelos de acompanhamento e agentes terão commits separados.
