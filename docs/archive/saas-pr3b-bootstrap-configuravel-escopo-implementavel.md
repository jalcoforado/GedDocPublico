# PR 3b — Escopo Implementável: Bootstrap configurável e configuração inicial do tenant

**Autor:** Jorge + assistente · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Consolida a [proposta](saas-pr3b-bootstrap-configuravel-escopo.md) com as **10
> decisões do Jorge** já fechadas. Define o que será implementado. **Nada será
> alterado em código até autorização explícita.**

---

## 1. Objetivo

Permitir que o **admin municipal** (usuário do próprio tenant, com permissão) revise e
ajuste a **configuração inicial** da prefeitura pela interface, reduzindo dependência de
CLI/scripts/alteração manual no banco. O foco é um "painel de configuração inicial"
simples e seguro — **não** reconstruir o que já existe. A maior parte do CRUD
(unidades, usuários, grupos, catálogos) **já está pronta**; o PR consolida/expõe e
acrescenta apenas: dados institucionais editáveis, reset de senha temporária e checklist
de onboarding.

## 2. Alterações de banco — migration `0023_tenant_config_inicial`

Tabela `aprimora_py.tenant` (sem RLS) — colunas **novas**, todas `nullable`:

| Coluna | Tipo | Notas |
|---|---|---|
| `sigla` | `varchar(20)` | |
| `email_institucional` | `varchar(255)` | |
| `telefone_institucional` | `varchar(20)` | |
| `endereco` | `text` | **texto simples** (decisão 1 — sem CEP/logradouro/UF) |
| `site_oficial` | `varchar(255)` | |
| `horario_atendimento` | `varchar(255)` | |
| `texto_boas_vindas_portal` | `text` | portal do cidadão |
| `id_unidade_padrao` | `integer` | **soft-ref** a `utils.unidade_trabalho.id` (sem FK rígida — segue o padrão de `usuario.id_unidade_trabalho`); validado no serviço |

**Já existentes — não recriar:** `logo_url` (varchar 500, decisão 2 → editado como URL),
`cor_primaria`, `nome`, `cnpj` (decisão 7 → CNPJ **não** entra no form institucional;
fica para dados fiscais/contratuais).

**Permissão (decisão 4):** a migration também faz `INSERT` **idempotente** em
`utils.transacao` da transação de configuração:

```sql
INSERT INTO utils.transacao (transacao, codigo)
VALUES ('Configuração do tenant', 'configuracao')
ON CONFLICT (codigo) DO NOTHING;
```

> Não mapear `sistema_transacao`/`grupo_transacao` na migration (id de sistema é
> ambiente-dependente e seria semeado depois). Super-usuário **bypassa** a checagem, então
> o admin provisionado já opera. Grupos não-SU recebem a permissão pela UI de
> **grupos → transações** (já existente). Registrado como nota operacional, não dívida.

**Reprodutibilidade CI:** o workflow `e2e-assinatura.yml` faz `alembic stamp 0020 &&
alembic upgrade head`, então a 0023 roda automaticamente. Validar a migration em banco
limpo antes de commit.

## 3. Endpoints (backend)

| Método | Rota | Auth/Permissão | Descrição |
|---|---|---|---|
| GET | `/api/v2/tenants/me` | `get_current_user` (existente) | **estender** `TenantMeResponse` com os campos institucionais + `id_unidade_padrao` |
| PUT | `/api/v2/tenants/me` | `require_permission("configuracao","atualizar")` | **NOVO** — atualiza só campos institucionais (whitelist §6) |
| GET | `/api/v2/tenants/me/onboarding` | `get_current_user` + `require_tenant_id` | **NOVO** — checklist calculado (§5), read-only |
| POST | `/api/v2/usuarios/{id}/resetar-senha` | `require_permission("usuario","atualizar")` | **NOVO** — gera senha temporária, retorna 1x, grava só hash, audita |
| PUT | `/api/v2/tenants/me/nup-config` | (migrar p/ `configuracao:atualizar`) | **existente** — só trocar o gate p/ consistência (§7) |

Catálogos/unidades/usuários/grupos: **sem novos endpoints** (CRUD já existe).

