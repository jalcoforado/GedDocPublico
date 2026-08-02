# Plano de implementação — arquitetura de monólito modular

> **Executor principal:** Claude Code
>
> **Especificação obrigatória:** [`../specs/2026-08-01-arquitetura-modular-monolito-design.md`](../specs/2026-08-01-arquitetura-modular-monolito-design.md)
>
> **Base do plano:** `main`, commit `6e368d1` em 2026-08-01; código funcional equivalente a `e1f2a08`

**Goal:** transformar a aplicação em um monólito modular no qual cada tenant contrata um ou mais módulos, cada usuário recebe papéis/capabilities e scopes por módulo, e os fontes ficam organizados por domínio sem quebrar contratos existentes.

**Architecture:** plataforma SaaS + core municipal sempre disponível + módulos comerciais Protocolo, Transporte, Frota e Pagamentos. Autorização em quatro camadas: tenant/RLS → entitlement → capability → data scope. Migração aditiva e vertical, com compatibilidade `legacy_safe → shadow → new`.

**Tech stack:** FastAPI, SQLAlchemy, PostgreSQL/RLS, Alembic manual, Celery/Redis, Next.js App Router, React Query, TypeScript, Vitest e pytest.

---

## 1. Protocolo de execução para o Claude Code

### 1.1 Antes de qualquer PR

1. Ler integralmente a especificação vinculada acima.
2. Executar `git status --short --branch` e `git rev-parse --short HEAD`.
3. Não sobrescrever, reformatar ou mover alterações locais do usuário.
4. Se a base avançou, revalidar todos os paths citados neste plano com `rg`; os paths alvo continuam válidos como arquitetura, mas números de linha não são contratos.
5. Procurar `AGENTS.md`, `CLAUDE.md` e instruções locais antes de editar.
6. Criar uma branch dedicada a um único PR. Não acumular várias tarefas deste plano na mesma branch.
7. Escrever ou atualizar testes de caracterização antes de mudar comportamento.
8. Manter o diff dentro dos arquivos declarados. Se surgir necessidade fora do escopo, parar e registrar a dependência no PR.
9. Não criar migration com número presumido. Executar `alembic heads`, confirmar um único head e gerar a próxima revisão sobre o head real.
10. Não reescrever migrations aplicadas, renomear schemas/tabelas ou mover dados de storage neste plano.

### 1.2 Ciclo obrigatório de cada PR

```text
confirmar precondições
  → teste vermelho de caracterização/regressão
    → menor implementação possível
      → testes focados
        → testes de contrato/estrutura
          → suíte proporcional ao risco
            → git diff --check
              → revisão de escopo, segurança e rollback
```

Na descrição de cada PR, preencher:

- problema resolvido;
- decisão arquitetural aplicada;
- arquivos e migrations;
- comportamento anterior e novo;
- evidência de testes;
- telemetria adicionada;
- rollback;
- itens explicitamente não resolvidos.

### 1.3 Comandos de verificação

Adaptar apenas se o ambiente do projeto exigir. Preferir os comandos já usados pelo repositório:

```powershell
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q <testes-focados>
Push-Location frontend
npm test -- <testes-focados>
npx tsc --noEmit
npm run build
Pop-Location
git diff --check
```

O container frontend padrão é standalone e não contém as devDependencies. Só usar Docker para Vitest/TypeScript quando um target de desenvolvimento com fontes e dependências estiver explicitamente ativo.
Não executar `npm run lint`: o repositório não possui ESLint configurado e o comando é interativo.

Para migrations:

```powershell
docker exec aprimora-py-backend alembic heads
docker exec aprimora-py-backend alembic current
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic downgrade -1
```

Se um teste de baseline já falhar antes da mudança, documentar o comando e a falha exata. Não alterar a asserção para mascarar regressão.

### 1.4 Regras globais de compatibilidade

- Nenhuma URL ou método HTTP muda antes do PR opcional `URL-01`.
- Nenhum nome lógico de task Celery muda durante a movimentação física.
- Wrappers nos paths Python antigos ficam até superar o maior horizonte de ETA/countdown + retries e comprovar filas drenadas; “um deploy” não é critério suficiente.
- `frontend/lib/api.ts` permanece como fachada temporária; novos imports são proibidos depois de `FE-01`.
- A tabela física `tenant_modulo` permanece. Somente seus booleanos legados, adapters e o RBAC legado podem ser removidos na família `CONTRACT-*`, após evidência de paridade.
- Uma migration aditiva não é revertida em rollback operacional; o código volta a ler o legado por flag.
- O superusuário do tenant nunca contorna entitlement.
- Uma operação sem classificação explícita falha no teste estrutural.
- Compatibilidade Celery inclui nome, assinatura/payload, serializer, routing key, fila, retry/ack e semântica de resultado. Contexto novo é buscado por `job_id`; não adicionar kwargs enquanto houver workers N-1.
- Todo gate novo possui ao menos um teste HTTP com usuário comum não-SU; suíte apenas com superusuário não valida o caminho real de permissões.
- O fail-open atual de transações sem owner/leitura sem permissão permanece em `legacy_safe`; só é substituído por deny v2 no PR de enforcement aprovado do módulo, junto com a atualização dos testes de caracterização.

### 1.5 Gates que exigem aprovação humana

O executor deve pausar o respectivo cutover se faltar:

- principal administrativo separado e seu `(issuer, subject, audience)` em `SEC-01A/B`;
- matriz capability × perfil × scope do módulo em `TRN-01`, `FRO-01`, `PAG-01` ou `PRO-01`;
- política de leitura histórica/suspensão do módulo em `ENT-02` e antes de cada cutover;
- divergência zero dos cenários críticos no shadow mode em `RBAC-02`;
- inventário completo de endpoints, tasks, CLI, uploads, exports, portal e integrações do módulo;
- autorização explícita para executar `URL-01`;
- `SEC-RLS-ROLLOUT`: cada promoção de ambiente (teste/dev → homologação → produção) é gate humano próprio. Produção exige paridade demonstrada, observabilidade e rollback ensaiado.

### 1.6 Verificação obrigatória de migrations

Toda onda com banco deve provar:

- upgrade em banco limpo;
- upgrade sobre fixture legada representativa do CI;
- binário N-1 operando sobre o schema expandido;
- binário novo antes e depois do backfill;
- RLS e grants exercitados diretamente com o papel real da aplicação;
- contagens e checksums antes/depois de backfill idempotente;
- um único Alembic head;
- backup/restore ensaiado quando houver contract destrutivo.
- quando catálogo/seed muda, atualizar e testar `seed_bootstrap.py`, `ci/seed-e2e.sql` e os workflows `backend-tests`/`e2e-assinatura` que repetem bootstrap.

Colunas usadas por runtime seguem `nullable/compatível → backfill observável → validação → NOT NULL em PR posterior`. Rollback de expand volta ao compatibility build, nunca a um binário que desconheça o dual-write já ativado.

---

## 2. Mapa de ondas e dependências

| Ordem | PR | Resultado | Depende de |
|---|---|---|---|
| S0 | `SEC-00` | IdP/realm administrativo decidido | — |
| S1 | `SEC-01A/B` | principal e UI SaaS separados de identidades/sessões municipais | `SEC-00` aprovado |
| S2 | `SEC-02` | bloqueio de autoelevação e grants fora da autoridade | `SEC-01A` |
| S3 | `SEC-RLS-00A` | prova de que o runtime ignora RLS (**F-12**) e inventário do que depende do bypass | nenhuma — pode correr em paralelo a `SEC-01A`, não muda runtime |
| S4 | `SEC-RLS-00B` | papéis mínimos por função, nenhum de runtime `SUPERUSER` | `SEC-RLS-00A`; papéis coordenados com `SEC-01A` |
| gate | `SEC-RLS-ROLLOUT` | trocar o papel do runtime por ambiente, com rollback comprovado | `SEC-RLS-00B` |
| A1 | `ARC-01` | inventário executável e guardas | pode ocorrer em paralelo à contenção, sem runtime |
| A2 | `ARC-02` | composition, manifestos lazy e contrato gerado | `ARC-01` |
| E1 | `ENT-01A/B` | expand compatível e cutover HTTP | `ARC-02`, deploys em ordem |
| C1 | `CORE-01` | owner core e fim da dependência comercial de Administração | `SEC-02`, `ENT-01B` |
| E1C | `ENT-01C` | onboarding versionado | `CORE-01` |
| E2 | `ENT-02` | lifecycle em portal/tasks/CLI/uploads/exports | `ENT-01C`, `CORE-01` |
| gate | `ENT-ROLLOUT` | liberar operações administrativas de lifecycle | `ENT-02` em API, worker e beat + playbooks aprovados |
| C2 | `CORE-02A..B` | schema transversal e providers backend | `ARC-02`, `ENT-02` |
| R1 | `RBAC-01` | schema v2/RLS/templates/estado de cutover | `SEC-02`, `CORE-01`, `ENT-02`, **`SEC-RLS-ROLLOUT` concluído** |
| T1 | `TRN-01` | matriz/templates Transporte | `RBAC-01` |
| R2 | `RBAC-02` | motor shadow e AccessSnapshot | `TRN-01`, `ENT-02` |
| F1 | `FE-01` | staff provider, route gates e registry frontend | `RBAC-02` |
| C3 | `CORE-02C` | home/busca/notificações frontend componíveis | `CORE-02B`, `FE-01` |
| T2 | `TRN-02..04` | movimento backend, enforcement dormente e frontend | `RBAC-02`, `FE-01` |
| gate | `TRN-ROLLOUT` | ativação humana por tenant | piloto pronto e limiares atendidos |
| seguinte | `FRO-01..04` | matriz → backend → shadow → frontend | saída do piloto Transporte |
| seguinte | `PAG-01`, `PAG-02A/B`, `PAG-03/04` | matriz → deploy Celery em dois passos → shadow → frontend | saída do piloto Transporte |
| seguinte | `PRO-01`, `PRO-02A..E`, `PRO-03/04` | matriz/política → subdomínios → shadow → frontend | Frota/Pagamentos estabilizados |
| depois | `PLAT-01..02` | consolidar plataforma/core/shared backend e frontend | módulos migrados |
| opcional | `URL-01` | `/m/<slug>` com redirects frontend | gates/manifestos estáveis e autorização explícita |
| final | `CONTRACT-01..04` | parar writes/reads, remover fachadas e contract DB | janelas/filas/telemetria concluídas |

`FRO-*` e `PAG-*` podem ser executados em ordem trocada depois do piloto, desde que cada módulo mantenha matriz → movimento → enforcement dormente → frontend → rollout humano. Código e rollout nunca são misturados no mesmo PR. Protocolo permanece por último.

---

## 3. Onda 0 — contenção de segurança

### PR `SEC-00` — fechar a arquitetura da identidade de operador SaaS

**Objetivo:** transformar a separação de realm em uma decisão implementável antes de tocar no gate cross-tenant.

**Arquivos a inspecionar:**

- `backend/app/auth/`
- `backend/app/config.py`
- emissão/validação JWT atual, OAuth e variáveis de ambiente
- `docker-compose.yml` e configuração de homologação/produção
- fluxos atuais de `admin_tenants`

**Novos arquivos alvo:**

- `docs/architecture/adr/ADR-016-platform-operator-identity.md`
- `docs/runbooks/platform-operator-bootstrap.md`
- fixtures de token administrativo em testes, sem chaves reais

**Decisões que o ADR deve fechar:**

- IdP/realm administrativo e ambientes;
- `(issuer, audience, subject)` e algoritmo/JWKS;
- aquisição e renovação de token;
- rotação/revogação de chaves e cache JWKS;
- MFA e lifecycle do operador;
- bootstrap inicial e aprovação/revogação;
- break-glass com prazo, dupla aprovação e auditoria;
- estratégia local/teste que não aceite token municipal;
- indisponibilidade do IdP/JWKS com fail-closed e procedimento operacional.
- role/conexão de banco exclusiva da fronteira de plataforma, separada do runtime municipal.

**Testes/provas:** matriz de claims aceitos/negados, threat model de confusão de token, exemplo local reproduzível e confirmação de que nenhum segredo será versionado.

**Aceite:** ADR aprovado pelo responsável técnico/operacional e todos os dados necessários a `SEC-01A/B` definidos. Sem aprovação, o executor para aqui.

**Rollback:** não aplicável ao runtime; este PR é de decisão e fixtures.

**Commit:** `docs(security): define platform operator identity realm`

**Não incluir:** implementar o gate, cadastrar operador real ou alterar autenticação municipal.

### PR `SEC-01A` — substituir allowlist por principal administrativo separado

**Dependência:** `SEC-00` aprovado.

**Objetivo:** eliminar o caminho em que uma conta municipal com e-mail coincidente recebe privilégios cross-tenant.

**Arquivos existentes candidatos:**

