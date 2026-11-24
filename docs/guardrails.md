# Guardrails do Executivo

Este mapa registra os controles existentes, seu alcance e a validação necessária.
“Backend” indica uma restrição executada pelo código. “Prompt” indica uma
orientação ao modelo: requer avaliação e não é uma garantia técnica de conformidade.
“Parcial” indica que existe controle, mas ele não cobre todo o risco descrito.

## Controles e responsabilidades

| ID | Objetivo | Aplicação atual | Garantia e limite | Verificação |
|---|---|---|---|---|
| G01 | Evitar escrita nas análises | Backend | Transação `READ ONLY` em todas as ferramentas; não há SQL livre nem ferramenta de alteração | `test_real_session_is_read_only_and_has_timeout` |
| G02 | Aceitar somente planos válidos | Backend | Domínios, métricas e dimensões enumerados; datas ordenadas; métricas do mesmo domínio; campos extras recusados | `test_invalid_analysis_plan` |
| G03 | Evitar injeção por filtros | Backend | Valores vinculados como parâmetros; nomes SQL escolhidos pelo compilador, não pelo usuário | `test_global_and_cross_dimensions_filters_and_empty_results` |
| G04 | Limitar execução e consumo | Backend, parcial | Até 10 turnos, 1500 tokens de saída por chamada, timeout total padrão 60s, timeout SQL padrão 5s; não é um teto financeiro ou controle de concorrência | Configurações e testes de erros do Executivo; carga e custo ainda não avaliados |
| G05 | Preservar o grão dos dados | Backend | Pedidos e avaliações deduplicados por grupo; valores calculados por item | Testes de vendedores, categorias e avaliações em `test_flexible_analytics.py` |
| G06 | Fundamentar números em resultados | Prompt + backend, parcial | Relatórios coletados no backend e IDs verificados; não se verifica automaticamente se cada frase corresponde aos números | Testes do Runner e de referência inventada; revisão exploratória real registrada |
| G07 | Mostrar evidências pertinentes | Prompt + backend, parcial | A IA seleciona IDs; o backend retorna apenas os IDs válidos selecionados. Pertinência semântica depende da IA | Teste flexível de atraso por vendedor e exclusão de evidência irrelevante |
| G08 | Não atribuir culpa sem evidência | Prompt + definição do relatório | Associação do vendedor ao pedido não comprova causa; não há bloqueio semântico posterior à geração | Cenários V10 e V11 |
| G09 | Explicitar critérios e população | Prompt + relatório, parcial | Filtros/plano e definição são retornados; sua explicação correta no texto depende da IA | Cenários V01–V09 |
| G10 | Não inventar dados ou ações | Prompt + ferramentas disponíveis | Só há consultas históricas; não há previsão implementada, mudança de prazo, compensação ou acionamento de transportadora | Cenários V11 e V12 |
| G11 | Tratar instruções maliciosas como dados | Prompt + acesso delimitado, parcial | Orientação para ignorar desvios; planos não executam SQL livre. Uma formulação adversária foi avaliada; não cobre outras variantes | Cenário V13, com falha inicial de pertinência e repetição corrigida |
| G12 | Proteger credenciais e dados enviados | Backend + configuração, parcial | Segredos mascarados, `.env` ignorado pelo Git, erros tratados, tracing desligado e `store=false`; perguntas e resultados agregados ainda são enviados ao provedor | Testes de configuração e erros; revisar conteúdo antes de avaliações externas |
| G13 | Tratar falhas sem fabricar resposta | Backend + prompt | Configuração ausente: 503; falha SQL tratada: 503; falha do provedor/turnos: 502; timeout total: 504. Lista vazia não é erro | Testes de banco, Executivo e ausência de resultados |
| G14 | Permitir correção autônoma do plano | Backend + modelo | Plano inválido retorna orientação para reformulação, dentro dos limites da execução | Caso `RecoveringPlanModel` no teste flexível do Executivo |
| G15 | Apresentar linguagem compreensível | Prompt | Nome do estado com sigla na explicação; sigla mantida nos filtros e evidências. Não há formatador determinístico da prosa | Cenário V02 |
| G16 | Restringir acesso à demonstração | Backend, parcial | `X-API-Key` em análises, Executivo e readiness quando configurada; chave obrigatória em `production`, distinta da OpenAI. Não substitui identidades e permissões individuais | `test_api_security.py` |
| G17 | Separar leitura de administração no Neon | Banco + backend | API com role `marketplace_runtime` de leitura em `historical`; migrações/importação usam URL direta administrativa separada. Novos schemas operacionais exigirão política própria | `test_deployment.py`, `test_neon_configuration.py` e verificação real em `neon-setup.md` |

