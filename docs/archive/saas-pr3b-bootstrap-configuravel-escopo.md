# PR 3b — Bootstrap configurável e configuração inicial do tenant

> Documento de **proposta técnica / escopo**. Nenhuma implementação foi feita.
> Próximo passo do processo: o Jorge fecha as decisões em aberto (§11) e autoriza
> o escopo implementável; só então se codifica.

## 1. Contexto

O PR 3a entregou o Admin SaaS de **plataforma**: painel `/admin/tenants`, criação de
tenant via serviço único de provisionamento (`services/provisioning_tenant`), admin
inicial, limites armazenados, módulos derivados do plano e provisionamento seguro sob
RLS. Esse painel é operado pela **allowlist** `PLATFORM_ADMIN_EMAILS` — é o operador
da plataforma, não a prefeitura.

O PR 3b muda de audiência: o objetivo é o **admin municipal** (usuário do próprio
tenant, com permissão) revisar e ajustar a configuração inicial da prefeitura **pela
interface**, reduzindo a dependência de scripts/CLI/alteração manual no banco.

## 2. Achado central — a maior parte do CRUD já existe

A varredura do código (modelos, routers, frontend) mostra que **boa parte do brief já
está implementada** em PRs anteriores. Reconstruir seria churn. O PR 3b deve
**consolidar/expor** o que existe e construir **apenas** o que falta.

Legenda: ✅ já existe · 🟡 existe parcial / ajuste · 🆕 novo · ⏸️ fasear · ⛔ fora.

| Item do brief | Estado atual | Ação no PR 3b |
|---|---|---|
| **Unidades** (CRUD) | ✅ `GET/POST/PUT/DELETE /api/v2/unidades-trabalho` + `api.unidades.*` + página `/unidades-trabalho`; hierarquia já existe via `id_unidade_pai` (soft-FK) | Consolidar/expor. 🆕 só "unidade padrão de protocolo" (não existe) |
| **Usuários** (listar/criar/ativar/desativar/vincular grupo/unidade) | ✅ CRUD completo + `setGrupos`/`setUnidades` + página `/usuarios` | Consolidar. 🆕 só "resetar senha temporária" (hoje admin **digita** a senha) |
| **Grupos/perfis** (CRUD + permissões) | ✅ `GET/POST/PUT /api/v2/grupos` + `/grupos/{id}/transacoes` + `setTransacoes` + página `/grupos` | Apenas consolidar — **sem redesenho de RBAC** |
| **Catálogos** (assuntos, tipos de processo, espécies documentais, canais, tipos de manifestante, tipos de anexo) | ✅ CRUD completo de todos, sob `require_permission("catalogo", …)` / `("manifestante", …)`, com páginas | Apenas consolidar/expor |
| **Ações** (catálogo) | 🟡 sem CRUD **e** tabela **global** (`protocolos.acao`, sem `tenant_id`) | ⛔ não é config de tenant — fora |
| **Config institucional do tenant** (nome, sigla, e-mail, telefone, endereço, site, horário, boas-vindas, cor, logo) | 🟡 só `nome/cnpj/cor_primaria/logo_url` no modelo; `GET /tenants/me` é **read-only** (exceto NUP) | 🆕 **principal**: migration + PUT self-service + UI |
| **Checklist de onboarding** | 🆕 não existe | 🆕 endpoint calculado + card |
| **Segurança multi-tenant** | ✅ RLS nas 26 tabelas tenant + middleware + `require_tenant_id`/`require_permission`/`can()` | Herdar + testes cross-tenant |

**Conclusão:** o conteúdo *real* e novo do PR 3b é **(a) dados institucionais
editáveis** (exige migration), **(b) reset de senha temporária**, **(c) checklist de
onboarding**, e **(d) consolidação** do que já existe numa área coerente de
"configuração inicial". É um PR menor e mais seguro do que o enunciado sugere.

## 3. Audiência e modelo de permissão (decisão de arquitetura)

- **Admin municipal ≠ admin de plataforma.** O admin de plataforma é a allowlist
  (`PLATFORM_ADMIN_EMAILS`, `require_platform_admin`) — opera o painel cross-tenant
  `/admin/tenants`. O PR 3b **não** usa essa allowlist.
- **Admin municipal = usuário do tenant com permissão**, via o RBAC já existente:
  super-usuário (`nivel.valor == 0`, bypass total em `auth/perms.py`) **ou** usuário
  com a *transação* adequada. O front decide visibilidade com `can(codigo, acao)`
  (`frontend/lib/auth.tsx`); o back protege com `require_permission(codigo, acao)`.
- A página `/configuracoes` **já** adota esse padrão (`can("usuario","atualizar")`).
  O PR 3b mantém o mesmo padrão por padrão (ver decisão §11.4 sobre criar ou não um
  código de transação dedicado `configuracao`).