- `backend/app/auth/deps.py`
- `backend/app/config.py`
- `backend/app/routers/admin_tenants.py`
- `backend/app/routers/usuarios.py`
- `backend/app/models/usuario.py` ou barrel equivalente
- `backend/app/cli/`
- `backend/tests/test_admin_tenants.py`
- testes de autenticação relacionados

**Novos arquivos alvo:**

- `backend/app/platform/operator_identity/principal.py` ou, antes de `ARC-02`, serviço compatível em `backend/app/services/platform_admin.py`
- `backend/app/models/platform_identity.py` temporário, se a estrutura alvo ainda não existir
- `backend/alembic/versions/<next>_platform_admin_identity.py`
- `backend/tests/test_platform_admin_identity.py`

**Implementação:**

1. Escrever teste que cria, em outro tenant, usuário com e-mail da allowlist atual e prova que ele é negado em operação cross-tenant.
2. Introduzir `platform_principal` em namespace de segurança separado, identificado por `(issuer, subject)` ou ID dedicado; proibir vínculo a `utils.usuario.id`, e-mail ou qualquer cadastro do tenant.
3. Configurar validação de issuer/audience/realm administrativo e rejeitar tokens municipais nas rotas de plataforma.
4. Garantir que endpoints municipais não criam, alteram ou concedem principal de plataforma.
5. Substituir `require_platform_admin` para validar token administrativo e consultar o principal dedicado ativo.
6. Separar dependency/transaction manager das rotas SaaS: não reutilizar `require_tenant_id` nem sessão RLS municipal; tenant alvo vem explicitamente da operação e é auditado.
7. Remover a allowlist de e-mails do caminho de autorização. Bootstrap ocorre por fluxo operacional restrito fora das APIs municipais.
8. Auditar grant, revoke e uso de operações cross-tenant, incluindo issuer, subject e tenant alvo normalizados.
9. Documentar procedimento operacional de bootstrap/MFA sem segredo no repositório.

**Testes mínimos:**

- colisão do mesmo e-mail em tenants distintos é negada;
- issuer ou audience incorretos são negados;
- subject colidente em issuer diferente não é confundido;
- principal não provisionado é negado e principal administrativo ativo é permitido;
- usuário municipal excluído/recriado não afeta o principal administrativo;
- usuário desativado/revogado é negado;
- endpoint municipal não concede identidade de plataforma;
- rota SaaS não herda tenant/default tenant municipal e usa apenas o tenant alvo explicitamente validado;
- isolamento/RLS das rotas municipais continua válido.

**Aceite:** nenhuma checagem de autorização cross-tenant depende apenas de string de e-mail; `rg` não encontra o allowlist no caminho de decisão.

**Rollback:** voltar a versão anterior das telas/fluxos administrativos mantendo o gate de token administrativo e principal dedicado; nunca restaurar autorização por e-mail, ID ou token municipal. A tabela aditiva permanece.

**Commit sugerido:** `fix(security): require dedicated platform operator principal`

**Não incluir:** refactor da autenticação municipal, movimentação física dos módulos ou mudanças de RBAC de negócio.

### PR `SEC-01B` — separar sessão e cliente da UI de operador

**Dependências:** `SEC-01A` e o fluxo definido em `SEC-00`.

**Arquivos candidatos:** rotas frontend de administração cross-tenant, login/clients HTTP, middleware e testes de sessão.

**Arquivos alvo:** `frontend/app/(operator)/`, `frontend/platform/operator-admin/` e cliente HTTP operator dedicado.

**Implementação:**

1. Autenticar operador pelo realm/audience administrativo e armazenar credencial separada da municipal.
2. Mover telas cross-tenant para árvore/provider/query cache de operador.
3. Rejeitar cookie/token staff nas rotas SaaS e nunca enviar token operator a APIs municipais/cidadão.
4. Implementar logout/revogação e erros fail-closed conforme o runbook.

**Testes:** token/cookie cruzado em ambas as direções, issuer/audience errados, logout/revoke, cache isolation e build.

**Aceite:** nenhuma tela/rota cross-tenant usa sessão municipal; as quatro superfícies operator/staff/cidadão/público estão isoladas.

**Rollback:** manter UI administrativa indisponível se o realm falhar; nunca voltar a token municipal/e-mail.

**Commit:** `fix(frontend-security): isolate platform operator session`

### PR `SEC-02` — autoridade de concessão e proteção contra autoelevação

**Objetivo:** impedir que `usuario.atualizar` ou edição de grupo conceda superusuário/papel acima da autoridade do ator.

**Arquivos existentes candidatos:**

- `backend/app/routers/usuarios.py`
- `backend/app/routers/grupos.py`
- `backend/app/services/permissoes.py`
- `backend/app/models/grupo.py`
- `backend/app/schemas/grupo.py`
- `backend/app/models/audit.py`
- testes de usuários, grupos, permissões e auditoria

**Novos arquivos alvo:**

- `backend/app/services/grant_policy.py`
- `backend/tests/test_grant_policy.py`

**Implementação:**

1. Caracterizar os caminhos atuais: atribuir grupo arbitrário, criar nível 0, editar grupo privilegiado e elevar a si próprio.
2. Criar uma política central `assert_can_manage_role` / `assert_can_assign_role`; não espalhar condicionais nos routers.
3. Como contenção anterior ao RBAC v2, permitir mudança de grupo/assignment privilegiado somente por superusuário ativo distinto do alvo; a própria pessoa nunca altera sua elevação.
4. Bloquear autoelevação e edição/rebaixamento de papéis protegidos sem capability privilegiada.
5. Validar no backend que usuário, grupo/papel e vínculos pertencem ao mesmo tenant.
6. Separar semanticamente gerir usuário, gerir papel, atribuir papel e conceder papel privilegiado, ainda que inicialmente adaptadas às transações legadas.
7. Proteger o último tenant owner/superusuário ativo contra remoção sem substituto.
8. Auditar criação/edição de grupo, mudança de nível, grant, revoke, `revoked_by`, motivo e tentativa negada relevante.

**Testes mínimos:**

- usuário com `usuario.atualizar` comum não atribui nível 0;
- ninguém eleva a si próprio;
- concedente não atribui papel fora de sua autoridade;
- alteração posterior de um grupo/papel já atribuído revalida todos os usuários afetados;
- último tenant owner não é removido sem substituto;
- ator autorizado atribui papel permitido a outro usuário;
- IDs cross-tenant são rejeitados;
- superusuário legado não contorna módulo não contratado;
- alterações geram auditoria.

**Aceite:** os exploits F-02 possuem testes de regressão; decisão de grant está em um serviço único.

**Rollback:** manter endpoint anterior atrás de flag apenas em ambiente de recuperação e deny por padrão; não remover validações cross-tenant.

**Commit sugerido:** `fix(security): enforce delegated role grant policy`

**Não incluir:** tabelas completas de RBAC v2, mudança de menus ou papéis de Transporte.

### PR `SEC-RLS-00A` — caracterizar F-12 e inventariar o que depende do bypass

**Dependência:** nenhuma. Pode correr em paralelo a `SEC-01A`. Não altera runtime.

**Contexto:** a aplicação conecta como `ged_user`, `SUPERUSER` e `BYPASSRLS` (achado **F-12** da especificação). A RLS que o invariante 10 chama de última barreira está inerte. Este PR **não conserta** — ele mede. A ordem é deliberada: o runtime opera com bypass há tempo suficiente para que caminhos hoje funcionais dependam dele sem registro, e trocar a credencial antes do inventário converte um achado conhecido em incidente desconhecido.

**Arquivos a inspecionar:**

- `docker-compose.yml`, `docker-compose.dev.yml`, `backend/.env.example`, `scripts/deploy.sh`
- `backend/app/database.py` (engine, `get_db`, listener `after_begin`, `tenant_filter`)
- `backend/tests/conftest.py` (`admin_engine` × `app_session`)
- todas as migrations com `POLICY`, `ROW LEVEL SECURITY`, `GRANT` ou `SECURITY DEFINER`
- `backend/app/tasks/` e `backend/app/cli/` — como abrem sessão e se definem `app.tenant_id`

**Novos arquivos alvo:**

- `backend/tests/test_rls_bypass_caracterizacao.py`
- `docs/architecture/security/rls-bypass-inventory.md`

**Implementação:**

1. Escrever teste que **prova** o bypass por inversão, não por afirmação: com `ged_user` e `app.tenant_id` de um tenant A, um `SELECT` na tabela de negócio **retorna** linhas do tenant B; o mesmo `SELECT` com `aprimora_app` **não** retorna. Um teste que só afirmasse `rolbypassrls = true` no catálogo provaria configuração, não consequência.
2. Inventariar, com consulta ao catálogo e não de memória: papéis existentes e seus atributos (`pg_roles`), tabelas com `relrowsecurity`/`relforcerowsecurity` e as que **não** têm (`pg_class`), policies (`pg_policies`), grants por papel (`information_schema.role_table_grants`), sequences (`role_usage_grants`) e funções `SECURITY DEFINER` (`pg_proc.prosecdef`).
3. Registrar cada divergência: tabela tenanted **sem** RLS, tabela com RLS **sem** grant para `aprimora_app`, sequence sem `USAGE`, policy que referencia `current_setting` sem o `true` de tolerância.
4. Rodar a suíte completa com `aprimora_app` como papel da aplicação — **sem** commitar a troca. Registrar cada falha com comando, teste e erro exato. Uma falha aqui é dado do inventário, não bug a corrigir neste PR.
5. Classificar cada consumidor de banco em quatro categorias, com o papel alvo de cada um: **API municipal** (sujeito a RLS), **worker Celery** (grants mínimos), **migrations/DDL** (dono do schema, fora do runtime) e **plataforma** (cross-tenant por grant explícito).
6. Fechar o inventário com a lista nominal do que **hoje depende** do bypass e por quê — é esse conjunto que `SEC-RLS-00B` tem de resolver com policy ou grant.

**Testes mínimos:**

- bypass demonstrado por diferença de resultado entre os dois papéis;
- `aprimora_app` de fato não tem `BYPASSRLS` nem `SUPERUSER` (guarda contra regressão de provisionamento);
- guarda estrutural: toda tabela em `aprimora_py.*` e `frota.*` com coluna `tenant_id` tem RLS habilitada **e** forçada, ou consta de uma allowlist com razão escrita.

**Aceite:** o inventário lista todo consumidor de banco com seu papel alvo, e a execução da suíte com `aprimora_app` está registrada com o resultado real — inclusive as falhas.

**Rollback:** não aplicável. Nenhuma mudança de runtime, nenhum papel criado.

**Commit sugerido:** `test(security): caracteriza bypass de RLS no runtime (F-12)`

**Não incluir:** criar papel, alterar `DATABASE_URL`, corrigir policy ou grant. Corrigir aqui destruiria a medição.

### PR `SEC-RLS-00B` — papéis mínimos por função e compatibilidade

**Dependência:** `SEC-RLS-00A` concluído. Papéis coordenados com `SEC-01A`.

**Objetivo:** dar a cada consumidor de banco o menor papel que o faz funcionar, sem nenhum papel de runtime `SUPERUSER`.

**Divisão de autoridade sobre papéis — não violar:**

| Papel | Criado por | Observação |
|---|---|---|
| `aprimora_platform` | `SEC-01A` | `SEC-RLS-00B` **verifica**, não redefine |
| `aprimora_app` | já existe | ajustar grants |
| `aprimora_worker` | `SEC-RLS-00B` | grants mínimos por task |
| `aprimora_migrator` | `SEC-RLS-00B` | DDL; nunca usado por runtime |

Duas migrations que criem o mesmo papel colidem no `CREATE ROLE`. Se a ordem de merge for incerta, usar `DO $$ ... IF NOT EXISTS`, e ainda assim manter a autoridade acima.

**Novos arquivos alvo:**

- `backend/alembic/versions/<next>_papeis_minimos_runtime.py`
- `backend/tests/test_rls_papeis_minimos.py`

**Implementação:**

1. Criar `aprimora_worker` e `aprimora_migrator` com grants enumerados. Nenhum recebe `SUPERUSER`; nenhum recebe `BYPASSRLS`.
2. Ajustar os grants de `aprimora_app` para cobrir o que o inventário de `00A` mostrou faltando — tabela a tabela, sequence a sequence.
3. Resolver cada dependência de bypass listada em `00A` **na policy ou no grant**. Restaurar `BYPASSRLS` é proibido, inclusive "temporariamente".
4. Tornar o papel do runtime **configurável**: a troca é seleção de `DATABASE_URL` por ambiente, e a variável antiga continua válida. É esse mecanismo que dá rollback sem redeploy de código durante `SEC-RLS-ROLLOUT`.
5. Não trocar o valor efetivo em nenhum ambiente neste PR. A troca é `SEC-RLS-ROLLOUT`.

**Requisitos que vieram da medição de `SEC-RLS-00A`** — decididos em 2026-08-01, com o inventário na mão:

6. **`transporte_regulado` é o maior item.** 20 policies em 5 tabelas referenciam `current_setting('app.current_tenant_id')`, GUC que a aplicação **nunca** seta — ela seta `app.tenant_id` (`backend/app/database.py`). E estão **sem** o segundo argumento `true`, então a policy não nega: derruba a consulta com `unrecognized configuration parameter`. Somam-se 4 tabelas e 6 sequences sem grant para `aprimora_app` e 8 tabelas com `ENABLE` sem `FORCE`. A migration 0061 corrigiu só `alvara`. Sem isto, o módulo inteiro para no instante em que o bypass sair.
7. **Falhas silenciosas antes das ruidosas.** `limpar_jobs_antigos` no modo beat (`tenant_id=None`) e `cli/backup.py` leem tabelas com RLS sem `app.tenant_id` e recebem **zero linhas sem erro**. O backup produz arquivo sintaticamente válido e vazio, e o sintoma só aparece no restore — longe da causa. Além do contexto de tenant explícito, o backup passa a **falhar alto** quando resultar em zero linhas para um tenant que tem dados. Erro barulhento é requisito, não refinamento.
8. **`services/audit.py` para de engolir a exceção do flush.** Hoje o `except` converte "operação falha" em "operação sem trilha", com erro só no log. Sem bypass, esse vira o modo de falha padrão das rotas que auditam. A mudança é **aqui e não antes**: só faz sentido falhar alto depois que todos os caminhos de auditoria estiverem provadamente corretos, senão um defeito latente vira 500 imediato.
9. **Consertar o arreio de teste é pré-requisito, não consequência.** Os arquivos que sobrepõem `require_tenant_id` sem também definir `request.state.tenant_id` — de onde `get_db` tira o `SET LOCAL` — falham por defeito do teste, não do código. Corrija-os **antes** de mexer em policy, senão as falhas restantes se confundem com regressão causada por este PR. A lista está na §8.8 do inventário; `test_sec1_login_me_flag.py` tem o padrão correto, com header `Host`.
10. **Partir o provisionamento de tenant em dois atos.** Decidido em 2026-08-01, durante `SEC-01A`. **FEITO em `SEC-RLS-00C` (2026-08-02), branch `sec-rls/00c-partir-provisionamento`.** `provisionar_tenant` gravava em `tenant`, `tenant_modulo` e `audit_log` **e** nas tabelas de negócio do tenant (`utils.usuario`, `utils.grupo`, `protocolos.tipo_manifestante`), tudo sob o papel municipal. Isso contradizia o ADR-016 §2.3, que nega DML de entitlement a `aprimora_app` — mas mover o bloco inteiro para `aprimora_platform` seria pior: daria ao papel de plataforma DML nas tabelas de negócio dos tenants, exatamente o que o §2.3 lhe nega. A saída foi **partir**, não afrouxar: `criar_registro_de_tenant` (tenant + contratação inicial) roda sob `aprimora_platform`; `semear_tenant` (usuário admin, grupo SU, unidade, catálogos, trilha) roda sob o papel municipal, já com `SET LOCAL app.tenant_id` no tenant novo; `_concluir_ativacao` fecha. Efeito colateral desejado, obtido: o provisionamento tem hoje uma fronteira explícita onde havia um bloco monolítico que só funcionava porque um papel podia tudo.

   **O modo de falha novo, decidido e escrito:** partir uma transação em duas cria a possibilidade de o ato 1 comitar e o ato 2 falhar. A escolha foi **marcar + reexecutar, nunca compensar**. O tenant nasce `ativo = false` e só o ato 3 o ativa, de modo que um provisionamento pelo meio deixa um tenant **inerte** — o `TenantMiddleware` resolve com `slug = :s AND ativo = true`, então ninguém entra nele. O ato 2 é idempotente (get-or-create por chave natural) e a retomada é um comando nomeado, `retomar_provisionamento` / `python -m app.cli.tenant retomar`, que **recusa tenant ativo** (retomar um tenant vivo criaria um super-usuário num município em produção). Compensação por `DELETE` foi descartada: apagar tenant não é operação de runtime nenhum, e a 0076 deliberadamente não deu `DELETE` nem ao papel de plataforma.

**O buraco de entitlement que isso deixava — revogado pela migration `0079` (`SEC-RLS-00C`); fecha em produção quando `APP_DATABASE_URL` for definida.** A fronteira estava fechada no HTTP e **aberta no SQL**: `aprimora_app` tinha `INSERT` em `aprimora_py.tenant_modulo`, tabela que **não tem RLS** por decisão registrada, de modo que o `GRANT` era a única barreira e qualquer injeção ou defeito de service no runtime municipal auto-contratava módulo para qualquer tenant. A 0079 revoga `INSERT` em `tenant` e em `tenant_modulo`; `UPDATE` em `tenant` **fica** (configuração institucional do próprio município, `services/tenant_config` — mas o grant é de tabela inteira e alcança `ativo`/`plano`/`slug`: ver `SEC-RLS-00D` no backlog) e `INSERT` em `audit_log` **fica** (trilha do próprio município, e a tabela tem RLS FORCE — há segunda barreira). Estado hoje: `tenant | SELECT,UPDATE` e `tenant_modulo | SELECT`. Guarda com controle positivo e prova por inversão em `tests/test_entitlement_fronteira_sql.py`.

**A qualificação importa e não é formalidade:** `APP_DATABASE_URL` está vazia em todos os ambientes, então o runtime ainda conecta como `ged_user` (`rolbypassrls = t`) e o `REVOKE` não tem efeito ali. Os testes provam a propriedade **sob `aprimora_app`** — o papel que o `SEC-RLS-ROLLOUT` vai promover. Revogar antes de trocar o papel é a ordem certa; o que não se pode é ler isto como "fechado em produção". Registrado como item 1.0.86 do backlog. Continua verdade que `POST /admin/tenants` usa a sessão municipal para o ato 2, mas agora ela é exatamente a sessão que **não** contrata.

11. **Duas falhas pré-existentes** (`test_jwt_compat::test_emitted_token_has_required_claims`, por `APP_NAME` local valer `aprimora` e o teste esperar `sistemas`; e `test_pr5a_dashboard_servicos::test_http_dashboard_com_perm_acessa`) não têm relação com F-12, falham igual nos dois papéis e **não** são escopo deste PR. Não as conserte junto; não as use como sinal de regressão.

**Testes mínimos:**

- nenhum papel de runtime é `SUPERUSER` ou tem `BYPASSRLS` — teste que varre `pg_roles`;
- com `aprimora_app`, um usuário do tenant A não alcança dado do tenant B em nenhuma tabela de negócio;
- a suíte completa passa com `aprimora_app` como papel da aplicação;
- pelo menos um teste HTTP com **usuário comum não-SU** por módulo contratado, porque a suíte só com superusuário não exercita o caminho real;
- worker executa suas tasks com `aprimora_worker`;
- `aprimora_migrator` aplica `upgrade head` em banco limpo; `aprimora_app` **não** consegue DDL.

**Aceite:** todas as suítes verdes com papéis sujeitos a RLS, e a lista de dependências de bypass de `00A` zerada ou com razão registrada por item remanescente.

**Rollback:** apontar `DATABASE_URL` de volta ao papel anterior. Os papéis e grants criados permanecem — são aditivos.

**Commit sugerido:** `feat(security): papeis minimos de runtime sujeitos a RLS`

**Não incluir:** trocar o papel efetivo em homologação ou produção; mudar RBAC de negócio.

### Gate operacional `SEC-RLS-ROLLOUT` — trocar o papel do runtime por ambiente

**Dependência:** `SEC-RLS-00B` em `main`.

Não é PR de código. É a sequência de promoção, um gate humano por degrau:

0. **`PLATFORM_DB_URL` — o degrau que ninguém percebeu que faltava.** Ela **não está definida em ambiente nenhum**: nem no `docker-compose.yml`, nem no `backend/.env`, nem no CI. Só o arreio de teste a define. Consequência: o papel `aprimora_platform`, criado pelo `SEC-01A` justamente para isolar a fronteira cross-tenant, **existe, tem grants, tem teste — e nada o usa em execução**. As rotas de plataforma caem na credencial administrativa. A separação de papel está provada nos testes e **não vigora no runtime**. Este é o primeiro degrau porque é o de menor risco: as rotas de plataforma já estão inalcançáveis hoje (sem OIDC configurado e com `is_platform_admin` constante `false`), então ligar a conexão dedicada não pode quebrar caminho em uso.
1. **Teste e desenvolvimento.** Trocar, rodar a suíte completa, o e2e e a navegação manual dos cinco módulos.
2. **Homologação.** Trocar e validar **todos** os módulos, jobs, uploads, exports e tasks Celery — incluindo os agendados pelo beat, que só aparecem no horário. Exercitar isolamento com usuário comum não-SU em cada módulo contratado.
3. **Produção.** Somente após paridade demonstrada, observabilidade instalada (erro de permissão de banco precisa ser distinguível de erro de negócio no log) e rollback ensaiado de verdade, não descrito.

**Critério de parada:** qualquer erro de permissão em caminho não previsto pelo inventário volta para `SEC-RLS-00B` como correção de policy ou grant. Voltar o papel é rollback aceitável; reativar `BYPASSRLS` não é.


---

## 4. Onda 1 — inventário, limites e composition root

### PR `ARC-01` — inventário executável e testes de guarda

**Objetivo:** tornar visível e verificável quem é dono de cada superfície antes de mover fontes.

**Arquivos existentes candidatos:**

- `backend/tests/test_guarda_modularizacao.py`
- `backend/tests/test_leitura_por_modulo.py`
- `frontend/lib/menus/`
- `frontend/lib/modulos.ts` ou mapas equivalentes
- `docs/`

**Novos arquivos alvo:**

- `docs/architecture/module-inventory.md`
- `backend/tests/contracts/openapi.normalized.json`
- `backend/tests/architecture/test_module_surface_inventory.py`
- `backend/tests/architecture/test_import_boundaries.py`
- `frontend/__tests__/architecture/module-registry.test.ts`
- script de inventário somente se necessário em `scripts/architecture/`

**Inventário obrigatório:**

- endpoint/método → core/plataforma/módulo → capability → scope suportado;
- task/schedule → módulo → nome lógico → fila;
- CLI → proprietário;
- upload/export/storage → proprietário;
- tabela/schema → proprietário;
- portal/inbound webhook → proprietário;
- rota frontend/menu/query → módulo;
- integrações e FKs cross-module.

**Implementação:**

1. Gerar snapshot OpenAPI normalizado (ordem estável, sem servers/versões voláteis) de paths, métodos e schemas. Atualização exige diff no PR e aprovação explícita; breaking changes são bloqueadas.
2. Consolidar as tabelas manuais atuais em inventário versionado.
3. Criar teste de igualdade entre o inventário e os conjuntos extraídos de OpenAPI, registry Celery, comandos CLI registrados e rotas frontend; qualquer item ausente ou excedente exige classificação explícita.
4. Criar primeira guarda de imports, inicialmente em modo relatório para violações legadas e erro para novas violações: shared não importa core/platform/modules; core/platform não importam módulo; módulo não importa outro; composition é o único agregador.
5. Congelar nomes de tasks Celery e registrar aliases necessários.
6. Registrar contagem/base dos imports de `@/lib/api` para permitir apenas redução.

**Testes mínimos:** testes arquiteturais novos, geração determinística do snapshot e `git diff --check`.

**Aceite:** a igualdade automatizada dos quatro conjuntos passa; uma rota/task/CLI/path fictício sem dono faz o teste falhar.

**Rollback:** remover somente a integração de CI se ela bloquear por falso positivo; preservar inventário. Nenhum runtime muda.

**Commit sugerido:** `test(architecture): inventory module-owned surfaces`

**Não incluir:** mover arquivos ou mudar autorização.

### PR `ARC-02` — skeleton de plataforma, módulos, manifestos e registry

**Objetivo:** criar a casca arquitetural e substituir registro manual por composição, sem alterar comportamento externo.

**Arquivos existentes candidatos:**

- `backend/app/main.py`
- `backend/app/tasks/celery_app.py`
- `backend/app/routers/__init__.py`
- `backend/tests/test_guarda_modularizacao.py`

**Novos arquivos alvo:**

```text
backend/app/composition/__init__.py
backend/app/composition/api.py
backend/app/composition/celery.py
backend/app/composition/module_registry.py
backend/app/platform/__init__.py
backend/app/core/__init__.py
backend/app/modules/{protocolo,pagamentos,frota,transporte}/__init__.py
backend/app/modules/{protocolo,pagamentos,frota,transporte}/manifest.py
backend/app/shared/__init__.py
backend/tests/architecture/test_module_registry.py
backend/app/composition/export_module_contract.py
backend/app/core/manifest.py
frontend/core/modules/module-contract.generated.json
```

**Implementação:**