### 3.1 `PUT /tenants/me` (whitelist de campos)
Aceita **apenas**: `nome, sigla, email_institucional, telefone_institucional, endereco,
site_oficial, horario_atendimento, texto_boas_vindas_portal, logo_url, cor_primaria,
id_unidade_padrao`. **Ignora** qualquer outro campo do corpo (id, slug, plano, ativo,
limites, cnpj, codigo_orgao_nup, etc.). Se `id_unidade_padrao` vier, **validar** que a
unidade existe e é do tenant (senão 400/422) — evita apontar para unidade de outro tenant.

### 3.2 `POST /usuarios/{id}/resetar-senha` (decisão 5)
- Carrega o usuário **escopado ao tenant** (404 se não for do tenant — sem cross-tenant).
- Gera senha temporária (reusar o gerador do `services/provisioning_tenant`, ex.
  `secrets.token_urlsafe(...)`); grava **só** `senha_bcrypt = hash_password(temp)`; mantém
  `senha` (MD5 legado) inalterado/vazio (não persistir claro).
- Retorna a senha **uma única vez** no corpo da resposta.
- **Audita** (`audit_log`, `acao="usuario.senha_resetada"`, sem a senha no payload).
- Não envia e-mail; sem `must_change_password` (fora de escopo).

## 4. Frontend

Tudo na página **existente** `/configuracoes` (`frontend/app/(app)/configuracoes/page.tsx`)
— **não criar página nova**:

1. **Seção "Identidade institucional"** — form com os campos da migration (Input/Textarea),
   editável quando `can("configuracao","atualizar")`, senão read-only. Salva via
   `tenantsApi.updateInstitucional(payload)`.
2. **Unidade padrão** — `Select` populado por `api.unidades.list()` do tenant.
3. **Card de checklist de onboarding** — consome `tenantsApi.onboarding()`; cada item
   pendente com deep-link para a área correspondente (unidades, usuários, grupos,
   assuntos, tipos de processo, espécies).
4. **Reset de senha** — botão na página existente `/usuarios` (por usuário) → `confirm`
   → chama `api.usuarios.resetarSenha(id)` → exibe a senha temporária **uma vez** num
   dialog (com aviso de copiar agora).

`lib/api.ts`: adicionar `tenantsApi.updateInstitucional`, `tenantsApi.onboarding`,
`api.usuarios.resetarSenha`. Reusar `Dialog`, `Input`, `Textarea`, `Select`, `useToast`,
`useConfirm`, `PageHeader`.

## 5. Checklist de onboarding (decisão 6)

`GET /tenants/me/onboarding` → booleanos calculados (queries tenant-scoped, contagens):

| Item | Cálculo |
|---|---|
| `dados_institucionais` | campos essenciais preenchidos (ex.: `email_institucional` e `telefone_institucional`) |
| `unidade_padrao` | `tenant.id_unidade_padrao` não nulo |
| `unidade_ativa` | ≥ 1 unidade com `excluido=false` |
| `usuarios_ativos` | ≥ 1 usuário `ativo` além do admin inicial |
| `grupos` | ≥ 1 grupo |
| `assuntos` | ≥ 1 assunto |
| `tipos_processo` | ≥ 1 tipo de processo |
| `especies_documentais` | ≥ 1 espécie documental |
| `assinatura` | `"assinatura" in modulos_do_plano(plano)` (hoje sempre true → "módulo habilitado"; placeholder honesto até haver config por tenant) |
| `portal_cidadao` | `texto_boas_vindas_portal` preenchido |

> Itens sem cálculo seguro: marcar como `null`/"não avaliado". Nenhum item depende de
> dado sensível; tudo do próprio tenant.

## 6. Permissões

- **Nova transação `configuracao`** (`codigo='configuracao'`), ação `atualizar`. Gate de
  `PUT /tenants/me` (e, por consistência, do `PUT /tenants/me/nup-config` e da edição na
  página `/configuracoes`).
- **Super-usuário** (`nivel.valor==0`) bypassa — o admin provisionado opera de imediato.
- **Não-SU**: recebem `configuracao` via a UI **grupos → transações** (já existe).
- **Reset de senha** usa `usuario:atualizar` (é gestão de usuário, não config de tenant).
- **`can("configuracao","atualizar")`** no front controla o modo edição (SU sempre true).