## 4. Item 1 — Configuração institucional do tenant (núcleo do PR)

### 4.1 Modelo / migration (0023)

Hoje `aprimora_py.tenant` tem: `nome, cnpj, id_cidade, cor_primaria, logo_url,
codigo_orgao_nup, usar_nup_federal, limite_*`. **Faltam** os campos institucionais.
Proposta: migration **0023** adicionando colunas **nullable** (mudança pequena e
aditiva, sem reescrever modelo):

- `sigla` (String, curto)
- `email_institucional` (String)
- `telefone` (String)
- `site_url` (String)
- `horario_atendimento` (String/Text)
- `texto_boas_vindas` (Text) — portal do cidadão
- `endereco` — **decisão §11.1**: texto simples agora **(recomendado)** vs FK
  estruturada para `utils.endereco`/`cidade` (mudança maior → fasear)

`cnpj` e `cor_primaria` já existem. **`tenant` não tem RLS** (confirmado em migrations
0006/0022) — ver §8 para o cuidado de escopo no update.

### 4.2 Backend

- 🆕 `PUT /api/v2/tenants/me` (self-service do tenant) atualizando **apenas** os campos
  institucionais acima. Gate: `require_permission(...)` (§11.4). **Escopo obrigatório
  por `request.state.tenant_id`** — nunca aceitar `id` no corpo (a tabela não tem RLS).
- 🆕/🟡 estender o schema de `GET /tenants/me` (`TenantMeResponse`) para devolver os
  novos campos. NUP permanece no endpoint dedicado `PUT /tenants/me/nup-config` (não
  mexer).
- ⛔ **Não** expor slug, plano, limites, `ativo` — esses são da plataforma (PR 3a).

### 4.3 Frontend

- Estender a página **existente** `/configuracoes` (`frontend/app/(app)/configuracoes/page.tsx`)
  com uma seção "Identidade institucional" (form de campos do §4.1). **Não criar página
  nova.** Reaproveitar `PageHeader`, `Input`, `Label`, `Textarea`, `useToast`, padrão
  `can("usuario","atualizar")` → modo leitura quando sem permissão.
- A seção "Tenant atual" (hoje read-only "alteração via CLI") passa a ser editável no
  que for institucional; ID/slug/plano continuam read-only.

### 4.4 Logo / brasão — **decisão §11.2**

Não existe infraestrutura de upload de **branding** (o único upload é de anexos de
processo, `routers/anexos.py`, escopado a processo). O brief condiciona o upload a "já
haver infra segura". Recomendação: **nesta fase, editar `logo_url` como string (URL)**;
upload de arquivo de branding fica para PR posterior (ou item §11.2 se o Jorge quiser
construir um endpoint mínimo reusando o padrão de storage por tenant).

## 5. Item 2 — Unidades

CRUD completo já existe. PR 3b **consolida/expõe** (link/seção a partir da área de
configuração). Único item novo possível:

- 🆕 **"Unidade padrão de protocolo"** — não existe. **Decisão §11.3**: modelar como
  `tenant.id_unidade_padrao` (single source, recomendado) **vs** flag booleana por
  unidade. Alimenta o checklist (§7).
- ⛔ Organograma avançado (já há `id_unidade_pai` suficiente para hierarquia simples).

## 6. Item 3 — Usuários · Item 4 — Grupos · Item 5 — Catálogos

- **Usuários:** CRUD + vínculos já existem. 🆕 único novo: **reset de senha temporária**
  — `POST /api/v2/usuarios/{id}/resetar-senha` que **gera** senha temporária, retorna
  **uma vez**, grava **só o hash** (bcrypt; `senha` MD5 = `""`). Reusar a geração de
  senha do `provisioning_tenant`. Hoje o reset é o admin **digitar** a senha no `PUT`
  (`usuarios.py:172`) — não há senha temporária gerada. **Decisão §11.5.**
  - ⛔ convite por e-mail; ⛔ `must_change_password` (segue como dívida técnica).
- **Grupos/perfis:** CRUD + mapeamento de transações já existe. **Apenas consolidar,
  sem redesenho.** Nota menor: o CRUD de grupos é gated por `require_permission("usuario","atualizar")`
  (não um código `grupo`); manter como está salvo decisão explícita.
- **Catálogos:** todos já têm CRUD (`catalogo`/`manifestante`). PR 3b **só expõe** numa
  navegação coerente de configuração. **Ações** ficam ⛔ (tabela global, sem tenant).

## 7. Item 6 — Checklist de onboarding (novo)