1. Definir `ModuleManifest` com slug, dependências, referências lazy/factories de routers/tasks/providers, capabilities, schedules e storage.
2. Criar manifesto `core` e manifestos adaptadores comerciais que apontam para routers/tasks atuais. Antes das matrizes v2, declarar owner/superfícies legadas e deixar capabilities de negócio pendentes de forma explícita, sem inventar catálogo.
3. Construir registry determinístico na composition root.
4. Fazer FastAPI registrar routers pela composição preservando ordem, prefixos e tags.
5. Fazer Celery consumir metadados sem mudar nomes lógicos nem schedule.
6. Validar slug único, dependência conhecida/sem ciclo e classificação completa; importar `manifest.py` isoladamente não pode carregar routers, models ou tasks.
7. Gerar contrato JSON determinístico do registry Python; o frontend só referencia slugs/capabilities desse artefato e o CI regenera/exige diff zero.
8. Manter todos os routers do binário registrados globalmente; entitlement decide em runtime.
9. Manter `app.main:app` e entrypoints atuais compatíveis.

**Testes mínimos:**

- snapshot OpenAPI sem diff não aprovado;
- lista/ordem efetiva de routers preservada;
- nomes de tasks e beat schedule preservados;
- registry rejeita duplicação/ciclo;
- startup e health check.

**Aceite:** composition conhece todos os módulos; módulos continuam nos paths antigos; nenhuma mudança funcional ou de URL.

**Rollback:** `main.py` e `celery_app.py` voltam a registrar listas manuais; manifestos inertes podem permanecer.

**Commit sugerido:** `refactor(architecture): add module composition registry`

**Não incluir:** entitlement novo, RBAC novo ou movimento de código de negócio.

---

## 5. Onda 2 — entitlement completo e core obrigatório

### PR `ENT-01A` — expandir entitlement com build de compatibilidade N-1

**Objetivo:** expandir `TenantModulo` sem mudar ainda a autoridade de leitura e provar deploy misto seguro.

**Arquivos existentes candidatos:**

- `backend/app/models/modulo.py`
- `backend/app/services/modulos.py`
- `backend/app/auth/modulos.py`
- `backend/app/auth/perms.py`
- `backend/app/routers/admin_tenants.py`
- `backend/app/config.py`
- testes de modularização e tenants

**Novos arquivos alvo:**

- `backend/app/platform/entitlements/models.py`
- `backend/app/platform/entitlements/compatibility.py`
- `backend/alembic/versions/<next>_expand_module_entitlements.py`
- `backend/tests/platform/test_entitlements.py`

**Implementação:**

1. Adicionar campos nullable/compatíveis de status, vigência, origem, referência comercial, provisioning, versão e autoria na tabela física existente. Não criar segunda tabela.
2. Fazer o build de compatibilidade continuar lendo `ativo/excluido` e passar a dual-write os novos campos em qualquer mutação.
3. Não ativar deny por campo novo nesta etapa; um processo N-1 continua funcional sobre o schema expandido.
4. Definir transições, intervalo UTC `[from, until)`, lock otimista e mapeamento booleanos↔status, ainda sem cutover.
5. Instrumentar writes N-1 detectáveis e divergências, sem alterar o resultado de acesso.

**Testes mínimos:** migration em banco limpo/legado, binário N-1 sobre schema expandido, dual-write do compatibility build, concorrência de versão e nenhuma alteração de OpenAPI/decisão.

**Aceite:** API, worker e beat de compatibilidade podem ser implantados em qualquer ordem com N-1; todos os processos novos dual-write e a autoridade ainda é legada.

**Rollback:** voltar ao compatibility build; campos aditivos permanecem. Não voltar a binário anterior depois de iniciar backfill/cutover.

**Commit sugerido:** `feat(entitlements): expand module lifecycle compatibly`

**Não incluir:** backfill, autoridade nova, onboarding ou RBAC v2.

### PR `ENT-01B` — backfill, paridade e autoridade canônica em HTTP

**Dependência operacional:** `ENT-01A` implantado em API, workers e beat; nenhum processo N-1 anterior ao compatibility build.

**Novos arquivos alvo:**

- `backend/app/platform/entitlements/service.py`
- `backend/app/platform/entitlements/policy.py`
- `backend/alembic/versions/<next>_harden_entitlement_rls_grants.py`
- backfill idempotente em `backend/app/cli/` ou migration de dados controlada
- testes de cutover/paridade

**Implementação:**

1. Executar backfill idempotente com contagens/checksums e repetir até divergência zero.
2. Implementar `get_entitlement` e `assert_module_active(tenant_id, module_slug, access_mode)`. Allow exige tenant/catálogo ativos, status `active`, vigência UTC e provisioning `ready`.
3. Fazer `require_modulo` e `require_permission` delegarem ao serviço sob flag por ambiente/tenant.
4. Parar de derivar acesso de `PLANO_MODULOS`; plano permanece metadado comercial.
5. Manter booleanos derivados na mesma linha durante deploy misto; divergência após ativação resulta em deny + alerta.
6. Separar grants/conexões: runtime municipal com RLS/visão tenant e sem DML de entitlement; plataforma com role próprio para cross-tenant/DML após token administrativo; worker com grants mínimos. Testar todos com os papéis reais.
7. Auditar transitions, provisioning e mudança de versão.

**Testes mínimos:** limites de vigência, tenant/catálogo desativado, provisioning parcial/falho, superusuário, paridade, write N-1 simulado, falha parcial de dual-write, rollback de pending/suspended/cancelled/expired e autorização cross-tenant.

**Aceite:** toda decisão HTTP usa a autoridade canônica; divergência é zero antes da flag e fail-closed depois dela.

**Rollback:** desativar a flag e voltar ao compatibility build de `ENT-01A`; `legacy_safe` só permite quando o estado canônico também está efetivamente ativo/ready. Nunca voltar ao binário anterior ao dual-write.

**Commit sugerido:** `feat(entitlements): activate canonical module policy for http`

**Não incluir:** canais não HTTP ou mudança breaking de onboarding.

### PR `ENT-01C` — onboarding versionado com módulos explícitos

**Dependência:** `CORE-01`.

**Objetivo:** impedir que novos tenants recebam todos os módulos sem quebrar consumidores do contrato atual.

**Arquivos:** `backend/app/routers/admin_tenants.py`, schemas administrativos, `backend/app/services/provisioning_tenant.py`, clientes administrativos e testes OpenAPI.

**Implementação:**

1. Criar endpoint/schema versionado ou adicionar campo opcional de forma comprovadamente compatível; nunca tornar campo existente obrigatório no mesmo contrato.
2. No contrato novo, exigir lista explícita de módulos comerciais e criar linhas de entitlement somente para os contratados; provisionar defaults de core sem criar uma linha `tenant_modulo` para `core`.
3. Manter o contrato antigo deprecado com telemetria de consumidores até migração completa; não removê-lo nesta onda.
4. Atualizar clientes conhecidos e publicar prazo de depreciação.

**Testes:** OpenAPI aditivo aprovado, cliente antigo preservado, cliente novo sem módulos implícitos, módulo inválido, lista vazia/core-only e provisioning idempotente.

**Aceite:** todo consumidor conhecido usa o contrato novo e novos fluxos não contratam todos silenciosamente.

**Rollback:** voltar geração de chamadas ao endpoint antigo; não apagar entitlements já criados.

**Commit:** `feat(onboarding): add explicit module contract version`

**Não incluir:** remover o endpoint antigo.

### PR `ENT-02` — fechar canais não HTTP e ciclo de descontratação

**Dependências:** `ENT-01C` e `CORE-01`.

**Objetivo:** garantir que descontratar um módulo interrompe sua execução em todos os canais.

**Arquivos existentes candidatos:**

- `backend/app/routers/cidadao.py`
- `backend/app/routers/servico.py`
- `backend/app/tasks/snapshot_saldos_pagamentos.py`
- `backend/app/tasks/verificar_sla_workflows.py`
- `backend/app/tasks/celery_app.py`
- `backend/app/services/modulos.py`
- `backend/app/services/jobs.py`
- routers de upload/export e comandos `backend/app/cli/`

**Novos arquivos alvo:**

- `backend/app/platform/entitlements/decorators.py`
- `backend/app/platform/entitlements/celery.py`
- `backend/app/platform/entitlements/lifecycle.py`
- `backend/app/core/identity_access/service_principals.py`
- `backend/alembic/versions/<next>_service_principal_task_policy.py`
- `backend/alembic/versions/<next>_access_revision_outbox.py`
- `backend/tests/platform/test_entitlement_channels.py`
- testes por task/portal afetado

**Implementação:**

1. Gatear catálogo público e novas operações de cidadão pelo módulo proprietário.
2. Fazer beat selecionar somente tenants com entitlement ativo.
3. Fazer cada worker revalidar ator ativo ou service principal, entitlement e a autorização atual no início e antes de publicar o resultado; nesta onda a porta usa o adapter `legacy_safe`, e `RBAC-02` passa a fornecer capability/scopes v2 sem enfraquecer o gate. Encerrar de forma não retentável quando removida.
4. Gatear CLI de negócio, uploads, exports e integrações classificadas em `ARC-01`.
5. Modelar service principals e a política registrada `task_name → module → principal → operation_code → scopes`; tasks de usuário continuam usando `requested_by`. Nesta fase `operation_code` é o código estável declarado no manifesto, porque o catálogo RBAC v2 ainda não existe; não criar FK fictícia.
6. Introduzir hooks idempotentes de provision/deprovision no manifesto; inicialmente podem ser no-op auditado.
7. Persistir `access_revision(tenant_id, revision, updated_at)` e uma `access_state_outbox` transacional; toda mudança de entitlement incrementa a revisão e publica `access_state_changed` de modo idempotente. O AccessSnapshot passa a consumi-las em `RBAC-02`.
8. Implementar as transições em ordem fechada: ativação `pending/provisioning → hook → active/ready`; suspensão `suspended/deprovisioning` com deny atômico antes do hook → `suspended/deprovisioned`; reativação `pending/provisioning → hook → active/ready`; cancelamento `cancelled/deprovisioning` com deny atômico antes do hook → `cancelled/deprovisioned`. Falha mantém deny e retry idempotente; recontratação cria nova versão contratual e nunca salta de `cancelled` para `active`.
9. Implementar `AccessMode` fechado (`execute`, `historical_read`, `public_validation`) declarado pelo registry. Enquanto a política histórica versionada não estiver aprovada, o padrão é deny; endpoints não escolhem livremente o modo.
10. Adicionar métricas de task ignorada/abortada, hook/retry/outbox e decisão por canal.

**Testes mínimos:**

- tenant sem Protocolo não abre processo, complementa nem envia anexo pelo portal;
- tenant sem Pagamentos não entra no snapshot;
- tenant sem Protocolo não entra no SLA;
- tarefa enfileirada antes da suspensão aborta ao iniciar;
- tarefa cujo ator/papel/scope foi revogado aborta antes de executar ou publicar;
- task de sistema exige service principal explícito e não usa actor nulo como bypass;
- principal revogado/expirado e policy task×módulo divergente são negados;
- upload/export/CLI negam sem entitlement;
- reativação idempotente não duplica defaults;
- falha/retry de hook nunca torna o módulo efetivo antes de `ready`, e suspensão/cancelamento negam antes de executar deprovision;
- outbox não perde nem duplica efeito após rollback/retry e a revisão é monotônica por tenant;
- dados existentes permanecem.

**Aceite:** matriz de canais de `ARC-01` está 100% coberta ou explicitamente core; descontratação satisfaz os critérios sistêmicos.

**Rollback:** desabilitar hooks/schedules novos e voltar seleção ao adaptador anterior sem liberar operações descontratadas; dados não são revertidos.

**Commit sugerido:** `feat(entitlements): enforce module lifecycle across channels`

**Não incluir:** nova matriz de capabilities por módulo.

### Gate operacional `ENT-ROLLOUT` — liberar o lifecycle administrativo

Não é PR de código. As ações de suspender, cancelar, reativar e recontratar permanecem ocultas/bloqueadas até:

- o build de `ENT-02` estar implantado em todas as APIs, workers e instâncias de beat;
- filas antigas terem sido classificadas e os workers comprovarem revalidação no início e antes da publicação;
- provision/deprovision, falha, retry e recuperação de outbox terem sido exercitados em homologação;
- o playbook comprovar deny imediato, preservação de dados e rollback sem reativação acidental;
- métricas e alertas de hook, outbox e task abortada estarem operacionais.

O gate libera primeiro um tenant interno/piloto e depois lotes pequenos. Qualquer violação pausa o lote; correção ocorre em PR separado.

### PR `CORE-01` — reclassificar IAM, unidades e configuração essencial

**Dependências:** `SEC-02` e `ENT-01B`.

**Objetivo:** tornar um tenant somente com Transporte operacional sem contratar Administração.

**Arquivos existentes candidatos:**

