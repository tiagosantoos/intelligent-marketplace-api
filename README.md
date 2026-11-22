# Intelligent Marketplace API

Backend da solução Intelligent Marketplace. Projeto independente do frontend
`intelligent-marketplace-web`.

A solução prevê três agentes: Logístico, Jornada do Cliente e Executivo, que também
atua como Orquestrador. Sua implementação será feita em etapas pequenas, com um
commit específico para cada entrega.

## Estado atual

API HTTP em Python com FastAPI e Uvicorn. Inclui configuração por ambiente,
conexão opcional ao PostgreSQL com SQLAlchemy, documentação OpenAPI e testes.
Não há tabelas, importação do dataset ou agentes implementados nesta etapa.

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
Migrações, os schemas `historical` e `application`, importação e ferramentas
analíticas terão etapas próprias. Nenhuma consulta dinâmica de IA foi liberada.

## Verificar

```sh
uv run pytest
```

Os testes verificam a resposta HTTP, o contrato do endpoint, a leitura das
configurações, a precedência das variáveis e a desativação da documentação.
Também cobrem conexão não configurada, tratamento de falhas, sessões e encerramento.
Por padrão, não fazem chamadas a serviços externos.

Para verificar uma conexão real, configure `TEST_DATABASE_URL` explicitamente.
Exemplo no PowerShell para o PostgreSQL local:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://marketplace:marketplace@localhost:5432/marketplace"
uv run pytest -m integration
```

O teste de integração executa apenas `SELECT 1`; não cria ou apaga dados. Sem essa
variável, ele é marcado como ignorado. Os demais testes não dependem do Docker.

## Estrutura

```text
intelligent-marketplace-api/
├── docs/                         # Decisões e documentação do backend
├── src/
│   └── intelligent_marketplace/
│       ├── main.py                # Criação da aplicação FastAPI
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

Definir as migrações e as tabelas do histórico. Importador, consultas analíticas,
modelos de acompanhamento e agentes terão commits separados.
