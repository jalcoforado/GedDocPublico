# PR 3a — Escopo Implementável Consolidado: Admin SaaS / Gestão de Tenants

**Autor:** Jorge + assistente · **Data:** 2026-05-29 · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Base para operar várias prefeituras de forma repetível: painel da plataforma
> para **criar / listar / editar / ativar / desativar** tenants, com
> **provisionamento mínimo** (admin SU + grupo + unidade + catálogos)
> reaproveitando a lógica do CLI num **serviço único transacional**.
>
> Todas as decisões estão **fechadas** (§1). Proposta original em
> `docs/saas-pr3a-admin-tenants-escopo.md`. **Nada será implementado até
> autorização.**

---

## 1. Decisões fechadas

| # | Tema | Decisão |
|---|---|---|
| 1 | Auth admin de plataforma | **Allowlist via env** (`PLATFORM_ADMIN_EMAILS`). SU de tenant **não** é admin de plataforma. 403 para autenticado fora da allowlist. Sem app separado; sem mudança profunda de JWT; não misturar permissão de tenant com plataforma. |
| 2 | Status | Só `ativo` boolean. `ativo=false` bloqueia acesso pelo subdomínio (comportamento já existente). Sem enum agora. |
| 3 | Limites | Adicionar `limite_usuarios` + `limite_armazenamento_mb` (**só armazenados**, sem enforcement). |
| 4 | Módulos | **Derivar do `plano`** (mapa em config). Sem tabela `tenant_modulo`. |
| 5 | Senha do admin inicial | **Senha temporária auto-gerada, exibida 1x** na resposta. Só hash bcrypt persistido. Troca-no-1º-acesso = **pendência** (não trivial; ver §8). Convite por e-mail fora de escopo. |
| 6 | RLS no provisionamento | Ponto crítico (§5/§11): registro do tenant cross-tenant; inserts tenant-scoped com `SET LOCAL app.tenant_id=<novo>`; funciona sob role de produção; falha clara se contexto ausente; **atômico**. |
| 7 | Serviço único | Extrair `services/provisioning_tenant.py`; CLI e API reusam. |
| 8 | Slug | **Imutável após criação**. Editar nome sim, slug não. |
| 9 | Delete | **Sem DELETE físico**. Desativar = `ativo=false`. |

## 2. Modelo de dados — migration `00XX_tenant_limites`

Colunas novas em `aprimora_py.tenant` (nullable, **só armazenadas**):
- `limite_usuarios` `integer` null
- `limite_armazenamento_mb` `integer` null

`aprimora_py.tenant` **não tem RLS** (continua assim). Sem outras tabelas novas
(auth é por env; módulos por plano). Nenhuma alteração nas 26 tabelas RLS.

## 3. Auth do admin de plataforma

- Config: `platform_admin_emails: str = ""` (env `PLATFORM_ADMIN_EMAILS`,
  separado por vírgula) + helper `is_platform_admin(email) -> bool`.
- Dependência `require_platform_admin` em `auth/deps.py`:
  1. autentica via JWT (reusa o fluxo de `get_current_user`; o claim `tenant_id`
     do token é usado p/ carregar o usuário sob RLS — **sem** depender do
     subdomínio nem de `require_permission`).
  2. checa `usuario.email ∈ allowlist`. **403** caso contrário.
  - **Não** chama `require_tenant_id` nem `require_permission` (sem mistura
    tenant↔plataforma).
- Allowlist inicial documentada no `.env`/RUNBOOK para o operador atual.

## 4. Serviço único de provisionamento — `services/provisioning_tenant.py`

`async def provisionar_tenant(db, *, slug, nome, cnpj=None, id_cidade=None,
plano="basico", cor_primaria=None, logo_url=None, limite_usuarios=None,
limite_armazenamento_mb=None, admin_email, admin_nome) -> (Tenant, senha_temp)`