- `backend/app/cli/seed_bootstrap.py`
- `backend/app/routers/usuarios.py`
- `backend/app/routers/grupos.py`
- `backend/app/routers/catalogo.py`
- routers/models de unidades, configuração, preferências e branding
- `backend/app/services/provisioning_tenant.py`
- `ci/seed-e2e.sql`
- `.github/workflows/backend-tests.yml`
- `.github/workflows/e2e-assinatura.yml`
- testes de modularização/onboarding
- menus frontend de Administração, apenas se necessário para refletir core

**Novos arquivos alvo:**

- adaptadores em `backend/app/core/identity_access/` e `backend/app/core/organization/`
- `backend/alembic/versions/<next>_add_non_contractable_core_owner.py`
- `backend/tests/platform/test_transport_only_tenant.py`

**Implementação:**

1. Adicionar ao catálogo o owner `core`, ativo e `contratavel = false`, por migration/seed idempotente.
2. Classificar capabilities/transações mínimas de usuários, papéis, unidades e preferências como `core.*`; adaptar vínculos hoje em `administracao`/`comum`.
3. Marcar `administracao` como alias legado não contratável, removê-lo do launcher/oferta e preservar `TenantModulo` históricos como linhas inertes.
4. Remover a exigência comercial de `administracao` desses casos de uso.
5. Preservar checagens de capability e autoridade de grant de `SEC-02`; core sempre disponível não significa público.
6. Alterar provisioning para criar apenas defaults de core e dos módulos explicitamente contratados.
7. Parar de criar defaults de Protocolo para tenant que não o contratou.
8. Manter aliases de rotas/transações legadas até `CONTRACT-*`.
9. Ajustar frontend para exibir gestão essencial sob Plataforma/Configurações, sem card vendável “Administração”.
10. Atualizar o manifesto `core`, regenerar `module-contract.generated.json` deterministicamente e fazer o CI exigir diff zero; `core` nunca entra na lista de módulos contratáveis.

**Testes mínimos:**

- tenant somente Transporte cria/lista/edita usuário autorizado;
- atribui papel permitido e administra unidade mínima;
- não obtém dados de Transporte apenas por ser tenant admin;
- não recebe defaults de Protocolo;
- launcher e API comercial não exibem Administração; vínculos históricos continuam consultáveis para auditoria;
- tenant legado mantém acesso equivalente.

**Aceite:** cenário “prefeitura somente Transporte” administra core e não exige entitlement `administracao`.

**Rollback:** aliases legados voltam a resolver as transações anteriores; não remover registros de core criados.

**Commit sugerido:** `refactor(core): make tenant identity and organization always available`

**Não incluir:** administração avançada nova ou movimento físico completo de todos os routers.

### PR `CORE-02A` — expandir contexto modular de jobs, auditoria e notificações

**Objetivo:** preparar o schema transversal de forma aditiva antes de mudar providers ou UI.

**Arquivos existentes candidatos:**

- `backend/app/services/jobs.py`
- `backend/app/routers/jobs.py`
- `backend/app/models/audit.py`
- modelos/serviços de notificações

**Novos arquivos alvo:**

- migration aditiva para `module_slug`/contexto em job, audit e notification quando necessário
- backfill idempotente com contagens/checksums

**Implementação:**

1. Adicionar colunas nullable para owner/capability/contexto, sem mudar leitores.
2. Backfill por fonte conhecida; linhas ambíguas ficam `legacy_unmapped`, nunca recebem owner inventado.
3. Adicionar contexto modular, actor/service principal e scope snapshot a Job.
4. Adicionar `module_slug`, capability, canal e correlation ID à auditoria comum e owner a notificações.
5. Validar RLS/grants e, só em PR contract posterior, tornar campos obrigatórios onde houver cobertura total.

**Testes mínimos:** banco limpo/legado, N-1 sobre schema expandido, backfill idempotente/checksum, `legacy_unmapped`, RLS/grants e nenhum diff de comportamento.

**Aceite:** schema e backfill estão prontos para providers sem exigir dados inventados nem quebrar N-1.

**Rollback:** voltar ao build compatível; colunas aditivas permanecem nullable.

**Commit sugerido:** `feat(core): expand module context for shared records`

**Não incluir:** providers, frontend, `NOT NULL` ou mover Protocolo.

### PR `CORE-02B` — portas e providers transversais no backend

**Dependência:** `CORE-02A`, `ARC-02` e `ENT-02`.

**Arquivos:** `backend/app/services/dashboard.py`, jobs, busca e notificações; novos `backend/app/core/{jobs,audit,search}/` e contratos de provider.

**Implementação:**

1. Definir portas de dashboard, home, busca e notificação no core.
2. Registrar providers por referências lazy nos manifestos; importar manifesto não carrega router/model/task.
3. Classificar dashboard atual como provider de Protocolo.
4. Validar no core owner do provider, capability e filtro backend antes de retornar busca/notificação.
5. Alinhar leitura/entrega de Job à autorização atual e ao contexto persistido.
6. Preservar trilhas específicas ligadas ao evento comum quando aplicável.

**Testes:** import leve do manifesto, provider desativado não executa, busca/notificação cross-module negada, job legível apenas por ator ainda autorizado e core sem imports de modelos concretos.

**Aceite:** backend comum compõe apenas providers ativos/autorizados e core não importa domínios.

**Rollback:** composition volta aos adapters anteriores; schema de `CORE-02A` permanece.

**Commit:** `refactor(core): compose module-aware backend providers`

**Não incluir:** home/dashboard frontend.

---

## 6. Onda 3 — RBAC v2 e AccessSnapshot

### PR `RBAC-01` — schema aditivo, catálogo de capabilities e templates

**Objetivo:** criar o modelo persistente v2 sem alterar decisões de acesso em produção.

**Arquivos existentes candidatos:**

- `backend/app/models/grupo.py`
- `backend/app/models/modulo.py`
- `backend/app/models/__init__.py`
- `backend/app/cli/seed_bootstrap.py`
- Alembic atual

**Novos arquivos alvo:**

```text
backend/app/core/identity_access/models.py
backend/app/core/identity_access/capabilities.py
backend/app/core/identity_access/role_templates.py
backend/app/core/identity_access/repository.py
backend/alembic/versions/<next>_expand_rbac_v2.py
backend/alembic/versions/<next>_link_task_policy_capability.py
backend/tests/platform/test_rbac_v2_models.py
backend/tests/platform/test_role_templates.py
```

**Implementação:**

1. Criar `capability`, `role_template`, associações normalizadas de scopes, `tenant_role`, `user_role_assignment`, associação de unidades, regras explícitas de delegação, `global_access_revision` e estado `module_authorization_state(tenant_id, module_id, mode, first_cutover_at, v2_ceiling_enforced_at, version)`.
2. Usar FK de módulo, FKs reais de unidade e constraints compostas de tenant; adicionar `valid_until > valid_from`, unicidade parcial de assignment ativo, versão e campos completos de grant/revoke.
3. Tornar cada versão de template imutável; atualização cria versão nova e upgrade de papéis tenant exige preview, aprovação e auditoria.
4. Ativar RLS nas tabelas tenant-owned e grants mínimos: catálogos globais são read-only para fluxos municipais; unit scope exige unidades do mesmo tenant; `own/tenant` proíbem linhas de unidade.
5. Cadastrar somente capabilities `core.*` inequívocas nesta etapa, atualizar o manifesto core e regenerar o contrato JSON; CI exige diff zero.
6. Resolver o `operation_code` criado em `ENT-02` contra o catálogo, adicionar `capability_id` com FK real em `service_principal_capability`/`task_execution_policy`, validar paridade e só então torná-lo autoridade. Código não resolvido mantém a policy inativa/deny e gera inventário, nunca grant implícito.
7. Backfill de grupo misto ou sem owner vira inventário `legacy_unmapped` para shadow, nunca grant v2 autoritativo. O backfill por módulo ocorre após sua matriz aprovada e pode dividir um grupo legado em papéis de compatibilidade separados por owner.
8. Criar, idempotentemente, estado `legacy_safe` para todo par tenant+módulo comercial já presente em `tenant_modulo` e para `core` de todo tenant. Após esse backfill, toda nova contratação cria seu `module_authorization_state` na mesma transação do entitlement.
9. Não fazer o runtime consultar o estado durante o expand/backfill. Ativar a leitura somente por feature flag depois de contagens/checksums/paridade e teste de rollback; após a ativação, estado ausente ou ilegível é deny, nunca fallback implícito.

**Testes mínimos:** migration upgrade em banco limpo e legado, head único, backfill idempotente e completo do estado `legacy_safe`, criação transacional do estado para contrato novo, RLS/grants com papel da aplicação, constraints cross-tenant/cross-module/cross-unit, invariantes own/unit/tenant, intervalo temporal, assignment ativo único, templates imutáveis/versionados, upgrade explícito, resolução/deny de `operation_code`, `legacy_unmapped`, estado de cutover e revoke preservado.

**Aceite:** schema v2 populado e consultável; runtime continua decidindo pelo legado.

**Rollback:** desligar dual-write/backfill; tabelas aditivas permanecem sem serem lidas.

**Commit sugerido:** `feat(rbac): add scoped capability and role model`

**Não incluir:** cutover de módulo ou UI completa de papéis.

### PR `RBAC-02` — motor de decisão, shadow mode e AccessSnapshot

**Dependências:** `RBAC-01`, `TRN-01` e `ENT-02`.

**Objetivo:** calcular decisões v2 lado a lado com o legado, observar divergências e fornecer acesso efetivo ao frontend.

**Arquivos existentes candidatos:**

- `backend/app/auth/perms.py`
- `backend/app/services/permissoes.py`
- `backend/app/routers/auth.py` ou endpoint de sessão
- `frontend/lib/auth.tsx` apenas para contrato temporário, se necessário

**Novos arquivos alvo:**

- `backend/app/core/identity_access/decision.py`
- `backend/app/core/identity_access/scopes.py`
- `backend/app/core/identity_access/shadow.py`
- `backend/app/core/identity_access/access_snapshot.py`
- `backend/app/core/identity_access/router.py`
- `backend/tests/platform/test_access_decision.py`
- `backend/tests/platform/test_access_snapshot.py`
- `backend/tests/platform/test_rbac_shadow.py`

**Implementação:**

1. Criar decisão pura que recebe actor, tenant, módulo, capability, recurso/contexto e retorna allow/deny + união normalizada de predicados de scope + motivo.
2. Implementar resolutores de scope sem aceitar IDs fornecidos pelo cliente como autoridade.
3. Adicionar modos por tenant/módulo: `legacy_safe`, `shadow`, `new`; nenhum modo ignora entitlement canônico nem proteções de grant.
4. Em `shadow`, manter a resposta `legacy_safe` e calcular v2 com avaliador puro, sem grants, provisioning, mutações, cache writes ou efeitos de negócio. Classificar `legacy_safe deny/v2 allow` como crítico e `legacy_safe allow/v2 deny` como aperto funcional a aprovar.
5. Implementar endpoint versionado de `AccessSnapshot` com seção core, módulos, união de grants e `nextRefreshAt`. O ETag deriva de `access_revision` do tenant, `global_access_revision` e hash determinístico do estado efetivo recalculado com UTC do banco.
6. Incrementar `access_revision` transacionalmente ou pela outbox já criada em mudança de papel, atribuição, usuário ou unidade; mudanças globais de catálogo/capability/template incrementam `global_access_revision`. Definir `nextRefreshAt` no primeiro `valid_from`/`valid_until` futuro relevante, nunca depois dele, para que expiração/ativação temporal invalide o snapshot mesmo sem escrita.
7. Implementar dual-write de grants legados/v2 somente onde mapeamento for inequívoco; registrar o restante para migração assistida.
8. Documentar que snapshot/ETag são somente UX, nunca autorização, e criar métrica/dashboard operacional de divergências.

**Testes mínimos:** composição `own + unit`, múltiplas unidades disjuntas, ausência de hierarquia implícita, múltiplos papéis/módulos, deny padrão, tenant errado, papel expirado/revogado, mudança de unidade, invalidation/revisões/outbox, mudança global de catálogo, passagem exata por `valid_from`/`valid_until`, `nextRefreshAt`, `304` antes e novo ETag depois do limite temporal, pureza do shadow, classificação das duas direções de divergência e ausência de vazamento na telemetria.

**Aceite:** Transporte pode entrar em shadow sem mudar resposta; endpoint entrega somente acesso efetivo.

**Rollback:** configurar tenant/módulo como `legacy_safe`, preservando entitlement canônico, `SEC-02` e as restrições v2 como teto para nunca ampliar dados. Motor e tabelas permanecem para análise.

**Commit sugerido:** `feat(rbac): evaluate scoped capabilities in shadow mode`

**Não incluir:** ativar globalmente o modo `new`.

---

## 7. Onda 4 — fundação frontend

### PR `FE-01` — AccessProvider, gates e registry frontend

