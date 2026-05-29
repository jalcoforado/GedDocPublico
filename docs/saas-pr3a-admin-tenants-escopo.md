# PR 3a — Escopo Técnico: Admin SaaS / Gestão de Tenants

**Autor:** Jorge + assistente · **Data:** 2026-05-28 · **Status:** PROPOSTA (não implementar)

> Criar a **base para operar várias prefeituras de forma repetível**, sem
> intervenção manual no banco nem ajuste de desenvolvedor: um painel
> administrativo da plataforma para **criar / listar / editar / ativar /
> desativar** tenants, com **provisionamento mínimo** (admin inicial + catálogos)
> reaproveitando a lógica que já existe no CLI.
>
> Documento é **só proposta** — nada será implementado até aprovação. Há
> **decisões humanas pendentes** no §13 (modelo de auth do admin de plataforma,
> status, limites, módulos por tenant).

---

## 0. Situação atual (apurada no código)

- **Tenant** (`models/tenant.py`): `id, slug(50,único), nome(150), cnpj(20),
  id_cidade, ativo(bool), plano(20, default 'basico'), cor_primaria(7),
  logo_url(500), criado_em, atualizado_em, codigo_orgao_nup(5), usar_nup_federal`.
  **Sem** campos de limite/quota.
- **Criação de tenant hoje = só CLI** (`app/cli/tenant.py create`). **Não há
  endpoint**. `tenant.py:13` já diz "endpoint admin fica para fase futura".
- **Endpoints de tenant**: `GET /tenants/me`, `PUT /tenants/me/nup-config`,
  `GET /branding/me` — **todos tenant-scoped**; nenhum cross-tenant.
- **Não existe admin de plataforma.** Super-usuário = `nivel.valor==0` **dentro
  do próprio tenant** (`permissoes.load_permissions`). Toda permissão passa por
  `require_tenant_id()` (do subdomínio). Nenhum endpoint opera cross-tenant.
- **`aprimora_py.tenant` NÃO tem RLS** (as 26 tabelas tenant-scoped têm). Logo,
  operar o **registro** de tenants é seguro fora do RLS; provisionar o **conteúdo**
  do novo tenant (usuário/grupo/unidade) toca tabelas com RLS.
- **Bootstrap mínimo (do CLI)**: 1 `tenant` + `tipo_unidade_trabalho` +
  `unidade_trabalho` + `tipo_manifestante` + `usuario`(admin) + `grupo`(SU,
  nivel.valor=0) + `usuario_grupo`. Pré-requisitos **globais**: `nivel`(valor=0),
  `sistema`(app='sistemas'), `categoria`.
- **Módulos**: `Modulo`/`ConfiguracoesModulos` são **globais** (schema public),
  por ambiente — **não há ativação por tenant**; `plano` é string sem enforcement.
- **Frontend**: só `app/(app)/configuracoes` (read-only do tenant + NUP). Sem
  área de plataforma.

## 1. Painel admin da plataforma

Área **separada** do app tenant-scoped, p/ operador da plataforma (não da
prefeitura). Rotas frontend fora do fluxo normal, ex.: `app/(plataforma)/admin/tenants`.
Backend sob prefixo **não tenant-scoped** `/api/v2/admin/...` (ver §10 auth).

Telas: **lista** de tenants (busca/ordenação por nome/slug/status/plano),
**criar**, **editar**, **ativar/desativar**, **ver detalhe** (dados +
status + admin inicial gerado).

## 2. CRUD de tenants (endpoints)

Todos sob `require_platform_admin` (§10), **sem** `require_tenant_id`:

| Método | Rota | Ação |
|---|---|---|
| GET | `/api/v2/admin/tenants` | listar (paginado, filtros slug/status/plano) |
| POST | `/api/v2/admin/tenants` | **criar + provisionar** (§7) |
| GET | `/api/v2/admin/tenants/{id}` | detalhe |
| PUT | `/api/v2/admin/tenants/{id}` | editar dados institucionais/plano/branding |
| POST | `/api/v2/admin/tenants/{id}/ativar` | ativar |
| POST | `/api/v2/admin/tenants/{id}/desativar` | desativar |

- **Não** há DELETE físico (tenant carrega dados): desativar = `ativo=false`
  (middleware já bloqueia login pelo subdomínio: resolve só `ativo=true`).
- Toda ação gera **audit_log** (tenant_id do alvo + ator plataforma).

## 3. Plano / módulos ativos

- `plano` (string) editável. **Decisão (§13.4)**: módulos por tenant —
  opções: (a) derivar de `plano` (mapa plano→módulos em config) ou (b) tabela
  `aprimora_py.tenant_modulo` (ativação explícita). Recomendação: começar por
  **(a) derivado do plano**, sem nova tabela, e deixar ativação fina para PR 3b.