- **Transação única (atômica)**: tudo ou nada.
- Passos:
  1. valida slug (§7); cria `aprimora_py.tenant` (sem RLS) → obtém `novo_id`.
  2. **`SET LOCAL app.tenant_id = novo_id`** (a partir daqui, inserts tenant-scoped).
  3. garante globais idempotentes: `nivel`(valor=0), `sistema`(app='sistemas'),
     `categoria`(PF) — só cria se faltar.
  4. cria `tipo_unidade_trabalho` + `unidade_trabalho`("Protocolo Geral") +
     `tipo_manifestante`("Pessoa Física") + `usuario`(admin, bcrypt) +
     `grupo`(SU, nivel.valor=0) + `usuario_grupo`.
  5. gera **senha temporária** (`secrets.token_urlsafe`), grava só `senha_bcrypt`,
     retorna a senha em claro **uma vez** (nunca logar/persistir em claro).
  6. audit_log `tenant.provisionado` (ator plataforma + tenant alvo).
- **CLI `app/cli/tenant.py` passa a chamar este serviço** (uma lógica só).
- **Falha clara** se `app.tenant_id` não setado antes dos inserts tenant-scoped
  (em prod a RLS bloquearia; o serviço deve setar explicitamente e validar).

## 5. Endpoints admin (`routers/admin_tenants.py`, prefixo `/api/v2/admin`)

Todos sob `require_platform_admin`, **sem** `require_tenant_id`:

| Método | Rota | Ação |
|---|---|---|
| GET | `/admin/tenants` | listar (paginado; filtros slug/ativo/plano) — só `aprimora_py.tenant` (sem dados tenant-scoped) |
| POST | `/admin/tenants` | `provisionar_tenant(...)`; resposta inclui a senha temporária 1x |
| GET | `/admin/tenants/{id}` | detalhe (registro do tenant; nunca conteúdo interno) |
| PUT | `/admin/tenants/{id}` | editar `nome, cnpj, id_cidade, plano, cor_primaria, logo_url, limite_*` (**slug imutável**) |
| POST | `/admin/tenants/{id}/ativar` | `ativo=true` + audit |
| POST | `/admin/tenants/{id}/desativar` | `ativo=false` + audit |

- Listagem **nunca** lê tabelas tenant-scoped (sem vazamento cross-tenant).
- Toda mutação → audit_log (`tenant.criado/editado/ativado/desativado`).

## 6. Slug

dns-safe (`[a-z0-9-]`, 3–50, sem `-` nas pontas), **único** (constraint existe),
**reservados** bloqueados (`www, api, admin, app, mail, static, assets`).
**Imutável** após criação (PUT rejeita mudança de slug).

## 7. Senha do admin inicial

- Auto-gerada, exibida 1x na resposta de criação. Só `senha_bcrypt` persistido.
- **Troca no 1º acesso = pendência** (não-trivial: exige flag em `usuario` +
  enforcement no login). Registrar como follow-up (PR futuro). PR3a só entrega a
  senha temporária 1x com aviso explícito na UI.

## 8. Módulos por plano

- Constante `PLANO_MODULOS: dict[str, list[str]]` (config) mapeando
  `basico/profissional/enterprise` → módulos. Helper `modulos_do_plano(plano)`.
- O painel **exibe** os módulos derivados do plano. **Sem enforcement/gating**
  funcional neste PR; sem tabela `tenant_modulo`.

## 9. Frontend — painel da plataforma

- Área separada `app/(plataforma)/admin/tenants/` (fora do fluxo tenant-scoped),
  **só visível** para platform admin (gating: a API responde 403; a nav esconde
  o item quando o usuário não é platform-admin — flag exposta por um endpoint
  leve, ex. `GET /admin/me` → `{is_platform_admin: bool}`).
- Telas: **lista** (busca/filtro por status/plano), **criar** (mostra a senha
  temporária 1x com aviso), **editar** (sem slug), **ativar/desativar** (confirmação).
- `lib/api.ts`: cliente `api.admin.tenants.*`.

## 10. RLS / isolamento (ponto crítico)

- Rotas admin **não** setam tenant pelo subdomínio; operam em `aprimora_py.tenant`
  (sem RLS) → seguro listar/editar o registro.
- **Provisionamento** seta `SET LOCAL app.tenant_id=<novo>` antes dos inserts
  tenant-scoped; sem isso, sob produção (`aprimora_app`, NOBYPASSRLS) a RLS
  bloqueia (e em dev superuser "funcionaria", escondendo o bug) → **teste deve
  simular produção** (rodar o provisionamento com a role `aprimora_app`/RLS, como
  o fixture `app_session` já faz nos testes de RLS).