**Objetivo:** impedir montagem/query de módulo indisponível e unificar menus, rotas e landing sem mudar URLs.

**Arquivos existentes candidatos:**

- `frontend/app/(app)/layout.tsx`
- `frontend/app/(launcher)/layout.tsx`
- `frontend/app/(launcher)/modulos/page.tsx`
- `frontend/components/Sidebar.tsx`
- `frontend/components/CommandPalette.tsx`
- `frontend/lib/auth.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/menus/`
- `frontend/middleware.ts`

**Novos arquivos alvo:**

```text
frontend/core/http/client.ts
frontend/core/auth/
frontend/core/access/AccessProvider.tsx
frontend/core/access/ModuleGate.tsx
frontend/core/access/RouteAccessGate.tsx
frontend/core/access/CapabilityGate.tsx
frontend/core/modules/types.ts
frontend/core/modules/registry.ts
frontend/core/query/
frontend/modules/{protocolo,transporte,frota,pagamentos}/manifest.ts
frontend/__tests__/architecture/module-registry.test.ts
frontend/app/(staff)/layout.tsx
```

**Implementação:**

1. Extrair base HTTP/erros e preservar clientes distintos: operador SaaS (audience/realm próprio), staff (`aprimora_token`), cidadão (`aprimora_cidadao_token`) e público/anônimo; não unificar cookies, caches, interceptors ou redirects.
2. Mover todos os consumidores do shell, auth, branding, launcher, switcher, notificações e Ctrl+K para `core/http`; `core`, `shared` e shell ficam com zero import de `@/lib/api`.
3. Criar ancestral `app/(staff)/layout.tsx` com StaffSession, QueryClient e AccessProvider compartilhados por launcher/workspace/tenant-admin. Operador SaaS usa `app/(operator)`; cidadão e público permanecem separados.
4. Consumir AccessSnapshot com core + módulos, ETag, refetch em foco/navegação e polling máximo de 60 s; mutations invalidam localmente e 403 estruturado força refresh.
5. Criar `RouteAccessGate` por regra de rota (módulo + capability), além de `ModuleGate`; wrappers server não fazem fetch antes do gate e queries usam `enabled: false` até acesso conhecido. Screen server futura chama `assertRouteAccess()` antes de I/O.
6. Preservar precedência de `must_change_password` sobre snapshot/gates.
7. Criar `CapabilityGate` e hooks `hasModule`, `can`, `grantsFor` e `canAt`; não reduzir scopes a um valor singular.
8. Criar manifestos leves com regras por rota e migrar `ROTA_MODULO`, `MENUS` e landing para o registry/contrato gerado.
9. Exigir regra de acesso explícita em cada rota e item de navegação.
10. Resolver landing pela primeira capability disponível; slug desconhecido mostra incompatibilidade de versão.
11. Medir baseline de imports da fachada por camada; impedir novos imports e exigir zero em core/shared/shell/launcher.
12. Em `ENTITLEMENT_INACTIVE`, redirecionar ao launcher; capability/scope negado mostra tela local de acesso negado, sem redirecionamento genérico.
13. Tratar `lib/api.ts` como adapter folha, sem efeitos colaterais ou ciclos; consumidores legados podem usá-lo, mas nenhuma composição/core importa o agregado.

**Testes mínimos:**

- URL direta de módulo indisponível não monta screen nem dispara query;
- rota de módulo ativo sem capability não monta screen, não faz prefetch nem I/O em Server Component;
- ação sem capability não aparece e chamada direta continua negada pelo backend;
- capabilities core, múltiplos módulos/papéis e grants `own + unit` no snapshot;
- landing permitido;
- menu, launcher, switcher e Ctrl+K usam o mesmo registry;
- logout e troca de tenant limpam cache; operador, staff, cidadão e público não compartilham credencial/query cache;
- snapshot stale, refetch em foco, TTL e quatro códigos estruturados de 403;
- `npx tsc --noEmit`, Vitest focado e build.

**Aceite:** não existe novo mapa paralelo de módulo; core/shared/shell/launcher não importam a fachada; rota negada não executa código de domínio; frontend trata acesso consistente e backend continua autoridade.

**Rollback:** provider pode adaptar `/modulos/me` legado; gates permanecem fail-closed. Não remover manifestos.

**Commit sugerido:** `feat(frontend): add module access gates and registry`

**Não incluir:** mover todas as screens ou alterar para `/m/<slug>`.

### PR `CORE-02C` — compor home, busca e notificações no frontend

**Dependências:** `CORE-02B` e `FE-01`.

**Arquivos:** `frontend/app/(app)/home/page.tsx`, dashboard, `CommandPalette.tsx`, notificações e novos contratos de contribuição em `frontend/core/`.

**Implementação:**

1. Tornar home neutra e carregar contribuições lazy somente dos módulos efetivos.
2. Mover o dashboard atual para a contribuição de Protocolo.
3. Filtrar busca/notificações já validadas pelo backend e passar todo link pelo RouteAccessGate.
4. Garantir que loaders de módulos descontratados/negados nem sejam invocados.

**Testes:** tenant só Transporte não dispara query/import loader de Protocolo; capability negada filtra contribuição; link de notificação/busca passa pelo gate; TypeScript/Vitest/build.

**Aceite:** áreas transversais não conhecem modelos/screens concretos e não executam código de módulo indisponível.

**Rollback:** voltar à home neutra sem contribuições; nunca restaurar chamadas fixas a Protocolo para todos os tenants.

**Commit:** `refactor(frontend): compose module-aware home and discovery`

---

## 8. Onda 5 — Transporte como piloto

### PR `TRN-01` — matriz de capabilities, scopes e templates de Transporte

**Objetivo:** transformar os perfis aprovados em uma matriz executável antes do cutover.

**Arquivos existentes candidatos:**

- `backend/app/routers/transporte_regulado.py`
- `backend/app/services/transporte_regulado.py`
- `backend/app/models/transporte_regulado.py`
- `backend/app/cli/seed_bootstrap.py`
- testes de Transporte
- inventário de `ARC-01`

**Novos arquivos alvo:**

- `docs/architecture/access/transporte-matrix.md`
- `backend/app/modules/transporte/capabilities.py`
- `backend/app/modules/transporte/role_templates.py`
- `backend/tests/modules/transporte/test_capability_matrix.py`

**Implementação:**

1. Inventariar cada endpoint/caso de uso de permissionários, empresas, veículos, vistorias, alvarás, relatórios e auditoria.
2. Definir capabilities de negócio e scopes suportados por recurso.
3. Definir propriedade de `own` de modo objetivo; não inferir apenas por usuário criador se o negócio exigir outro vínculo.
4. Aprovar templates: administrador, secretaria/gestor, fiscal/vistoriador, consulta/auditoria e solicitante interno.
5. Cadastrar/atualizar templates de forma idempotente.
6. Mapear a transação legado `transporte_regulado` para capabilities para shadow; grupos mistos são divididos por owner somente quando inequívoco, e o restante fica `legacy_unmapped`.

**Testes mínimos:** toda rota tem capability; toda capability tem dono; templates não concedem `core.role.*`; scopes inválidos falham; seed é idempotente.

**Aceite:** matriz assinada pelo responsável de negócio e carregada pelo registry; nenhuma autorização por nome de papel.

**Rollback:** templates/capabilities ficam inativos; Transporte continua `legacy_safe`.

**Commit sugerido:** `feat(transporte): define scoped capability matrix`

**Não incluir:** mover router ou ligar modo `new`.

### PR `TRN-02` — mover fisicamente o backend de Transporte

**Objetivo:** separar os fontes de Transporte sem alterar URL, schema, task ou política de acesso.

**Arquivos existentes candidatos:**

- `backend/app/routers/transporte_regulado.py`
- `backend/app/services/transporte_regulado.py`
- `backend/app/models/transporte_regulado.py`
- `backend/app/schemas/transporte_regulado.py`
- imports relacionados e testes

**Arquivos alvo:**

```text
backend/app/modules/transporte/
  manifest.py
  models.py
  api/
  permissionarios/
  empresas/
  veiculos/
  vistorias/
  alvaras/
  relatorios/
```

**Implementação:**

1. Congelar OpenAPI e imports públicos antes do movimento.
2. Extrair por fatias internas pequenas, preservando um router público compatível.
3. Manter reexports nos paths antigos para consumidores ainda não migrados.
4. Atualizar o manifesto para apontar ao novo router, sem mudar ordem/prefixo/tags.
5. Manter classes SQL nos mesmos schemas/tabelas e nomes de metadata.
6. Proibir imports de internals de Frota/Pagamentos/Protocolo.
7. Migrar testes de módulo para a nova pasta ou manter imports compatíveis conforme padrão do repositório.

**Testes mínimos:** suíte completa de Transporte, snapshot OpenAPI, startup, Alembic head/current sem nova migration, teste de imports antigos e novos, testes arquiteturais.

**Aceite:** implementação real reside em `app/modules/transporte`; paths antigos são apenas fachadas; comportamento é idêntico.

**Rollback:** registry volta ao router wrapper antigo; fachadas garantem imports. Não há migration nem mudança de dados.

**Commit sugerido:** `refactor(transporte): move backend into module boundary`

**Não incluir:** enforcement v2, mudanças de resposta ou URL.

### PR `TRN-03` — implementar enforcement dormente e shadow de Transporte

**Objetivo:** deixar autorização fina pronta e observável sem fazer rollout de produção dentro do PR.

**Arquivos existentes/alvo:**

- casos de uso e routers sob `backend/app/modules/transporte/`
- `backend/app/core/identity_access/`
- filtros/repositories de Transporte
- testes de Transporte e RLS

**Implementação:**

1. Implementar `require_capability` e predicados atrás do estado por tenant/módulo; o merge não ativa `new` automaticamente.
2. Colocar tenants de teste em `shadow` e executar fixtures enumeradas para cada linha da matriz.
3. Corrigir divergências de mapeamento, nunca ajustar v2 para reproduzir um privilégio legado inseguro sem decisão explícita.
4. Aplicar autorização nos casos de uso, não somente no router, e scopes nas queries/mutações.
5. Proteger export, anexos, auditoria e relatórios com as mesmas regras.
6. Entregar comando/runbook auditado de mudança `shadow → new → legacy_safe`, mas não executá-lo como parte do merge.

**Testes mínimos:**

- administrador de módulo com scope tenant;
- secretaria limitada às unidades atribuídas;
- solicitante cria/consulta somente próprios e não enumera recursos alheios;
- fiscal executa vistoria sem emitir/configurar fora da matriz;
- tenant admin sem papel de Transporte não lê dados;
- módulo descontratado nega até superusuário;
- IDOR/cross-tenant/cross-unit em leitura e mutação;
- downloads/exports respeitam scope.

**Aceite:** zero diferença de allow/deny e de predicados de scope nas fixtures enumeradas; enforcement permanece dormente para produção e o runbook foi ensaiado em ambiente de teste.

**Rollback:** mudar somente o modo do tenant/módulo para `legacy_safe`; preservar entitlement, teto de scope, eventos shadow e dados v2. O conjunto autorizado após rollback não pode ser maior que antes dele.

**Commit sugerido:** `feat(transporte): enforce scoped capabilities`

**Não incluir:** mover frontend ou alterar URLs.

### PR `TRN-04` — mover frontend de Transporte e extrair sua API

**Objetivo:** organizar screens, componentes e cliente de Transporte sob uma única fronteira.

**Arquivos existentes candidatos:**

- páginas de Transporte em `frontend/app/(app)/`
- componentes de Transporte hoje dispersos
- seção de Transporte em `frontend/lib/api.ts`
- menus/mapas antigos

**Arquivos alvo:**

```text
frontend/modules/transporte/
  manifest.ts
  access.ts
  api/contracts.ts
  api/client.ts
  api/query-keys.ts
  screens/
  components/
  __tests__/
```

**Implementação:**

1. Extrair contratos/cliente/query keys de Transporte de `lib/api.ts`.
2. Manter reexports temporários em `lib/api.ts` para consumidores fora da fatia.
3. Mover componentes e screens verticalmente.
4. Transformar páginas Next atuais em wrappers finos; manter URLs.
5. Aplicar RouteAccessGate nas rotas e CapabilityGate nas ações.
6. Medir build manifest antes/depois, bytes raw/gzip, issuers e chunks shared permitidos; usar `next/dynamic` em Recharts/XYFlow/TipTap/PDF apenas quando a medição provar benefício.
7. Mover CSS global de biblioteca ao módulo owner ou registrá-lo explicitamente como shared.
8. Confirmar que navegar em Transporte não carrega chunks cujo issuer pertença a outros módulos e que JS inicial não cresce mais de 5% sem justificativa aprovada.

**Testes mínimos:** Vitest com mocks de fetch existentes, clientes/gates/screens, TypeScript, build, relatório reproduzível de chunks, rotas antigas, launcher/sidebar/command palette.

