# Intelligent Marketplace API

Backend da solução Intelligent Marketplace. Projeto independente do frontend
`intelligent-marketplace-web`.

A solução prevê três agentes: Logístico, Jornada do Cliente e Executivo, que também
atua como Orquestrador. Sua implementação será feita em etapas pequenas, com um
commit específico para cada entrega.

## Estado atual

API HTTP inicial em Python com FastAPI e Uvicorn. Inclui um endpoint de saúde,
documentação OpenAPI, configuração por ambiente e testes locais. Banco e agentes ainda não estão
implementados. Não é necessário configurar credenciais para executar esta etapa.

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
| `http://127.0.0.1:8000/docs` | Documentação interativa da API |
| `http://127.0.0.1:8000/openapi.json` | Contrato OpenAPI para integrações futuras |

Resposta de `GET /health`:

```json
{"status": "ok"}
```

Esse endpoint confirma somente que a API está respondendo. Não representa
disponibilidade de banco, agentes ou outros serviços.

## Verificar

```sh
uv run pytest
```

Os testes verificam a resposta HTTP, o contrato do endpoint, a leitura das
configurações, a precedência das variáveis e a desativação da documentação.
Não fazem chamadas de rede externas.

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
│       ├── infrastructure/         # Persistência e integrações externas
│       └── services/               # Casos de uso da aplicação
├── tests/                          # Testes do backend
├── .editorconfig
├── .env.example                    # Exemplo de configuração sem segredos
├── .gitattributes
├── .gitignore
├── pyproject.toml
├── uv.lock                         # Versões resolvidas das dependências
└── README.md
```

Os diretórios de agentes, serviços e infraestrutura reservam responsabilidades
para etapas posteriores. O projeto não depende de arquivos fora desta pasta.

## Convenções

- Nomes de pacotes, módulos e campos em inglês, no padrão `snake_case`.
- Documentação em português.
- Identidade genérica, sem nomes de empresas reais em pacotes e serviços.
- Segredos e arquivos `.env` fora do versionamento.
- Cada passo deve informar escopo, verificação e commit correspondente.
- Mensagens de commit no formato `tipo(escopo): descrição`.

## Próximo passo

Definir a configuração e a conexão com o banco de dados. Modelos de negócio,
agentes e hospedagem terão etapas próprias, com commits separados.
