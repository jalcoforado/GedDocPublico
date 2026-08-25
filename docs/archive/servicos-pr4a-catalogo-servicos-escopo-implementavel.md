# PR 4a — Escopo Implementável: Catálogo de Serviços / Carta de Serviços

**Autor:** Jorge + assistente · **Status:** ESCOPO FECHADO (aguardando autorização para implementar)

> Consolida a [proposta](servicos-pr4a-catalogo-servicos-escopo.md) com as **6
> decisões do Jorge (D1–D6)** fechadas. Cria a **base administrativa** da Carta
> de Serviços + um **portal público mínimo** (somente leitura). **Não** implementa
> abertura de protocolo por serviço (PR 4b). Nada será alterado em código até
> autorização explícita.

---

## 1. Objetivo

Cada prefeitura cadastra e gerencia seus serviços públicos pela interface interna;
o cidadão **vê** (somente leitura) a lista de serviços ativos no portal. O fluxo
de abertura por serviço **não** muda neste PR.

**Decisões fechadas:** D1 documentos = JSONB simples · D2 soft-delete + UI
ativar/desativar · D3 `nivel_sigilo_padrao` default `ostensivo` · D4
`canal_entrada_permitido` valor único default `portal` · D5 portal público mínimo
**incluído** · D6 **não** mexer no `provisioning_tenant`.

## 2. Migration `0024_servico_catalogo`

Cria `protocolos.servico` (tenant-scoped, **RLS**) seguindo o padrão da
[`0015`](../backend/alembic/versions/0015_protocolo_especie_documental.py):
`create_table` → GRANTs (`aprimora_app` + seq) → `ENABLE/FORCE ROW LEVEL SECURITY`
→ policies `tenant_isolation_select` e `tenant_isolation_modify`.

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | integer PK | |
| `tenant_id` | integer FK `aprimora_py.tenant.id` NOT NULL | RLS |
| `nome` | varchar(150) NOT NULL | |
| `slug` | varchar(80) NOT NULL | `UniqueConstraint(tenant_id, slug)` |
| `descricao_curta` | varchar(300) nullable | |
| `descricao_detalhada` | text nullable | |
| `publico_alvo` | varchar(255) nullable | |
| `instrucoes_cidadao` | text nullable | |
| `documentos_exigidos` | JSONB nullable | lista de objetos (D1) |
| `prazo_estimado_dias` | integer nullable | |
| `id_unidade_responsavel` | integer FK `utils.unidade_trabalho.id` nullable | validado same-tenant |
| `id_tipo_processo_padrao` | integer FK `protocolos.tipo_processo.id` nullable | validado same-tenant |
| `id_assunto_padrao` | integer FK `protocolos.assunto.id` nullable | validado same-tenant |
| `id_especie_documental_padrao` | integer FK `protocolos.especie_documental.id` nullable | validado same-tenant |
| `nivel_sigilo_padrao` | varchar(20) NOT NULL default `'ostensivo'` | enum existente (sem enum novo) |
| `canal_entrada_permitido` | varchar(20) NOT NULL default `'portal'` | valor único (D4) |
| `ativo` | boolean NOT NULL default TRUE | |
| `excluido` | boolean NOT NULL default FALSE | soft-delete (D2) |
| `destaque` | boolean NOT NULL default FALSE | |
| `ordem_exibicao` | integer NOT NULL default 0 | |
| `categoria` | varchar(80) nullable | texto simples |
| `texto_confirmacao` | text nullable | usado só no 4b |
| `criado_em` | timestamp NOT NULL default NOW() | |
| `atualizado_em` | timestamp nullable | |

> Sem coluna de "usuário criador": catálogos existentes (`especie_documental`,
> `assunto`) não rastreiam isso — mantemos a consistência. Auditoria de quem
> alterou fica fora de escopo.

Índice `ix_servico_tenant_ativo_ordem (tenant_id, ativo, ordem_exibicao)`.

**Seed de permissão (idempotente, padrão da `0023`):**
```sql
INSERT INTO utils.transacao (transacao, codigo)
SELECT 'Catálogo de Serviços', 'servico'
WHERE NOT EXISTS (SELECT 1 FROM utils.transacao WHERE codigo = 'servico');
```
`downgrade`: remove `grupo_transacao`/`sistema_transacao` da transação, depois a
transação e a tabela (FK-safe), e dropa policies/índice.

**CI:** `e2e-assinatura.yml` faz `stamp 0020 → upgrade head`, então a 0024 roda
em banco limpo automaticamente. Validar round-trip antes do commit.

## 3. Modelos e schemas