- Nenhuma query das rotas admin toca tabelas tenant-scoped sem escopo.

## 11. Sequência de implementação

1. Migration `tenant_limites` (2 colunas).
2. `provisioning_tenant.py` (extraído do CLI) + CLI passa a chamá-lo; testes do serviço (incl. RLS-prod).
3. Config `platform_admin_emails` + `require_platform_admin` + `GET /admin/me`.
4. `routers/admin_tenants.py` (CRUD + ativar/desativar) + schemas; testes de API + 403.
5. `PLANO_MODULOS` + `modulos_do_plano`.
6. Frontend `(plataforma)/admin/tenants/*` + cliente + gating de nav; testes vitest.
7. Atualizar RUNBOOK/README (operação via painel + `PLATFORM_ADMIN_EMAILS`).

## 12. Critérios de aceite

- Platform admin (allowlist) cria/lista/edita/ativa/desativa tenants pela UI.
- Usuário comum e **SU de tenant comum → 403** nas rotas `/api/v2/admin/...`.
- Criação provisiona tenant + admin SU + grupo + unidade + catálogos, **atômica**.
- Provisionamento funciona **sob RLS de produção** (app.tenant_id setado); falha
  clara se contexto ausente.
- Slug **imutável**; nome editável.
- Desativar bloqueia acesso pelo subdomínio; ativar restaura.
- `limite_*` e `plano` persistidos (sem enforcement).
- CLI e API usam o **mesmo** serviço.
- Listagem **não** expõe dados tenant-scoped.
- Senha temporária exibida 1x; só hash persistido.
- Sem regressão; pytest + vitest verdes.

## 13. Testes obrigatórios

**Backend**
1. platform admin cria tenant (provisiona tudo).
2. usuário comum → 403; 3. SU de tenant comum → 403.
4. tenant criado com admin inicial; 5. com grupo/unidade/catálogos mínimos.
6. bootstrap transacional (falha no meio → rollback, sem tenant parcial).
7. slug não pode ser alterado (PUT rejeita).
8. tenant desativado bloqueia acesso/login pelo subdomínio.
9. provisionamento funciona **com app.tenant_id setado** (fixture role RLS).
10. criar dados tenant-scoped **sem** contexto falha/é protegido (sob RLS).
11. CLI e API usam o mesmo serviço (ex.: CLI test chama `provisionar_tenant`).
12. `limite_*` armazenados; 13. `plano` persistido.
14. listagem de tenants não expõe dados tenant-scoped indevidos.

**Frontend (vitest)**
15. lista tenants; 16. cria tenant (mostra senha 1x); 17. edita dados permitidos;
18. ativa/desativa; 19. **não** permite editar slug; 20. painel não aparece p/
   não-plataforma.

## 14. Fora de escopo

billing/cobrança; enforcement de limites; tabela `tenant_modulo`; convite por
e-mail; domínio customizado/DNS automático; trial/inadimplência/cancelamento;
métricas avançadas; backup por tenant; suporte/tickets; impersonation; exclusão
física; migração complexa de tenants existentes; app separado de plataforma;
troca obrigatória de senha no 1º acesso (pendência, §7).

## 15. Arquivos prováveis

**Backend**: `alembic/versions/00XX_tenant_limites.py`;
`services/provisioning_tenant.py` (novo, extraído do CLI); `app/cli/tenant.py`
(chama o serviço); `routers/admin_tenants.py` (novo); `auth/deps.py`
(`require_platform_admin`); `config.py` (`platform_admin_emails`, `PLANO_MODULOS`);
`schemas/admin_tenant.py`; registro do router no `main.py`.
**Frontend**: `app/(plataforma)/admin/tenants/*`; `lib/api.ts` (cliente admin);
gating de nav.
**Docs**: RUNBOOK/README (operação + `PLATFORM_ADMIN_EMAILS`).

---

> **Parar aqui.** Escopo consolidado e fechado, nada implementado. Aguardando
> autorização para iniciar na ordem do §11 (migration → serviço → auth → API →
> frontend → testes).