- 🆕 `GET /api/v2/tenants/me/onboarding` → objeto de booleanos **calculado** (contagens
  tenant-scoped, read-only). Itens propostos (decisão §11.6 para fechar a lista):
  - `dados_institucionais` — campos essenciais do §4 preenchidos
  - `unidade_padrao` — definida (depende §11.3)
  - `usuarios` — ≥ 1 usuário além do admin inicial
  - `grupos` — ≥ 1 grupo configurado
  - `assuntos` — ≥ 1 assunto
  - `tipos_processo` — ≥ 1 tipo
  - `assinatura` — assinatura ativa/utilizável (ver `services/assinaturas`)
  - `portal_cidadao` — `texto_boas_vindas` preenchido (proxy simples de "pronto")
- 🆕 UI: card de progresso na página de configuração (lista de pendências com
  link/atalho para cada área). Sem sofisticação — lista calculada.

## 8. Item 7 — Segurança / multi-tenant

- **Herdado:** RLS nas 26 tabelas tenant (migration 0006), middleware resolve tenant por
  subdomínio, `require_tenant_id` em todas as rotas, `require_permission`/`can()`.
- **Cuidado específico (tenant sem RLS):** o `PUT /tenants/me` atualiza a linha de
  `aprimora_py.tenant`, que **não** tem RLS. O update **deve** filtrar por
  `request.state.tenant_id` e ignorar qualquer `id` do corpo — caso contrário haveria
  risco de edição cross-tenant. Esse é o ponto de segurança mais sensível do PR.
- **Separação de audiência:** garantir que `require_platform_admin` (plataforma) e o
  RBAC do tenant não se confundam; um super-usuário de prefeitura **não** vira admin de
  plataforma e vice-versa.
- O reset de senha temporária retorna a senha **uma vez** e persiste só hash.

## 9. Item 8 — Fora de escopo

billing · cobrança · enforcement de limites · domínio customizado · DNS automático ·
`tenant_modulo` · convite por e-mail · `must_change_password` · **upload de arquivo de
logo/brasão** (sem infra segura — só URL nesta fase) · organograma avançado · workflow
builder · portal por serviços completo · dashboards executivos · GED/versionamento ·
importação em massa · gov.br/ICP-Brasil · **CRUD de "ações"** (catálogo global) ·
**endereço estruturado** (FK; só texto simples nesta fase).

## 10. Item 9 — Testes obrigatórios

**Backend (pytest):**

- admin municipal acessa só o próprio tenant; cross-tenant falha (404/403).
- usuário sem permissão **não** edita configuração (`PUT /tenants/me` → 403).
- `PUT /tenants/me` ignora `id`/`slug`/`plano` do corpo (não escala privilégio).
- reset de senha gera temporária, retorna 1x, **não** persiste em claro (só hash bcrypt;
  `senha` MD5 = `""`); login com a temporária funciona.
- "unidade padrão" respeita o tenant (se §11.3 aprovar).
- checklist reflete estado real (sem dados → tudo `false`; após criar → `true`).
- (CRUD de unidades/usuários/catálogos já é coberto por testes existentes —
  acrescentar apenas o que for novo).

**Frontend (vitest, `fireEvent.change` por causa do focus-trap do Dialog):**

- `/configuracoes` renderiza a seção institucional e salva (mock de `PUT /tenants/me`).
- modo leitura quando `can("usuario","atualizar") === false`.
- reset de senha exibe a senha temporária **uma vez**.
- card de checklist exibe pendências calculadas.

**Infra:** migration 0023 validada em banco limpo (fluxo CI `stamp 0020 → upgrade head`).

## 11. Decisões a fechar (para o escopo implementável)

1. **Endereço:** texto simples agora *(recomendado)* vs FK estruturada (fasear)?
2. **Logo/brasão:** só `logo_url` (URL) nesta fase *(recomendado)* vs construir endpoint
   mínimo de upload de branding?
3. **Unidade padrão de protocolo:** `tenant.id_unidade_padrao` *(recomendado)* vs flag
   por unidade?
4. **Permissão de edição da config:** reusar `can/require_permission("usuario","atualizar")`
   *(recomendado, igual à página atual)* vs criar transação dedicada `configuracao`?
5. **Reset de senha:** confirmar `POST /usuarios/{id}/resetar-senha` com senha temporária
   gerada e exibida 1x (sem `must_change_password`).
6. **Checklist:** confirmar a lista de itens do §7 e suas regras de cálculo.
7. **Campos institucionais (§4.1):** confirmar a lista exata da migration 0023.

## 12. Riscos / dívida técnica

- Tenant sem RLS → o `PUT /tenants/me` depende de filtro explícito por tenant (mitigado
  por teste dedicado).
- `must_change_password` continua não implementado (dívida já registrada no RUNBOOK):
  a senha temporária do reset é exibida 1x, troca é manual.
- `endereco`/logo como texto/URL é solução de transição — estruturação fica para PR
  futuro.
- Itens de plataforma (limites, módulos, status) seguem fora — consistente com a dívida
  técnica do PR 3a.