O limite inicial do Executivo autenticado é de seis requisições/minuto e uma
execução simultânea, configurável. O controle é local ao processo e se reinicia
com o serviço; não controla gasto agregado nem protege todo o tráfego HTTP.
Somente `/health` é mantido público independentemente da chave; a documentação
também fica pública se explicitamente habilitada.

Arquivos de referência: [agente e prompt](../src/intelligent_marketplace/agents/executive/assistant.py),
[sessões de leitura](../src/intelligent_marketplace/infrastructure/database.py),
[configurações](../src/intelligent_marketplace/core/config.py),
[contrato do plano](../src/intelligent_marketplace/services/analysis_plan.py).

## Decisões de comportamento

O agente escolhe análises e pode consultar novamente ou reformular um plano sem
solicitar intervenção humana para completar a análise. Ambiguidades comuns devem
ser resolvidas com um critério explícito, conforme o catálogo de métricas.
Não se devem acrescentar consultas sem relação com a pergunta somente para
produzir uma evidência.

Sem dados elegíveis, a resposta deve explicar o recorte sem concluir que o
fenômeno nunca ocorreu. Sem campos para comprovar uma conclusão, deve apresentar
o que é observável e identificar o que falta. Taxa elevada com amostra pequena
deve ser contextualizada; ainda não há limiar estatístico validado para classificar
um vendedor como arriscado.

O Executivo é o ponto previsto para orquestração e consolidação de alertas. Nesta
implementação, ele executa análises históricas; os agentes Logístico e Jornada do
Cliente e seus fluxos operacionais ainda não foram integrados. Compensações
permanecem fora do escopo acordado.

## Lacunas registradas para as próximas etapas

| Prioridade | Lacuna | Próxima validação ou implementação |
|---|---|---|
| Antes de ampliar a confiança no modelo real | Há duas rodadas exploratórias de 14 perguntas, com revisão assistida, dados pequenos e sem repetições por versão | Ampliar formulações/amostras, repetir execuções e obter revisão humana |
| Antes de ampliar o uso | ID válido não garante pertinência; o backend aceita uma resposta com `evidence_ids=[]` e não identifica números sem suporte | Definir validação de fundamentação e política de resposta sem evidências |
| Antes de ampliar a publicação | Há chave compartilhada, limite do Executivo por processo e role de leitura no Neon; faltam identidades individuais e limites persistentes/distribuídos | Definir autenticação/auditoria conforme o público e revisar privilégios quando houver escrita operacional |
| Antes de auditar execuções | Evidências existem somente na resposta e no contexto temporário; não há trilha persistente de execução | Registrar versão do prompt, modelo, plano, fontes, duração e resultado com política de dados sensíveis |
| Antes de prometer controle de custo | Limites por execução não controlam orçamento agregado | Medir tokens/custo e estabelecer orçamento e concorrência |
| Antes de comparar rankings entre rotas | Arredondamento na ordenação difere entre plano flexível e rota simples por estado | Harmonizar ordenação antes de exigir resultados idênticos em empates aproximados |
| Antes de prever atrasos | Não há estimador de risco, calibração, política de alertas ou eventos operacionais atuais | Definir e validar o método preditivo e integrá-lo ao Agente Logístico |

Este mapeamento não aprova implantação em produção nem comprova eficácia do
modelo. A [matriz de validação](validation-scenarios.md) distingue os testes
determinísticos existentes da avaliação de comportamento. A primeira execução,
suas falhas e a repetição estão no [relatório de avaliação](evaluations/2026-11-22-review.md).
