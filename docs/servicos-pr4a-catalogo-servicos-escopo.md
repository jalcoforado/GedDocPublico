# PR 4a — Escopo técnico: Catálogo de Serviços / Carta de Serviços

**Autor:** Jorge + assistente · **Status:** PROPOSTA (aguardando autorização — nada implementado)

> Cria a **base administrativa** da Carta de Serviços: cada prefeitura cadastra
> e gerencia seus serviços públicos digitais. **Não** altera o fluxo de abertura
> de protocolo — isso fica para o **PR 4b** (abertura por serviço). Listagem
> pública somente leitura é opcional aqui (ver decisão D5).

---

## 1. Objetivo

Transformar a base para um portal orientado a serviços, começando pelo **cadastro
e gestão** dos serviços do tenant. O cidadão poderá, no máximo, **ver** uma lista
de serviços ativos; **não** abre protocolo por serviço neste PR.

## 2. Achados no código (o que será reusado, não recriado)

| Necessidade do PR | Já existe no código | Decisão |
|---|---|---|
| Tabela tenant-scoped com RLS + GRANTs + seed | Padrão da migration [`0015_protocolo_especie_documental.py`](../backend/alembic/versions/0015_protocolo_especie_documental.py) (create_table → GRANT → ENABLE/FORCE RLS → 2 policies → seed) | **Reusar o padrão** para `protocolos.servico` |
| CRUD admin tenant-scoped (gate + soft-delete + 409 de slug) | [`routers/protocolo.py`](../backend/app/routers/protocolo.py) (espécies) e [`routers/assuntos.py`](../backend/app/routers/assuntos.py) | **Espelhar a estrutura** |
| Endpoint público resolvido por Host (sem login, RLS via middleware) | [`routers/branding.py`](../backend/app/routers/branding.py) (`GET /branding/me`) | **Reusar o padrão** para `/portal/servicos` |
| Permissão por transação (`codigo` + ações) | [`auth/perms.py`](../backend/app/auth/perms.py) + [`services/permissoes.py`](../backend/app/services/permissoes.py); SU (`nivel.valor==0`) **bypassa** | Nova transação `servico` (ver §4) |
| Seed idempotente de transação na migration | `configuracao` na [`0023`](../backend/alembic/versions/0023_tenant_config_inicial.py) (`WHERE NOT EXISTS`, sem índice único em `codigo`) | **Reusar** para `servico` |
| Validação de FK same-tenant (FK do Postgres **não** filtra por tenant) | `id_unidade_padrao` validado no serviço em [`services/tenant_config.py`](../backend/app/services/tenant_config.py) (PR 3b) | **Mesmo padrão** para unidade/assunto/tipo/espécie padrão |
| JSONB | `from sqlalchemy.dialects.postgresql import JSONB` — usado em `audit_log.payload`, `workflow.dsl`, `job.parametros`, `notificacao.payload` | **Reusar** para `documentos_exigidos` |
| Enums já existentes | `nivel_sigilo`: `ostensivo\|interno\|reservado\|secreto\|ultrassecreto`; `canal_entrada`: `balcao\|portal\|email\|api\|interno` (migration 0015) | **Reusar os mesmos valores** |
| Catálogos referenciados (defaults) | `utils.unidade_trabalho`, `protocolos.tipo_processo`, `protocolos.assunto`, `protocolos.especie_documental` — todos tenant-scoped c/ RLS | Referenciados como **defaults nullable** |
| Frontend: página CRUD interna | `(app)/assuntos`, `(app)/configuracoes`; nav em [`components/Sidebar.tsx`](../frontend/components/Sidebar.tsx) (item com `perm`) | Nova página `(app)/servicos` |
| Frontend: portal do cidadão | `app/cidadao/*` (login/cadastrar/processos/abrir) | Listagem pública opcional em `/cidadao/servicos` (D5) |

**Não existe** nada de `servico`/Carta de Serviços hoje — é base nova.
Última migration = `0023` → **nova = `0024`**.

## 3. Modelo de dados — migration `0024_servico_catalogo` (`protocolos.servico`, tenant-scoped, RLS)

