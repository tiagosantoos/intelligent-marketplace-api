# Primeira publicação — Render Free e Neon Free

Destino da primeira versão: Executivo com consultas históricas, evidências e
acesso por chave compartilhada. Os agentes especialistas e os jobs logísticos
não fazem parte desta publicação. A configuração está no repositório; criar
contas, configurar segredos e realizar o deploy são etapas separadas.

## Arquitetura e limites

```text
Consumidor → HTTPS + X-API-Key → Render Free (FastAPI, um worker)
                                  ├── TLS → Neon Free (PostgreSQL)
                                  └── API → OpenAI (consumo cobrado)
```

O Render suspende o serviço gratuito após inatividade; a primeira chamada pode
demorar durante o despertar. Não execute jobs contínuos nessa instância nem
guarde dados no filesystem efêmero. O Neon também pode suspender o compute.
Escolha regiões próximas quando as opções dos planos permitirem. Verifique as
franquias atuais nos painéis: gratuidade de infraestrutura não inclui OpenAI.

`render.yaml` define explicitamente `plan: free`, sem banco Render, disco pago,
worker ou cron. Deploys automáticos ficam desligados inicialmente. O primeiro
deploy da criação do Blueprint ainda acontece após configurar os campos exigidos.
O modelo é configurável e o template usa `gpt-5.4-mini`.

## 1. Preparar o Neon

1. Crie um projeto no plano **Free**, com banco e branch exclusivos para a demo.
2. Em **Connect**, copie a conexão direta do proprietário para migrações/carga.
   Guarde-a localmente; não envie a URL no chat nem a publique no Git.
3. A aplicação aceita `postgresql://` e normaliza internamente para o driver
   `postgresql+psycopg://`. Preserve hostname, senha codificada e parâmetros TLS, incluindo
   `sslmode=require` e `channel_binding=require`, quando fornecidos pelo Neon.

Exemplo sem credenciais reais:

```text
postgresql+psycopg://OWNER:SENHA@HOST/neondb?sslmode=require&channel_binding=require
```

Para não trocar o `.env` do desenvolvimento, leia a URL por entrada protegida
somente nesta sessão do PowerShell:

```powershell
$neonConnection = Read-Host "URL Neon direta com prefixo postgresql+psycopg" -AsSecureString
$env:DATABASE_URL = [System.Net.NetworkCredential]::new("", $neonConnection).Password
uv run alembic upgrade head
uv run marketplace-import --source-dir "CAMINHO_DOS_CSVS" --validate-only
uv run marketplace-import --source-dir "CAMINHO_DOS_CSVS"
Remove-Item Env:DATABASE_URL
Remove-Variable neonConnection
```

Substitua `CAMINHO_DOS_CSVS`. Confira o projeto/branch/banco antes dos comandos.
Execute a carga localmente, sem subir CSVs ao Render ou ao GitHub. O importador
usa transação e checksum; a segunda execução com os mesmos arquivos é ignorada.
Em caso de falha, limpe a variável de ambiente ao terminar e confira o erro antes
de prosseguir. O volume final e os índices devem permanecer dentro da franquia
do Neon, com espaço para crescimento e manutenção; a medição local não é uma
garantia do uso contabilizado pelo provedor.

## 2. Separar credenciais de runtime

Execute [neon-runtime-role.sql](../scripts/neon-runtime-role.sql) no SQL Editor
como proprietário das tabelas. A role `marketplace_runtime` recebe leitura no
schema `historical` e não recebe privilégios administrativos ou de escrita.
Depois, defina uma senha forte usando o reset de senha dessa role no console
e guarde-a no gerenciador de segredos. Não adicione senha ao SQL versionado.

Criar uma role diretamente pelo botão de criação do console pode conceder
`neon_superuser`; por isso o script cria a role por SQL. Não use o proprietário
da carga como credencial da API. Monte ou copie a URL da role de runtime com os
parâmetros TLS; prefira a conexão pooled (`-pooler`) para o serviço web.
Migrações e carga continuam na conexão direta do proprietário. As permissões
padrão futuras valem para tabelas criadas pelo proprietário que executou o script.

