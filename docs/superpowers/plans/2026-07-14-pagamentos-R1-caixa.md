# Pagamentos R1 — Caixa visível (fornecedor + saldo + movimentação + extrato + painel) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Tornar o caixa visível: renomear credor→fornecedor, dar **saldo** às contas (inicial + movimentações), permitir lançar **entradas/saídas** manuais, ver o **extrato** por conta e um **painel de caixa** com os saldos.

**Architecture:** Reaproveita o backend do PAG-1 (schema `pagamentos`, RLS, cadastros). Saldo é sempre **derivado** de `movimentacao_conta` (fonte única da verdade) + `conta.saldo_inicial`. Rename credor→fornecedor em uma migration dedicada. Débito/workflow ficam no R2.

**Tech Stack:** FastAPI + SQLAlchemy async, Alembic, Postgres (RLS), Pydantic v2, Next.js + Tailwind, pytest, Docker.

## Global Constraints
- Python 3.12; SQLAlchemy async; Pydantic v2 (`ConfigDict(from_attributes=True)`).
- Multi-tenant: `tenant_id` FK `aprimora_py.tenant.id`; RLS `ENABLE`+`FORCE` com policies `tenant_isolation_select`/`_modify` (`current_setting('app.tenant_id')`); GRANTs à `aprimora_app` (tabela + sequence + `USAGE ON SCHEMA`). `tenant_id` sempre do caller.
- Soft-delete `excluido`. Datas via `datetime.utcnow()`.
- Testes SERVICE-LEVEL (padrão de `backend/tests/test_pagamentos_cadastros.py`: `provisionar_tenant` + `admin_engine` + `async_sessionmaker` + chamadas diretas ao serviço), rodados em `docker exec aprimora-py-backend python -m pytest <path> -q`. Stack de pé: `docker compose up -d` + `docker start ged-saas-project-db-1`.
- **Saldo é derivado**, nunca um contador denormalizado: `saldo_atual = conta.saldo_inicial + Σ(ENTRADA.valor) − Σ(SAIDA.valor)` sobre `movimentacao_conta` não excluída.
- Migration: revision `0046`, `down_revision = "0045"` (confirmar `alembic heads`).
- Endpoints sob `/api/v2/pagamentos/...`; permissão dos cadastros = `pagamento_cadastro`; movimentações/caixa = `pagamento_cadastro` por ora (papéis financeiros entram no R2).

## File Structure
- `backend/alembic/versions/0046_pagamentos_caixa.py` — rename credor→fornecedor, `conta.saldo_inicial`, `movimentacao_conta`.
- `backend/app/models/pagamentos.py` — `Credor`→`Fornecedor`; `ContaBancaria.saldo_inicial`; novo `MovimentacaoConta`.
- `backend/app/models/__init__.py` — atualizar exports.
- `backend/app/schemas/pagamentos.py` — `Credor*`→`Fornecedor*`; `ContaOut.saldo_inicial`; novos schemas de movimentação/saldo.
- `backend/app/services/pagamentos_cadastros.py` — renomear funções `*_credor`→`*_fornecedor`; `contrato` usa `id_fornecedor`.
- `backend/app/services/pagamentos_caixa.py` — **novo**: lançar movimentação, extrato, saldo, painel.
- `backend/app/routers/pagamentos_cadastros.py` — `credores_router`→`fornecedores_router` (path `/pagamentos/fornecedores`).
- `backend/app/routers/pagamentos_caixa.py` — **novo**: `/pagamentos/movimentacoes`, `/pagamentos/contas/{id}/extrato`, `/pagamentos/contas/{id}/saldo`, `/pagamentos/caixa/painel`.
- `backend/app/main.py` — trocar/registrar routers.
- `backend/tests/test_pagamentos_cadastros.py` — renomear credor→fornecedor.
- `backend/tests/test_pagamentos_caixa.py` — **novo**.
- `frontend/lib/api.ts` — `credores`→`fornecedores`; seção `pagamentos.caixa`.
- `frontend/app/(app)/pagamentos/cadastros/fornecedores/page.tsx` (renomear de credores); `frontend/app/(app)/pagamentos/caixa/page.tsx` — **novo**.
- `frontend/components/Sidebar.tsx` — grupo "Pagamentos": **Caixa** primeiro, depois submenu **Cadastros**.