Tabela nova seguindo o padrão da 0015 (RLS + GRANTs + policies select/modify).

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `tenant_id` | integer FK `aprimora_py.tenant.id` NOT NULL | RLS |
| `nome` | varchar(150) NOT NULL | |
| `slug` | varchar(80) NOT NULL | **único por tenant** (`UniqueConstraint(tenant_id, slug)`) |
| `descricao_curta` | varchar(300) | resumo p/ listagem |
| `descricao_detalhada` | text | |
| `publico_alvo` | varchar(255) | |
| `instrucoes` | text | instruções ao cidadão |
| `documentos_exigidos` | JSONB nullable | lista de `{nome, obrigatorio: bool, observacao?}` (D1) |
| `prazo_estimado_dias` | integer nullable | |
| `id_unidade_responsavel` | integer FK `utils.unidade_trabalho.id` nullable | validado same-tenant (§7) |
| `id_tipo_processo_padrao` | integer FK `protocolos.tipo_processo.id` nullable | validado same-tenant |
| `id_assunto_padrao` | integer FK `protocolos.assunto.id` nullable | validado same-tenant |
| `id_especie_documental_padrao` | integer FK `protocolos.especie_documental.id` nullable | validado same-tenant |
| `nivel_sigilo_padrao` | varchar(20) NOT NULL default `'ostensivo'` | valores do enum existente |
| `canal_entrada_permitido` | varchar(20) nullable default `'portal'` | valor único do enum existente (D4) |
| `ativo` | boolean NOT NULL default TRUE | |
| `destaque` | boolean NOT NULL default FALSE | destaque no portal |
| `ordem` | integer NOT NULL default 0 | ordem de exibição |
| `categoria` | varchar(80) nullable | texto simples (categorias complexas fora de escopo) |
| `texto_confirmacao` | text nullable | mensagem pós-solicitação (usada só no 4b) |
| `excluido` | boolean NOT NULL default FALSE | soft-delete (padrão da casa) |
| `criado_em` | timestamp NOT NULL default NOW() | |
| `atualizado_em` | timestamp nullable | |

Índice `ix_servico_tenant_ativo_ordem (tenant_id, ativo, ordem)` para a listagem pública/admin.

**FK + RLS — atenção (igual PR 3b):** a checagem de FK do Postgres **não** respeita
RLS, então um payload poderia apontar um default para registro de **outro** tenant
e a FK passaria. Por isso os 4 defaults (unidade/tipo/assunto/espécie) são
**validados no serviço** contra o tenant atual (`WHERE id=? AND tenant_id=? AND excluido=false`).

## 4. Permissões (avaliado contra o padrão atual)

O sistema **não tem** ações `listar/criar/desativar`. As ações existentes são
**`inserir` / `atualizar` / `excluir`** (e `action=None` = "tem a transação"/ler).
Ver [`auth/perms.py`](../backend/app/auth/perms.py). Portanto **não** se cria
`servico:listar/criar/desativar`; em vez disso:

- **Nova transação `servico`** (`codigo='servico'`), semeada **idempotente** na
  migration 0024 (`INSERT ... WHERE NOT EXISTS`, como `configuracao` na 0023).
- Mapeamento das operações do brief para o modelo real:

  | Operação pedida | Gate efetivo |
  |---|---|
  | `servico:listar` | `require_permission("servico")` (action=None — presença) |
  | `servico:criar` | `require_permission("servico", "inserir")` |
  | `servico:atualizar` | `require_permission("servico", "atualizar")` |
  | `servico:desativar` | `require_permission("servico", "atualizar")` (alterna `ativo`) |

- **Super-usuário bypassa** → admin provisionado opera de imediato.
- **Não-SU** recebem `servico` pela UI **grupos → transações** (já existente).
- Front: `can("servico", "inserir"/"atualizar")` controla botões; SU sempre true.

> Alternativa `servico:gerenciar` (uma transação, sem granularidade) foi
> **descartada**: não combina com o modelo de 3 ações nem com a UI de grupos.