**Aceite:** o módulo Transporte tem zero import de `@/lib/api`; app routes contêm apenas composição; URL indevida não dispara query; orçamento e isolamento de chunks passam.

**Rollback:** wrappers voltam a importar screens anteriores; reexports mantêm contratos.

**Commit sugerido:** `refactor(transporte): move frontend into module boundary`

**Não incluir:** outros módulos ou `/m/transporte`.

### Gate operacional `TRN-ROLLOUT` — ativar Transporte por tenant

Não é PR de código. Um operador autorizado muda tenants por lotes após:

- shadow por no mínimo 7 dias e 1.000 decisões; se o tráfego não atingir o volume, manter 7 dias, executar toda a suíte sintética e exigir aprovação explícita;
- zero divergência crítica de allow/deny **e** scope nos cenários enumerados;
- toda divergência de aperto funcional classificada/aprovada;
- nenhuma regressão não explicada de 5xx/latência e overhead p95 da autorização até 10% do baseline;
- rollback `new → legacy_safe` exercitado sem ampliar acesso;
- mudança e reversão auditadas por tenant+módulo.

Qualquer limiar violado pausa o lote. Correção de código ocorre em novo PR; não se altera código durante rollout.

### Gate de saída do piloto

Não iniciar expansão em massa até comprovar:

- tenant somente Transporte completo;
- descontratação em todos os canais;
- grants seguros;
- scopes own/unit/tenant;
- rollback `new → legacy_safe` exercitado sem ampliação de acesso;
- observabilidade e playbook operacional;
- OpenAPI, Celery, banco e URLs compatíveis;
- front sem query cruzada e sem chunk cujo issuer pertença a outro módulo; orçamento de bytes registrado.

---

## 9. Onda 6 — repetir o padrão por módulo

As tarefas abaixo repetem o protocolo do piloto. Cada item continua sendo um PR isolado.

### PR `FRO-01` — matriz, scopes e templates de Frota

**Arquivos:** `backend/app/routers/frota.py`, `backend/app/services/frota.py`, modelos/schemas/testes e novos `backend/app/modules/frota/{capabilities.py,role_templates.py}`.

**Passos:** inventariar solicitações, aprovações, saídas/retornos, abastecimento, manutenção, motoristas, ocorrências, documentos e relatórios; aprovar matriz; seed idempotente; dividir backfill inequívoco por owner e manter o restante `legacy_unmapped`.

**Testes:** cobertura rota×capability×scope, templates, seed/backfill idempotente e ausência de capabilities administrativas indevidas.

**Aceite:** matriz assinada e carregada; nenhuma mudança de decisão runtime.

**Rollback:** desativar catálogo/templates novos; runtime não mudou.

**Commit:** `feat(frota): define scoped capability matrix`

### PR `FRO-02` — mover backend Frota

**Arquivos alvo:** `backend/app/modules/frota/{manifest.py,models.py,api/,solicitacoes/,veiculos/,motoristas/,abastecimentos/,manutencoes/,relatorios/}` e fachadas nos paths antigos.

**Passos/testes:** mesmo protocolo físico de `TRN-02`; preservar OpenAPI, schemas SQL, imports e quaisquer tasks.

**Aceite:** código real de Frota sob módulo; fachadas sem lógica.

**Rollback:** registry/import wrappers.

**Commit:** `refactor(frota): move backend into module boundary`

### PR `FRO-03` — enforcement dormente e shadow de Frota

**Passos:** repetir `TRN-03` nos casos de uso movidos, incluindo filtros own/unit/tenant, downloads, exports e tasks; entregar runbook sem ativar `new` no merge.

**Testes:** solicitante own; unidades disjuntas; aprovador/operador/manutenção; tenant admin sem papel; IDOR; descontratação; pureza e divergências do shadow.

**Aceite:** zero divergência nas fixtures enumeradas e rollout dormente.

**Rollback:** `legacy_safe`, sem ampliação.

**Commit:** `feat(frota): implement scoped authorization in shadow`

### PR `FRO-04` — mover frontend Frota

**Arquivos alvo:** `frontend/modules/frota/{manifest.ts,api/,screens/,components/,__tests__/}`; páginas atuais viram wrappers; seção de `lib/api.ts` vira reexport.

**Testes:** gates, fluxos principais, TypeScript, build, URLs e ausência de imports novos da fachada.

**Aceite:** fronteira frontend equivalente à de Transporte.

**Rollback:** wrappers/reexports.

**Commit:** `refactor(frota): move frontend into module boundary`

### Gate operacional `FRO-ROLLOUT`

**Precondição:** `FRO-04` implantado e validado. Aplicar os mesmos limiares e processo do `TRN-ROLLOUT`, com métricas e fixtures de Frota.

### PR `PAG-01` — matriz, scopes e segregação de Pagamentos

**Arquivos:** routers/services/models/testes de Pagamentos e novos `backend/app/modules/pagamentos/capabilities.py`, `role_templates.py`.

**Passos:** definir capabilities de cadastros, caixa, débitos, autorização, execução, conciliação e relatórios; explicitar segregação de funções; seed/backfill inequívoco e aprovação da matriz.

**Testes:** quem cria não aprova quando a política exigir; scopes; dados financeiros; export; tenant admin; descontratação.

**Aceite:** matriz aprovada e sem mudança runtime.

**Rollback:** desativar catálogo/templates novos; runtime não mudou.

**Commit:** `feat(pagamentos): define scoped financial capability matrix`

### PR `PAG-02A` — mover backend e instalar wrappers de tasks de Pagamentos

**Arquivos alvo:** `backend/app/modules/pagamentos/{manifest.py,models.py,api/,cadastros/,caixa/,debitos/,autorizacoes/,relatorios/,tasks/}`; wrappers de router/service/task antigos.

**Passos:** preservar schema, nome, payload, serializer, routing key, fila, retry/ack e resultado; implantar implementação/fachada nova mantendo o include antigo. Contexto adicional é carregado por `job_id`, sem kwargs novos.

**Testes:** OpenAPI, domínio, task por tenant elegível, mensagem/payload antigo, imports e matriz old/new producer×worker com o include ainda antigo.

**Aceite:** wrappers novos estão em produção antes de qualquer mudança do include.

**Rollback:** continuar usando include antigo.

**Commit:** `refactor(pagamentos): install compatible module task wrappers`

### PR `PAG-02B` — trocar composition/include de Pagamentos

**Dependência operacional:** `PAG-02A` implantado em todos os workers e filas observadas.

**Passos:** apontar registry/include ao novo path sem mudar nome/contrato; testar old/new producer×old/new worker×beat; manter wrapper até superar ETA/countdown + retry horizon e drenar filas.

**Aceite:** deploy misto e mensagens antigas processam com resultado equivalente.

**Rollback:** composition/include retorna ao path antigo; wrappers ficam.

**Commit:** `refactor(pagamentos): switch celery composition to module tasks`

### PR `PAG-03` — enforcement dormente e shadow de Pagamentos

**Passos/testes:** repetir `TRN-03`, adicionando segregação de funções, autorização atual antes de publicar jobs financeiros e todos os canais/task.

**Aceite:** zero divergência nas fixtures financeiras enumeradas; `new` não é ativado pelo merge.

**Rollback:** `legacy_safe`, sem ampliar acesso.

**Commit:** `feat(pagamentos): implement financial authorization in shadow`

### PR `PAG-04` — mover frontend Pagamentos

**Arquivos alvo:** `frontend/modules/pagamentos/{manifest.ts,api/,screens/,components/,__tests__/}`.

**Testes/aceite/rollback:** mesmo protocolo de `TRN-04`, adicionando testes de ações financeiras sensíveis e segregação.

**Commit:** `refactor(pagamentos): move frontend into module boundary`

### Gate operacional `PAG-ROLLOUT`

**Precondição:** `PAG-04` implantado e validado. Aplicar os mesmos limiares do `TRN-ROLLOUT`; qualquer divergência de segregação é crítica.

### PR `PRO-01` — matriz, portais e política histórica de Protocolo

**Arquivos:** routers/services/models de processo, serviço, workflow, cidadão, documentos, relatórios, SLA e testes relacionados.

**Passos:**

1. Definir capabilities e scopes do quadro interno.
2. Separar identidade/política do cidadão.
3. Classificar catálogo público, abertura, complementação, upload, validação histórica, assinatura, workflow, SLA e relatórios.
4. Aprovar política de suspensão/cancelamento e retenção legal.
5. Aprovar matriz e backfill inequívoco; deixar grupos mistos como `legacy_unmapped`.

**Testes:** portal com/sem entitlement; cidadão não acessa processo de outro; solicitante interno own; secretaria unit; workflow/SLA; documento/download/assinatura; histórico após cancelamento; tenant admin sem papel.

**Aceite:** toda superfície possui capability/AccessMode e owner; não há mudança runtime.

**Rollback:** desativar catálogo/templates novos; gates de entitlement existentes permanecem e runtime de RBAC não mudou.

**Commit:** `feat(protocolo): define staff citizen and historical access matrix`

### Família de PRs `PRO-02A..E` — mover backend Protocolo por subdomínios

**Arquivos alvo:**

```text
backend/app/modules/protocolo/
  manifest.py
  models.py
  api/
  processos/
  servicos/
  workflow/
  documentos/
  assinaturas/
  relatorios/
  portal_cidadao/
  tasks/
```

Separar obrigatoriamente:

- `PRO-02A`: processos e serviços;
- `PRO-02B`: workflow e SLA, instalando wrappers Celery sem trocar include;
- `PRO-02C`: documentos, assinaturas e relatórios;
- `PRO-02D`: portal cidadão;
- `PRO-02E`: trocar include/composition somente após `PRO-02B` estar implantado em todos os workers.

Preservar schema `protocolos`, tabelas workflow atuais e contrato Celery completo. Cada PR tem OpenAPI/import snapshot próprio; `PRO-02E` testa matriz old/new producer×worker×beat e mantém wrappers até filas drenadas mais o horizonte máximo de retry/ETA.

**Testes:** suíte completa de Protocolo, portal, workflow, documentos, assinatura, jobs, OpenAPI, Celery, imports e Alembic.

**Aceite da família:** nenhum core importa modelos Protocolo; cada subdomínio real reside no módulo e paths antigos são fachadas.

**Rollback:** registry/wrappers, sem rollback de dados.

**Commits:** `refactor(protocolo): move <subdomain> into module boundary`

### PR `PRO-03` — enforcement dormente e shadow de Protocolo

**Passos:** aplicar matriz a quadro interno, portal cidadão, workflow, SLA, documentos, assinatura, validação pública e jobs. `historical_read`/`public_validation` são fail-closed quando não aprovados. Entregar runbook sem ativar `new` no merge.

**Testes:** portal com/sem entitlement; cidadão sem IDOR; own/unit; workflow/SLA; documento/download/assinatura; histórico após cancelamento; tenant admin sem papel; worker e service principal.

**Aceite:** zero divergência nas fixtures enumeradas e nenhuma exceção implícita de portal.

**Rollback:** `legacy_safe` interno; portal continua negando novas operações sem entitlement e preserva teto v2.

**Commit:** `feat(protocolo): implement scoped access in shadow`

### PR `PRO-04` — mover frontend Protocolo e portal cidadão

**Arquivos alvo:** `frontend/modules/protocolo/`, `frontend/modules/protocolo/portal_cidadao/`, shell de realm em `frontend/portals/cidadao/`, wrappers de `frontend/app/` e seções restantes de `lib/api.ts`.

**Passos:** extrair clientes/screens de negócio para o módulo; deixar em `portals/cidadao` somente sessão/layout/cliente do realm; preservar cache separado, contribuições já criadas em `CORE-02C` e URLs; retirar o CSS global de XYFlow de `frontend/app/layout.tsx` ou registrá-lo como shared com evidência de necessidade.

**Testes:** staff e cidadão separados, gates, home sem Protocolo, workflow/documentos, TypeScript, build, links históricos.

**Aceite:** frontend Protocolo isolado; core não importa screens/modelos do módulo; tenant sem Protocolo não executa suas queries.

**Rollback:** wrappers/reexports e provider de contribuição anterior.

**Commit:** `refactor(protocolo): move frontend and citizen portal into boundaries`

### Gate operacional `PRO-ROLLOUT`

**Precondição:** `PRO-04` implantado e validado. Aplicar os limiares do `TRN-ROLLOUT` mais validação jurídica/contratual da política histórica.

---

## 10. Onda 7 — consolidação física da plataforma e do core

### PR `PLAT-01` — consolidar backend de plataforma, core e shared

**Objetivo:** concluir a separação física dos elementos transversais depois que os módulos de negócio não dependem mais de internals legados.

**Arquivos existentes candidatos:**