## 3. Publicar no Render

O repositório deve conter `Dockerfile`, `.dockerignore`, `render.yaml`, `uv.lock`
e o código. O contexto Docker é uma lista permitida: não inclui `.env`, `.git`,
CSVs, testes, relatórios locais ou chaves. A imagem instala dependências fixadas
no lockfile, sem dependências de teste, e executa como usuário sem privilégios.

No Render, escolha **New → Blueprint**, conecte o repositório GitHub e selecione
`render.yaml`. Confirme **Free** e configure nos campos secretos:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | URL Neon da role `marketplace_runtime`, com prefixo `postgresql+psycopg://` e TLS |
| `OPENAI_API_KEY` | Chave válida do projeto OpenAI, inserida somente no painel |
| `API_ACCESS_KEY` | O Blueprint gera um segredo aleatório; copie do painel para os consumidores autorizados |
| `APP_ENV` | `production`; impede iniciar sem chave de acesso |
| `DOCS_ENABLED` | `false`; pode ser habilitado temporariamente para uma apresentação |

Não use `API_ACCESS_KEY` igual à chave OpenAI. Não coloque segredos em build args,
URLs de chamada HTTP ou no frontend público. A chave compartilhada é uma proteção
inicial para demonstração; contas e permissões individuais ficam para evolução.

O Render fornece `PORT`; a imagem escuta em `0.0.0.0:$PORT`, com um worker. O
health check é `/health` para não exigir autenticação nem manter o Neon ativo
por consultas de monitoramento. Esse health check não comprova tabelas ou carga.
Não há comando de migração no startup: o pre-deploy não está disponível no plano
Free, e repetir migrações/carga em cada cold start é desnecessário.

## 4. Conferir a publicação

| Verificação | Esperado |
|---|---|
| `GET /health`, sem chave | HTTP 200 |
| Consulta analítica sem chave | HTTP 401 |
| `GET /health/ready`, com `X-API-Key` | HTTP 200; apenas verifica conexão |
| `GET /api/v1/analytics/delivery-by-state?limit=1`, com chave | HTTP 200 e resultado da carga real |
| `POST /api/v1/executive/messages`, com chave e pergunta | HTTP 200 com resposta e evidências; consome créditos |
| Chamadas acima do limite ou simultâneas | HTTP 429 e `Retry-After` |

Use a URL HTTPS gerada pelo Render. A primeira chamada após suspensão pode ser
lenta. Se houver 503, confira configuração, despertar/conexão do banco e tabelas.
Não publique logs com credenciais. `/docs` e `/openapi.json` retornam 404 quando
desabilitados; se habilitados, use **Authorize** no Swagger para informar a chave.

O limite padrão do Executivo é global ao processo: seis requisições/minuto e uma
execução simultânea. Reiniciar o processo reinicia os contadores; não há garantia
de teto financeiro. Configure também os controles de consumo disponíveis na
conta OpenAI. Para pausar chamadas ao modelo, remova sua chave do ambiente e
faça redeploy; não apague o banco.

## Atualizações e reversão

Use deploy manual de um commit revisado. Mudanças de schema exigem aplicar a
migração localmente com a credencial proprietária antes do código que a utiliza,
verificando compatibilidade. Nunca execute `downgrade base` no banco hospedado
como tentativa de corrigir um deploy: ele remove os dados históricos.
Um rollback de imagem/código não reverte o banco. Para alterações destrutivas,
planeje uma branch/backup do Neon e uma reversão específica.

Referências oficiais: [Render Free](https://render.com/docs/free),
[Blueprint](https://render.com/docs/blueprint-spec),
[conexão Neon](https://neon.com/docs/connect/connect-from-any-app) e
[roles Neon](https://neon.com/docs/manage/roles).
