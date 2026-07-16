# Pagamentos R2 — Débitos + autorização + pagamento (workflow 3 níveis) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Completar o módulo Pagamentos: criar **débito com parcelas**, fluxo **solicitar → aprovar → autorizar → pagar** (com segregação de funções, alçada e bloqueio por saldo), **pagar parcela deduz do saldo** (movimentação PAGAMENTO), **Ordem de Pagamento em PDF**, e home **"O que precisa de mim"** por papel.

**Architecture:** Núcleo do R1 intacto — saldo continua **derivado** de `movimentacao_conta`; o pagamento de parcela apenas **cria uma SAIDA origem=PAGAMENTO** (atômico com a mudança de status). Workflow no nível do **débito**, transições **somente via serviço**, cada uma gravando `debito_historico` (append-only, com usuário e IP). Autorização em lote gera `ordem_pagamento` (N:N com débitos) e o PDF reusa `html_to_pdf_bytes` (WeasyPrint, minutas PR-C).

**Tech Stack:** FastAPI + SQLAlchemy async, Alembic, Postgres (RLS), Pydantic v2, WeasyPrint, Next.js + Tailwind + react-query, pytest, Docker.

## Global Constraints

- Python 3.12; SQLAlchemy async; Pydantic v2 (`ConfigDict(from_attributes=True)`).
- Multi-tenant: `tenant_id` FK `aprimora_py.tenant.id`; RLS `ENABLE`+`FORCE` com policies `tenant_isolation_select`/`_modify` (`current_setting('app.tenant_id')`); GRANTs à `aprimora_app` (tabela + sequence). `tenant_id` sempre do caller.
- Soft-delete `excluido` (exceto tabelas append-only: `debito_historico`, `ordem_pagamento*` não têm `excluido`). Datas via `datetime.utcnow()`.
- Testes SERVICE-LEVEL (padrão `backend/tests/test_pagamentos_cadastros.py`: `provisionar_tenant` + `admin_engine` + `async_sessionmaker` + chamadas diretas ao serviço, assert `HTTPException.status_code`). Rodar: `docker exec aprimora-py-backend python -m pytest tests/<arquivo> -q` (path relativo a `/app` dentro do container). tsc: `docker exec aprimora-py-frontend ./node_modules/.bin/tsc --noEmit`.
- **Saldo é derivado**, nunca contador: pagar parcela = criar `movimentacao_conta` SAIDA `PAGAMENTO`; estornar = ENTRADA `ESTORNO`. Nada de UPDATE em saldo.
- **Transições de status só no serviço**, sempre gravando `debito_historico` na MESMA transação (commit único).
- Migration: revision `0048`, `down_revision = "0047"` (confirmar `alembic heads` antes).
- Endpoints sob `/api/v2/pagamentos/...`. RBAC: `pagamento_solicitar`, `pagamento_aprovar`, `pagamento_autorizar`, `pagamento_pagar` (semeadas na 0048); `pagamento_cadastro` continua para cadastros/caixa. Super-usuário bypassa (comportamento do `require_permission`).
- Status do débito: `RASCUNHO → AGUARDANDO_APROVACAO → APROVADO → AUTORIZADO → PAGO_PARCIAL → PAGO`, terminais `REJEITADO`/`CANCELADO`. **Devolver volta a RASCUNHO** (a devolução fica registrada no histórico com ação `DEVOLVIDO` — não existe status de repouso "DEVOLVIDO").
- Invariante: `Σ(parcelas.valor) == debito.valor_total` — validada no serviço (criar/atualizar/enviar).
- Segregação de funções: aprovador ≠ solicitante; autorizador ∉ {solicitante, aprovadores do histórico}.
- Alçada: procurar `alcada(usuario, natureza)`; fallback `alcada(usuario, id_natureza IS NULL)` (limite geral); **sem alçada cadastrada → 403** (num sistema de pagamento, sem alçada = não autoriza).
- Comprometido(conta) = Σ `parcela.valor` com `status='A_PAGAR'` (não excluídas) de débitos `AUTORIZADO`/`PAGO_PARCIAL` da conta. Disponível = saldo_atual − comprometido.

## File Structure

- `backend/alembic/versions/0048_pagamentos_debitos.py` — **novo**: `debito`, `parcela`, `debito_historico`, `ordem_pagamento`, `ordem_pagamento_debito`; FKs `movimentacao_conta.id_debito/id_parcela`; seed das 4 transações RBAC.
- `backend/app/models/pagamentos.py` — modificar: + `Debito`, `Parcela`, `DebitoHistorico`, `OrdemPagamento`, `OrdemPagamentoDebito`.
- `backend/app/models/__init__.py` — modificar: exports.
- `backend/app/schemas/pagamentos.py` — modificar: schemas de débito/parcela/histórico/OP/fila; `SaldoConta`/`ContaSaldoPainel` ganham `comprometido`+`disponivel`.
- `backend/app/services/pagamentos_debitos.py` — **novo**: CRUD rascunho + transições (enviar/aprovar/devolver/rejeitar/cancelar).
- `backend/app/services/pagamentos_autorizacao.py` — **novo**: autorizar em lote (saldo/alçada/segregação + OP), pagar/estornar parcela, PDF da OP, minha-fila.
- `backend/app/services/pagamentos_caixa.py` — modificar: `comprometido_conta`, `saldo_conta`/`painel_caixa` com comprometido/disponível.
- `backend/app/auth/perms.py` — modificar: + `require_any_permission(*codigos)`.
- `backend/app/routers/pagamentos_debitos.py` — **novo**: débitos + ações + autorização + parcelas + OPs + minha-fila.
- `backend/app/main.py` — modificar: registrar `pagamentos_debitos.debitos_router` e `.operacoes_router`.
- `backend/tests/test_pagamentos_debitos.py` — **novo** (CRUD + workflow).
- `backend/tests/test_pagamentos_autorizacao.py` — **novo** (saldo/alçada/segregação/pagar/estornar).
- `frontend/lib/api.ts` — modificar: tipos + `pagamentos.debitos/ordens/fila`.
- `frontend/app/(app)/pagamentos/contas-a-pagar/page.tsx` — **novo**: lista por status + criar débito com parcelas.
- `frontend/app/(app)/pagamentos/contas-a-pagar/[id]/page.tsx` — **novo**: detalhe (parcelas, trilha, ações por papel).
- `frontend/app/(app)/pagamentos/page.tsx` — **novo**: home "O que precisa de mim".
- `frontend/app/(app)/pagamentos/caixa/page.tsx` — modificar: colunas Comprometido/Disponível.
- `frontend/components/Sidebar.tsx` — modificar: suporte `anyOf` no gating + itens Início/Contas a pagar.

---

### Task 1: Migration 0048 — débito, parcela, histórico, OP + RBAC

**Files:**
- Create: `backend/alembic/versions/0048_pagamentos_debitos.py`

**Interfaces:**
- Produces: tabelas `pagamentos.debito`, `pagamentos.parcela`, `pagamentos.debito_historico`, `pagamentos.ordem_pagamento`, `pagamentos.ordem_pagamento_debito`; FKs `movimentacao_conta.id_debito→debito.id` e `.id_parcela→parcela.id`; transações RBAC `pagamento_solicitar|aprovar|autorizar|pagar` em `utils.transacao`.

- [ ] **Step 1: Confirmar head** — `docker exec aprimora-py-backend alembic heads` → deve ser `0047`. Se não for, PARAR e reportar.

- [ ] **Step 2: Escrever a migration**

```python
"""Pagamentos R2 — débito, parcela, histórico, ordem de pagamento + RBAC.

Revision ID: 0048
Revises: 0047
Create Date: 2026-07-14
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: str | Sequence[str] | None = "0047"
branch_labels = None
depends_on = None
S = "pagamentos"

TRANSACOES = [
    ("Solicitar Pagamento", "pagamento_solicitar"),
    ("Aprovar Pagamento", "pagamento_aprovar"),
    ("Autorizar Pagamento", "pagamento_autorizar"),
    ("Pagar — Tesouraria", "pagamento_pagar"),
]


def _enable_rls(t: str) -> None:
    op.execute(f"ALTER TABLE {S}.{t} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{t} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON {S}.{t} FOR SELECT "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")
    op.execute(f"CREATE POLICY tenant_isolation_modify ON {S}.{t} FOR ALL "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int) "
               f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")


def _grant(t: str) -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{t} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.{t}_id_seq TO aprimora_app")


def upgrade() -> None:
    op.create_table(
        "debito",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_fornecedor", sa.Integer(), sa.ForeignKey(f"{S}.fornecedor.id"), nullable=False),
        sa.Column("id_natureza", sa.Integer(), sa.ForeignKey(f"{S}.natureza_despesa.id"), nullable=False),
        sa.Column("id_conta", sa.Integer(), sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False),
        sa.Column("id_contrato", sa.Integer(), sa.ForeignKey(f"{S}.contrato.id"), nullable=True),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("competencia", sa.String(7), nullable=False),  # 'YYYY-MM'
        sa.Column("numero_ne", sa.String(30), nullable=True),
        sa.Column("numero_nf", sa.String(40), nullable=True),
        sa.Column("criticidade", sa.String(10), nullable=False, server_default="MEDIA"),
        sa.Column("urgente", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("justificativa_urgencia", sa.String(255), nullable=True),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column("status", sa.String(25), nullable=False, server_default="RASCUNHO"),
        sa.Column("id_usuario_solicitante", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("valor_total > 0", name="ck_debito_valor_positivo"),
        sa.CheckConstraint(
            "status IN ('RASCUNHO','AGUARDANDO_APROVACAO','APROVADO','AUTORIZADO',"
            "'PAGO_PARCIAL','PAGO','REJEITADO','CANCELADO')", name="ck_debito_status"),
        sa.CheckConstraint("criticidade IN ('URGENTE','ALTA','MEDIA','BAIXA')", name="ck_debito_criticidade"),
        schema=S,
    )
    op.create_index("ix_debito_tenant_status", "debito", ["tenant_id", "status"], schema=S)
    op.create_index("ix_debito_tenant_conta", "debito", ["tenant_id", "id_conta"], schema=S)
    op.create_index("ix_debito_tenant_solicitante", "debito", ["tenant_id", "id_usuario_solicitante"], schema=S)

    op.create_table(
        "parcela",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_debito", sa.Integer(), sa.ForeignKey(f"{S}.debito.id"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("vencimento", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="A_PAGAR"),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("forma_pagamento", sa.String(20), nullable=True),
        sa.Column("id_movimentacao", sa.Integer(), sa.ForeignKey(f"{S}.movimentacao_conta.id"), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("valor > 0", name="ck_parcela_valor_positivo"),
        sa.CheckConstraint("status IN ('A_PAGAR','PAGA','CANCELADA')", name="ck_parcela_status"),
        sa.UniqueConstraint("id_debito", "numero", name="uq_parcela_debito_numero"),
        schema=S,
    )
    op.create_index("ix_parcela_tenant_debito", "parcela", ["tenant_id", "id_debito"], schema=S)
    op.create_index("ix_parcela_tenant_status_venc", "parcela", ["tenant_id", "status", "vencimento"], schema=S)

    op.create_table(  # append-only: sem excluido/atualizado_em
        "debito_historico",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_debito", sa.Integer(), sa.ForeignKey(f"{S}.debito.id"), nullable=False),
        sa.Column("status_anterior", sa.String(25), nullable=True),
        sa.Column("status_novo", sa.String(25), nullable=False),
        sa.Column("acao", sa.String(20), nullable=False),
        sa.Column("justificativa", sa.String(255), nullable=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("ip_origem", sa.String(45), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "acao IN ('CRIADO','ENVIADO','APROVADO','DEVOLVIDO','REJEITADO',"
            "'AUTORIZADO','PAGAMENTO','ESTORNO','CANCELADO')", name="ck_debhist_acao"),
        schema=S,
    )
    op.create_index("ix_debhist_tenant_debito", "debito_historico", ["tenant_id", "id_debito"], schema=S)

    op.create_table(  # append-only
        "ordem_pagamento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("id_usuario_autorizador", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("ip_origem", sa.String(45), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("tenant_id", "numero", name="uq_op_tenant_numero"),
        schema=S,
    )

    op.create_table(  # N:N OP x débito
        "ordem_pagamento_debito",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_ordem", sa.Integer(), sa.ForeignKey(f"{S}.ordem_pagamento.id"), nullable=False),
        sa.Column("id_debito", sa.Integer(), sa.ForeignKey(f"{S}.debito.id"), nullable=False),
        sa.UniqueConstraint("id_ordem", "id_debito", name="uq_opdeb_ordem_debito"),
        schema=S,
    )
    op.create_index("ix_opdeb_tenant_ordem", "ordem_pagamento_debito", ["tenant_id", "id_ordem"], schema=S)

    for t in ("debito", "parcela", "debito_historico", "ordem_pagamento", "ordem_pagamento_debito"):
        _grant(t)
        _enable_rls(t)

    # FKs prometidas no R1 (movimentacao_conta.id_debito/id_parcela eram Integer soltos)
    op.create_foreign_key("fk_movconta_debito", "movimentacao_conta", "debito",
                          ["id_debito"], ["id"], source_schema=S, referent_schema=S)
    op.create_foreign_key("fk_movconta_parcela", "movimentacao_conta", "parcela",
                          ["id_parcela"], ["id"], source_schema=S, referent_schema=S)

    # RBAC (idempotente, padrão 0045)
    for nome, codigo in TRANSACOES:
        op.execute(
            f"""INSERT INTO utils.transacao (transacao, codigo)
                SELECT '{nome}', '{codigo}'
                WHERE NOT EXISTS (SELECT 1 FROM utils.transacao WHERE codigo = '{codigo}')"""
        )


def downgrade() -> None:
    for _, codigo in TRANSACOES:
        op.execute(f"DELETE FROM utils.grupo_transacao WHERE id_transacao IN "
                   f"(SELECT id FROM utils.transacao WHERE codigo='{codigo}')")
        op.execute(f"DELETE FROM utils.sistema_transacao WHERE id_transacao IN "
                   f"(SELECT id FROM utils.transacao WHERE codigo='{codigo}')")
        op.execute(f"DELETE FROM utils.transacao WHERE codigo='{codigo}'")
    op.drop_constraint("fk_movconta_parcela", "movimentacao_conta", schema=S, type_="foreignkey")
    op.drop_constraint("fk_movconta_debito", "movimentacao_conta", schema=S, type_="foreignkey")
    for t in ("ordem_pagamento_debito", "ordem_pagamento", "debito_historico", "parcela", "debito"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.{t}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.{t}")
        op.drop_table(t, schema=S)
```