- `backend/app/auth/`
- modelos/routers/services de tenant, usuário, grupo/papel, unidade e configuração essencial
- modelos/routers/services de auditoria, notificações, arquivos, jobs e integrações
- `backend/app/database.py` e utilitários técnicos realmente compartilhados
- barrels `backend/app/models/__init__.py` e equivalentes

**Arquivos alvo:**

```text
backend/app/platform/
  tenancy/
  entitlements/
  operator_identity/
backend/app/core/
  identity_access/
  organization/
  audit/
  notifications/
  files/
  jobs/
  integrations/
  preferences/
backend/app/shared/
  database.py
  errors.py
  clock.py
  pagination.py
```

**Implementação:**

1. Inventariar os consumidores restantes e mover uma família por commit interno, sem mudança funcional.
2. Definir `public API` de cada pacote de core; módulos importam somente core e shared. Acesso a entitlement ocorre pela porta estreita ligada na composition.
3. Manter wrappers/reexports nos paths antigos até a respectiva remoção em `CONTRACT-03`.
4. Migrar `database.py` por fachada, preservando exatamente o mesmo `Base`, engine/session e comportamento RLS; nunca criar duas instâncias de metadata.
5. Reduzir barrels globais e registrar dependências via composition.
6. Confirmar que plataforma e core não importam modelos concretos de módulo.
7. Não mover tabelas entre schemas nem gerar migration para simples mudança de path Python.

**Testes mínimos:** autenticação, tenant/RLS, entitlement, RBAC/grants, unidades, auditoria, notificações, files/jobs, startup, OpenAPI, Alembic sem nova revisão e guardas de import.

**Aceite:** operação SaaS reside em `platform`, serviços municipais transversais em `core` e utilitários técnicos em `shared`; os paths antigos contêm apenas fachadas; existe um único `Base`/metadata e uma única composição de sessão.

**Rollback:** composition volta a importar wrappers antigos; reexports preservam identidade de classes e objetos.

**Commit:** `refactor(platform): consolidate backend core boundaries`

**Não incluir:** remoção das fachadas, migration contract ou mudança de URL.

### PR `PLAT-02` — consolidar frontend core, platform e shared

**Objetivo:** concluir a árvore frontend separando infraestrutura, administração do tenant e componentes realmente compartilhados.

**Arquivos existentes candidatos:**

- providers, layouts e autenticação em `frontend/app/` e `frontend/lib/`
- telas de usuários, papéis, unidades, configurações, auditoria, jobs e notificações
- componentes genéricos hoje na raiz de `frontend/components/`
- utilitários de formatação/validação

**Arquivos alvo:**

```text
frontend/core/{auth,access,http,modules,query,shell,tenant-admin}/
frontend/platform/operator-admin/
frontend/shared/{ui,validation,formatting}/
frontend/portals/cidadao/
```

**Implementação:**

1. Mover apenas componentes comprovadamente genéricos para `shared`; componentes de negócio retornam ao módulo dono.
2. Mover screens municipais de IAM/organização para `core/tenant-admin` e telas cross-tenant para `platform/operator-admin`; manter páginas Next como wrappers.
3. Consolidar provider staff sem compartilhar cache com operador SaaS ou portais externos.
4. Definir query keys com tenant, módulo e recurso para impedir cache cruzado.
5. Remover dependências de core/platform em screens de módulos.
6. Manter aliases/reexports temporários e não adotar `frontend/src/` neste PR.

**Testes mínimos:** login/logout/troca de tenant, launcher/workspace, gestão de usuário/papel/unidade, isolamento de cookie/audience/cache operador×staff×cidadão×público, TypeScript, Vitest, build e guardas de import.

**Aceite:** implementação transversal real reside em `core`, `platform`, `shared` e `portals`; app routes permanecem wrappers; não há cache de uma identidade/tenant reutilizado em outro.

**Rollback:** wrappers voltam aos imports anteriores; providers continuam fail-closed e limpam cache.

**Commit:** `refactor(frontend): consolidate core and platform boundaries`

**Não incluir:** mover para `src/`, alterar URLs ou remover a fachada final.

---

## 11. Onda 8 — URL opcional e remoção do legado

### PR `URL-01` — introduzir `/m/<slug>` sem quebrar links existentes

**Precondição:** autorização explícita do produto e todos os manifestos/gates estáveis.

**Arquivos candidatos:** Next route groups/config, middleware, nginx/proxy, links de notificação/busca, login `next=`, testes E2E/route.

**Implementação:**

1. Definir mapa completo URL antiga → nova.
2. Limitar 308 a páginas frontend; não usar esta fase para APIs/métodos mutáveis.
3. Validar `next=` como path relativo same-origin para impedir open redirect.
4. Preservar deep links, notificações, Ctrl+K e retorno pós-login. Fragmentos `#...` são validados em teste browser, pois não chegam ao servidor/redirect.
5. Atualizar nginx e observabilidade de uso dos caminhos antigos; route groups continuam sem efeito na URL.
6. Não remover redirects até janela de depreciação aprovada.

**Testes:** cada URL antiga e nova, query string, hash, `next=`, usuário sem módulo, slug inválido, refresh e proxy.

**Aceite:** nenhum link histórico válido quebra; métricas distinguem antigo/novo.

**Rollback:** manter novas rotas como aliases e voltar geração de links aos caminhos anteriores.

**Commit:** `feat(routes): add module-prefixed frontend paths with redirects`

**Não incluir:** mudanças de RBAC ou movimentos físicos.

### Família `CONTRACT-01..04` — retirar compatibilidade sem big bang destrutivo

**Precondições:**

- tenants ativos, suspensos, cancelados e inativos classificados; todos os módulos aplicáveis em `new` pela janela registrada no runbook;
- divergência crítica zero;
- nenhuma mensagem Celery incompatível após superar retenção, ETA/countdown e retry horizon e comprovar filas drenadas;
- telemetria sem imports/URLs/fachadas legadas em uso;
- backup e restore testados;
- aprovação operacional.

**Arquivos candidatos:**

- wrappers em `backend/app/{routers,services,models,schemas,tasks}/`
- `backend/app/config.py` (`PLANO_MODULOS` operacional)
- RBAC legado `GrupoTransacao`/adapters após contract migration
- `frontend/lib/api.ts`
- `frontend/lib/menus/` e mapas antigos
- allowlists temporárias dos testes estruturais

**PR `CONTRACT-01` — parar writes legados:** desligar dual-write somente após provar que nenhum N-1 existe; manter colunas/leitores. Rollback reativa dual-write no mesmo build.

**PR `CONTRACT-02` — parar reads legados:** remover fallback de booleanos/grupos/mapas, mantendo tabelas/fachadas. Exercitar inclusive tenants cancelados/inativos. Rollback volta ao último build canônico compatível, sem remover proteções `SEC-01A/B` e `SEC-02`.

**Família `CONTRACT-03` — remover fachadas por consumidor:** uma família de imports por PR (routers/services/models/tasks e depois frontend). Provar por `rg`, testes e telemetria; tornar guardas absolutas. Remover `lib/api.ts` somente com zero imports. Nenhuma migration destrutiva.

**PR `CONTRACT-04` — migration contract:** remover somente colunas/tabelas comprovadamente obsoletas, preservar auditoria exigida e manter `tenant_modulo` como tabela física canônica. Backup/restore, downtime/RPO e plano de forward-fix são aprovados antes da execução.

**Testes por etapa:** suítes completas, OpenAPI, matriz de tenants por estado, workers/filas, build e guardas sem allowlist. `CONTRACT-04` adiciona upgrade em banco limpo/legado já totalmente backfilled e restore ensaiado.

**Aceite final:** uma fonte de verdade para módulos/acesso; nenhum adapter ou fachada ativa; documentação atualizada.

**Rollback:** `CONTRACT-01..03` retornam ao último build compatível. Depois de `CONTRACT-04`, não prometer rollback simples de aplicação: usar forward-fix ou restore com downtime/RPO previamente aceitos.

**Commits:** `refactor(architecture): stop legacy <writes|reads|facade>` e `refactor(database): contract retired access schema`.

Mover `frontend/` para `src/` continua fora de escopo e exige plano próprio.

---

## 12. Critérios de revisão por PR

### Segurança

- Existe deny padrão?
- Entitlement é verificado antes do bypass privilegiado?
- Scope entra na query e na mutação?
- IDs cross-tenant são impossíveis também no banco quando aplicável?
- A mudança permite autoelevação ou concessão transitiva?
- Portal, task e download repetem a mesma decisão?
- Auditoria identifica actor, tenant, módulo, capability, alvo e resultado?

### Compatibilidade

- OpenAPI teve mudança breaking ou aditiva não aprovada? Endpoints aditivos versionados e snapshots explicitamente aprovados são permitidos; alteração acidental falha.
- Nome de task, fila ou schedule mudou?
- Schema/tabela/constraint antiga foi renomeada?
- Algum import público foi removido sem wrapper?
- Alguma URL frontend mudou antes de `URL-01`?
- Migration mantém um head e funciona em banco legado?

### Modularidade

- Composition é o único lugar que conhece todos os módulos?
- Platform/core importa algum modelo/screen concreto?
- Um módulo importa internals de outro?
- O manifesto permanece leve e sem I/O?
- A nova superfície foi adicionada ao inventário?
- O frontend adicionou novo import de `@/lib/api`?

### Operação

- Há métrica/log estruturado para cutover e deny?
- Rollback foi exercitado em ambiente de teste?
- Feature flag é por tenant/módulo e fail-closed?
- Worker misto entre versões continua compatível?
- Backfill é idempotente e observável?

---

## 13. Matriz final de aceitação

| Cenário | HTTP | UI | Task/beat | Upload/export | Resultado esperado |
|---|---|---|---|---|---|
| Tenant só Transporte | permite core + Transporte | mostra apenas destinos permitidos | somente jobs Transporte/core | somente Transporte autorizado | operação completa |
| Acesso direto a Protocolo sem contrato | 403/deny | screen não monta | não agenda/executa | nega | nenhum efeito colateral |
| Descontratação com task enfileirada | novas chamadas negadas | snapshot invalida | worker aborta sem retry infinito | nega novos | dados preservados |
| Tenant admin sem papel de módulo | core permitido, negócio negado | gestão de acesso visível, dados ocultos | não executa em nome próprio | nega | menor privilégio |
| Secretaria Transporte | capability permitida | ações coerentes | jobs dentro do scope | export dentro do scope | somente unidades atribuídas |
| Solicitante Transporte | create/read próprios | lista própria | job próprio se permitido | anexos próprios | sem enumeração alheia |
| Administrador do módulo | todas capabilities do módulo | módulo completo | tasks autorizadas | export tenant | sem acesso platform/cross-tenant |
| E-mail igual ao operador SaaS | nega platform | sem UI platform | n/a | n/a | identidade não colide |
| Token/cookie municipal em rota SaaS | nega por issuer/audience | árvore operator não monta | n/a | n/a | realms isolados |
| Autoatribuição privilegiada | nega e audita | ação ausente/erro claro | n/a | n/a | sem elevação |
| Múltiplos papéis/módulos | união controlada por capability/scope | launcher coerente | cada módulo isolado | por módulo | sem papel global acidental |

---

## 14. Definition of Done da transformação

- [ ] Todos os critérios sistêmicos da especificação passam.
- [ ] Todo tenant ativo possui entitlements canônicos e auditáveis.
- [ ] Todos os módulos usam capabilities/scopes v2 em produção.
- [ ] Não há decisão cross-tenant baseada em e-mail/ID municipal nem token/cookie compartilhado entre realms.
- [ ] Não há autoelevação ou grant acima da autoridade.
- [ ] Todas as superfícies estão no registry/inventário.
- [ ] Backend está organizado em `composition`, `platform`, `core`, `modules` e `shared`.
- [ ] Frontend está organizado em `core`, `platform`, `modules`, `portals` e `shared`.
- [ ] Nenhum módulo importa internals de outro.
- [ ] Core não importa modelos/screens de negócio.
- [ ] `frontend/lib/api.ts` e fachadas antigas foram removidas após a janela.
- [ ] OpenAPI e links suportados permanecem compatíveis ou têm migração isolada aprovada.
- [ ] Nomes de tasks e filas foram preservados durante deploys mistos.
- [ ] Alembic possui um único head e migrations antigas permanecem intactas.
- [ ] Playbooks de provisionar, suspender, reativar, cancelar, rollback e restore foram exercitados.
- [ ] Documentação e ADRs refletem o estado efetivamente implantado.

## 15. Primeiro passo recomendado ao executor

Começar exclusivamente por `SEC-00`. O Claude deve inventariar a autenticação atual e produzir o ADR/fixtures; sem aprovação do realm administrativo, não inicia `SEC-01A/B`. Depois da aprovação, o primeiro commit de `SEC-01A` reproduz a colisão de identidade/token e o seguinte implementa o principal separado. Não iniciar movimentos de pasta ou RBAC v2 enquanto `SEC-01A/B` e `SEC-02` não estiverem revisados e implantáveis.
