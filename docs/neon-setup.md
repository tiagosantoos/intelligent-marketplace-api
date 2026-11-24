# Configuração Neon — 24/11/2026

## Escopo e destino

- Projeto: `holy-sound-87433935` (`intelligent-marketplace-db`).
- Organização: `org-raspy-morning-32251584`.
- Branch: `production` (`br-tiny-cloud-bccyyzd4`).
- Região confirmada no projeto: `aws-us-east-1` (Virgínia).
- Serviço utilizado: **somente PostgreSQL**, versão observada `18.7`.
- Backend: Python/FastAPI no ambiente local; destino de hospedagem continua Render.
- Nenhum Auth, Function, Object Storage, AI Gateway ou Realtime foi habilitado.

O PostgreSQL já existia no projeto indicado e estava vazio. `neon config plan`
e `neon deploy` confirmaram que a branch já correspondia ao `neon.ts`; não houve
criação de outro projeto nem troca de plano. O deploy atualizou cinco variáveis
locais, sem substituir as configurações da aplicação não gerenciadas pelo Neon.
`NEON_FUNCTION_HOST_SUFFIX` é metadado retornado pelo CLI, não uma Function criada.

## Skills e MCP

Foi consultada a [skill solicitada](https://neon.com/.well-known/agent-skills/neon/SKILL.md).
As skills `neon` e `neon-postgres` foram instaladas localmente em `.agents/skills`.
`neon skills status` informou **up to date** para ambas. O arquivo
`skills-lock.json` registra a origem e o commit das versões instaladas; os textos
baixados ficam fora do Git e podem ser reinstalados por:

```sh
neon skills -y --agent codex --skill neon --skill neon-postgres
```

Não havia Neon em `mcp_servers` global ou configuração MCP local. Foi adicionada
somente a entrada `[mcp_servers.Neon]` em `.codex/config.toml`, com OAuth e URL
restrita ao projeto, `readonly=true`. A configuração global do Codex, incluindo
`node_repl`, permaneceu com o mesmo hash antes/depois da instalação local.
Nenhuma API key foi gravada na configuração MCP. O MCP não foi carregado nem
autenticado nesta sessão: o agente poderá pedir OAuth no primeiro uso após
carregar/reabrir o projeto. Login do CLI e OAuth do MCP são autorizações distintas.

## Comandos de configuração e preservação

`npm i -g neon@latest` instalou o CLI **9.9.7**. O `init` solicitado ficou parado
na instalação opcional do plugin Codex; o processo foi interrompido sem alterar
o aplicativo. A configuração foi retomada com os mesmos IDs e serviços, usando
`--no-agent-setup`, e as skills e o MCP foram instalados separadamente.

O `init` retomado escreveu o vínculo offline. Depois do login no navegador,
concluído no perfil `DEFAULT`, a configuração remota foi conferida:

```text
neon config plan
No changes — branch production already matches the policy.
Utilized services: Postgres

neon deploy
No changes — branch production already matches the policy.
Utilized services: Postgres
Pulled 5 Neon variables into .env
```

Foram recebidas `DATABASE_URL`, `DATABASE_URL_UNPOOLED`, `NEON_BRANCH`,
`NEON_BRANCH_ID` e `NEON_FUNCTION_HOST_SUFFIX`. O `.env` anterior foi preservado
em backup privado dentro de `.uv-cache`; o `.env`, o backup, `.neon` e
`node_modules` não entram no Git nem no contexto Docker. Configurações existentes
de OpenAI, acesso, documentação e timeouts foram preservadas.

O `neon.ts` gerado foi preservado, inclusive sua política de branch. Ele mantém
`auth: false`, sem declarar outros serviços. `package.json` e `package-lock.json`
gerenciam as dependências de configuração Neon; não substituem o Python.

## Integração com a aplicação

- A configuração aceita `postgresql://`, `postgres://` e `postgresql+psycopg://`,
  normalizando o driver para psycopg e preservando senha codificada e TLS.
- A API utiliza `DATABASE_URL` pooled. Alembic e a importação preferem
  `DATABASE_URL_UNPOOLED`, com fallback para a URL única em instalações locais.
- Foi criada `marketplace_runtime`, com `--access read_only --schema historical`.
  A conexão dessa role foi validada e selecionada para a API; a conexão direta
  administrativa ficou separada.
- `scripts/neon_runtime_env.py` torna essa seleção reproduzível após um novo
  deploy/env pull, que pode voltar a preencher a URL do proprietário. O comando
  verifica leitura e ausência de INSERT/UPDATE/DELETE antes de atualizar somente
  `DATABASE_URL`, sem imprimir a credencial.
- `render.yaml` agora fixa `region: virginia`, próximo ao banco selecionado.
  Nenhuma publicação no Render foi executada nesta etapa.

```sh
npm run neon:runtime -- --branch production
```

As migrações foram testadas em uma branch temporária derivada da production vazia,
com expiração de 24 horas, antes de serem aplicadas à production. A branch de
validação é descartável e não recebeu a carga real. A produção recebeu a revisão
`0002`, dez tabelas em `historical` (nove de origem e o controle da importação)
e os **1.550.922 registros** dos nove CSVs, por uma única transação do importador.
Nenhum CSV original foi alterado ou publicado no Git.
Após a validação, a branch temporária foi removida. O PostgreSQL 18 Docker usado
pela suíte também foi descartado, sem alterar o banco local de desenvolvimento.

## Evidências de funcionamento

Construção solicitada:

```text
npm run build
> uv build
Successfully built dist\intelligent_marketplace_api-0.1.0.tar.gz
Successfully built dist\intelligent_marketplace_api-0.1.0-py3-none-any.whl
```

O build produz distribuição-fonte e wheel Python. Não é um build de frontend.
Teste automatizado em PostgreSQL 18 local descartável, separado da production:

```text
101 passed in 7.01s
```

Permissões verificadas na conexão real da aplicação:

```json
{"role":"marketplace_runtime","can_read":true,"can_insert":false,"can_update":false,"can_delete":false}
```

Aplicação iniciada em `http://127.0.0.1:8010`. Verificação real via HTTP local,
FastAPI, SQLAlchemy/psycopg e PostgreSQL Neon:

```json
{"health":200,"readiness":200,"analytics_query":200,"eligible_deliveries":96470,"late_orders":6534,"late_rate_percent":"6.77","seller_query":200,"top_seller_order_count":1819}
```

Foram conferidas a taxa global de atraso e a consulta de vendas por vendedor.
Não houve chamadas pagas à OpenAI para esses testes; o serviço novo validado é
o PostgreSQL. Essa verificação não substitui os testes do comportamento do agente.

## Limitações e próximos passos

O instalador opcional do plugin travou; a alternativa com skills/MCP local
funcionou. O MCP depende de carregamento e OAuth no cliente para seu uso futuro,
enquanto o CLI e a integração SQL da aplicação já foram autenticados e testados.

Atualizações do Neon não aplicam as migrações Alembic nem publicam o backend.
A conexão administrativa direta não deve ser levada ao runtime do Render.
O próximo passo é configurar o serviço Render com a URL pooled da role de leitura,
chave OpenAI e chave própria de acesso, conforme o [guia](deploy-render-neon.md).