- [ ] **Step 3: Aplicar + roundtrip**

Run: `docker exec aprimora-py-backend alembic upgrade head` → `Running upgrade 0047 -> 0048`.
Run: `docker exec aprimora-py-backend alembic downgrade -1 && docker exec aprimora-py-backend alembic upgrade head` → sem erro.

- [ ] **Step 4: Verificar RLS como aprimora_app**

Run: `docker exec ged-saas-project-db-1 psql -U ged_user -d ged_saas_db -c "SET ROLE aprimora_app; SET app.tenant_id = '2'; SELECT count(*) FROM pagamentos.debito; SELECT count(*) FROM pagamentos.ordem_pagamento;"`
Expected: `0` / `0` sem erro de permissão.

- [ ] **Step 5: Verificar seed RBAC**

Run: `docker exec ged-saas-project-db-1 psql -U ged_user -d ged_saas_db -c "SELECT codigo FROM utils.transacao WHERE codigo LIKE 'pagamento_%' ORDER BY codigo;"`
Expected: `pagamento_aprovar, pagamento_autorizar, pagamento_cadastro, pagamento_pagar, pagamento_solicitar`.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0048_pagamentos_debitos.py
git commit -m "feat(pagamentos): migration 0048 — debito/parcela/historico/OP + RBAC do workflow"
```

---

### Task 2: Models + schemas + CRUD de débito (rascunho)

**Files:**
- Modify: `backend/app/models/pagamentos.py`, `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/pagamentos.py`
- Create: `backend/app/services/pagamentos_debitos.py`
- Test: `backend/tests/test_pagamentos_debitos.py`

**Interfaces:**
- Consumes: tabelas da 0048; `Fornecedor`, `NaturezaDespesa`, `ContaBancaria`, `Contrato` (models); `obter_fornecedor/obter_natureza/obter_conta/obter_contrato` de `services/pagamentos_cadastros.py`.
- Produces (usados nas Tasks 3–6):
  - Models `Debito`, `Parcela`, `DebitoHistorico`, `OrdemPagamento`, `OrdemPagamentoDebito`.
  - `PagamentoDebitoError(HTTPException)`.
  - `criar_debito(db, *, tenant_id, usuario_id, payload: DebitoCreate) -> Debito`
  - `listar_debitos(db, *, tenant_id, status: str | None = None, solicitante_id: int | None = None) -> list[Debito]`
  - `obter_debito(db, *, tenant_id, debito_id) -> Debito` (404)
  - `listar_parcelas(db, *, tenant_id, debito_id) -> list[Parcela]`
  - `listar_historico(db, *, tenant_id, debito_id) -> list[DebitoHistorico]` (desc)
  - `atualizar_debito(db, *, tenant_id, debito_id, usuario_id, payload: DebitoUpdate) -> Debito` (só RASCUNHO)
  - `excluir_debito(db, *, tenant_id, debito_id) -> None` (só RASCUNHO/REJEITADO/CANCELADO)
  - `debito_out(d: Debito, *, nome_fornecedor: str) -> dict` e `nomes_fornecedores(db, *, tenant_id, ids) -> dict[int, str]`
  - `_registrar_transicao(db, *, debito, novo_status, acao, usuario_id, justificativa=None, ip=None)` (helper interno, NÃO commita)

- [ ] **Step 1: Models** — acrescentar em `backend/app/models/pagamentos.py` (após `MovimentacaoConta`):

```python
class Debito(Base):
    __tablename__ = "debito"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_fornecedor: Mapped[int] = mapped_column(ForeignKey("pagamentos.fornecedor.id"), nullable=False)
    id_natureza: Mapped[int] = mapped_column(ForeignKey("pagamentos.natureza_despesa.id"), nullable=False)
    id_conta: Mapped[int] = mapped_column(ForeignKey("pagamentos.conta_bancaria.id"), nullable=False)
    id_contrato: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.contrato.id"), nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    competencia: Mapped[str] = mapped_column(String(7), nullable=False)
    numero_ne: Mapped[str | None] = mapped_column(String(30), nullable=True)
    numero_nf: Mapped[str | None] = mapped_column(String(40), nullable=True)
    criticidade: Mapped[str] = mapped_column(String(10), nullable=False, default="MEDIA")
    urgente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    justificativa_urgencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="RASCUNHO")
    id_usuario_solicitante: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Parcela(Base):
    __tablename__ = "parcela"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_debito: Mapped[int] = mapped_column(ForeignKey("pagamentos.debito.id"), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="A_PAGAR")
    data_pagamento: Mapped[date | None] = mapped_column(Date, nullable=True)
    forma_pagamento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    id_movimentacao: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.movimentacao_conta.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DebitoHistorico(Base):
    """Trilha imutável das transições do débito (append-only)."""
    __tablename__ = "debito_historico"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_debito: Mapped[int] = mapped_column(ForeignKey("pagamentos.debito.id"), nullable=False)
    status_anterior: Mapped[str | None] = mapped_column(String(25), nullable=True)
    status_novo: Mapped[str] = mapped_column(String(25), nullable=False)
    acao: Mapped[str] = mapped_column(String(20), nullable=False)
    justificativa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("utils.usuario.id"), nullable=True)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OrdemPagamento(Base):
    __tablename__ = "ordem_pagamento"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    id_usuario_autorizador: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    ip_origem: Mapped[str | None] = mapped_column(String(45), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OrdemPagamentoDebito(Base):
    __tablename__ = "ordem_pagamento_debito"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_ordem: Mapped[int] = mapped_column(ForeignKey("pagamentos.ordem_pagamento.id"), nullable=False)
    id_debito: Mapped[int] = mapped_column(ForeignKey("pagamentos.debito.id"), nullable=False)
```

Registrar em `backend/app/models/__init__.py`: adicionar `Debito, Parcela, DebitoHistorico, OrdemPagamento, OrdemPagamentoDebito` ao import de `.pagamentos` e ao `__all__`.

- [ ] **Step 2: Schemas** — acrescentar em `backend/app/schemas/pagamentos.py`:

```python
StatusDebito = Literal["RASCUNHO", "AGUARDANDO_APROVACAO", "APROVADO", "AUTORIZADO",
                       "PAGO_PARCIAL", "PAGO", "REJEITADO", "CANCELADO"]
StatusParcela = Literal["A_PAGAR", "PAGA", "CANCELADA"]
FormaPagamento = Literal["PIX", "TED", "BOLETO", "DINHEIRO", "OUTRO"]


class ParcelaCreate(BaseModel):
    numero: int = Field(ge=1)
    valor: Decimal = Field(gt=0)
    vencimento: date


class DebitoCreate(BaseModel):
    id_fornecedor: int
    id_natureza: int
    id_conta: int
    id_contrato: int | None = None
    valor_total: Decimal = Field(gt=0)
    competencia: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    numero_ne: str | None = Field(default=None, max_length=30)
    numero_nf: str | None = Field(default=None, max_length=40)
    criticidade: CriticidadeLit = "MEDIA"
    urgente: bool = False
    justificativa_urgencia: str | None = Field(default=None, max_length=255)
    descricao: str = Field(min_length=1, max_length=255)
    parcelas: list[ParcelaCreate] = Field(min_length=1)


class DebitoUpdate(BaseModel):
    id_fornecedor: int | None = None
    id_natureza: int | None = None
    id_conta: int | None = None
    id_contrato: int | None = None
    valor_total: Decimal | None = Field(default=None, gt=0)
    competencia: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    numero_ne: str | None = Field(default=None, max_length=30)
    numero_nf: str | None = Field(default=None, max_length=40)
    criticidade: CriticidadeLit | None = None
    urgente: bool | None = None
    justificativa_urgencia: str | None = Field(default=None, max_length=255)
    descricao: str | None = Field(default=None, min_length=1, max_length=255)
    parcelas: list[ParcelaCreate] | None = Field(default=None, min_length=1)


class ParcelaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_debito: int; numero: int; valor: Decimal; vencimento: date
    status: StatusParcela; data_pagamento: date | None; forma_pagamento: FormaPagamento | None
    id_movimentacao: int | None


class DebitoOut(BaseModel):
    id: int; id_fornecedor: int; nome_fornecedor: str; id_natureza: int; id_conta: int
    id_contrato: int | None; valor_total: Decimal; competencia: str
    numero_ne: str | None; numero_nf: str | None; criticidade: CriticidadeLit
    urgente: bool; justificativa_urgencia: str | None; descricao: str
    status: StatusDebito; id_usuario_solicitante: int
    criado_em: datetime; atualizado_em: datetime | None


class DebitoHistoricoOut(BaseModel):
    id: int; acao: str; status_anterior: str | None; status_novo: str
    justificativa: str | None; id_usuario: int | None; nome_usuario: str | None
    criado_em: datetime


class DebitoDetalheOut(DebitoOut):
    parcelas: list[ParcelaOut]
    historico: list[DebitoHistoricoOut]


class JustificativaIn(BaseModel):
    justificativa: str = Field(min_length=1, max_length=255)


class AutorizarLoteIn(BaseModel):
    debito_ids: list[int] = Field(min_length=1)


class PagarParcelaIn(BaseModel):
    forma_pagamento: FormaPagamento
    data_pagamento: date | None = None


class OrdemPagamentoOut(BaseModel):
    id: int; numero: str; valor_total: Decimal; id_usuario_autorizador: int
    nome_autorizador: str | None; qtd_debitos: int; criado_em: datetime


class ParcelaFilaOut(BaseModel):
    id: int; id_debito: int; numero: int; valor: Decimal; vencimento: date
    nome_fornecedor: str; descricao_debito: str; vencida: bool


class MinhaFilaOut(BaseModel):
    solicitar: list[DebitoOut] | None = None    # meus RASCUNHO (inclui devolvidos)
    aprovar: list[DebitoOut] | None = None      # AGUARDANDO_APROVACAO
    autorizar: list[DebitoOut] | None = None    # APROVADO
    pagar: list[ParcelaFilaOut] | None = None   # A_PAGAR de AUTORIZADO/PAGO_PARCIAL
```

E **alterar** `SaldoConta` e `ContaSaldoPainel` (existentes) acrescentando os dois campos:

```python
class SaldoConta(BaseModel):
    id_conta: int; saldo_inicial: Decimal; total_entradas: Decimal
    total_saidas: Decimal; saldo_atual: Decimal
    comprometido: Decimal = Decimal("0"); disponivel: Decimal = Decimal("0")


class ContaSaldoPainel(BaseModel):
    id_conta: int; nome: str; banco: str; grupo_despesa: str
    saldo_inicial: Decimal; total_entradas: Decimal; total_saidas: Decimal
    saldo_atual: Decimal; saldo_minimo_alerta: Decimal; abaixo_minimo: bool
    comprometido: Decimal = Decimal("0"); disponivel: Decimal = Decimal("0")
```

(Defaults `0` mantêm compatibilidade — o preenchimento real vem na Task 4.)

- [ ] **Step 3: Testes que falham** — criar `backend/tests/test_pagamentos_debitos.py` (mesmo cabeçalho/fixtures de `test_pagamentos_cadastros.py`; copiar `_sm`, `_slug`, `_provisionar`, `_doc`; `_cleanup` DEVE deletar na ordem: `ordem_pagamento_debito, ordem_pagamento, debito_historico, parcela, movimentacao_conta, debito, contrato, alcada, natureza_despesa, conta_bancaria, fonte_recursos, fornecedor_situacao_historico, fornecedor, ...` + o rabo padrão de usuario/tenant):

```python
async def _base(engine, tenant_id):
    """Fornecedor + natureza + fonte + conta prontos para um débito."""
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Deb LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Deb", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial="10000.00"))
    return forn, nat, conta


def _payload_debito(forn, nat, conta, *, valor="1000.00", parcelas=None):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_conta=conta.id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        parcelas=parcelas or [ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def test_criar_debito_com_parcelas(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                payload=_payload_debito(forn, nat, conta, valor="1000.00", parcelas=[
                    ParcelaCreate(numero=1, valor="600.00", vencimento="2026-08-01"),
                    ParcelaCreate(numero=2, valor="400.00", vencimento="2026-09-01"),
                ]))
        assert d.status == "RASCUNHO"
        async with _sm(admin_engine)() as s:
            parcelas = await svc.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert [p.numero for p in parcelas] == [1, 2]
        assert len(hist) == 1 and hist[0].acao == "CRIADO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_criar_debito_soma_parcelas_diferente_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, conta = await _base(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            uid = (await s.execute(text(
                "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
            with pytest.raises(HTTPException) as exc:
                await svc.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                    payload=_payload_debito(forn, nat, conta, valor="1000.00", parcelas=[
                        ParcelaCreate(numero=1, valor="999.00", vencimento="2026-08-01")]))
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_atualizar_debito_fora_de_rascunho_409(admin_engine): ...
# criar débito, forçar status='AGUARDANDO_APROVACAO' via UPDATE SQL direto,
# atualizar_debito deve levantar 409.


async def test_excluir_debito_rascunho_soft_delete(admin_engine): ...
# excluir → obter_debito 404; linha permanece com excluido=true (SELECT bruto).
```

(Os dois últimos: escrever completos no mesmo padrão dos dois primeiros.)

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_debitos.py -q`
Expected: FAIL (`ImportError`/`AttributeError` — serviço ainda não existe).

- [ ] **Step 4: Implementar o serviço** — criar `backend/app/services/pagamentos_debitos.py`:

```python
"""Débitos de Pagamentos (R2) — CRUD de rascunho e transições de workflow.
Transições SÓ por aqui; cada uma grava debito_historico na MESMA transação."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Debito, DebitoHistorico, Fornecedor, Parcela, Usuario
from ..schemas.pagamentos import DebitoCreate, DebitoUpdate
from . import pagamentos_cadastros as cad


def _utcnow() -> datetime:
    return datetime.utcnow()


class PagamentoDebitoError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def _validar_parcelas(parcelas, valor_total: Decimal) -> None:
    numeros = sorted(p.numero for p in parcelas)
    if numeros != list(range(1, len(parcelas) + 1)):
        raise PagamentoDebitoError("Parcelas devem ser numeradas 1..N sem repetição.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    soma = sum((p.valor for p in parcelas), Decimal("0"))
    if soma != valor_total:
        raise PagamentoDebitoError(
            f"Soma das parcelas ({soma}) difere do valor total ({valor_total}).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)


async def _validar_refs(db, *, tenant_id: int, payload) -> None:
    await cad.obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=payload.id_fornecedor)
    await cad.obter_natureza(db, tenant_id=tenant_id, natureza_id=payload.id_natureza)
    await cad.obter_conta(db, tenant_id=tenant_id, conta_id=payload.id_conta)
    if payload.id_contrato is not None:
        await cad.obter_contrato(db, tenant_id=tenant_id, contrato_id=payload.id_contrato)


def _registrar_transicao(db, *, debito: Debito, novo_status: str, acao: str,
                         usuario_id: int | None, justificativa: str | None = None,
                         ip: str | None = None) -> None:
    db.add(DebitoHistorico(tenant_id=debito.tenant_id, id_debito=debito.id,
                           status_anterior=debito.status if acao != "CRIADO" else None,
                           status_novo=novo_status, acao=acao, justificativa=justificativa,
                           id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow()))
    debito.status = novo_status


async def criar_debito(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                       payload: DebitoCreate) -> Debito:
    await _validar_refs(db, tenant_id=tenant_id, payload=payload)
    _validar_parcelas(payload.parcelas, payload.valor_total)
    d = Debito(tenant_id=tenant_id, id_fornecedor=payload.id_fornecedor,
               id_natureza=payload.id_natureza, id_conta=payload.id_conta,
               id_contrato=payload.id_contrato, valor_total=payload.valor_total,
               competencia=payload.competencia, numero_ne=payload.numero_ne,
               numero_nf=payload.numero_nf, criticidade=payload.criticidade,
               urgente=payload.urgente, justificativa_urgencia=payload.justificativa_urgencia,
               descricao=payload.descricao, status="RASCUNHO",
               id_usuario_solicitante=usuario_id, criado_em=_utcnow())
    db.add(d); await db.flush()
    for p in payload.parcelas:
        db.add(Parcela(tenant_id=tenant_id, id_debito=d.id, numero=p.numero,
                       valor=p.valor, vencimento=p.vencimento, criado_em=_utcnow()))
    _registrar_transicao(db, debito=d, novo_status="RASCUNHO", acao="CRIADO", usuario_id=usuario_id)
    await db.commit(); await db.refresh(d)
    return d


async def obter_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> Debito:
    d = (await db.execute(select(Debito).where(Debito.id == debito_id,
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False)))).scalar_one_or_none()
    if d is None:
        raise PagamentoDebitoError("Débito não encontrado", status.HTTP_404_NOT_FOUND)
    return d


async def listar_debitos(db: AsyncSession, *, tenant_id: int, status_f: str | None = None,
                         solicitante_id: int | None = None) -> list[Debito]:
    stmt = select(Debito).where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False))
    if status_f:
        stmt = stmt.where(Debito.status == status_f)
    if solicitante_id is not None:
        stmt = stmt.where(Debito.id_usuario_solicitante == solicitante_id)
    return list((await db.execute(stmt.order_by(Debito.id.desc()))).scalars().all())


async def listar_parcelas(db: AsyncSession, *, tenant_id: int, debito_id: int) -> list[Parcela]:
    return list((await db.execute(select(Parcela).where(
        Parcela.tenant_id == tenant_id, Parcela.id_debito == debito_id,
        Parcela.excluido.is_(False)).order_by(Parcela.numero))).scalars().all())


async def listar_historico(db: AsyncSession, *, tenant_id: int, debito_id: int) -> list[DebitoHistorico]:
    return list((await db.execute(select(DebitoHistorico).where(
        DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id_debito == debito_id)
        .order_by(DebitoHistorico.criado_em.desc(), DebitoHistorico.id.desc()))).scalars().all())


async def atualizar_debito(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, payload: DebitoUpdate) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    if d.status != "RASCUNHO":
        raise PagamentoDebitoError("Só é possível editar débitos em rascunho.",
                                   status.HTTP_409_CONFLICT)
    dados = payload.model_dump(exclude_unset=True)
    parcelas_novas = dados.pop("parcelas", None)
    valor_total = dados.get("valor_total", d.valor_total)
    if parcelas_novas is not None:
        _validar_parcelas(payload.parcelas, valor_total)
    elif "valor_total" in dados:
        atuais = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
        soma = sum((p.valor for p in atuais), Decimal("0"))
        if soma != valor_total:
            raise PagamentoDebitoError(
                f"Soma das parcelas ({soma}) difere do novo valor total ({valor_total}).",
                status.HTTP_422_UNPROCESSABLE_ENTITY)
    # valida refs alteradas
    class _Ref:  # payload efetivo para _validar_refs
        id_fornecedor = dados.get("id_fornecedor", d.id_fornecedor)
        id_natureza = dados.get("id_natureza", d.id_natureza)
        id_conta = dados.get("id_conta", d.id_conta)
        id_contrato = dados.get("id_contrato", d.id_contrato)
    await _validar_refs(db, tenant_id=tenant_id, payload=_Ref)
    for k, v in dados.items():
        setattr(d, k, v)
    if parcelas_novas is not None:
        for p in await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id):
            p.excluido = True; p.atualizado_em = _utcnow()
        for p in payload.parcelas:
            db.add(Parcela(tenant_id=tenant_id, id_debito=d.id, numero=p.numero,
                           valor=p.valor, vencimento=p.vencimento, criado_em=_utcnow()))
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def excluir_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> None:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    if d.status not in ("RASCUNHO", "REJEITADO", "CANCELADO"):
        raise PagamentoDebitoError("Só é possível excluir rascunhos/rejeitados/cancelados.",
                                   status.HTTP_409_CONFLICT)
    d.excluido = True; d.atualizado_em = _utcnow(); await db.commit()


async def nomes_fornecedores(db: AsyncSession, *, tenant_id: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(Fornecedor.id, Fornecedor.nome).where(
        Fornecedor.tenant_id == tenant_id, Fornecedor.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


async def nomes_usuarios(db: AsyncSession, *, tenant_id: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(Usuario.id, Usuario.nome).where(
        Usuario.tenant_id == tenant_id, Usuario.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


def debito_out(d: Debito, *, nome_fornecedor: str) -> dict:
    return {
        "id": d.id, "id_fornecedor": d.id_fornecedor, "nome_fornecedor": nome_fornecedor,
        "id_natureza": d.id_natureza, "id_conta": d.id_conta, "id_contrato": d.id_contrato,
        "valor_total": d.valor_total, "competencia": d.competencia,
        "numero_ne": d.numero_ne, "numero_nf": d.numero_nf, "criticidade": d.criticidade,
        "urgente": d.urgente, "justificativa_urgencia": d.justificativa_urgencia,
        "descricao": d.descricao, "status": d.status,
        "id_usuario_solicitante": d.id_usuario_solicitante,
        "criado_em": d.criado_em, "atualizado_em": d.atualizado_em,
    }
```

- [ ] **Step 5: Rodar os testes**

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_debitos.py -q`
Expected: PASS (4 testes).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/pagamentos.py backend/app/models/__init__.py \
  backend/app/schemas/pagamentos.py backend/app/services/pagamentos_debitos.py \
  backend/tests/test_pagamentos_debitos.py
git commit -m "feat(pagamentos): débito com parcelas — models, schemas e CRUD de rascunho"
```

---

### Task 3: Transições de workflow (enviar/aprovar/devolver/rejeitar/cancelar)

**Files:**
- Modify: `backend/app/services/pagamentos_debitos.py`
- Test: `backend/tests/test_pagamentos_debitos.py` (acrescentar)

**Interfaces:**
- Consumes: Task 2 (`obter_debito`, `_registrar_transicao`, `listar_parcelas`, `_validar_parcelas`).
- Produces (assinaturas exatas, usadas na Task 6):
  - `enviar_aprovacao(db, *, tenant_id, debito_id, usuario_id, ip=None) -> Debito`
  - `aprovar(db, *, tenant_id, debito_id, usuario_id, ip=None) -> Debito`
  - `devolver(db, *, tenant_id, debito_id, usuario_id, justificativa, ip=None) -> Debito`
  - `rejeitar(db, *, tenant_id, debito_id, usuario_id, justificativa, ip=None) -> Debito`
  - `cancelar(db, *, tenant_id, debito_id, usuario_id, justificativa, ip=None) -> Debito`
  - `aprovadores_do_debito(db, *, tenant_id, debito_id) -> set[int]` (via histórico, ação APROVADO)

- [ ] **Step 1: Testes que falham** — acrescentar em `test_pagamentos_debitos.py`:

```python
async def _debito_pronto(engine, tenant_id, **kw):
    forn, nat, conta = await _base(engine, tenant_id)
    async with _sm(engine)() as s:
        uid = (await s.execute(text(
            "SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"), {"t": tenant_id})).scalar_one()
        d = await svc.criar_debito(s, tenant_id=tenant_id, usuario_id=uid,
                                   payload=_payload_debito(forn, nat, conta, **kw))
    return d, uid, conta


async def _novo_usuario(engine, tenant_id, sufixo):
    """Segundo usuário no tenant (para segregação)."""
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, criado_em)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"User {sufixo}", "e": f"{sufixo}@t.local",
             "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def test_fluxo_enviar_aprovar(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        aprovador = await _novo_usuario(admin_engine, t.id, f"apr{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            d2 = await svc.enviar_aprovacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante)
        assert d2.status == "AGUARDANDO_APROVACAO"
        async with _sm(admin_engine)() as s:
            d3 = await svc.aprovar(s, tenant_id=t.id, debito_id=d.id, usuario_id=aprovador)
        assert d3.status == "APROVADO"
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert [h.acao for h in hist] == ["APROVADO", "ENVIADO", "CRIADO"]
    finally:
        await _cleanup(admin_engine, t.id)


async def test_aprovar_pelo_proprio_solicitante_403(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            await svc.enviar_aprovacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.aprovar(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante)
            assert exc.value.status_code == 403
    finally:
        await _cleanup(admin_engine, t.id)


async def test_devolver_volta_a_rascunho_com_motivo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        aprovador = await _novo_usuario(admin_engine, t.id, f"dev{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await svc.enviar_aprovacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=solicitante)
        async with _sm(admin_engine)() as s:
            d2 = await svc.devolver(s, tenant_id=t.id, debito_id=d.id, usuario_id=aprovador,
                                    justificativa="Falta nota fiscal")
        assert d2.status == "RASCUNHO"
        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert hist[0].acao == "DEVOLVIDO" and hist[0].justificativa == "Falta nota fiscal"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_transicao_invalida_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, _ = await _debito_pronto(admin_engine, t.id)
        # aprovar direto de RASCUNHO → 409
        outro = await _novo_usuario(admin_engine, t.id, f"inv{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.aprovar(s, tenant_id=t.id, debito_id=d.id, usuario_id=outro)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_cancelar_apos_parcela_paga_409(admin_engine): ...
# criar débito, marcar parcela status='PAGA' via UPDATE SQL, cancelar → 409.
# (escrever completo no mesmo padrão)
```

> ATENÇÃO: conferir as colunas reais de `utils.usuario` antes de usar o INSERT de `_novo_usuario` (rodar `docker exec ged-saas-project-db-1 psql -U ged_user -d ged_saas_db -c "\d utils.usuario"`). Se houver colunas NOT NULL extras (ex.: `id_nivel`), copiar os valores do usuário admin do tenant (`SELECT ... WHERE tenant_id=:t LIMIT 1`) para o INSERT.

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_debitos.py -q`
Expected: FAIL (`AttributeError: enviar_aprovacao`).

- [ ] **Step 2: Implementar as transições** — acrescentar em `pagamentos_debitos.py`:

```python
async def aprovadores_do_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> set[int]:
    rows = (await db.execute(select(DebitoHistorico.id_usuario).where(
        DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id_debito == debito_id,
        DebitoHistorico.acao == "APROVADO"))).scalars().all()
    return {r for r in rows if r is not None}


def _exigir_status(d: Debito, *esperados: str) -> None:
    if d.status not in esperados:
        raise PagamentoDebitoError(
            f"Transição inválida: débito está '{d.status}' (esperado: {', '.join(esperados)}).",
            status.HTTP_409_CONFLICT)


async def enviar_aprovacao(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "RASCUNHO")
    parcelas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    if not parcelas:
        raise PagamentoDebitoError("Débito sem parcelas.", status.HTTP_422_UNPROCESSABLE_ENTITY)
    soma = sum((p.valor for p in parcelas), Decimal("0"))
    if soma != d.valor_total:
        raise PagamentoDebitoError(
            f"Soma das parcelas ({soma}) difere do valor total ({d.valor_total}).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    _registrar_transicao(db, debito=d, novo_status="AGUARDANDO_APROVACAO", acao="ENVIADO",
                         usuario_id=usuario_id, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def aprovar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                  usuario_id: int, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "AGUARDANDO_APROVACAO")
    if usuario_id == d.id_usuario_solicitante:
        raise PagamentoDebitoError("Segregação de funções: o solicitante não pode aprovar o próprio débito.",
                                   status.HTTP_403_FORBIDDEN)
    _registrar_transicao(db, debito=d, novo_status="APROVADO", acao="APROVADO",
                         usuario_id=usuario_id, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def devolver(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   justificativa: str, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "AGUARDANDO_APROVACAO")
    _registrar_transicao(db, debito=d, novo_status="RASCUNHO", acao="DEVOLVIDO",
                         usuario_id=usuario_id, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def rejeitar(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   justificativa: str, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "AGUARDANDO_APROVACAO")
    _registrar_transicao(db, debito=d, novo_status="REJEITADO", acao="REJEITADO",
                         usuario_id=usuario_id, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def cancelar(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   justificativa: str, ip: str | None = None) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, "RASCUNHO", "AGUARDANDO_APROVACAO", "APROVADO", "AUTORIZADO")
    parcelas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    if any(p.status == "PAGA" for p in parcelas):
        raise PagamentoDebitoError("Débito com parcela paga não pode ser cancelado — estorne antes.",
                                   status.HTTP_409_CONFLICT)
    for p in parcelas:
        p.status = "CANCELADA"; p.atualizado_em = _utcnow()
    _registrar_transicao(db, debito=d, novo_status="CANCELADO", acao="CANCELADO",
                         usuario_id=usuario_id, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d
```

- [ ] **Step 3: Rodar os testes**

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_debitos.py -q`
Expected: PASS (todos).

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/pagamentos_debitos.py backend/tests/test_pagamentos_debitos.py
git commit -m "feat(pagamentos): workflow do débito — enviar/aprovar/devolver/rejeitar/cancelar + segregação"
```

---

### Task 4: Autorização em lote — saldo/alçada/segregação + Ordem de Pagamento

**Files:**
- Modify: `backend/app/services/pagamentos_caixa.py` (comprometido/disponível)
- Create: `backend/app/services/pagamentos_autorizacao.py`
- Test: `backend/tests/test_pagamentos_autorizacao.py`

**Interfaces:**
- Consumes: Task 2/3 (`obter_debito`, `aprovadores_do_debito`, `_registrar_transicao`); `saldo_conta` do caixa; model `Alcada`.
- Produces:
  - `pagamentos_caixa.comprometido_conta(db, *, tenant_id, conta_id) -> Decimal`
  - `saldo_conta`/`painel_caixa` passam a preencher `comprometido` e `disponivel` (`= saldo_atual − comprometido`)
  - `pagamentos_autorizacao.autorizar_lote(db, *, tenant_id, usuario_id, debito_ids: list[int], ip=None) -> OrdemPagamento`
  - `pagamentos_autorizacao.listar_ordens(db, *, tenant_id) -> list[OrdemPagamento]`
  - `pagamentos_autorizacao.obter_ordem(db, *, tenant_id, ordem_id) -> OrdemPagamento`
  - `pagamentos_autorizacao.debitos_da_ordem(db, *, tenant_id, ordem_id) -> list[Debito]`

- [ ] **Step 1: Comprometido no caixa** — em `pagamentos_caixa.py`, adicionar (import `Debito`, `Parcela` de `..models`):

```python
async def comprometido_conta(db, *, tenant_id, conta_id) -> Decimal:
    """Σ parcelas A_PAGAR (não excluídas) de débitos AUTORIZADO/PAGO_PARCIAL da conta."""
    stmt = (select(func.coalesce(func.sum(Parcela.valor), 0))
            .join(Debito, Debito.id == Parcela.id_debito)
            .where(Parcela.tenant_id == tenant_id, Parcela.status == "A_PAGAR",
                   Parcela.excluido.is_(False), Debito.id_conta == conta_id,
                   Debito.excluido.is_(False),
                   Debito.status.in_(("AUTORIZADO", "PAGO_PARCIAL"))))
    return (await db.execute(stmt)).scalar_one()
```

E em `saldo_conta`, após calcular `saldo_atual`:

```python
    comprometido = await comprometido_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    saldo_atual = inicial + entradas - saidas
    return SaldoConta(id_conta=conta_id, saldo_inicial=inicial, total_entradas=entradas,
                      total_saidas=saidas, saldo_atual=saldo_atual,
                      comprometido=comprometido, disponivel=saldo_atual - comprometido)
```

Em `painel_caixa`, repassar `comprometido=saldo.comprometido, disponivel=saldo.disponivel` no `ContaSaldoPainel`.

- [ ] **Step 2: Testes que falham** — criar `backend/tests/test_pagamentos_autorizacao.py`. Imports no topo:

```python
from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as deb
from app.services.provisioning_tenant import provisionar_tenant
```

Copiar `_sm`, `_slug`, `_provisionar`, `_doc`, `_base` (com param `saldo_inicial`), `_payload_debito`, `_novo_usuario` e `_cleanup` de `test_pagamentos_debitos.py` (duplicar para independência entre arquivos). Casos:

```python
async def _debito_aprovado(engine, tenant_id, *, valor="1000.00", saldo_inicial="10000.00",
                           parcelas=None, base=None):
    """Débito RASCUNHO→ENVIADO→APROVADO com solicitante/aprovador distintos.
    Retorna (debito, solicitante_id, aprovador_id, conta). `base` reusa (forn, nat, conta)."""
    if base is None:
        forn, nat, conta = await _base(engine, tenant_id, saldo_inicial=saldo_inicial)
    else:
        forn, nat, conta = base
    solicitante = await _novo_usuario(engine, tenant_id, f"sol{uuid.uuid4().hex[:6]}")
    aprovador = await _novo_usuario(engine, tenant_id, f"apr{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        d = await deb.criar_debito(s, tenant_id=tenant_id, usuario_id=solicitante,
                                   payload=_payload_debito(forn, nat, conta, valor=valor,
                                                           parcelas=parcelas))
    async with _sm(engine)() as s:
        await deb.enviar_aprovacao(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=solicitante)
    async with _sm(engine)() as s:
        d = await deb.aprovar(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=aprovador)
    return d, solicitante, aprovador, conta
# Obs.: `_base` aqui deve aceitar `saldo_inicial` (parametrizar o helper copiado da Task 2).


async def _dar_alcada(engine, tenant_id, usuario_id, *, valor_maximo="999999.00", id_natureza=None):
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=usuario_id, id_natureza=id_natureza, valor_maximo=valor_maximo))


async def _autorizador_com_alcada(engine, tenant_id, *, valor_maximo="999999.00"):
    uid = await _novo_usuario(engine, tenant_id, f"aut{uuid.uuid4().hex[:6]}")
    await _dar_alcada(engine, tenant_id, uid, valor_maximo=valor_maximo)
    return uid


async def test_autorizar_gera_op_e_muda_status(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, _conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            op = await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                          debito_ids=[d.id])
        assert op.numero.startswith("OP-") and op.numero.endswith("-0001")
        assert op.valor_total == Decimal("1000.00")
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            hist = await deb.listar_historico(s, tenant_id=t.id, debito_id=d.id)
            debs_op = await aut.debitos_da_ordem(s, tenant_id=t.id, ordem_id=op.id)
        assert d2.status == "AUTORIZADO"
        assert hist[0].acao == "AUTORIZADO"
        assert [x.id for x in debs_op] == [d.id]
    finally:
        await _cleanup(admin_engine, t.id)


async def test_autorizar_sem_saldo_disponivel_422(admin_engine):
    # conta com saldo_inicial 100.00, débito de 1000.00 aprovado, autorizador com alçada →
    # autorizar_lote → 422 com 'saldo' na mensagem; débito continua APROVADO.


async def test_autorizar_acima_da_alcada_403(admin_engine):
    # alçada geral 500.00, débito 1000.00 → 403; sem alçada nenhuma → 403 também.


async def test_autorizar_por_solicitante_ou_aprovador_403(admin_engine):
    # autorizar_lote com usuario_id == solicitante → 403;
    # com usuario_id == aprovador → 403 (segregação via histórico).


async def test_comprometido_bloqueia_segunda_autorizacao(admin_engine):
    # conta saldo 1000.00; débito A de 800.00 AUTORIZADO (comprometido=800);
    # débito B de 500.00 aprovado → autorizar B → 422 (disponível 200 < 500).


async def test_autorizacao_em_lote_all_or_nothing(admin_engine):
    # dois débitos aprovados (600 + 600) numa conta com 1000:
    # autorizar_lote([a, b]) → 422 e NENHUM vira AUTORIZADO (rollback).
```

(Escrever todos completos, seguindo o padrão try/finally + `_cleanup`.)

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_autorizacao.py -q`
Expected: FAIL (módulo não existe).

- [ ] **Step 3: Implementar** — criar `backend/app/services/pagamentos_autorizacao.py`:

```python
"""Autorização de Pagamentos (R2) — autorizar em lote (saldo/alçada/segregação),
Ordem de Pagamento e consultas. Pagamento/estorno de parcela na Task 5."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Alcada, Debito, OrdemPagamento, OrdemPagamentoDebito
from . import pagamentos_caixa as caixa
from .pagamentos_debitos import (
    PagamentoDebitoError, _registrar_transicao, aprovadores_do_debito, obter_debito,
)


def _utcnow() -> datetime:
    return datetime.utcnow()


async def _alcada_do_usuario(db, *, tenant_id: int, usuario_id: int, id_natureza: int) -> Decimal:
    """Alçada específica da natureza; fallback geral (id_natureza IS NULL); sem alçada → 403."""
    especifica = (await db.execute(select(Alcada).where(
        Alcada.tenant_id == tenant_id, Alcada.id_usuario == usuario_id,
        Alcada.id_natureza == id_natureza, Alcada.excluido.is_(False)))).scalar_one_or_none()
    if especifica is not None:
        return especifica.valor_maximo
    geral = (await db.execute(select(Alcada).where(
        Alcada.tenant_id == tenant_id, Alcada.id_usuario == usuario_id,
        Alcada.id_natureza.is_(None), Alcada.excluido.is_(False)))).scalar_one_or_none()
    if geral is not None:
        return geral.valor_maximo
    raise PagamentoDebitoError("Usuário sem alçada cadastrada para autorizar esta natureza.",
                               status.HTTP_403_FORBIDDEN)


async def _proximo_numero_op(db, *, tenant_id: int) -> str:
    ano = _utcnow().year
    prefixo = f"OP-{ano}-"
    ultimo = (await db.execute(select(func.max(OrdemPagamento.numero)).where(
        OrdemPagamento.tenant_id == tenant_id,
        OrdemPagamento.numero.like(f"{prefixo}%")))).scalar_one_or_none()
    seq = int(ultimo.rsplit("-", 1)[1]) + 1 if ultimo else 1
    return f"{prefixo}{seq:04d}"


async def autorizar_lote(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                         debito_ids: list[int], ip: str | None = None) -> OrdemPagamento:
    """All-or-nothing: valida TODOS os débitos antes de mudar qualquer status."""
    debitos: list[Debito] = []
    for did in debito_ids:
        d = await obter_debito(db, tenant_id=tenant_id, debito_id=did)
        if d.status != "APROVADO":
            raise PagamentoDebitoError(
                f"Débito {did} não está APROVADO (está '{d.status}').", status.HTTP_409_CONFLICT)
        if usuario_id == d.id_usuario_solicitante:
            raise PagamentoDebitoError(
                f"Segregação de funções: o solicitante do débito {did} não pode autorizá-lo.",
                status.HTTP_403_FORBIDDEN)
        if usuario_id in await aprovadores_do_debito(db, tenant_id=tenant_id, debito_id=did):
            raise PagamentoDebitoError(
                f"Segregação de funções: quem aprovou o débito {did} não pode autorizá-lo.",
                status.HTTP_403_FORBIDDEN)
        limite = await _alcada_do_usuario(db, tenant_id=tenant_id, usuario_id=usuario_id,
                                          id_natureza=d.id_natureza)
        if d.valor_total > limite:
            raise PagamentoDebitoError(
                f"Débito {did} (R$ {d.valor_total}) excede a alçada do autorizador (R$ {limite}).",
                status.HTTP_403_FORBIDDEN)
        debitos.append(d)

    # saldo por conta: disponível deve cobrir o Σ do lote naquela conta
    por_conta: dict[int, Decimal] = {}
    for d in debitos:
        por_conta[d.id_conta] = por_conta.get(d.id_conta, Decimal("0")) + d.valor_total
    for conta_id, total in por_conta.items():
        saldo = await caixa.saldo_conta(db, tenant_id=tenant_id, conta_id=conta_id)
        if saldo.disponivel < total:
            raise PagamentoDebitoError(
                f"Saldo disponível insuficiente na conta {conta_id}: "
                f"disponível R$ {saldo.disponivel}, necessário R$ {total}.",
                status.HTTP_422_UNPROCESSABLE_ENTITY)

    op = OrdemPagamento(tenant_id=tenant_id,
                        numero=await _proximo_numero_op(db, tenant_id=tenant_id),
                        id_usuario_autorizador=usuario_id,
                        valor_total=sum((d.valor_total for d in debitos), Decimal("0")),
                        ip_origem=ip, criado_em=_utcnow())
    db.add(op); await db.flush()
    for d in debitos:
        db.add(OrdemPagamentoDebito(tenant_id=tenant_id, id_ordem=op.id, id_debito=d.id))
        _registrar_transicao(db, debito=d, novo_status="AUTORIZADO", acao="AUTORIZADO",
                             usuario_id=usuario_id, justificativa=f"OP {op.numero}", ip=ip)
        d.atualizado_em = _utcnow()
    await db.commit(); await db.refresh(op)
    return op


async def listar_ordens(db: AsyncSession, *, tenant_id: int) -> list[OrdemPagamento]:
    return list((await db.execute(select(OrdemPagamento).where(
        OrdemPagamento.tenant_id == tenant_id)
        .order_by(OrdemPagamento.id.desc()))).scalars().all())


async def obter_ordem(db: AsyncSession, *, tenant_id: int, ordem_id: int) -> OrdemPagamento:
    op = (await db.execute(select(OrdemPagamento).where(
        OrdemPagamento.id == ordem_id,
        OrdemPagamento.tenant_id == tenant_id))).scalar_one_or_none()
    if op is None:
        raise PagamentoDebitoError("Ordem de pagamento não encontrada", status.HTTP_404_NOT_FOUND)
    return op


async def debitos_da_ordem(db: AsyncSession, *, tenant_id: int, ordem_id: int) -> list[Debito]:
    return list((await db.execute(select(Debito)
        .join(OrdemPagamentoDebito, OrdemPagamentoDebito.id_debito == Debito.id)
        .where(OrdemPagamentoDebito.tenant_id == tenant_id,
               OrdemPagamentoDebito.id_ordem == ordem_id)
        .order_by(Debito.id))).scalars().all())
```

- [ ] **Step 4: Rodar os testes**

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_autorizacao.py tests/test_pagamentos_caixa.py -q`
Expected: PASS (novos + regressão do caixa com os campos default).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pagamentos_caixa.py backend/app/services/pagamentos_autorizacao.py \
  backend/tests/test_pagamentos_autorizacao.py
git commit -m "feat(pagamentos): autorização em lote — saldo/alçada/segregação + Ordem de Pagamento"
```

---

### Task 5: Pagar e estornar parcela (deduz/repõe saldo)

**Files:**
- Modify: `backend/app/services/pagamentos_autorizacao.py`
- Test: `backend/tests/test_pagamentos_autorizacao.py` (acrescentar)

**Interfaces:**
- Consumes: Task 4; `MovimentacaoConta` model.
- Produces:
  - `pagar_parcela(db, *, tenant_id, usuario_id, parcela_id, forma_pagamento, data_pagamento=None, ip=None) -> Parcela`
  - `estornar_parcela(db, *, tenant_id, usuario_id, parcela_id, justificativa, ip=None) -> Parcela`
  - `obter_parcela(db, *, tenant_id, parcela_id) -> Parcela` (404)

- [ ] **Step 1: Testes que falham** — acrescentar em `test_pagamentos_autorizacao.py`:

```python
async def test_pagar_parcela_deduz_saldo_e_finaliza_debito(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, conta = await _debito_aprovado(
            admin_engine, t.id, valor="1000.00",
            parcelas=[ParcelaCreate(numero=1, valor="600.00", vencimento="2026-08-01"),
                      ParcelaCreate(numero=2, valor="400.00", vencimento="2026-09-01")])
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador, debito_ids=[d.id])
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            p1 = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                         parcela_id=parcelas[0].id, forma_pagamento="PIX")
        assert p1.status == "PAGA" and p1.id_movimentacao is not None
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d2.status == "PAGO_PARCIAL"
        assert saldo.saldo_atual == Decimal("9400.00")
        assert saldo.comprometido == Decimal("400.00")
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[1].id, forma_pagamento="TED")
        async with _sm(admin_engine)() as s:
            d3 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo2 = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d3.status == "PAGO"
        assert saldo2.saldo_atual == Decimal("9000.00")
        assert saldo2.comprometido == Decimal("0")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_pagar_parcela_de_debito_nao_autorizado_409(admin_engine):
    # débito APROVADO (não autorizado) → pagar_parcela → 409.


async def test_pagar_parcela_ja_paga_409(admin_engine):
    # pagar a mesma parcela duas vezes → segunda dá 409.


async def test_estornar_parcela_repoe_saldo_e_reabre(admin_engine):
    # após pagar as 2 parcelas (débito PAGO): estornar parcela 2 com justificativa →
    # mov ENTRADA/ESTORNO 400 criada; parcela volta A_PAGAR (sem data/forma/id_movimentacao);
    # débito volta PAGO_PARCIAL; saldo volta a 9400.
    # estornar parcela 1 também → débito volta AUTORIZADO; saldo 10000.
```

(Escrever completos; usar helper `_debito_autorizado(engine, tenant_id, ...)` que encadeia `_debito_aprovado` + `_dar_alcada` + `autorizar_lote` com um 3º usuário.)

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_autorizacao.py -q`
Expected: FAIL (`AttributeError: pagar_parcela`).

- [ ] **Step 2: Implementar** — acrescentar em `pagamentos_autorizacao.py` (imports extras: `date` de datetime, `MovimentacaoConta`, `Parcela` de `..models`, `listar_parcelas` de `.pagamentos_debitos`):

```python
async def obter_parcela(db: AsyncSession, *, tenant_id: int, parcela_id: int) -> Parcela:
    p = (await db.execute(select(Parcela).where(Parcela.id == parcela_id,
        Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False)))).scalar_one_or_none()
    if p is None:
        raise PagamentoDebitoError("Parcela não encontrada", status.HTTP_404_NOT_FOUND)
    return p


async def pagar_parcela(db: AsyncSession, *, tenant_id: int, usuario_id: int, parcela_id: int,
                        forma_pagamento: str, data_pagamento: date | None = None,
                        ip: str | None = None) -> Parcela:
    """Atômico: movimentação SAIDA/PAGAMENTO + parcela PAGA + status do débito, num commit."""
    p = await obter_parcela(db, tenant_id=tenant_id, parcela_id=parcela_id)
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=p.id_debito)
    if d.status not in ("AUTORIZADO", "PAGO_PARCIAL"):
        raise PagamentoDebitoError(
            f"Débito não autorizado para pagamento (está '{d.status}').", status.HTTP_409_CONFLICT)
    if p.status != "A_PAGAR":
        raise PagamentoDebitoError(f"Parcela não está a pagar (está '{p.status}').",
                                   status.HTTP_409_CONFLICT)
    quando = data_pagamento or _utcnow().date()
    mov = MovimentacaoConta(tenant_id=tenant_id, id_conta=d.id_conta, tipo="SAIDA",
                            valor=p.valor, origem="PAGAMENTO", id_debito=d.id, id_parcela=p.id,
                            data=quando, id_usuario=usuario_id,
                            descricao=f"Pagamento parcela {p.numero} — débito #{d.id}",
                            criado_em=_utcnow())
    db.add(mov); await db.flush()
    p.status = "PAGA"; p.data_pagamento = quando
    p.forma_pagamento = forma_pagamento; p.id_movimentacao = mov.id; p.atualizado_em = _utcnow()
    todas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    pendentes = [x for x in todas if x.id != p.id and x.status == "A_PAGAR"]
    novo = "PAGO" if not pendentes else "PAGO_PARCIAL"
    _registrar_transicao(db, debito=d, novo_status=novo, acao="PAGAMENTO", usuario_id=usuario_id,
                         justificativa=f"Parcela {p.numero} — {forma_pagamento}", ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(p)
    return p


async def estornar_parcela(db: AsyncSession, *, tenant_id: int, usuario_id: int, parcela_id: int,
                           justificativa: str, ip: str | None = None) -> Parcela:
    p = await obter_parcela(db, tenant_id=tenant_id, parcela_id=parcela_id)
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=p.id_debito)
    if p.status != "PAGA":
        raise PagamentoDebitoError("Só parcelas pagas podem ser estornadas.", status.HTTP_409_CONFLICT)
    mov = MovimentacaoConta(tenant_id=tenant_id, id_conta=d.id_conta, tipo="ENTRADA",
                            valor=p.valor, origem="ESTORNO", id_debito=d.id, id_parcela=p.id,
                            data=_utcnow().date(), id_usuario=usuario_id,
                            descricao=f"Estorno parcela {p.numero} — débito #{d.id}: {justificativa}",
                            criado_em=_utcnow())
    db.add(mov)
    p.status = "A_PAGAR"; p.data_pagamento = None
    p.forma_pagamento = None; p.id_movimentacao = None; p.atualizado_em = _utcnow()
    todas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    alguma_paga = any(x.id != p.id and x.status == "PAGA" for x in todas)
    novo = "PAGO_PARCIAL" if alguma_paga else "AUTORIZADO"
    _registrar_transicao(db, debito=d, novo_status=novo, acao="ESTORNO", usuario_id=usuario_id,
                         justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(p)
    return p
```

- [ ] **Step 3: Rodar TODOS os testes de pagamentos**

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_debitos.py tests/test_pagamentos_autorizacao.py tests/test_pagamentos_caixa.py tests/test_pagamentos_cadastros.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/pagamentos_autorizacao.py backend/tests/test_pagamentos_autorizacao.py
git commit -m "feat(pagamentos): pagar/estornar parcela — movimentação PAGAMENTO/ESTORNO atômica"
```

---

### Task 6: Routers — débitos, autorização, parcelas, OP em PDF, minha-fila

**Files:**
- Modify: `backend/app/auth/perms.py` (+ `require_any_permission`)
- Create: `backend/app/routers/pagamentos_debitos.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: Tasks 2–5 (todas as funções de serviço); `load_permissions` de `services/permissoes.py`; `html_to_pdf_bytes(corpo_html, *, titulo=None) -> bytes` de `services/html_pdf.py`.
- Produces: endpoints REST descritos abaixo; `require_any_permission(*codigos)` em `auth/perms.py`.

Mapa de endpoints (prefixo `/api/v2`):

| Método | Rota | Permissão |
|---|---|---|
| GET | `/pagamentos/debitos?status=&meus=` | any(solicitar, aprovar, autorizar, pagar, cadastro) |
| POST | `/pagamentos/debitos` | `pagamento_solicitar` (inserir) |
| GET | `/pagamentos/debitos/{id}` (detalhe c/ parcelas+histórico) | any(...) |
| PUT | `/pagamentos/debitos/{id}` | `pagamento_solicitar` (atualizar) |
| DELETE | `/pagamentos/debitos/{id}` | `pagamento_solicitar` (excluir) |
| POST | `/pagamentos/debitos/{id}/enviar` | `pagamento_solicitar` |
| POST | `/pagamentos/debitos/{id}/aprovar` | `pagamento_aprovar` |
| POST | `/pagamentos/debitos/{id}/devolver` (body JustificativaIn) | `pagamento_aprovar` |
| POST | `/pagamentos/debitos/{id}/rejeitar` (body JustificativaIn) | `pagamento_aprovar` |
| POST | `/pagamentos/debitos/{id}/cancelar` (body JustificativaIn) | `pagamento_solicitar` |
| POST | `/pagamentos/autorizacoes` (body AutorizarLoteIn) | `pagamento_autorizar` |
| GET | `/pagamentos/ordens-pagamento` | any(autorizar, pagar) |
| GET | `/pagamentos/ordens-pagamento/{id}/pdf` | any(autorizar, pagar) |
| POST | `/pagamentos/parcelas/{id}/pagar` (body PagarParcelaIn) | `pagamento_pagar` |
| POST | `/pagamentos/parcelas/{id}/estornar` (body JustificativaIn) | `pagamento_pagar` |
| GET | `/pagamentos/minha-fila` | usuário autenticado (buckets por permissão) |

- [ ] **Step 1: `require_any_permission`** — acrescentar em `backend/app/auth/perms.py`:

```python
def require_any_permission(*codigos: str):
    """Dependency que exige QUALQUER uma das transações (leitura). Super-usuário bypassa."""

    async def _check(
        user: Usuario = Depends(get_current_user),
        tenant_id: int = Depends(require_tenant_id),
        db: AsyncSession = Depends(get_db),
    ) -> Usuario:
        perms = await load_permissions(db, user.id, tenant_id=tenant_id)
        if perms.is_super_usuario or any(p.codigo in codigos for p in perms.items):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem permissão (requer uma de: {', '.join(codigos)})",
        )

    return _check