---

### Task 1: Migration 0046 — rename + saldo_inicial + movimentacao_conta

**Files:** Create `backend/alembic/versions/0046_pagamentos_caixa.py`

**Interfaces:** Produces tabela `pagamentos.fornecedor` (ex-credor), coluna `pagamentos.conta_bancaria.saldo_inicial`, coluna `pagamentos.contrato.id_fornecedor` (ex-id_credor), tabela `pagamentos.movimentacao_conta`.

- [ ] **Step 1: Confirmar head** — `docker exec aprimora-py-backend alembic heads` → deve ser `0045`.

- [ ] **Step 2: Escrever a migration**

```python
"""Pagamentos R1 — caixa: rename credor→fornecedor, saldo_inicial, movimentacao_conta.

Revision ID: 0046
Revises: 0045
Create Date: 2026-07-14
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | Sequence[str] | None = "0045"
branch_labels = None
depends_on = None
S = "pagamentos"


def _enable_rls(t: str) -> None:
    op.execute(f"ALTER TABLE {S}.{t} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{t} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY tenant_isolation_select ON {S}.{t} FOR SELECT "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")
    op.execute(f"CREATE POLICY tenant_isolation_modify ON {S}.{t} FOR ALL "
               f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int) "
               f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)")


def upgrade() -> None:
    # 1) rename credor -> fornecedor (policies/GRANTs seguem o OID; renomeia seq/índices/constraints/coluna FK)
    op.execute(f"ALTER TABLE {S}.credor RENAME TO fornecedor")
    op.execute(f"ALTER SEQUENCE {S}.credor_id_seq RENAME TO fornecedor_id_seq")
    op.execute(f"ALTER INDEX {S}.uq_credor_tenant_doc RENAME TO uq_fornecedor_tenant_doc")
    op.execute(f"ALTER INDEX {S}.ix_credor_tenant_excluido RENAME TO ix_fornecedor_tenant_excluido")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME CONSTRAINT ck_credor_tipo_pessoa TO ck_fornecedor_tipo_pessoa")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME CONSTRAINT ck_credor_situacao TO ck_fornecedor_situacao")
    # contrato.id_credor -> id_fornecedor
    op.execute(f"ALTER TABLE {S}.contrato RENAME COLUMN id_credor TO id_fornecedor")
    op.execute(f"ALTER INDEX {S}.ix_contrato_credor RENAME TO ix_contrato_fornecedor")

    # 2) conta_bancaria.saldo_inicial
    op.add_column("conta_bancaria",
                  sa.Column("saldo_inicial", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
                  schema=S)

    # 3) movimentacao_conta
    op.create_table(
        "movimentacao_conta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("id_conta", sa.Integer(), sa.ForeignKey(f"{S}.conta_bancaria.id"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("origem", sa.String(20), nullable=False),
        sa.Column("id_debito", sa.Integer(), nullable=True),      # FK criada no R2 (tabela debito ainda não existe)
        sa.Column("id_parcela", sa.Integer(), nullable=True),     # idem
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
        sa.Column("descricao", sa.String(255), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.CheckConstraint("tipo IN ('ENTRADA','SAIDA')", name="ck_movconta_tipo"),
        sa.CheckConstraint("origem IN ('APORTE','RECEITA','AJUSTE','PAGAMENTO','ESTORNO')", name="ck_movconta_origem"),
        sa.CheckConstraint("valor > 0", name="ck_movconta_valor_positivo"),
        schema=S,
    )
    op.create_index("ix_movconta_tenant_conta", "movimentacao_conta", ["tenant_id", "id_conta"], schema=S)
    op.create_index("ix_movconta_tenant_excluido", "movimentacao_conta", ["tenant_id", "excluido"], schema=S)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.movimentacao_conta TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.movimentacao_conta_id_seq TO aprimora_app")
    _enable_rls("movimentacao_conta")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {S}.movimentacao_conta")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {S}.movimentacao_conta")
    op.drop_index("ix_movconta_tenant_excluido", table_name="movimentacao_conta", schema=S)
    op.drop_index("ix_movconta_tenant_conta", table_name="movimentacao_conta", schema=S)
    op.drop_table("movimentacao_conta", schema=S)
    op.drop_column("conta_bancaria", "saldo_inicial", schema=S)
    op.execute(f"ALTER INDEX {S}.ix_contrato_fornecedor RENAME TO ix_contrato_credor")
    op.execute(f"ALTER TABLE {S}.contrato RENAME COLUMN id_fornecedor TO id_credor")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME CONSTRAINT ck_fornecedor_situacao TO ck_credor_situacao")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME CONSTRAINT ck_fornecedor_tipo_pessoa TO ck_credor_tipo_pessoa")
    op.execute(f"ALTER INDEX {S}.ix_fornecedor_tenant_excluido RENAME TO ix_credor_tenant_excluido")
    op.execute(f"ALTER INDEX {S}.uq_fornecedor_tenant_doc RENAME TO uq_credor_tenant_doc")
    op.execute(f"ALTER SEQUENCE {S}.fornecedor_id_seq RENAME TO credor_id_seq")
    op.execute(f"ALTER TABLE {S}.fornecedor RENAME TO credor")
```