- **Modelo** `backend/app/models/servico.py` → `Servico` (registrado em
  `models/__init__.py`); `documentos_exigidos: Mapped[list | None] = mapped_column(JSONB)`.
- **Schemas** `backend/app/schemas/servico.py`:
  - `ServicoDocumento` — `nome: str` (1–150), `obrigatorio: bool`,
    `descricao: str | None`. Valida D1 (lista de objetos) → JSON inválido = **422**.
  - `ServicoCreate` — `nome, slug` (obrigatórios; slug `^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$`),
    demais opcionais; `nivel_sigilo_padrao` ∈ enum (default `ostensivo`);
    `documentos_exigidos: list[ServicoDocumento] | None`.
  - `ServicoUpdate` — todos opcionais (**whitelist**; `tenant_id`/`id` nunca aceitos).
  - `ServicoOut` — visão admin completa.
  - `ServicoPublicOut` — projeção **segura** (§5.2).

## 4. Serviço de domínio — `backend/app/services/servico.py`

- `criar_servico(db, *, tenant_id, payload) -> Servico`
- `atualizar_servico(db, *, tenant_id, servico_id, payload) -> Servico`
- `set_ativo(db, *, tenant_id, servico_id, ativo: bool) -> Servico` (alterna `ativo`)
- `listar_servicos(db, *, tenant_id, incluir_inativos: bool)`
- `listar_publico(db, *, tenant_id)` — só `ativo=true & excluido=false`, join no
  nome da unidade responsável, ordem `destaque DESC, ordem_exibicao, nome`.
- `_validar_slug_unico(db, tenant_id, slug, excluir_id=None)` → 409 se duplicado.
- `_validar_defaults(db, tenant_id, payload)` — para cada default **não nulo**,
  exige `WHERE id=? AND tenant_id=? AND excluido=false` (FK do PG **não** filtra
  por tenant — mesmo padrão do `id_unidade_padrao` do PR 3b); senão **400**.

Regras: carga por id sempre `WHERE id=? AND tenant_id=?` (404 cross-tenant);
`tenant_id` vem de `require_tenant_id`, **nunca** do payload; soft-delete via `excluido`.

## 5. Endpoints

### 5.1 Admin interno — `routers/servico.py` (`router`, prefix `/servicos`, registrado em `main.py`)
| Método | Rota | Gate | Descrição |
|---|---|---|---|
| GET | `/api/v2/servicos` | `require_permission("servico")` | lista do tenant (`?incluir_inativos=true`) |
| GET | `/api/v2/servicos/{id}` | `require_permission("servico")` | detalhe (404 cross-tenant) |
| POST | `/api/v2/servicos` | `require_permission("servico","inserir")` | cria (409 slug dup) |
| PUT | `/api/v2/servicos/{id}` | `require_permission("servico","atualizar")` | edita (whitelist) |
| POST | `/api/v2/servicos/{id}/ativar` | `require_permission("servico","atualizar")` | `ativo=true` |
| POST | `/api/v2/servicos/{id}/desativar` | `require_permission("servico","atualizar")` | `ativo=false` |

Permissão (padrão do sistema — sem ações novas): listar=presença · criar=`inserir`
· editar/ativar/desativar=`atualizar`. **SU bypassa**; não-SU recebem `servico`
via UI **grupos → transações**.