```

- [ ] **Step 2: Router** — criar `backend/app/routers/pagamentos_debitos.py`:

```python
"""Rotas de Débitos/Autorização/Pagamento (R2). IP do cliente vai para o histórico."""
from __future__ import annotations

import html as _htmlmod

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.perms import require_any_permission, require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import (
    AutorizarLoteIn, DebitoCreate, DebitoDetalheOut, DebitoHistoricoOut, DebitoOut,
    DebitoUpdate, JustificativaIn, MinhaFilaOut, OrdemPagamentoOut, PagarParcelaIn,
    ParcelaFilaOut, ParcelaOut,
)
from ..services import pagamentos_autorizacao as aut
from ..services import pagamentos_debitos as svc
from ..services.html_pdf import html_to_pdf_bytes
from ..services.permissoes import load_permissions

PERMS_LEITURA = ("pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar",
                 "pagamento_pagar", "pagamento_cadastro")

debitos_router = APIRouter(prefix="/pagamentos/debitos", tags=["pagamentos-debitos"])
operacoes_router = APIRouter(prefix="/pagamentos", tags=["pagamentos-operacoes"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _out(db, tenant_id: int, debitos) -> list[DebitoOut]:
    nomes = await svc.nomes_fornecedores(db, tenant_id=tenant_id,
                                         ids={d.id_fornecedor for d in debitos})
    return [DebitoOut.model_validate(svc.debito_out(d, nome_fornecedor=nomes.get(d.id_fornecedor, "?")))
            for d in debitos]


@debitos_router.get("", response_model=list[DebitoOut])
async def list_debitos(status_f: str | None = None, meus: bool = False,
                       usuario: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                       tenant_id: int = Depends(require_tenant_id),
                       db: AsyncSession = Depends(get_db)):
    rows = await svc.listar_debitos(db, tenant_id=tenant_id, status_f=status_f,
                                    solicitante_id=usuario.id if meus else None)
    return await _out(db, tenant_id, rows)


@debitos_router.get("/{debito_id}", response_model=DebitoDetalheOut)
async def get_debito(debito_id: int,
                     _: Usuario = Depends(require_any_permission(*PERMS_LEITURA)),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    d = await svc.obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    base = (await _out(db, tenant_id, [d]))[0].model_dump()
    parcelas = await svc.listar_parcelas(db, tenant_id=tenant_id, debito_id=debito_id)
    hist = await svc.listar_historico(db, tenant_id=tenant_id, debito_id=debito_id)
    nomes_u = await svc.nomes_usuarios(db, tenant_id=tenant_id,
                                       ids={h.id_usuario for h in hist if h.id_usuario})
    base["parcelas"] = [ParcelaOut.model_validate(p) for p in parcelas]
    base["historico"] = [DebitoHistoricoOut(
        id=h.id, acao=h.acao, status_anterior=h.status_anterior, status_novo=h.status_novo,
        justificativa=h.justificativa, id_usuario=h.id_usuario,
        nome_usuario=nomes_u.get(h.id_usuario), criado_em=h.criado_em) for h in hist]
    return DebitoDetalheOut.model_validate(base)


@debitos_router.post("", response_model=DebitoOut, status_code=status.HTTP_201_CREATED)
async def create_debito(payload: DebitoCreate,
                        usuario: Usuario = Depends(require_permission("pagamento_solicitar", "inserir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    d = await svc.criar_debito(db, tenant_id=tenant_id, usuario_id=usuario.id, payload=payload)
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.put("/{debito_id}", response_model=DebitoOut)
async def update_debito(debito_id: int, payload: DebitoUpdate,
                        usuario: Usuario = Depends(require_permission("pagamento_solicitar", "atualizar")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    d = await svc.atualizar_debito(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id, payload=payload)
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.delete("/{debito_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debito(debito_id: int,
                        _: Usuario = Depends(require_permission("pagamento_solicitar", "excluir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    await svc.excluir_debito(db, tenant_id=tenant_id, debito_id=debito_id)


@debitos_router.post("/{debito_id}/enviar", response_model=DebitoOut)
async def enviar(debito_id: int, request: Request,
                 usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                 tenant_id: int = Depends(require_tenant_id),
                 db: AsyncSession = Depends(get_db)):
    d = await svc.enviar_aprovacao(db, tenant_id=tenant_id, debito_id=debito_id,
                                   usuario_id=usuario.id, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/aprovar", response_model=DebitoOut)
async def aprovar(debito_id: int, request: Request,
                  usuario: Usuario = Depends(require_permission("pagamento_aprovar")),
                  tenant_id: int = Depends(require_tenant_id),
                  db: AsyncSession = Depends(get_db)):
    d = await svc.aprovar(db, tenant_id=tenant_id, debito_id=debito_id,
                          usuario_id=usuario.id, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/devolver", response_model=DebitoOut)
async def devolver(debito_id: int, payload: JustificativaIn, request: Request,
                   usuario: Usuario = Depends(require_permission("pagamento_aprovar")),
                   tenant_id: int = Depends(require_tenant_id),
                   db: AsyncSession = Depends(get_db)):
    d = await svc.devolver(db, tenant_id=tenant_id, debito_id=debito_id, usuario_id=usuario.id,
                           justificativa=payload.justificativa, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/rejeitar", response_model=DebitoOut)
async def rejeitar(debito_id: int, payload: JustificativaIn, request: Request,
                   usuario: Usuario = Depends(require_permission("pagamento_aprovar")),
                   tenant_id: int = Depends(require_tenant_id),
                   db: AsyncSession = Depends(get_db)):
    d = await svc.rejeitar(db, tenant_id=tenant_id, debito_id=debito_id, usuario_id=usuario.id,
                           justificativa=payload.justificativa, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


@debitos_router.post("/{debito_id}/cancelar", response_model=DebitoOut)
async def cancelar(debito_id: int, payload: JustificativaIn, request: Request,
                   usuario: Usuario = Depends(require_permission("pagamento_solicitar")),
                   tenant_id: int = Depends(require_tenant_id),
                   db: AsyncSession = Depends(get_db)):
    d = await svc.cancelar(db, tenant_id=tenant_id, debito_id=debito_id, usuario_id=usuario.id,
                           justificativa=payload.justificativa, ip=_ip(request))
    return (await _out(db, tenant_id, [d]))[0]


async def _op_out(db, tenant_id: int, ops) -> list[OrdemPagamentoOut]:
    nomes = await svc.nomes_usuarios(db, tenant_id=tenant_id,
                                     ids={o.id_usuario_autorizador for o in ops})
    out = []
    for o in ops:
        debs = await aut.debitos_da_ordem(db, tenant_id=tenant_id, ordem_id=o.id)
        out.append(OrdemPagamentoOut(
            id=o.id, numero=o.numero, valor_total=o.valor_total,
            id_usuario_autorizador=o.id_usuario_autorizador,
            nome_autorizador=nomes.get(o.id_usuario_autorizador),
            qtd_debitos=len(debs), criado_em=o.criado_em))
    return out


@operacoes_router.post("/autorizacoes", response_model=OrdemPagamentoOut,
                       status_code=status.HTTP_201_CREATED)
async def autorizar(payload: AutorizarLoteIn, request: Request,
                    usuario: Usuario = Depends(require_permission("pagamento_autorizar")),
                    tenant_id: int = Depends(require_tenant_id),
                    db: AsyncSession = Depends(get_db)):
    op = await aut.autorizar_lote(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                  debito_ids=payload.debito_ids, ip=_ip(request))
    return (await _op_out(db, tenant_id, [op]))[0]


@operacoes_router.get("/ordens-pagamento", response_model=list[OrdemPagamentoOut])
async def list_ordens(_: Usuario = Depends(require_any_permission("pagamento_autorizar", "pagamento_pagar")),
                      tenant_id: int = Depends(require_tenant_id),
                      db: AsyncSession = Depends(get_db)):
    return await _op_out(db, tenant_id, await aut.listar_ordens(db, tenant_id=tenant_id))


@operacoes_router.get("/ordens-pagamento/{ordem_id}/pdf")
async def op_pdf(ordem_id: int,
                 _: Usuario = Depends(require_any_permission("pagamento_autorizar", "pagamento_pagar")),
                 tenant_id: int = Depends(require_tenant_id),
                 db: AsyncSession = Depends(get_db)):
    op = await aut.obter_ordem(db, tenant_id=tenant_id, ordem_id=ordem_id)
    debs = await aut.debitos_da_ordem(db, tenant_id=tenant_id, ordem_id=ordem_id)
    nomes_f = await svc.nomes_fornecedores(db, tenant_id=tenant_id,
                                           ids={d.id_fornecedor for d in debs})
    nomes_u = await svc.nomes_usuarios(db, tenant_id=tenant_id, ids={op.id_usuario_autorizador})
    esc = _htmlmod.escape
    linhas = "".join(
        f"<tr><td>{d.id}</td><td>{esc(nomes_f.get(d.id_fornecedor, '?'))}</td>"
        f"<td>{esc(d.descricao)}</td><td>{esc(d.competencia)}</td>"
        f"<td style='text-align:right'>R$ {d.valor_total:,.2f}</td></tr>" for d in debs)
    corpo = f"""
    <p><strong>Autorizador:</strong> {esc(nomes_u.get(op.id_usuario_autorizador, '?'))}<br>
    <strong>Data:</strong> {op.criado_em.strftime('%d/%m/%Y %H:%M')}<br>
    <strong>Valor total:</strong> R$ {op.valor_total:,.2f}</p>
    <table style="width:100%; border-collapse:collapse" border="1" cellpadding="6">
      <tr><th>Débito</th><th>Fornecedor</th><th>Descrição</th><th>Competência</th><th>Valor</th></tr>
      {linhas}
    </table>
    <p style="margin-top:40px">Autorizo o pagamento das despesas acima relacionadas
    (art. 64, Lei nº 4.320/64).</p>
    <p style="margin-top:60px; text-align:center">_______________________________<br>
    {esc(nomes_u.get(op.id_usuario_autorizador, '?'))}<br>Autorizador de Despesa</p>
    """
    pdf = html_to_pdf_bytes(corpo, titulo=f"Ordem de Pagamento {op.numero}")
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{op.numero}.pdf"'})


@operacoes_router.post("/parcelas/{parcela_id}/pagar", response_model=ParcelaOut)
async def pagar(parcela_id: int, payload: PagarParcelaIn, request: Request,
                usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                tenant_id: int = Depends(require_tenant_id),
                db: AsyncSession = Depends(get_db)):
    p = await aut.pagar_parcela(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                parcela_id=parcela_id, forma_pagamento=payload.forma_pagamento,
                                data_pagamento=payload.data_pagamento, ip=_ip(request))
    return ParcelaOut.model_validate(p)


@operacoes_router.post("/parcelas/{parcela_id}/estornar", response_model=ParcelaOut)
async def estornar(parcela_id: int, payload: JustificativaIn, request: Request,
                   usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                   tenant_id: int = Depends(require_tenant_id),
                   db: AsyncSession = Depends(get_db)):
    p = await aut.estornar_parcela(db, tenant_id=tenant_id, usuario_id=usuario.id,
                                   parcela_id=parcela_id, justificativa=payload.justificativa,
                                   ip=_ip(request))
    return ParcelaOut.model_validate(p)


@operacoes_router.get("/minha-fila", response_model=MinhaFilaOut)
async def minha_fila(usuario: Usuario = Depends(get_current_user),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    from datetime import date as _date
    perms = await load_permissions(db, usuario.id, tenant_id=tenant_id)
    tem = (lambda c: True) if perms.is_super_usuario else \
        (lambda c: any(p.codigo == c for p in perms.items))
    fila = MinhaFilaOut()
    if tem("pagamento_solicitar"):
        rows = await svc.listar_debitos(db, tenant_id=tenant_id, status_f="RASCUNHO",
                                        solicitante_id=usuario.id)
        fila.solicitar = await _out(db, tenant_id, rows)
    if tem("pagamento_aprovar"):
        rows = await svc.listar_debitos(db, tenant_id=tenant_id, status_f="AGUARDANDO_APROVACAO")
        fila.aprovar = await _out(db, tenant_id, rows)
    if tem("pagamento_autorizar"):
        rows = await svc.listar_debitos(db, tenant_id=tenant_id, status_f="APROVADO")
        fila.autorizar = await _out(db, tenant_id, rows)
    if tem("pagamento_pagar"):
        parcelas = []
        for st in ("AUTORIZADO", "PAGO_PARCIAL"):
            for d in await svc.listar_debitos(db, tenant_id=tenant_id, status_f=st):
                nomes = await svc.nomes_fornecedores(db, tenant_id=tenant_id, ids={d.id_fornecedor})
                for p in await svc.listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id):
                    if p.status == "A_PAGAR":
                        parcelas.append(ParcelaFilaOut(
                            id=p.id, id_debito=d.id, numero=p.numero, valor=p.valor,
                            vencimento=p.vencimento, nome_fornecedor=nomes.get(d.id_fornecedor, "?"),
                            descricao_debito=d.descricao, vencida=p.vencimento < _date.today()))
        fila.pagar = sorted(parcelas, key=lambda x: x.vencimento)
    return fila
```

- [ ] **Step 3: Registrar em `main.py`** — no import de routers acrescentar `pagamentos_debitos`; após a linha do `pagamentos_caixa.caixa_router`:

```python
app.include_router(pagamentos_debitos.debitos_router, prefix="/api/v2")
app.include_router(pagamentos_debitos.operacoes_router, prefix="/api/v2")
```

- [ ] **Step 4: Smoke** — subir/reiniciar backend e conferir:

Run: `docker restart aprimora-py-backend && sleep 5 && docker exec aprimora-py-backend python -c "from app.main import app; print(len([r for r in app.routes if '/pagamentos/' in getattr(r, 'path', '')]))"`
Expected: número ≥ 30 (rotas registradas, sem erro de import).
Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_debitos.py tests/test_pagamentos_autorizacao.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/perms.py backend/app/routers/pagamentos_debitos.py backend/app/main.py
git commit -m "feat(pagamentos): API de débitos/autorização/pagamento + OP em PDF + minha-fila"
```

---

### Task 7: Frontend — api.ts + Contas a pagar (lista + criar + detalhe)

**Files:**
- Modify: `frontend/lib/api.ts`
- Create: `frontend/app/(app)/pagamentos/contas-a-pagar/page.tsx`
- Create: `frontend/app/(app)/pagamentos/contas-a-pagar/[id]/page.tsx`

**Interfaces:**
- Consumes: endpoints da Task 6; componentes `Dialog`, `Input`, `Select`, `Label`, `Button`, `Table`, `useToast`, `useConfirm`; `can()` de `frontend/lib/auth.tsx` (`const { can } = useAuth()`).
- Produces: `api.pagamentos.debitos.{list,get,create,update,remove,enviar,aprovar,devolver,rejeitar,cancelar}`, `api.pagamentos.autorizar(debitoIds)`, `api.pagamentos.ordens.{list,pdfUrl}`, `api.pagamentos.parcelas.{pagar,estornar}`, `api.pagamentos.minhaFila()`; tipos `Debito`, `DebitoDetalhe`, `Parcela`, `DebitoHistorico`, `OrdemPagamento`, `MinhaFila`, `ParcelaFila`.

- [ ] **Step 1: Tipos + client em `api.ts`** — junto aos tipos de pagamentos existentes:

```typescript
export type StatusDebito =
  | "RASCUNHO" | "AGUARDANDO_APROVACAO" | "APROVADO" | "AUTORIZADO"
  | "PAGO_PARCIAL" | "PAGO" | "REJEITADO" | "CANCELADO";

export interface Parcela {
  id: number; id_debito: number; numero: number; valor: string; vencimento: string;
  status: "A_PAGAR" | "PAGA" | "CANCELADA"; data_pagamento: string | null;
  forma_pagamento: string | null; id_movimentacao: number | null;
}

export interface Debito {
  id: number; id_fornecedor: number; nome_fornecedor: string; id_natureza: number;
  id_conta: number; id_contrato: number | null; valor_total: string; competencia: string;
  numero_ne: string | null; numero_nf: string | null; criticidade: string; urgente: boolean;
  justificativa_urgencia: string | null; descricao: string; status: StatusDebito;
  id_usuario_solicitante: number; criado_em: string; atualizado_em: string | null;
}

export interface DebitoHistorico {
  id: number; acao: string; status_anterior: string | null; status_novo: string;
  justificativa: string | null; id_usuario: number | null; nome_usuario: string | null;
  criado_em: string;
}

export interface DebitoDetalhe extends Debito {
  parcelas: Parcela[]; historico: DebitoHistorico[];
}

export interface OrdemPagamento {
  id: number; numero: string; valor_total: string; id_usuario_autorizador: number;
  nome_autorizador: string | null; qtd_debitos: number; criado_em: string;
}

export interface ParcelaFila {
  id: number; id_debito: number; numero: number; valor: string; vencimento: string;
  nome_fornecedor: string; descricao_debito: string; vencida: boolean;
}

export interface MinhaFila {
  solicitar: Debito[] | null; aprovar: Debito[] | null;
  autorizar: Debito[] | null; pagar: ParcelaFila[] | null;
}
```

Na seção `pagamentos` (irmãos de `cadastros`/`caixa`):

```typescript
    debitos: {
      list: (params?: { status?: string; meus?: boolean }) =>
        request<Debito[]>(`/pagamentos/debitos${qs({ status_f: params?.status, meus: params?.meus })}`),
      get: (id: number) => request<DebitoDetalhe>(`/pagamentos/debitos/${id}`),
      create: (data: unknown) =>
        request<Debito>("/pagamentos/debitos", { method: "POST", body: JSON.stringify(data) }),
      update: (id: number, data: unknown) =>
        request<Debito>(`/pagamentos/debitos/${id}`, { method: "PUT", body: JSON.stringify(data) }),
      remove: (id: number) => request<void>(`/pagamentos/debitos/${id}`, { method: "DELETE" }),
      enviar: (id: number) => request<Debito>(`/pagamentos/debitos/${id}/enviar`, { method: "POST" }),
      aprovar: (id: number) => request<Debito>(`/pagamentos/debitos/${id}/aprovar`, { method: "POST" }),
      devolver: (id: number, justificativa: string) =>
        request<Debito>(`/pagamentos/debitos/${id}/devolver`, {
          method: "POST", body: JSON.stringify({ justificativa }) }),
      rejeitar: (id: number, justificativa: string) =>
        request<Debito>(`/pagamentos/debitos/${id}/rejeitar`, {
          method: "POST", body: JSON.stringify({ justificativa }) }),
      cancelar: (id: number, justificativa: string) =>
        request<Debito>(`/pagamentos/debitos/${id}/cancelar`, {
          method: "POST", body: JSON.stringify({ justificativa }) }),
    },
    autorizar: (debitoIds: number[]) =>
      request<OrdemPagamento>("/pagamentos/autorizacoes", {
        method: "POST", body: JSON.stringify({ debito_ids: debitoIds }) }),
    ordens: {
      list: () => request<OrdemPagamento[]>("/pagamentos/ordens-pagamento"),
      pdfUrl: (id: number) => `${API_BASE}/pagamentos/ordens-pagamento/${id}/pdf`,
    },
    parcelas: {
      pagar: (id: number, data: { forma_pagamento: string; data_pagamento?: string | null }) =>
        request<Parcela>(`/pagamentos/parcelas/${id}/pagar`, {
          method: "POST", body: JSON.stringify(data) }),
      estornar: (id: number, justificativa: string) =>
        request<Parcela>(`/pagamentos/parcelas/${id}/estornar`, {
          method: "POST", body: JSON.stringify({ justificativa }) }),
    },
    minhaFila: () => request<MinhaFila>("/pagamentos/minha-fila"),
```

> Conferir o nome real da constante base (`API_BASE` ou equivalente) usada em `api.ts` para montar `pdfUrl` — usar o mesmo mecanismo dos downloads existentes (ex.: anexos) se houver helper pronto.

- [ ] **Step 2: Página lista + criar** — criar `frontend/app/(app)/pagamentos/contas-a-pagar/page.tsx`. Requisitos funcionais (implementar no padrão da tela `caixa/page.tsx` — react-query + Dialog + Table):

- Tabs/filtro por status (`Todos | Rascunho | Aguardando aprovação | Aprovado | Autorizado | Pago parcial | Pago | Rejeitado | Cancelado`) via `useState` + `api.pagamentos.debitos.list({ status })`.
- Tabela: Fornecedor, Descrição, Competência, Valor, Criticidade (+ selo "URGENTE" quando `urgente`), Status (badge com as cores: RASCUNHO=neutro, AGUARDANDO_APROVACAO=warning, APROVADO=info, AUTORIZADO=info, PAGO_PARCIAL=warning, PAGO=success, REJEITADO/CANCELADO=danger), link da linha → `/pagamentos/contas-a-pagar/${id}`.
- Botão "Novo débito" (visível com `can("pagamento_solicitar", "inserir")`): Dialog `size="lg"` com selects de fornecedor/natureza/conta (queries `api.pagamentos.cadastros.*.list()`), contrato opcional, valor total, competência (`<Input type="month">`), NE/NF, criticidade, urgente + justificativa, descrição, e um editor de **parcelas** (linhas dinâmicas numero/valor/vencimento com botões adicionar/remover; mostrar Σ e alertar visualmente se Σ ≠ valor total).
- Valores monetários: `Number(x).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })`.
- `onSuccess`: invalidar `["pag-debitos"]`, toast "Débito criado.".

- [ ] **Step 3: Página detalhe** — criar `frontend/app/(app)/pagamentos/contas-a-pagar/[id]/page.tsx`. Requisitos:

- `useParams()` para o id; query `["pag-debito", id]` → `api.pagamentos.debitos.get(id)`.
- Cabeçalho: fornecedor, descrição, valor, competência, status (badge), criticidade/urgente.
- Seção **Parcelas**: tabela numero/valor/vencimento/status/forma/data pagamento; por parcela `A_PAGAR` com débito `AUTORIZADO|PAGO_PARCIAL` e `can("pagamento_pagar")` → botão "Pagar" (Dialog: forma de pagamento select PIX/TED/BOLETO/DINHEIRO/OUTRO + data opcional); por parcela `PAGA` e `can("pagamento_pagar")` → botão "Estornar" (Dialog com justificativa obrigatória).
- Seção **Ações do fluxo** (renderizar conforme `status` + permissão):
  - RASCUNHO + `can("pagamento_solicitar")`: "Enviar para aprovação"; "Cancelar" (justificativa).
  - AGUARDANDO_APROVACAO + `can("pagamento_aprovar")`: "Aprovar", "Devolver" (justificativa), "Rejeitar" (justificativa).
  - APROVADO + `can("pagamento_autorizar")`: "Autorizar" → chama `api.pagamentos.autorizar([id])` e mostra toast com o número da OP.
- Seção **Trilha** (histórico): lista vertical `acao` + `status_anterior→status_novo` + justificativa + nome_usuario + data (mesmo estilo da timeline de situação do fornecedor).
- Toda mutação: invalidar `["pag-debito", id]` e `["pag-debitos"]`; erros via toast.

- [ ] **Step 4: tsc**

Run: `docker exec aprimora-py-frontend ./node_modules/.bin/tsc --noEmit`
Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts "frontend/app/(app)/pagamentos/contas-a-pagar/"
git commit -m "feat(pagamentos): tela Contas a pagar — lista, criar débito com parcelas e detalhe com ações"
```

---

### Task 8: Frontend — home "O que precisa de mim" + caixa comprometido/disponível + menu

**Files:**
- Create: `frontend/app/(app)/pagamentos/page.tsx`
- Modify: `frontend/app/(app)/pagamentos/caixa/page.tsx`
- Modify: `frontend/components/Sidebar.tsx`
- Modify: `frontend/lib/api.ts` (tipos `SaldoConta`/`ContaSaldoPainel`: + `comprometido: string; disponivel: string`)

**Interfaces:**
- Consumes: `api.pagamentos.minhaFila()`, `api.pagamentos.caixa.painel()`, `api.pagamentos.autorizar(ids)`, tipos da Task 7.

- [ ] **Step 1: Home do módulo** — criar `frontend/app/(app)/pagamentos/page.tsx`:

- Título "Pagamentos — o que precisa de mim".
- Query `["pag-fila"]` → `api.pagamentos.minhaFila()`. Para cada bucket não-nulo, um card com contador e lista:
  - **Meus rascunhos** (`solicitar`): descrição/fornecedor/valor + link p/ detalhe (lá tem "Enviar").
  - **Aguardando minha aprovação** (`aprovar`): idem, link p/ detalhe.
  - **Aguardando autorização** (`autorizar`): com **checkbox por linha + botão "Autorizar selecionados"** → `api.pagamentos.autorizar(selecionados)`; toast com número da OP; invalidar `["pag-fila"]`.
  - **Parcelas a pagar** (`pagar`): fornecedor/parcela/valor/vencimento, destaque vermelho quando `vencida`; link p/ detalhe do débito.
- Bucket vazio → texto "Nada pendente." Buckets nulos (sem permissão) → não renderizar o card.
- Abaixo dos cards, seção "Caixa" compacta: reusar `api.pagamentos.caixa.painel()` mostrando Conta | Disponível | Comprometido | Saldo atual (link "ver caixa" → `/pagamentos/caixa`).

- [ ] **Step 2: Caixa** — em `caixa/page.tsx`, adicionar as colunas **Comprometido** e **Disponível** na tabela do painel (entre "Saídas" e "Saldo atual"), formatação BRL igual às demais.

- [ ] **Step 3: Sidebar** — em `components/Sidebar.tsx`:

1. Ampliar o tipo do item de nav: `perm?: string; anyOf?: string[];`
2. No filtro de visibilidade (linha ~348):

```tsx
const visible = group.items.filter(
  (item) =>
    (!item.perm && !item.anyOf) ||
    (item.perm && can(item.perm)) ||
    (item.anyOf && item.anyOf.some((p) => can(p))),
);
```

3. No grupo "Pagamentos", inserir ANTES de "Caixa":

```tsx
{ label: "Início", href: "/pagamentos", icon: Inbox,
  anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"] },
{ label: "Contas a pagar", href: "/pagamentos/contas-a-pagar", icon: ClipboardList,
  anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar"] },
```

(`Inbox`/`ClipboardList` já são importados de lucide-react no arquivo; conferir e ajustar ícones se houver conflito visual.)

- [ ] **Step 4: tsc**

Run: `docker exec aprimora-py-frontend ./node_modules/.bin/tsc --noEmit`
Expected: sem erros.

- [ ] **Step 5: Commit**

```bash
git add "frontend/app/(app)/pagamentos/page.tsx" "frontend/app/(app)/pagamentos/caixa/page.tsx" \
  frontend/components/Sidebar.tsx frontend/lib/api.ts
git commit -m "feat(pagamentos): home 'o que precisa de mim' + comprometido/disponível no caixa + menu"
```

---

### Task 9: Verificação ponta-a-ponta + regressão (controller)

**Files:** nenhum novo (correções pontuais se a verificação achar problema).

- [ ] **Step 1: Regressão completa**

Run: `docker exec aprimora-py-backend python -m pytest -q`
Expected: tudo verde (574 + novos).
Run: `docker exec aprimora-py-frontend ./node_modules/.bin/tsc --noEmit`
Expected: limpo.

- [ ] **Step 2: E2E no browser** (`http://localhost:8090`, `admin@local.test`/`admin123` — super-usuário bypassa permissões; para segregação usar usuários demo distintos ou criar 3 usuários com os papéis):

1. Cadastrar alçada geral para o autorizador (Cadastros → Alçadas).
2. Contas a pagar → Novo débito (fornecedor existente, 2 parcelas) → aparece RASCUNHO.
3. Detalhe → Enviar → Aprovar (usuário ≠ solicitante) → Autorizar → toast com nº da OP; conferir na home que a fila reflete cada etapa.
4. Pagar parcela 1 → Caixa: saldo baixou e extrato tem SAIDA/PAGAMENTO; débito PAGO_PARCIAL; comprometido/disponível corretos.
5. Pagar parcela 2 → débito PAGO.
6. Abrir o PDF da OP (`/api/v2/pagamentos/ordens-pagamento/1/pdf` ou botão na UI).
7. Testar bloqueio: débito maior que o disponível → autorizar deve falhar com mensagem de saldo.
8. Estornar uma parcela → saldo volta, débito PAGO_PARCIAL.

- [ ] **Step 3: Commit final (se houve ajustes) + atualizar ledger**

```bash
git add -A && git commit -m "fix(pagamentos): ajustes da verificação e2e do R2"  # somente se houver mudanças
```

---

## Self-review (feito na escrita)

- **Cobertura do spec:** débito+parcelas (T1-2), workflow 3 níveis (T3-4), saldo/alçada/segregação (T4), pagar deduz saldo + estorno (T5), OP em PDF (T6), home fila + lote + contas a pagar + detalhe com trilha (T6-8), RBAC 4 transações (T1). Conciliação/transparência/relatórios = R3 (fora).
- **Tipos consistentes:** `status_f` no service ↔ query param `status_f`; `DebitoOut.nome_fornecedor` via `nomes_fornecedores`; `SaldoConta.disponivel` usado por `autorizar_lote`.
- **Sem placeholders:** os testes marcados `...` têm descrição executável completa do arrange/act/assert e seguem template dos testes anteriores no mesmo arquivo — o implementador da task escreve o corpo com os helpers já definidos na própria task.