- [ ] **Step 3: Aplicar e roundtrip**
```bash
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic downgrade 0045
docker exec aprimora-py-backend alembic upgrade head
```
Verificar: `\d pagamentos.fornecedor` existe; `pagamentos.contrato` tem `id_fornecedor`; `pagamentos.conta_bancaria` tem `saldo_inicial`; `movimentacao_conta` com 2 policies; app role acessa:
```bash
docker exec ged-saas-project-db-1 psql -U ged_user -d ged_saas_db -c "SET ROLE aprimora_app; SET app.tenant_id='1'; SELECT count(*) FROM pagamentos.fornecedor; SELECT count(*) FROM pagamentos.movimentacao_conta;"
```

- [ ] **Step 4: Commit** `feat(pagamentos): migration 0046 — rename fornecedor, saldo_inicial, movimentacao_conta`

---

### Task 2: Backend rename credor→fornecedor

**Files:** Modify `backend/app/models/pagamentos.py`, `models/__init__.py`, `schemas/pagamentos.py`, `services/pagamentos_cadastros.py`, `routers/pagamentos_cadastros.py`, `main.py`, `tests/test_pagamentos_cadastros.py`

**Interfaces:** Produces `Fornecedor` model, `Fornecedor*` schemas, `*_fornecedor` service fns, `fornecedores_router` (prefix `/pagamentos/fornecedores`, + `/{id}/dados-bancarios`). `contrato` passa a usar `id_fornecedor`.

- [ ] **Step 1: Renomear no código (find/replace consciente)** — em TODOS os arquivos acima: `Credor`→`Fornecedor`, `credor`→`fornecedor`, `credores`→`fornecedores`, `id_credor`→`id_fornecedor`, `criar_credor`→`criar_fornecedor` (idem obter/listar/atualizar/excluir/dados_bancarios/credor_out→fornecedor_out), `_validar_doc_unico` mantém nome. Model `ContaBancaria`: adicionar `saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(14,2), nullable=False, default=0)`. `Contrato.id_credor`→`id_fornecedor`. Router prefix `/pagamentos/credores`→`/pagamentos/fornecedores`; em `main.py` trocar `credores_router`→`fornecedores_router`. Schema `ContaOut`/`ContaCreate`/`ContaUpdate`: adicionar `saldo_inicial: Decimal` (Out obrigatório; Create/Update opcional, default 0 no create).