- PR3a **armazena** o plano; **enforcement** real (gating de features/quotas)
  é fora de escopo aqui (PR futuro).

## 4. Dados institucionais

Editáveis no painel: `nome`, `cnpj`, `id_cidade`, `cor_primaria`, `logo_url`,
`codigo_orgao_nup`, `usar_nup_federal`. `slug` **imutável após criação**
(é a identidade do subdomínio; renomear quebra URLs/QR/validação pública).

## 5. Subdomínio

- `slug`: validação **dns-safe** (minúsculo, `[a-z0-9-]`, 3–50, sem `-` nas
  pontas), **único** (constraint já existe), **reservados** bloqueados
  (`www, api, admin, app, mail, static, assets`).
- Resolução por subdomínio já funciona (`middleware/tenant.py`); PR3a só
  garante o slug válido na criação.

## 6. Admin inicial da prefeitura

- POST de criação recebe `admin_email` (+ nome). Gera o **usuário super** do
  tenant (grupo SU `nivel.valor=0`), como o CLI.
- **Senha**: gerar **senha temporária** (bcrypt, nunca MD5) retornada **uma única
  vez** na resposta da criação (ou enviar por e-mail se SMTP configurado).
  Forçar troca no primeiro login fica para PR futuro (flag opcional).

## 7. Bootstrap mínimo (provisionamento)

- **Extrair a lógica do CLI** (`app/cli/tenant.py`) para um **serviço
  reutilizável** `services/provisioning_tenant.py` (`provisionar_tenant(...)`),
  chamado **tanto pelo CLI quanto pelo endpoint** — fonte única, sem divergência.
- Cria: tenant + tipo_unidade_trabalho + unidade_trabalho("Protocolo Geral") +
  tipo_manifestante("Pessoa Física") + usuario(admin) + grupo(SU) + usuario_grupo.
- **Isolamento no provisionamento (crítico)**: os inserts de
  usuario/grupo/unidade/etc. são em tabelas **com RLS**. Em prod (`aprimora_app`,
  NOBYPASSRLS) é preciso `SET LOCAL app.tenant_id = <novo_id>` **antes** desses
  inserts (a sessão admin de plataforma não tem tenant). Em dev (`ged_user`
  superuser) passa, mas a implementação **deve** setar o tenant explicitamente
  para funcionar em prod. (Ver §12 riscos.)
- **Pré-requisitos globais** (`nivel` valor=0, `sistema` app='sistemas',
  `categoria`): garantir existência (idempotente) no provisionamento.
- **Transação única**: criação + bootstrap atômicos; falha → rollback total
  (não deixar tenant órfão sem admin).

## 8. Status do tenant

- Mínimo: `ativo` (já existe). **Decisão (§13.2)**: manter só boolean **ou**
  adicionar `status` enum (`provisionando|ativo|suspenso|encerrado`).
  Recomendação: **boolean `ativo`** no PR3a (suficiente p/ MVP); enum fica p/
  depois se o operacional exigir.

## 9. Limites básicos

- Hoje **não há** campos de limite. **Decisão (§13.3)**: (a) **não adicionar**
  agora (YAGNI) ou (b) adicionar campos nullable `limite_usuarios`,
  `limite_armazenamento_mb` **apenas armazenados** (sem enforcement).
  Recomendação: **(b) só armazenar** os 2 campos (migration pequena), enforcement
  em PR futuro — assim o painel já coleta o dado sem prometer bloqueio.

## 10. Permissões necessárias (auth do admin de plataforma)

**O ponto arquitetural central.** Hoje todo acesso é tenant-scoped; o admin de
plataforma precisa operar **cross-tenant**, então **não** pode usar
`require_tenant_id`. **Decisão (§13.1)** — opções:

- **(a) Allowlist em tabela** `aprimora_py.plataforma_admin` (FK usuario **ou**
  e-mail), + dependência `require_platform_admin(user)` que valida o usuário
  logado contra a allowlist **sem exigir tenant**. *Recomendada* — explícita,
  auditável, sem novo fluxo de login.
- (b) Claim no JWT (`role=platform_admin`) — exige emissor confiável.
- (c) App/login separado — maior esforço, fora do MVP.

Recomendação: **(a)**. O `require_platform_admin` resolve o usuário pelo JWT
(reusando `get_current_user` **sem** o filtro de tenant — precisa de variante que
não dependa de `request.state.tenant_id`), checa a allowlist e nega (403) caso
contrário. Seed inicial da allowlist via CLI/migration para o operador atual.