## 5. Endpoints

### 5.1 Admin interno (router `prefix="/servicos"`, autenticado + tenant)
| Método | Rota | Gate | Descrição |
|---|---|---|---|
| GET | `/api/v2/servicos` | `require_permission("servico")` | lista do tenant (inclui inativos via `?incluir_inativos=true`) |
| GET | `/api/v2/servicos/{id}` | `require_permission("servico")` | detalhe |
| POST | `/api/v2/servicos` | `require_permission("servico","inserir")` | cria (409 se slug duplicado no tenant) |
| PUT | `/api/v2/servicos/{id}` | `require_permission("servico","atualizar")` | edita (whitelist; `tenant_id` nunca do payload) |
| POST | `/api/v2/servicos/{id}/ativar` · `/desativar` | `require_permission("servico","atualizar")` | alterna `ativo` |
| POST | `/api/v2/servicos/reordenar` | `require_permission("servico","atualizar")` | (opcional) salva `ordem` em lote |

Tudo tenant-scoped via `tenant_filter` + RLS; carga por id com `WHERE id=? AND tenant_id=?` (404 cross-tenant).

### 5.2 Público — somente leitura (opcional, ver D5; padrão `branding.py`)
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/v2/portal/servicos` | **público** (Host → tenant) | só `ativo=true, excluido=false`, ordem `destaque desc, ordem, nome` |
| GET | `/api/v2/portal/servicos/{slug}` | **público** | detalhe seguro por slug |

Projeção pública **segura** (`ServicoPublicOut`): `nome, slug, descricao_curta,
descricao_detalhada, publico_alvo, instrucoes, prazo_estimado_dias,
unidade_responsavel_nome, documentos_exigidos, categoria, destaque, ordem`.
**Não** expõe: `id`/ids de defaults internos, `nivel_sigilo_padrao`,
`canal_entrada_permitido`, `ativo`, `excluido`, `tenant_id`. Sem botão "solicitar"
funcional (abertura é 4b) — exibir desabilitado com aviso ou ocultar.

## 6. Frontend

- **`(app)/servicos/page.tsx`** *(novo)* — tabela + diálogo de criar/editar
  (Input/Textarea/Select), toggle ativar/desativar, marcar destaque, campo de
  ordem. Selects de unidade/tipo/assunto/espécie populados por `api.*` já
  existentes (do tenant). Gate de edição via `can("servico", …)`. Item no
  [`Sidebar.tsx`](../frontend/components/Sidebar.tsx) com `perm: "servico"`.
- **`lib/api.ts`** — `servicosApi` (list/get/create/update/ativar/desativar) e,
  se D5 = incluir, `portalApi.servicos()` público.
- **(D5) `cidadao/servicos/page.tsx`** *(opcional)* — listagem pública mínima
  (nome, descrição curta, prazo, unidade, documentos). Sem redesenho do portal.

## 7. Segurança multi-tenant

- `servico` é tenant-scoped, com **RLS** (policies select/modify do padrão 0015).
- Admin: toda rota exige autenticação + permissão; carga por id filtra `tenant_id`
  (404 cross-tenant). `tenant_id` **nunca** vem do payload — vem de
  `require_tenant_id` (`request.state.tenant_id`).
- Defaults (unidade/tipo/assunto/espécie) **validados same-tenant** no serviço
  (FK não basta — §3).
- Público: resolve tenant pelo **Host** (middleware), aplica RLS, retorna **só**
  `ativo=true & excluido=false` e a projeção segura. Inativos/excluídos **nunca**
  aparecem. Sem login = sem acesso a dados internos.
- `slug` único por tenant (DB + checagem amigável 409).

## 8. Dados iniciais (bootstrap)

**Recomendação:** **não** alterar `services/provisioning_tenant.py` neste PR
(manter o bootstrap enxuto — alinhado ao que já decidimos em PR 3a/3b). Catálogo
de serviços começa vazio; a prefeitura cadastra pela tela. Seed de serviço padrão
"Protocolo Geral" fica como **decisão D6** (se incluído, deve ser idempotente e
não inflar o bootstrap).

## 9. Testes obrigatórios

**Backend (pytest, padrão `test_admin_tenants.py`/`test_pr3b_config_inicial.py`):**
- criar serviço; editar serviço; ativar/desativar.
- **slug único por tenant** (2º com mesmo slug → 409; mesmo slug em tenant B → OK).
- **tenant A não acessa serviço de B** (GET/PUT/{id} de B sob tenant A → 404).
- **payload não altera `tenant_id`** (campo ignorado; serviço permanece no tenant atual).
- usuário **sem** `servico` (não-SU) → **403** em criar/editar/desativar.
- defaults (`id_unidade_responsavel`/`id_tipo_processo_padrao`/`id_assunto_padrao`/
  `id_especie_documental_padrao`) de **outro tenant** → rejeitado (400).
- **inativo não aparece no público**; público lista **só ativos do tenant atual**.
- público **não** expõe campos internos (`nivel_sigilo_padrao`, ids de default).
- migration 0024 aplica em banco limpo (fluxo `stamp 0020 → upgrade head`);
  transação `servico` criada idempotente; round-trip down/upgrade.

**Frontend (vitest, `fireEvent.change` por causa do focus-trap do Dialog):**
- `/servicos` lista, cria, edita, desativa (mocks da `servicosApi`).
- modo leitura quando `can("servico","atualizar") === false`.
- form não envia `tenant_id`/campos proibidos.
- (D5) página pública renderiza só serviços ativos do mock.

## 10. Fora de escopo (PR 4b ou futuro)

abertura real de protocolo por serviço · formulário dinâmico complexo · workflow
por serviço · SLA operacional completo · cobrança · redesenho inteiro do portal ·
upload de documentos exigidos · complementação documental · avaliação do serviço ·
integração gov.br · busca avançada · categorias complexas · marketplace ·
importação em massa.

## 11. Decisões abertas (para o Jorge confirmar antes de implementar)

- **D1 — `documentos_exigidos`:** **JSONB** simples (`[{nome, obrigatorio, observacao?}]`).
  *Recomendado* (reduz escopo; suficiente para exibir no 4b). Tradeoff: sem
  integridade referencial nem query "serviços que exigem doc X" — não necessário
  em 4a/4b. Alternativa (tabela própria `servico_documento`) só se você já prevê
  validação/regra por documento no 4b.
- **D2 — soft-delete vs só ativar/desativar:** manter `excluido` (padrão da casa)
  **e** expor só `ativar/desativar` na UI (sem hard delete). OK?
- **D3 — `nivel_sigilo_padrao`:** default `'ostensivo'` (serviço público) — confirma?
- **D4 — `canal_entrada_permitido`:** **valor único** (varchar, default `'portal'`)
  no 4a; lista de canais fica para 4b. OK? (alternativa: JSONB de canais já agora.)
- **D5 — portal público no 4a:** *Recomendado incluir* só o **endpoint público
  `/portal/servicos` + página mínima** (pequeno, padrão `branding`, seguro). Ou
  **adiar todo o público para 4b** se preferir 4a 100% administrativo.
- **D6 — serviço padrão no bootstrap:** *Recomendado **não** mexer* no
  provisioning. Ou seed idempotente "Protocolo Geral" se você quiser tenant já
  com 1 serviço.

## 12. Critérios de aceite

- Migration 0024 cria `protocolos.servico` (RLS + policies + GRANTs) e semeia a
  transação `servico` idempotente; aplica em banco limpo; round-trip OK.
- CRUD admin tenant-scoped, gated por `servico` (SU bypassa; não-SU via grupos).
- `slug` único por tenant; cross-tenant bloqueado (404); `tenant_id` nunca do payload.
- Defaults validados same-tenant.
- (Se D5) público lista só ativos do tenant do Host, sem campos internos.
- Testes backend + frontend passando; sem regressão (pytest/vitest verdes).
- Itens fora de escopo **não** implementados.
- Relatório final: arquivos, testes, riscos, próximos passos (gancho p/ PR 4b).