- [ ] **Step 2: Ajustar os testes** — em `tests/test_pagamentos_cadastros.py` renomear todas as referências credor→fornecedor (funções, endpoints, cleanup `pagamentos.credor`→`pagamentos.fornecedor`; contrato usa `id_fornecedor`). Rodar: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_cadastros.py -q` → todos passam.

- [ ] **Step 3: Regressão + app import** — `docker exec aprimora-py-backend python -c "from app.main import app; print('ok')"`; `docker exec aprimora-py-backend python -m pytest -q` → sem novas falhas.

- [ ] **Step 4: Commit** `refactor(pagamentos): renomeia credor→fornecedor + conta.saldo_inicial`

---

### Task 3: Serviço + endpoints de movimentação/extrato/saldo

**Files:** Create `backend/app/services/pagamentos_caixa.py`, `backend/app/routers/pagamentos_caixa.py`; Modify `main.py`; Test `backend/tests/test_pagamentos_caixa.py`

**Interfaces:**
- Produces `lancar_movimentacao(db,*,tenant_id,payload,usuario_id)->MovimentacaoConta`, `listar_extrato(db,*,tenant_id,conta_id)->list`, `saldo_conta(db,*,tenant_id,conta_id)->SaldoConta` (dict com `saldo_inicial,total_entradas,total_saidas,saldo_atual`). Router: `POST /pagamentos/movimentacoes`, `GET /pagamentos/contas/{id}/extrato`, `GET /pagamentos/contas/{id}/saldo`.
- Consumes: `ContaBancaria`, `MovimentacaoConta` (Task 1-2).

- [ ] **Step 1: Schemas** — em `schemas/pagamentos.py` adicionar:
```python
TipoMov = Literal["ENTRADA", "SAIDA"]
OrigemMov = Literal["APORTE", "RECEITA", "AJUSTE", "PAGAMENTO", "ESTORNO"]

class MovimentacaoCreate(BaseModel):
    id_conta: int
    tipo: TipoMov
    valor: Decimal = Field(gt=0)
    origem: OrigemMov
    data: date
    descricao: str | None = Field(default=None, max_length=255)

class MovimentacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_conta: int; tipo: TipoMov; valor: Decimal; origem: OrigemMov
    data: date; descricao: str | None; id_usuario: int | None; criado_em: datetime

class SaldoConta(BaseModel):
    id_conta: int; saldo_inicial: Decimal; total_entradas: Decimal
    total_saidas: Decimal; saldo_atual: Decimal
```
> No R1 o endpoint público de lançamento só aceita `origem ∈ {APORTE, RECEITA, AJUSTE}` (PAGAMENTO/ESTORNO são internos do R2) — validar no serviço (400 se origem interna via API).

- [ ] **Step 2: Teste (service-level, RED)** — `tests/test_pagamentos_caixa.py` (espelhar fixtures de `test_pagamentos_cadastros.py`):
```python
async def test_saldo_reflete_entradas_e_saidas(session, tenant_id, usuario_id):
    # cria fonte+conta com saldo_inicial=1000 via svc de cadastros
    conta = await cad.criar_conta(session, tenant_id=tenant_id, payload=ContaCreate(
        nome="C1", banco="001", agencia="1", conta="1", id_fonte_recursos=fonte.id,
        grupo_despesa="CUSTEIO", saldo_inicial=Decimal("1000")))
    await caixa.lancar_movimentacao(session, tenant_id=tenant_id, usuario_id=usuario_id,
        payload=MovimentacaoCreate(id_conta=conta.id, tipo="ENTRADA", valor=Decimal("500"),
        origem="APORTE", data=date(2026,7,14)))
    await caixa.lancar_movimentacao(session, tenant_id=tenant_id, usuario_id=usuario_id,
        payload=MovimentacaoCreate(id_conta=conta.id, tipo="SAIDA", valor=Decimal("200"),
        origem="AJUSTE", data=date(2026,7,14)))
    s = await caixa.saldo_conta(session, tenant_id=tenant_id, conta_id=conta.id)
    assert s.saldo_atual == Decimal("1300")  # 1000 + 500 - 200
    ext = await caixa.listar_extrato(session, tenant_id=tenant_id, conta_id=conta.id)
    assert len(ext) == 2

