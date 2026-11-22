# Intelligent Marketplace API

Backend da solução Intelligent Marketplace. Projeto independente do frontend
`intelligent-marketplace-web`.

A solução prevê três agentes: Logístico, Jornada do Cliente e Executivo, que também
atua como Orquestrador. Sua implementação será feita em etapas pequenas, com um
commit específico para cada entrega.

## Estado atual

API HTTP inicial em Python com FastAPI e Uvicorn. Inclui um endpoint de saúde,
documentação OpenAPI e testes locais. Banco de dados e agentes ainda não estão
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

Os testes verificam a resposta HTTP e a publicação do contrato do endpoint.
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

Definir a configuração da aplicação e das variáveis de ambiente. Banco, agentes e
hospedagem terão etapas próprias, com commits separados.