## 11. Testes obrigatórios

**Backend**
1. criar tenant via API provisiona tenant + admin + grupo SU + unidade +
   catálogos (idempotente nos globais).
2. criação é **atômica** (falha no meio → rollback, sem tenant órfão).
3. slug inválido/reservado/duplicado → 422/409.
4. listar/editar/detalhe retornam dados corretos.
5. desativar → tenant some da resolução por subdomínio (login no subdomínio falha)
   e não aparece como ativo.
6. ativar volta a funcionar.
7. **isolamento**: provisionar tenant B não vaza/contamina dados do tenant A;
   o admin criado pertence só ao tenant novo (checar tenant_id em todas as linhas).
8. **auth**: usuário comum / super-usuário **de um tenant** (não-plataforma) →
   **403** nas rotas `/api/v2/admin/...`; só platform-admin acessa.
9. rotas admin **não** dependem de subdomínio (funcionam sem tenant resolvido).
10. audit_log gerado em criar/editar/ativar/desativar.

**Frontend**
11. lista renderiza tenants + status; busca/filtra.
12. criar tenant chama a API e mostra a senha temporária do admin uma única vez.
13. ativar/desativar com confirmação; reflete status.
14. painel de plataforma **não aparece** para usuário sem papel de plataforma.

## 12. Riscos de isolamento multi-tenant

- **Bypass de tenant nas rotas admin**: ao remover `require_tenant_id`, a sessão
  não seta `app.tenant_id` → sob RLS (prod) as 26 tabelas ficam **invisíveis**
  (policy compara com NULL). Isso é **bom** para o registro de tenants
  (`aprimora_py.tenant` sem RLS), mas o **provisionamento** precisa setar
  `app.tenant_id` do novo tenant para inserir nas tabelas com RLS (§7). Errar
  isso = bootstrap falha em prod (ou, pior, em dev com superuser, "funciona" e
  esconde o bug).
- **Vazamento cross-tenant**: qualquer query nas rotas admin que toque tabelas
  RLS sem tenant setado deve ser **explicitamente** escopada; nunca listar
  conteúdo de tenants no painel sem escopo.
- **Escalada de privilégio**: `require_platform_admin` é a única barreira para
  operar todas as prefeituras — testar 403 para super-usuário de tenant comum é
  obrigatório (teste 8).
- **Slug imutável**: renomear quebraria subdomínio/validação pública (PR2e/2f) —
  bloquear edição de slug.
- **Senha do admin inicial**: nunca logar/persistir em claro; bcrypt; exibir 1x.

## 13. Decisões humanas pendentes

1. **Auth do admin de plataforma**: (a) allowlist `plataforma_admin` *[recomendada]*,
   (b) claim JWT, (c) app separado?
2. **Status**: só `ativo` boolean *[recomendado]* ou enum `status`?
3. **Limites**: não adicionar agora, ou adicionar `limite_usuarios`/
   `limite_armazenamento_mb` só-armazenados *[recomendado]*?
4. **Módulos por tenant**: derivar de `plano` *[recomendado p/ 3a]* ou tabela
   `tenant_modulo` (PR 3b)?
5. **Senha do admin inicial**: exibir 1x na resposta *[recomendado p/ dev]* ou
   exigir SMTP/convite por e-mail?

## 14. Fora de escopo (PR 3a)

- Enforcement de quotas/limites (só armazenar, se decidido).
- Gating fino de módulos por feature; billing/cobrança.
- Self-service de cadastro de prefeitura pela própria prefeitura (signup público).
- Troca obrigatória de senha no 1º login (flag futura).
- Migração de dados entre tenants; exclusão física de tenant.
- gov.br / ICP-Brasil / qualquer item da trilha de assinatura.
- Observabilidade/billing por tenant; rate-limit por plano.

## 15. Arquivos prováveis

**Backend**: migration (allowlist `plataforma_admin` + eventuais
`limite_*`); `services/provisioning_tenant.py` (extraído do CLI);
`app/cli/tenant.py` (passa a chamar o serviço); `routers/admin_tenants.py` (novo,
`/api/v2/admin/...`); `auth/deps.py` (`require_platform_admin` + variante de
`get_current_user` sem tenant); `schemas/admin_tenant.py`.
**Frontend**: `app/(plataforma)/admin/tenants/*` (lista/criar/editar/detalhe);
`lib/api.ts` (cliente admin); gating de nav por papel de plataforma.
**Docs**: atualizar README/RUNBOOK (operação de provisionamento via painel).

---

> **Parar aqui.** Proposta apenas — nada implementado. Aguardando suas decisões
> (§13) e autorização para fechar o escopo implementável do PR 3a.
