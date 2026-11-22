# Intelligent Marketplace API

Backend da solução Intelligent Marketplace. Projeto independente do frontend
`intelligent-marketplace-web`.

A solução prevê três agentes: Logístico, Jornada do Cliente e Executivo, que também
atua como Orquestrador. Sua implementação será feita em etapas pequenas, com um
commit específico para cada entrega.

## Estado inicial

Este primeiro passo contém somente a organização do repositório. Ainda não há
servidor HTTP, agentes executáveis, integração com modelos ou conexão com banco.
Nenhuma instalação de dependências é necessária nesta etapa.

## Estrutura

```text
intelligent-marketplace-api/
├── docs/                         # Decisões e documentação do backend
├── src/
│   └── intelligent_marketplace/
│       ├── agents/
│       │   ├── customer_journey/   # Jornada do Cliente
│       │   ├── executive/          # Executivo e Orquestrador
│       │   └── logistics/          # Logístico
│       ├── api/                    # Interface HTTP
│       ├── core/                   # Configurações compartilhadas
│       ├── infrastructure/         # Persistência e integrações externas
│       └── services/               # Casos de uso da aplicação
├── tests/                          # Testes do backend
├── .editorconfig
├── .gitattributes
├── .gitignore
├── pyproject.toml
└── README.md
```

Os diretórios reservam responsabilidades; não representam funcionalidades já
implementadas. O projeto não depende de arquivos fora desta pasta.

## Convenções

- Nomes de pacotes, módulos e campos em inglês, no padrão `snake_case`.
- Documentação em português.
- Identidade genérica, sem nomes de empresas reais em pacotes e serviços.
- Segredos e arquivos `.env` fora do versionamento.
- Cada passo deve informar escopo, verificação e commit correspondente.
- Mensagens de commit no formato `tipo(escopo): descrição`.

## Próximo passo

Definir e implementar a inicialização mínima da API, com suas dependências e uma
verificação de funcionamento. Banco, agentes e hospedagem terão etapas próprias.