### 5.2 Público — `routers/servico.py` (`portal_router`, prefix `/portal`, sem login)
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/v2/portal/servicos` | **público** (Host→tenant, padrão `branding.py`) | só ativos/não excluídos |
| GET | `/api/v2/portal/servicos/{slug}` | **público** | detalhe seguro por slug |

`ServicoPublicOut` expõe **apenas**: `nome, slug, descricao_curta,
descricao_detalhada, publico_alvo, instrucoes_cidadao, prazo_estimado_dias,
unidade_responsavel` (nome), `documentos_exigidos, categoria, destaque,
ordem_exibicao` + `solicitar_habilitado: bool` (constante **false** no 4a).
**Nunca** expõe `id`/ids de defaults, `nivel_sigilo_padrao`,
`canal_entrada_permitido`, `ativo`, `excluido`, `tenant_id`.

## 6. Frontend

- **`lib/api.ts`**: `servicosApi` (`list/get/create/update/ativar/desativar`) +
  `portalApi.servicos()/servico(slug)` (público — `request` sem cookie de cidadão).
  Tipos `Servico`, `ServicoInput`, `ServicoDocumento`, `ServicoPublico`.
- **`(app)/servicos/page.tsx`** *(novo)* — tabela (nome, categoria, ativo,
  destaque, ordem) + diálogo criar/editar: Input/Textarea/Select; selects de
  unidade/tipo/assunto/espécie via `api.*` já existentes; **editor simples** de
  documentos exigidos (linhas `{nome, obrigatorio, descricao}`, add/remove — sem
  exagero); toggle ativar/desativar; destaque; ordem. Gate `can("servico", …)`.
  Item no [`Sidebar.tsx`](../frontend/components/Sidebar.tsx) com `perm: "servico"`.
- **`cidadao/servicos/page.tsx`** *(novo, público)* — cards de serviços ativos:
  nome, descrição curta, prazo, unidade, documentos, badge de destaque/categoria.
  Botão **"Solicitação disponível em breve"** (desabilitado) enquanto
  `solicitar_habilitado=false` (D5 — abertura real é 4b).

## 7. Segurança multi-tenant

- `servico` tenant-scoped com **RLS** (policies do padrão 0015).
- Admin: autenticação + permissão; carga por id filtra `tenant_id` (404
  cross-tenant); `tenant_id` **nunca** do payload (vem de `request.state.tenant_id`).
- Defaults validados **same-tenant** no serviço (FK não basta).
- Público: tenant pelo **Host**, RLS aplicada, só `ativo & não excluído`, projeção
  segura. Inativo/excluído **nunca** aparece. Sem filtro cross-tenant possível.
- `slug` único por tenant (constraint + 409 amigável).

## 8. Testes obrigatórios

**Backend (pytest — padrão `test_pr3b_config_inicial.py`/`test_admin_tenants.py`):**
- criar / editar / ativar / desativar serviço.
- `slug` único por tenant → 409; **mesmo slug em tenant B → OK**.
- usuário **sem** `servico` (não-SU) → **403** (criar/editar/desativar).
- tenant A não acessa serviço de B (GET/PUT/{id} → 404).
- payload **não** altera `tenant_id` (permanece no tenant atual).
- defaults (unidade/tipo/assunto/espécie) de **outro tenant** → **400**.
- `documentos_exigidos` inválido (não-lista / objeto sem `nome`) → **422**.
- público lista **só ativos do tenant atual**; **inativo/excluído não aparece**;
  projeção pública **não** traz campos internos.
- migration 0024 aplica em banco limpo (`stamp 0020 → upgrade head`); transação
  `servico` idempotente; round-trip down/upgrade.

**Frontend (vitest; `fireEvent.change` pelo focus-trap do Dialog):**
- `/servicos` lista, cria, edita, ativa/desativa (mocks de `servicosApi`).
- modo leitura quando `can("servico","atualizar") === false`.
- form não envia `tenant_id`/campos proibidos.
- portal público renderiza serviços ativos; **serviço inativo não aparece**.

## 9. Itens fora de escopo

abertura real de protocolo por serviço · formulário dinâmico complexo · upload de
documentos · pendência/complementação documental · workflow por serviço · SLA
operacional completo · **serviço padrão no bootstrap** · múltiplos canais de
entrada · categorias complexas · busca avançada · avaliação do serviço ·
integração gov.br · importação em massa · marketplace · redesign completo do
portal cidadão.

## 10. Critérios de aceite

- Migration 0024 cria `protocolos.servico` (RLS + policies + GRANTs) e semeia a
  transação `servico` idempotente; aplica em banco limpo; round-trip OK.
- CRUD admin tenant-scoped, gated por `servico` (SU bypassa; não-SU via grupos);
  `slug` único por tenant; cross-tenant bloqueado (404); `tenant_id` nunca do payload.
- Defaults validados same-tenant; `documentos_exigidos` validado como lista de objetos.
- Portal público lista só ativos do tenant do Host, sem campos internos; botão de
  solicitar desabilitado (abertura é 4b).
- `provisioning_tenant` **inalterado** (D6).
- Testes backend + frontend passando; sem regressão (pytest/vitest verdes).
- Itens fora de escopo **não** implementados.
- Relatório final: arquivos alterados, testes executados, riscos remanescentes e
  próximos passos (gancho para o PR 4b — abertura por serviço).

## 11. Dívida técnica / notas

- Mapear `servico` a `sistema_transacao`/grupos é operacional (UI existente); não
  automatizado na migration (id de sistema é ambiente-dependente) — mesma nota
  de `configuracao` (PR 3b).
- `documentos_exigidos` em JSONB: sem integridade referencial / sem upload (D1) —
  evolução (tabela própria, upload, pendência) fica para PR futuro.
- `canal_entrada_permitido` único (D4); múltiplos canais = PR futuro.
- Serviço padrão no bootstrap reavaliado no PR 4b (D6).