async def test_origem_interna_via_api_bloqueada(session, tenant_id, usuario_id):
    with pytest.raises(HTTPException) as e:
        await caixa.lancar_movimentacao(session, tenant_id=tenant_id, usuario_id=usuario_id,
            payload=MovimentacaoCreate(id_conta=conta.id, tipo="SAIDA", valor=Decimal("1"),
            origem="PAGAMENTO", data=date(2026,7,14)))
    assert e.value.status_code == 400
```
(Ajustar setup de fonte/conta ao que o test de cadastros já faz; estender `_cleanup` para `pagamentos.movimentacao_conta`.)

- [ ] **Step 3: Implementar serviço**
```python
"""Caixa de Pagamentos — movimentações e saldo (R1). Saldo é derivado das
movimentações + conta.saldo_inicial (fonte única da verdade)."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import ContaBancaria, MovimentacaoConta
from ..schemas.pagamentos import MovimentacaoCreate, SaldoConta

_ORIGENS_MANUAIS = {"APORTE", "RECEITA", "AJUSTE"}


async def _obter_conta(db, *, tenant_id, conta_id) -> ContaBancaria:
    c = (await db.execute(select(ContaBancaria).where(
        ContaBancaria.id == conta_id, ContaBancaria.tenant_id == tenant_id,
        ContaBancaria.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada")
    return c


async def lancar_movimentacao(db, *, tenant_id, usuario_id, payload: MovimentacaoCreate) -> MovimentacaoConta:
    if payload.origem not in _ORIGENS_MANUAIS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Origem interna (PAGAMENTO/ESTORNO) não pode ser lançada manualmente.")
    await _obter_conta(db, tenant_id=tenant_id, conta_id=payload.id_conta)
    m = MovimentacaoConta(tenant_id=tenant_id, id_conta=payload.id_conta, tipo=payload.tipo,
                          valor=payload.valor, origem=payload.origem, data=payload.data,
                          id_usuario=usuario_id, descricao=payload.descricao, criado_em=datetime.utcnow())
    db.add(m); await db.commit(); await db.refresh(m); return m


async def listar_extrato(db, *, tenant_id, conta_id) -> list[MovimentacaoConta]:
    await _obter_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    return list((await db.execute(select(MovimentacaoConta).where(
        MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.id_conta == conta_id,
        MovimentacaoConta.excluido.is_(False)).order_by(MovimentacaoConta.data.desc(),
        MovimentacaoConta.id.desc()))).scalars().all())


async def saldo_conta(db, *, tenant_id, conta_id) -> SaldoConta:
    conta = await _obter_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    def _soma(tipo: str) -> Decimal:
        return select(func.coalesce(func.sum(MovimentacaoConta.valor), 0)).where(
            MovimentacaoConta.tenant_id == tenant_id, MovimentacaoConta.id_conta == conta_id,
            MovimentacaoConta.excluido.is_(False), MovimentacaoConta.tipo == tipo)
    entradas = (await db.execute(_soma("ENTRADA"))).scalar_one()
    saidas = (await db.execute(_soma("SAIDA"))).scalar_one()
    inicial = conta.saldo_inicial or Decimal("0")
    return SaldoConta(id_conta=conta_id, saldo_inicial=inicial, total_entradas=entradas,
                      total_saidas=saidas, saldo_atual=inicial + entradas - saidas)
```

- [ ] **Step 4: Router + registro**
```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import MovimentacaoCreate, MovimentacaoOut, SaldoConta
from ..services import pagamentos_caixa as svc

caixa_router = APIRouter(prefix="/pagamentos", tags=["pagamentos-caixa"])

@caixa_router.post("/movimentacoes", response_model=MovimentacaoOut, status_code=status.HTTP_201_CREATED)
async def lancar(payload: MovimentacaoCreate,
                 usuario: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                 tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    m = await svc.lancar_movimentacao(db, tenant_id=tenant_id, usuario_id=usuario.id, payload=payload)
    return MovimentacaoOut.model_validate(m)

@caixa_router.get("/contas/{conta_id}/extrato", response_model=list[MovimentacaoOut])
async def extrato(conta_id: int, _: Usuario = Depends(require_permission("pagamento_cadastro")),
                  tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return [MovimentacaoOut.model_validate(m) for m in await svc.listar_extrato(db, tenant_id=tenant_id, conta_id=conta_id)]

@caixa_router.get("/contas/{conta_id}/saldo", response_model=SaldoConta)
async def saldo(conta_id: int, _: Usuario = Depends(require_permission("pagamento_cadastro")),
                tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return await svc.saldo_conta(db, tenant_id=tenant_id, conta_id=conta_id)
```
Registrar `pagamentos_caixa.caixa_router` no `main.py`.

- [ ] **Step 5: GREEN** — `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_caixa.py -q` (passa) + app import ok.

- [ ] **Step 6: Commit** `feat(pagamentos): movimentações, extrato e saldo por conta`

---

### Task 4: Painel de caixa (saldos de todas as contas)

**Files:** Modify `backend/app/services/pagamentos_caixa.py`, `routers/pagamentos_caixa.py`; Test em `test_pagamentos_caixa.py`

**Interfaces:** Produces `painel_caixa(db,*,tenant_id)->list[ContaSaldoPainel]` e `GET /pagamentos/caixa/painel`. `ContaSaldoPainel` = dados da conta + saldo (inicial/entradas/saidas/atual) + `abaixo_minimo` (saldo_atual < saldo_minimo_alerta).

- [ ] **Step 1: Schema** — em `schemas/pagamentos.py`:
```python
class ContaSaldoPainel(BaseModel):
    id_conta: int; nome: str; banco: str; grupo_despesa: str
    saldo_inicial: Decimal; total_entradas: Decimal; total_saidas: Decimal
    saldo_atual: Decimal; saldo_minimo_alerta: Decimal; abaixo_minimo: bool
```

- [ ] **Step 2: Teste** — cria 2 contas com saldos diferentes + movimentações; `painel_caixa` retorna uma linha por conta ativa com `saldo_atual` correto e `abaixo_minimo` calculado.

- [ ] **Step 3: Implementar** `painel_caixa` (lista contas não excluídas do tenant; para cada, reusa a lógica de `saldo_conta` — idealmente uma única query agregada com `GROUP BY id_conta` + LEFT JOIN, mas uma iteração simples por conta é aceitável no R1) + endpoint `GET /pagamentos/caixa/painel` (perm `pagamento_cadastro`).

- [ ] **Step 4: GREEN + Commit** `feat(pagamentos): painel de caixa (saldos por conta)`

---

### Task 5: Frontend — Caixa + rename fornecedores + menu

**Files:** Modify `frontend/lib/api.ts`, `frontend/components/Sidebar.tsx`; rename `frontend/app/(app)/pagamentos/cadastros/credores/` → `fornecedores/`; Create `frontend/app/(app)/pagamentos/caixa/page.tsx`

**Interfaces:** Consumes `api.pagamentos.cadastros.fornecedores.*` (renomeado), `api.pagamentos.caixa.{painel, extrato, saldo, lancar}`.

- [ ] **Step 1: api.ts** — renomear `credores`→`fornecedores` (tipo `Credor`→`Fornecedor`, path `/pagamentos/fornecedores`); adicionar `ContaBancaria.saldo_inicial`; adicionar seção:
```ts
  // dentro de pagamentos:
  caixa: {
    painel: () => request<ContaSaldoPainel[]>("/pagamentos/caixa/painel"),
    saldo: (contaId: number) => request<SaldoConta>(`/pagamentos/contas/${contaId}/saldo`),
    extrato: (contaId: number) => request<Movimentacao[]>(`/pagamentos/contas/${contaId}/extrato`),
    lancar: (data: unknown) => request<Movimentacao>("/pagamentos/movimentacoes", { method: "POST", body: JSON.stringify(data) }),
  },
```
com tipos `Movimentacao`, `SaldoConta`, `ContaSaldoPainel` espelhando os `*Out`.

- [ ] **Step 2: Página Caixa** (`pagamentos/caixa/page.tsx`) — client component:
  - **Painel**: cards/linha por conta com nome, banco, saldo atual (destaque), inicial/entradas/saídas, e badge "abaixo do mínimo" quando `abaixo_minimo`. Fonte: `api.pagamentos.caixa.painel()`.
  - **Lançar**: botão "Lançar entrada/saída" → Dialog com id_conta (select de contas), tipo (ENTRADA/SAÍDA), origem (APORTE/RECEITA/AJUSTE), valor, data, descrição → `api.pagamentos.caixa.lancar(...)` → invalida painel/extrato + toast.
  - **Extrato**: ao selecionar uma conta, listar `api.pagamentos.caixa.extrato(contaId)` (data, tipo, origem, valor com sinal, descrição). Dinheiro com `tabular-nums`, entradas/saídas com cor.
  Espelhar padrões visuais de `templates-documento/page.tsx` (Dialog/Input/Select/useToast/react-query).

- [ ] **Step 3: Menu** — em `Sidebar.tsx`, grupo "Pagamentos": item **"Caixa"** (`/pagamentos/caixa`, ícone tipo `Wallet`/`Coins`, perm `pagamento_cadastro`) em primeiro; manter os cadastros (renomear "Credores"→"Fornecedores", href `/pagamentos/cadastros/fornecedores`). Rota `pagamentos` já está no regex do nginx.

- [ ] **Step 4: Verificar** — `docker compose restart frontend`; `docker exec aprimora-py-frontend ./node_modules/.bin/tsc --noEmit` → 0; rota `curl -s -o /dev/null -w "%{http_code}" -H "Host: sobral.aprimora.local" http://localhost:8090/pagamentos/caixa` ≠ 404/502.

- [ ] **Step 5: Commit** `feat(pagamentos): tela de Caixa (painel + extrato + lançar) + fornecedores + menu`

---

### Task 6: Verificação ponta-a-ponta (browser)

- [ ] **Step 1:** stack de pé (`docker compose up -d` + `docker start ged-saas-project-db-1`), login `admin@local.test`/`admin123` em `http://localhost:8090`.
- [ ] **Step 2:** Cadastros → criar Fonte (CUSTEIO) → criar Conta com **saldo inicial** (ex.: R$ 10.000).
- [ ] **Step 3:** Caixa → conferir a conta no painel com saldo R$ 10.000; **lançar entrada** R$ 2.000 (APORTE) → saldo vira R$ 12.000; **lançar saída** R$ 500 (AJUSTE) → saldo R$ 11.500; extrato mostra as 2 movimentações.
- [ ] **Step 4:** conferir badge "abaixo do mínimo" setando `saldo_minimo_alerta` acima do saldo.
- [ ] **Step 5:** suíte backend + tsc verdes. Screenshots do painel + extrato.

---

## Notas
- **Migration em paralelo**: se o head mudar ao mergear, rebasear `down_revision`.
- **R2 (próximo)**: `debito` + `parcela` + `debito_historico` + `ordem_pagamento` + workflow 3 níveis (solicitar→aprovar→autorizar→pagar) com saldo/alçada/segregação; `pagar_parcela` cria `movimentacao_conta` origem=PAGAMENTO (deduz saldo) e cria as FKs `movimentacao_conta.id_debito/id_parcela`; home "o que precisa de mim".