## 7. Segurança multi-tenant (decisão 8 — obrigatório)

- `PUT /tenants/me` **usa `request.state.tenant_id`**; **nunca** aceita `tenant_id`/`id`
  do cliente como fonte de verdade.
- Como `aprimora_py.tenant` **não tem RLS**, o update faz `WHERE id = request.state.tenant_id`
  **explicitamente** (RLS não protege essa tabela).
- Ignora `id, slug, plano, ativo, limite_*, cnpj` e qualquer campo de plataforma do corpo.
- `id_unidade_padrao` validado contra unidades do **próprio** tenant.
- `resetar-senha`: usuário carregado com filtro `tenant_id` → **sem cross-tenant**.
- `onboarding`: todas as contagens com `tenant_filter`.
- Admin municipal (RBAC do tenant) **≠** admin de plataforma (`PLATFORM_ADMIN_EMAILS`):
  nenhuma rota nova usa `require_platform_admin`.

## 8. Testes obrigatórios

**Backend (pytest):**
- `PUT /tenants/me` atualiza só campos institucionais; **ignora** `id/slug/plano/ativo/limites/cnpj` enviados no corpo.
- `PUT /tenants/me` escopa por `request.state.tenant_id` — tentativa de alterar tenant diferente **falha** (ou é ignorada); sem cross-tenant.
- usuário **sem** `configuracao:atualizar` (e não-SU) recebe **403** no `PUT /tenants/me`.
- `id_unidade_padrao` de **outro** tenant é rejeitado.
- `resetar-senha`: gera temporária, retorna 1x, persiste **só hash** (login com a nova funciona; senha não fica em claro); **audita**; reset de usuário de outro tenant → 404.
- `onboarding`: tenant vazio → itens `false`; após criar dados → `true` (reflete estado real).
- migration 0023 aplica em banco limpo (fluxo `stamp 0020 → upgrade head`); transação `configuracao` criada idempotente.

**Frontend (vitest; `fireEvent.change` por causa do focus-trap do Dialog):**
- `/configuracoes` renderiza a seção institucional e salva (mock `PUT /tenants/me`).
- modo **leitura** quando `can("configuracao","atualizar") === false`.
- form não envia campos proibidos (id/slug/plano).
- reset de senha exibe a senha temporária **uma vez**.
- card de checklist exibe pendências calculadas.
- (CRUD de unidades/usuários/catálogos já tem cobertura — só adicionar o que é novo.)

## 9. Itens fora de escopo (decisão 10)

upload de logo · endereço estruturado · CNPJ (no form) · convite por e-mail ·
`must_change_password` · organograma avançado · redesenho de RBAC · novos CRUDs
duplicados · portal por serviços completo · GED/versionamento · dashboards executivos ·
billing · enforcement de limites · módulos por tenant · domínio customizado ·
CRUD de "ações" (catálogo global, sem tenant_id) · gov.br/ICP-Brasil.

## 10. Critérios de aceite

- Migration 0023 criada, aplicável em banco limpo e idempotente (incl. transação `configuracao`).
- `PUT /tenants/me` edita só campos institucionais, escopado ao tenant, ignorando campos de plataforma — com testes de tentativa cross-tenant e de campos proibidos.
- Reset de senha temporária funcionando: gerada, exibida 1x, só hash persistido, auditado, sem cross-tenant.
- Checklist de onboarding calculado, refletindo o estado real do tenant.
- Página `/configuracoes` estendida (institucional + unidade padrão + checklist); reset de senha na página `/usuarios`. CRUDs existentes **reaproveitados**, não recriados.
- Permissão `configuracao:atualizar` em uso (SU bypassa; não-SU via UI de grupos).
- Sem regressão: pytest + vitest + e2e verdes.
- Itens fora de escopo **não** implementados.

## 11. Dívida técnica / notas

- Mapear `configuracao` a `sistema_transacao`/grupos é operacional (UI existente); não
  automatizado na migration de propósito.
- `must_change_password` segue não implementado (a senha temporária é exibida 1x, troca
  manual) — dívida já registrada no RUNBOOK.
- `assinatura` no checklist é placeholder "módulo habilitado" até haver configuração de
  assinatura por tenant.
- Logo permanece como URL; upload de arquivo é PR futuro.
