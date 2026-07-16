# PAG-1 — Fundação + Cadastros do módulo de Pagamentos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a fundação de dados (schema `pagamentos` + RLS) e os cadastros básicos (credor com dados bancários cifrados, natureza de despesa, fonte de recursos, conta bancária, contrato, alçada) do módulo de Pagamentos Municipais, com CRUD backend + telas admin.

**Architecture:** Domínio `pagamentos` autônomo, tenant-scoped com RLS (padrão da migration 0043), reusando `UnidadeTrabalho` (órgão), RBAC (`require_permission`) e o padrão de router/service/schema de `transporte_regulado`. Dados bancários do credor são cifrados em repouso via helper Fernet reutilizável. Nenhuma lógica de saldo/fluxo neste PR (fica no PAG-2/PAG-3).

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async, Alembic, Postgres (RLS), Pydantic v2, `cryptography` (Fernet), Next.js 14 (App Router) + Tailwind, pytest, Docker Compose.

## Global Constraints

- Python 3.12; SQLAlchemy async (`AsyncSession`); Pydantic v2 (`ConfigDict(from_attributes=True)`).
- **Multi-tenant:** toda tabela nova tem `tenant_id` FK `aprimora_py.tenant.id`; RLS `ENABLE`+`FORCE` com policies `tenant_isolation_select` (FOR SELECT) e `tenant_isolation_modify` (FOR ALL), ambas com `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int`. GRANTs `SELECT,INSERT,UPDATE,DELETE` na tabela + `USAGE,SELECT` na sequence para `aprimora_app`. Padrão exato: `backend/alembic/versions/0043_transporte_regulado_veiculo.py` (numa branch irmã) ou `0041_transporte_regulado_permissionario.py` (nesta branch).
- **`tenant_id` sempre do caller** (`Depends(require_tenant_id)`), NUNCA do payload.
- **Soft-delete:** coluna `excluido` boolean; DELETE marca `excluido=true`.
- **RBAC:** `require_permission("pagamento_cadastro", <ação>)` onde ação ∈ {`inserir`,`atualizar`,`excluir`} ou None. Super-usuário bypassa (nada a fazer).
- **Datas:** serviços usam `datetime.utcnow()` para `criado_em`/`atualizado_em` (consistente com `services/transporte_regulado.py`).
- **Testes:** rodam dentro do container — `docker exec aprimora-py-backend python -m pytest <path> -q`. Fixtures: seguir `backend/tests/test_transporte_regulado_permissionario.py` (usa client autenticado + tenant). Antes de rodar testes, garantir stack de pé: `docker compose up -d` e DB externo `docker start ged-saas-project-db-1`.
- **Migration numbering:** revision `0045`; `down_revision` = head atual desta branch (confirmar com `docker exec aprimora-py-backend alembic heads` — hoje é `0042`). Nota: `0043`/`0044` existem em branches irmãs (transporte-veículo, minuta); ao mergear, rebasear `down_revision` para o head resultante.
- **Órgão = `UnidadeTrabalho`** (`utils.unidade_trabalho`); não criar entidade `orgao`.
- **Alçada por usuário** (`id_usuario`), não por grupo.

## File Structure

- `backend/app/core/crypto.py` — **novo**: helpers Fernet `encrypt`/`decrypt` (reutilizável pelo PR-D da minuta).
- `backend/app/config.py` — **modificar**: adicionar `dados_sensiveis_encryption_key` em `Settings`.
- `backend/alembic/versions/0045_pagamentos_cadastros.py` — **novo**: schema `pagamentos`, 6 tabelas, RLS/GRANTs, seed da transação `pagamento_cadastro`.
- `backend/app/models/pagamentos.py` — **novo**: enums `Criticidade`/`GrupoDespesa` + 6 models.
- `backend/app/models/__init__.py` — **modificar**: registrar os models.
- `backend/app/schemas/pagamentos.py` — **novo**: schemas Create/Update/Out por entidade.
- `backend/app/services/pagamentos_cadastros.py` — **novo**: CRUD + validações + Fernet no credor.
- `backend/app/routers/pagamentos_cadastros.py` — **novo**: routers REST por entidade.
- `backend/app/main.py` — **modificar**: registrar routers.
- `backend/tests/test_crypto.py` — **novo**.
- `backend/tests/test_pagamentos_cadastros.py` — **novo**.
- `frontend/lib/api.ts` — **modificar**: seção `pagamentos.cadastros`.
- `frontend/app/(app)/pagamentos/cadastros/{credores,naturezas,fontes,contas,contratos,alcadas}/page.tsx` — **novo**.
- `frontend/components/Sidebar.tsx` — **modificar**: grupo "Pagamentos".
- `nginx/default.conf` — **modificar**: adicionar `pagamentos` ao regex de rotas.

---

### Task 1: Helper de cifragem Fernet

**Files:**
- Create: `backend/app/core/crypto.py`
- Modify: `backend/app/config.py` (classe `Settings`)
- Test: `backend/tests/test_crypto.py`

**Interfaces:**
- Produces: `encrypt(texto: str | None) -> str | None`, `decrypt(cifrado: str | None) -> str | None` em `app.core.crypto`. `None`/`""` passam por sem cifrar (retornam o próprio valor `None`). Levanta `CryptoConfigError` se a chave não estiver configurada quando `encrypt`/`decrypt` de valor não-vazio for chamado.

- [ ] **Step 1: Add setting**

Em `backend/app/config.py`, dentro da classe `Settings` (perto de outros campos), adicionar:

```python
    # Cifragem de dados sensíveis (dados bancários de credor, tokens Google).
    # Fernet key (base64 urlsafe de 32 bytes). Vazio em dev → operações de cifra falham
    # explicitamente. Gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    dados_sensiveis_encryption_key: str = ""
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_crypto.py`:

```python
import pytest

from app.core import crypto


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setattr(crypto, "_get_key", lambda: b"a" * 32)  # placeholder; overridden below
    # usa uma chave Fernet válida real:
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("DADOS_SENSIVEIS_ENCRYPTION_KEY", key)
    crypto.get_settings.cache_clear()
    cif = crypto.encrypt("agencia-1234")
    assert cif != "agencia-1234"
    assert crypto.decrypt(cif) == "agencia-1234"


def test_none_and_empty_passthrough():
    assert crypto.encrypt(None) is None
    assert crypto.encrypt("") == ""
    assert crypto.decrypt(None) is None
    assert crypto.decrypt("") == ""


def test_missing_key_raises(monkeypatch):
    monkeypatch.setenv("DADOS_SENSIVEIS_ENCRYPTION_KEY", "")
    crypto.get_settings.cache_clear()
    with pytest.raises(crypto.CryptoConfigError):
        crypto.encrypt("x")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker exec aprimora-py-backend python -m pytest tests/test_crypto.py -q`
Expected: FAIL (`ModuleNotFoundError: app.core.crypto` ou `AttributeError`).

- [ ] **Step 4: Implement**

`backend/app/core/crypto.py`:

```python
"""Cifragem simétrica (Fernet) de dados sensíveis em repouso.

Reutilizável por qualquer campo bancário/sigiloso (credor de pagamentos) e por
tokens OAuth (PR-D da minuta). Chave em `settings.dados_sensiveis_encryption_key`
(Fernet key base64). Valores None/"" passam sem cifrar.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from ..config import get_settings


class CryptoConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = get_settings().dados_sensiveis_encryption_key
    if not key:
        raise CryptoConfigError(
            "DADOS_SENSIVEIS_ENCRYPTION_KEY não configurada — impossível cifrar dados sensíveis."
        )
    return Fernet(key.encode())


def encrypt(texto: str | None) -> str | None:
    if not texto:
        return texto
    return _fernet().encrypt(texto.encode()).decode()


def decrypt(cifrado: str | None) -> str | None:
    if not cifrado:
        return cifrado
    return _fernet().decrypt(cifrado.encode()).decode()
```

> Nota: o teste usa `crypto.get_settings.cache_clear()` — reexporte no módulo com `from ..config import get_settings` (já feito) e limpe o cache do `_fernet` no teste via `crypto._fernet.cache_clear()`. Ajuste o teste do Step 2 para chamar `crypto._fernet.cache_clear()` após setar a env, em vez de `crypto.get_settings.cache_clear()` (o `get_settings` do config já é `lru_cache`; limpe ambos: `get_settings.cache_clear(); crypto._fernet.cache_clear()`).

- [ ] **Step 5: Run test to verify it passes**

Run: `docker exec aprimora-py-backend python -m pytest tests/test_crypto.py -q`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/crypto.py backend/app/config.py backend/tests/test_crypto.py
git commit -m "feat(pagamentos): helper de cifragem Fernet para dados sensíveis"
```

---

### Task 2: Migration 0045 — schema, tabelas, RLS, seed de permissão

**Files:**
- Create: `backend/alembic/versions/0045_pagamentos_cadastros.py`

**Interfaces:**
- Produces: schema `pagamentos` com tabelas `credor`, `natureza_despesa`, `fonte_recursos`, `conta_bancaria`, `contrato`, `alcada`; transação `pagamento_cadastro` em `utils.transacao`.

- [ ] **Step 1: Confirmar head**

Run: `docker exec aprimora-py-backend alembic heads`
Expected: mostra `0042 (head)` nesta branch. Use esse valor em `down_revision`.

- [ ] **Step 2: Escrever a migration**

`backend/alembic/versions/0045_pagamentos_cadastros.py`:

```python
"""Pagamentos PAG-1 — schema `pagamentos` + cadastros básicos.

Revision ID: 0045
Revises: 0042
Create Date: 2026-07-13

Cria o schema `pagamentos` e as 6 tabelas de cadastro (credor, natureza_despesa,
fonte_recursos, conta_bancaria, contrato, alcada), todas tenant-scoped com RLS/GRANTs
no padrão de `transporte_regulado` (0041/0043). Semeia a transação `pagamento_cadastro`.
Órgão = utils.unidade_trabalho (sem entidade nova). Dados bancários do credor são
cifrados na aplicação (colunas *_cif Text).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0045"
down_revision: str | Sequence[str] | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "pagamentos"
TABELAS = ["credor", "natureza_despesa", "fonte_recursos", "conta_bancaria", "contrato", "alcada"]


def _enable_rls(qualified: str) -> None:
    op.execute(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_isolation_select ON {qualified}
            FOR SELECT USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)"""
    )
    op.execute(
        f"""CREATE POLICY tenant_isolation_modify ON {qualified}
            FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::int)"""
    )


def _grant(tabela: str) -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {SCHEMA}.{tabela} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {SCHEMA}.{tabela}_id_seq TO aprimora_app")


def _cols_comuns() -> list:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    ]


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # ---- credor ----
    op.create_table(
        "credor",
        *_cols_comuns(),
        sa.Column("tipo_pessoa", sa.String(length=10), nullable=False),
        sa.Column("cnpj_cpf", sa.String(length=18), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("situacao_cadastral", sa.String(length=10), nullable=False, server_default=sa.text("'REGULAR'")),
        sa.Column("motivo_pendencia", sa.String(length=255), nullable=True),
        sa.Column("banco_cif", sa.Text(), nullable=True),
        sa.Column("agencia_cif", sa.Text(), nullable=True),
        sa.Column("conta_cif", sa.Text(), nullable=True),
        sa.Column("chave_pix_cif", sa.Text(), nullable=True),
        sa.CheckConstraint("tipo_pessoa IN ('FISICA','JURIDICA')", name="ck_credor_tipo_pessoa"),
        sa.CheckConstraint("situacao_cadastral IN ('REGULAR','PENDENTE','IRREGULAR')", name="ck_credor_situacao"),
        schema=SCHEMA,
    )
    op.create_index("uq_credor_tenant_doc", "credor", ["tenant_id", "cnpj_cpf"], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_credor_tenant_excluido", "credor", ["tenant_id", "excluido"], schema=SCHEMA)

    # ---- natureza_despesa ----
    op.create_table(
        "natureza_despesa",
        *_cols_comuns(),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("descricao", sa.String(length=150), nullable=False),
        sa.Column("criticidade_padrao", sa.String(length=10), nullable=False, server_default=sa.text("'MEDIA'")),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.CheckConstraint("criticidade_padrao IN ('URGENTE','ALTA','MEDIA','BAIXA')", name="ck_natureza_criticidade"),
        schema=SCHEMA,
    )
    op.create_index("uq_natureza_tenant_codigo", "natureza_despesa", ["tenant_id", "codigo"], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_natureza_tenant_excluido", "natureza_despesa", ["tenant_id", "excluido"], schema=SCHEMA)

    # ---- fonte_recursos ----
    op.create_table(
        "fonte_recursos",
        *_cols_comuns(),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("descricao", sa.String(length=200), nullable=False),
        sa.Column("grupos_despesa_permitidos", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        schema=SCHEMA,
    )
    op.create_index("uq_fonte_tenant_codigo", "fonte_recursos", ["tenant_id", "codigo"], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_fonte_tenant_excluido", "fonte_recursos", ["tenant_id", "excluido"], schema=SCHEMA)

    # ---- conta_bancaria ----
    op.create_table(
        "conta_bancaria",
        *_cols_comuns(),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("banco", sa.String(length=100), nullable=False),
        sa.Column("agencia", sa.String(length=20), nullable=False),
        sa.Column("conta", sa.String(length=30), nullable=False),
        sa.Column("id_fonte_recursos", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.fonte_recursos.id"), nullable=False),
        sa.Column("grupo_despesa", sa.String(length=20), nullable=False),
        sa.Column("saldo_minimo_alerta", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.CheckConstraint("grupo_despesa IN ('PESSOAL','CUSTEIO','INVESTIMENTO','DIVIDA','OUTRAS')", name="ck_conta_grupo"),
        schema=SCHEMA,
    )
    op.create_index("ix_conta_tenant_excluido", "conta_bancaria", ["tenant_id", "excluido"], schema=SCHEMA)
    op.create_index("ix_conta_fonte", "conta_bancaria", ["id_fonte_recursos"], schema=SCHEMA)

    # ---- contrato ----
    op.create_table(
        "contrato",
        *_cols_comuns(),
        sa.Column("numero", sa.String(length=50), nullable=False),
        sa.Column("id_credor", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.credor.id"), nullable=False),
        sa.Column("id_unidade", sa.Integer(), sa.ForeignKey("utils.unidade_trabalho.id"), nullable=False),
        sa.Column("objeto", sa.String(length=255), nullable=False),
        sa.Column("vigencia_inicio", sa.Date(), nullable=False),
        sa.Column("vigencia_fim", sa.Date(), nullable=False),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("vigencia_fim >= vigencia_inicio", name="ck_contrato_vigencia"),
        schema=SCHEMA,
    )
    op.create_index("uq_contrato_tenant_numero", "contrato", ["tenant_id", "numero"], unique=True,
                    schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_contrato_tenant_excluido", "contrato", ["tenant_id", "excluido"], schema=SCHEMA)
    op.create_index("ix_contrato_credor", "contrato", ["id_credor"], schema=SCHEMA)

    # ---- alcada ----
    op.create_table(
        "alcada",
        *_cols_comuns(),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=False),
        sa.Column("id_natureza", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.natureza_despesa.id"), nullable=True),
        sa.Column("valor_maximo", sa.Numeric(14, 2), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("uq_alcada_tenant_usuario_natureza", "alcada", ["tenant_id", "id_usuario", "id_natureza"],
                    unique=True, schema=SCHEMA, postgresql_where=sa.text("excluido = false"))
    op.create_index("ix_alcada_tenant_excluido", "alcada", ["tenant_id", "excluido"], schema=SCHEMA)

    for t in TABELAS:
        _grant(t)
        _enable_rls(f"{SCHEMA}.{t}")

    # transação de permissão (idempotente, padrão 0028/0044)
    op.execute(
        """INSERT INTO utils.transacao (transacao, codigo)
           SELECT 'Cadastros de Pagamentos', 'pagamento_cadastro'
           WHERE NOT EXISTS (SELECT 1 FROM utils.transacao WHERE codigo = 'pagamento_cadastro')"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM utils.grupo_transacao WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo='pagamento_cadastro')")
    op.execute("DELETE FROM utils.sistema_transacao WHERE id_transacao IN (SELECT id FROM utils.transacao WHERE codigo='pagamento_cadastro')")
    op.execute("DELETE FROM utils.transacao WHERE codigo='pagamento_cadastro'")
    for t in reversed(TABELAS):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_modify ON {SCHEMA}.{t}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_select ON {SCHEMA}.{t}")
        op.drop_table(t, schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
```

- [ ] **Step 3: Aplicar e verificar roundtrip**

Run:
```bash
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic downgrade 0042
docker exec aprimora-py-backend alembic upgrade head
```
Expected: sobe até 0045, desce limpo (sem erro), re-sobe. Conferir tabelas e policies:
```bash
docker exec ged-saas-project-db-1 psql -U ged_user -d ged_saas_db -t -c "SELECT count(*) FROM pg_tables WHERE schemaname='pagamentos';"   # 6
docker exec ged-saas-project-db-1 psql -U ged_user -d ged_saas_db -t -c "SELECT count(*) FROM pg_policies WHERE schemaname='pagamentos';"  # 12
docker exec ged-saas-project-db-1 psql -U ged_user -d ged_saas_db -t -c "SELECT codigo FROM utils.transacao WHERE codigo='pagamento_cadastro';"
```

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/0045_pagamentos_cadastros.py
git commit -m "feat(pagamentos): migration 0045 — schema, cadastros, RLS e transação"
```

---

### Task 3: Enums + Models + registro

**Files:**
- Create: `backend/app/models/pagamentos.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: classes `Credor`, `NaturezaDespesa`, `FonteRecursos`, `ContaBancaria`, `Contrato`, `Alcada` e enums `Criticidade`, `GrupoDespesa` em `app.models`. Nomes de colunas conforme migration (Task 2).

- [ ] **Step 1: Escrever os models**

`backend/app/models/pagamentos.py`:

```python
"""Models do módulo de Pagamentos — cadastros (PAG-1). Schema `pagamentos`,
tenant-scoped com RLS (migration 0045). Dados bancários do credor guardados
cifrados (colunas *_cif); a cifra/decifra é responsabilidade do serviço."""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Criticidade(str, enum.Enum):
    URGENTE = "URGENTE"; ALTA = "ALTA"; MEDIA = "MEDIA"; BAIXA = "BAIXA"


class GrupoDespesa(str, enum.Enum):
    PESSOAL = "PESSOAL"; CUSTEIO = "CUSTEIO"; INVESTIMENTO = "INVESTIMENTO"
    DIVIDA = "DIVIDA"; OUTRAS = "OUTRAS"


class Credor(Base):
    __tablename__ = "credor"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    tipo_pessoa: Mapped[str] = mapped_column(String(10), nullable=False)
    cnpj_cpf: Mapped[str] = mapped_column(String(18), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    situacao_cadastral: Mapped[str] = mapped_column(String(10), nullable=False, default="REGULAR")
    motivo_pendencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banco_cif: Mapped[str | None] = mapped_column(Text, nullable=True)
    agencia_cif: Mapped[str | None] = mapped_column(Text, nullable=True)
    conta_cif: Mapped[str | None] = mapped_column(Text, nullable=True)
    chave_pix_cif: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class NaturezaDespesa(Base):
    __tablename__ = "natureza_despesa"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(String(150), nullable=False)
    criticidade_padrao: Mapped[str] = mapped_column(String(10), nullable=False, default="MEDIA")
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FonteRecursos(Base):
    __tablename__ = "fonte_recursos"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    grupos_despesa_permitidos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ContaBancaria(Base):
    __tablename__ = "conta_bancaria"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    banco: Mapped[str] = mapped_column(String(100), nullable=False)
    agencia: Mapped[str] = mapped_column(String(20), nullable=False)
    conta: Mapped[str] = mapped_column(String(30), nullable=False)
    id_fonte_recursos: Mapped[int] = mapped_column(ForeignKey("pagamentos.fonte_recursos.id"), nullable=False)
    grupo_despesa: Mapped[str] = mapped_column(String(20), nullable=False)
    saldo_minimo_alerta: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Contrato(Base):
    __tablename__ = "contrato"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    numero: Mapped[str] = mapped_column(String(50), nullable=False)
    id_credor: Mapped[int] = mapped_column(ForeignKey("pagamentos.credor.id"), nullable=False)
    id_unidade: Mapped[int] = mapped_column(ForeignKey("utils.unidade_trabalho.id"), nullable=False)
    objeto: Mapped[str] = mapped_column(String(255), nullable=False)
    vigencia_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    vigencia_fim: Mapped[date] = mapped_column(Date, nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Alcada(Base):
    __tablename__ = "alcada"
    __table_args__ = {"schema": "pagamentos"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("aprimora_py.tenant.id"), nullable=False)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("utils.usuario.id"), nullable=False)
    id_natureza: Mapped[int | None] = mapped_column(ForeignKey("pagamentos.natureza_despesa.id"), nullable=True)
    valor_maximo: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 2: Registrar em `__init__.py`**

Em `backend/app/models/__init__.py`, adicionar o import (perto dos outros, ordem alfabética) e as entradas em `__all__`:

```python
from .pagamentos import (
    Alcada,
    ContaBancaria,
    Contrato,
    Credor,
    Criticidade,
    FonteRecursos,
    GrupoDespesa,
    NaturezaDespesa,
)
```
E em `__all__` acrescentar: `"Alcada", "ContaBancaria", "Contrato", "Credor", "Criticidade", "FonteRecursos", "GrupoDespesa", "NaturezaDespesa",`.

- [ ] **Step 3: Verificar import + mappers**

Run:
```bash
docker exec aprimora-py-backend python -c "from app.models import Credor, ContaBancaria, Alcada; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('OK', Credor.__tablename__)"
```
Expected: `OK credor`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/pagamentos.py backend/app/models/__init__.py
git commit -m "feat(pagamentos): models e enums dos cadastros"
```

---

### Task 4: Schemas Pydantic

**Files:**
- Create: `backend/app/schemas/pagamentos.py`

**Interfaces:**
- Produces: por entidade, `<E>Create`, `<E>Update` (whitelist, todos os campos opcionais), `<E>Out`. Para credor: `CredorOut` mascara dados bancários; `CredorDadosBancariosOut` expõe decifrado. Consumido pelos routers (Task 6-9).

- [ ] **Step 1: Escrever os schemas**

`backend/app/schemas/pagamentos.py`:

```python
"""Schemas dos cadastros de Pagamentos. `*Update` são whitelist (nunca aceitam
tenant_id/id/excluido/timestamps). CredorOut mascara dados bancários; a revelação
decifrada é um schema/endpoint separado e auditado."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoPessoa = Literal["FISICA", "JURIDICA"]
SituacaoCadastral = Literal["REGULAR", "PENDENTE", "IRREGULAR"]
CriticidadeLit = Literal["URGENTE", "ALTA", "MEDIA", "BAIXA"]
GrupoDespesaLit = Literal["PESSOAL", "CUSTEIO", "INVESTIMENTO", "DIVIDA", "OUTRAS"]


# ---------- credor ----------
class DadosBancarios(BaseModel):
    banco: str | None = Field(default=None, max_length=200)
    agencia: str | None = Field(default=None, max_length=200)
    conta: str | None = Field(default=None, max_length=200)
    chave_pix: str | None = Field(default=None, max_length=200)


class CredorCreate(BaseModel):
    tipo_pessoa: TipoPessoa
    cnpj_cpf: str = Field(min_length=1, max_length=18)
    nome: str = Field(min_length=1, max_length=200)
    situacao_cadastral: SituacaoCadastral = "REGULAR"
    motivo_pendencia: str | None = Field(default=None, max_length=255)
    dados_bancarios: DadosBancarios | None = None


class CredorUpdate(BaseModel):
    tipo_pessoa: TipoPessoa | None = None
    cnpj_cpf: str | None = Field(default=None, max_length=18)
    nome: str | None = Field(default=None, max_length=200)
    situacao_cadastral: SituacaoCadastral | None = None
    motivo_pendencia: str | None = Field(default=None, max_length=255)
    dados_bancarios: DadosBancarios | None = None


class CredorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_pessoa: TipoPessoa
    cnpj_cpf: str
    nome: str
    situacao_cadastral: SituacaoCadastral
    motivo_pendencia: str | None
    tem_dados_bancarios: bool  # true se qualquer *_cif != null (preenchido no serviço)
    criado_em: datetime
    atualizado_em: datetime | None


class CredorDadosBancariosOut(DadosBancarios):
    pass


# ---------- natureza_despesa ----------
class NaturezaCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    descricao: str = Field(min_length=1, max_length=150)
    criticidade_padrao: CriticidadeLit = "MEDIA"
    ativa: bool = True


class NaturezaUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    descricao: str | None = Field(default=None, max_length=150)
    criticidade_padrao: CriticidadeLit | None = None
    ativa: bool | None = None


class NaturezaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; codigo: str; descricao: str; criticidade_padrao: CriticidadeLit; ativa: bool
    criado_em: datetime; atualizado_em: datetime | None


# ---------- fonte_recursos ----------
class FonteCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    descricao: str = Field(min_length=1, max_length=200)
    grupos_despesa_permitidos: list[GrupoDespesaLit] = Field(default_factory=list)


class FonteUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    descricao: str | None = Field(default=None, max_length=200)
    grupos_despesa_permitidos: list[GrupoDespesaLit] | None = None


class FonteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; codigo: str; descricao: str; grupos_despesa_permitidos: list[str]
    criado_em: datetime; atualizado_em: datetime | None


# ---------- conta_bancaria ----------
class ContaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    banco: str = Field(min_length=1, max_length=100)
    agencia: str = Field(min_length=1, max_length=20)
    conta: str = Field(min_length=1, max_length=30)
    id_fonte_recursos: int
    grupo_despesa: GrupoDespesaLit
    saldo_minimo_alerta: Decimal = Decimal("0")
    ativa: bool = True


class ContaUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=150)
    banco: str | None = Field(default=None, max_length=100)
    agencia: str | None = Field(default=None, max_length=20)
    conta: str | None = Field(default=None, max_length=30)
    id_fonte_recursos: int | None = None
    grupo_despesa: GrupoDespesaLit | None = None
    saldo_minimo_alerta: Decimal | None = None
    ativa: bool | None = None


class ContaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; nome: str; banco: str; agencia: str; conta: str
    id_fonte_recursos: int; grupo_despesa: GrupoDespesaLit
    saldo_minimo_alerta: Decimal; ativa: bool
    criado_em: datetime; atualizado_em: datetime | None


# ---------- contrato ----------
class ContratoCreate(BaseModel):
    numero: str = Field(min_length=1, max_length=50)
    id_credor: int
    id_unidade: int
    objeto: str = Field(min_length=1, max_length=255)
    vigencia_inicio: date
    vigencia_fim: date
    valor_total: Decimal


class ContratoUpdate(BaseModel):
    numero: str | None = Field(default=None, max_length=50)
    id_credor: int | None = None
    id_unidade: int | None = None
    objeto: str | None = Field(default=None, max_length=255)
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    valor_total: Decimal | None = None


class ContratoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; numero: str; id_credor: int; id_unidade: int; objeto: str
    vigencia_inicio: date; vigencia_fim: date; valor_total: Decimal
    criado_em: datetime; atualizado_em: datetime | None


# ---------- alcada ----------
class AlcadaCreate(BaseModel):
    id_usuario: int
    id_natureza: int | None = None
    valor_maximo: Decimal


class AlcadaUpdate(BaseModel):
    id_usuario: int | None = None
    id_natureza: int | None = None
    valor_maximo: Decimal | None = None


class AlcadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; id_usuario: int; id_natureza: int | None; valor_maximo: Decimal
    criado_em: datetime; atualizado_em: datetime | None
```

- [ ] **Step 2: Verificar import**

Run: `docker exec aprimora-py-backend python -c "from app.schemas.pagamentos import CredorCreate, ContaCreate, AlcadaOut; print('OK')"`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/pagamentos.py
git commit -m "feat(pagamentos): schemas dos cadastros"
```

---

### Task 5: Serviço do Credor (Fernet + unicidade + máscara)

**Files:**
- Create: `backend/app/services/pagamentos_cadastros.py` (começa aqui; cresce nas Tasks 7-8)
- Test: `backend/tests/test_pagamentos_cadastros.py`

**Interfaces:**
- Consumes: `app.core.crypto.encrypt/decrypt` (Task 1); models/schemas (Tasks 3-4).
- Produces: `criar_credor`, `listar_credores`, `obter_credor`, `atualizar_credor`, `excluir_credor`, `dados_bancarios_credor(db,*,tenant_id,credor_id)->DadosBancarios`. `CredorError`/`PagamentoCadastroError` (HTTPException-based). `_credor_out(credor)->dict` que preenche `tem_dados_bancarios`.

- [ ] **Step 1: Escrever teste**

`backend/tests/test_pagamentos_cadastros.py` (segue o padrão de `test_transporte_regulado_permissionario.py` para o client autenticado; ajuste imports de fixture conforme aquele arquivo):

```python
import pytest
from httpx import AsyncClient

# Fixtures `client` (AsyncClient autenticado como admin/super no tenant sobral) e
# `tenant_headers` — reusar as de tests/conftest.py / test_transporte_regulado_*.
pytestmark = pytest.mark.asyncio


async def test_credor_crud_e_cifragem(client: AsyncClient):
    # cria com dados bancários
    r = await client.post("/api/v2/pagamentos/credores", json={
        "tipo_pessoa": "JURIDICA", "cnpj_cpf": "12345678000190",
        "nome": "Medlar LTDA",
        "dados_bancarios": {"banco": "001", "agencia": "1234", "conta": "5678-9", "chave_pix": "pix@medlar"},
    })
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["tem_dados_bancarios"] is True
    # a listagem NÃO expõe dados bancários
    r = await client.get("/api/v2/pagamentos/credores")
    assert all("dados_bancarios" not in c and "conta_cif" not in c for c in r.json())
    # reveal decifra corretamente
    r = await client.get(f"/api/v2/pagamentos/credores/{cid}/dados-bancarios")
    assert r.status_code == 200
    assert r.json()["chave_pix"] == "pix@medlar"
    # unicidade de CNPJ
    r = await client.post("/api/v2/pagamentos/credores", json={
        "tipo_pessoa": "JURIDICA", "cnpj_cpf": "12345678000190", "nome": "Outro"})
    assert r.status_code == 409


async def test_credor_cifrado_no_banco(client: AsyncClient, db_conn):
    # db_conn = conexão psycopg de teste ao banco (reusar helper existente se houver;
    # senão, consultar via endpoint interno). Verifica que conta_cif != texto puro.
    r = await client.post("/api/v2/pagamentos/credores", json={
        "tipo_pessoa": "FISICA", "cnpj_cpf": "11122233344", "nome": "Fulano",
        "dados_bancarios": {"conta": "SEGREDO123"}})
    cid = r.json()["id"]
    row = db_conn.execute("SELECT conta_cif FROM pagamentos.credor WHERE id=%s", (cid,)).fetchone()
    assert row[0] is not None and "SEGREDO123" not in row[0]
```

> Se `test_transporte_regulado_*` não usa `AsyncClient` mas sim TestClient síncrono ou fixtures próprias, **espelhe exatamente aquele padrão** (mesma fixture de client/tenant/db). Não invente fixtures novas.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_cadastros.py -q`
Expected: FAIL (404 nos endpoints / módulo de serviço inexistente).

- [ ] **Step 3: Implementar serviço do credor**

`backend/app/services/pagamentos_cadastros.py`:

```python
"""Cadastros de Pagamentos — serviço de domínio (PAG-1). tenant-scoped, soft-delete,
unicidade por tenant. Dados bancários do credor cifrados via app.core.crypto."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import crypto
from ..models import Credor
from ..schemas.pagamentos import CredorCreate, CredorUpdate, DadosBancarios


def _utcnow() -> datetime:
    return datetime.utcnow()


class PagamentoCadastroError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def credor_out(c: Credor) -> dict:
    return {
        "id": c.id, "tipo_pessoa": c.tipo_pessoa, "cnpj_cpf": c.cnpj_cpf, "nome": c.nome,
        "situacao_cadastral": c.situacao_cadastral, "motivo_pendencia": c.motivo_pendencia,
        "tem_dados_bancarios": any([c.banco_cif, c.agencia_cif, c.conta_cif, c.chave_pix_cif]),
        "criado_em": c.criado_em, "atualizado_em": c.atualizado_em,
    }


async def _validar_doc_unico(db, *, tenant_id: int, cnpj_cpf: str, excluir_id: int | None = None) -> None:
    stmt = select(Credor.id).where(Credor.tenant_id == tenant_id, Credor.cnpj_cpf == cnpj_cpf,
                                   Credor.excluido.is_(False))
    if excluir_id is not None:
        stmt = stmt.where(Credor.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise PagamentoCadastroError(f"Já existe credor com o documento '{cnpj_cpf}'.", status.HTTP_409_CONFLICT)


def _aplicar_dados_bancarios(c: Credor, db_dados: DadosBancarios | None) -> None:
    if db_dados is None:
        return
    c.banco_cif = crypto.encrypt(db_dados.banco)
    c.agencia_cif = crypto.encrypt(db_dados.agencia)
    c.conta_cif = crypto.encrypt(db_dados.conta)
    c.chave_pix_cif = crypto.encrypt(db_dados.chave_pix)


async def obter_credor(db: AsyncSession, *, tenant_id: int, credor_id: int) -> Credor:
    c = (await db.execute(select(Credor).where(Credor.id == credor_id, Credor.tenant_id == tenant_id,
                                               Credor.excluido.is_(False)))).scalar_one_or_none()
    if c is None:
        raise PagamentoCadastroError("Credor não encontrado", status.HTTP_404_NOT_FOUND)
    return c


async def listar_credores(db: AsyncSession, *, tenant_id: int, q: str | None = None) -> list[Credor]:
    stmt = select(Credor).where(Credor.tenant_id == tenant_id, Credor.excluido.is_(False))
    if q:
        stmt = stmt.where(Credor.nome.ilike(f"%{q}%"))
    return list((await db.execute(stmt.order_by(Credor.nome))).scalars().all())


async def criar_credor(db: AsyncSession, *, tenant_id: int, payload: CredorCreate) -> Credor:
    await _validar_doc_unico(db, tenant_id=tenant_id, cnpj_cpf=payload.cnpj_cpf)
    c = Credor(tenant_id=tenant_id, tipo_pessoa=payload.tipo_pessoa, cnpj_cpf=payload.cnpj_cpf,
               nome=payload.nome, situacao_cadastral=payload.situacao_cadastral,
               motivo_pendencia=payload.motivo_pendencia, criado_em=_utcnow())
    _aplicar_dados_bancarios(c, payload.dados_bancarios)
    db.add(c); await db.commit(); await db.refresh(c)
    return c


async def atualizar_credor(db: AsyncSession, *, tenant_id: int, credor_id: int, payload: CredorUpdate) -> Credor:
    c = await obter_credor(db, tenant_id=tenant_id, credor_id=credor_id)
    dados = payload.model_dump(exclude_unset=True)
    if "cnpj_cpf" in dados:
        await _validar_doc_unico(db, tenant_id=tenant_id, cnpj_cpf=dados["cnpj_cpf"], excluir_id=credor_id)
    for campo in ("tipo_pessoa", "cnpj_cpf", "nome", "situacao_cadastral", "motivo_pendencia"):
        if campo in dados:
            setattr(c, campo, dados[campo])
    if "dados_bancarios" in dados and payload.dados_bancarios is not None:
        _aplicar_dados_bancarios(c, payload.dados_bancarios)
    c.atualizado_em = _utcnow(); await db.commit(); await db.refresh(c)
    return c


async def excluir_credor(db: AsyncSession, *, tenant_id: int, credor_id: int) -> None:
    c = await obter_credor(db, tenant_id=tenant_id, credor_id=credor_id)
    c.excluido = True; c.atualizado_em = _utcnow(); await db.commit()


async def dados_bancarios_credor(db: AsyncSession, *, tenant_id: int, credor_id: int) -> DadosBancarios:
    c = await obter_credor(db, tenant_id=tenant_id, credor_id=credor_id)
    return DadosBancarios(banco=crypto.decrypt(c.banco_cif), agencia=crypto.decrypt(c.agencia_cif),
                          conta=crypto.decrypt(c.conta_cif), chave_pix=crypto.decrypt(c.chave_pix_cif))
```

- [ ] **Step 4: Router do credor + registro + nginx + chave Fernet no ambiente**

Criar `backend/app/routers/pagamentos_cadastros.py` (só credor por enquanto):

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import (
    CredorCreate, CredorDadosBancariosOut, CredorOut, CredorUpdate,
)
from ..services import pagamentos_cadastros as svc

credores_router = APIRouter(prefix="/pagamentos/credores", tags=["pagamentos-cadastros"])


@credores_router.get("", response_model=list[CredorOut])
async def list_credores(q: str | None = None,
                        _: Usuario = Depends(require_permission("pagamento_cadastro")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    rows = await svc.listar_credores(db, tenant_id=tenant_id, q=q)
    return [CredorOut.model_validate(svc.credor_out(r)) for r in rows]


@credores_router.get("/{credor_id}", response_model=CredorOut)
async def get_credor(credor_id: int,
                     _: Usuario = Depends(require_permission("pagamento_cadastro")),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    c = await svc.obter_credor(db, tenant_id=tenant_id, credor_id=credor_id)
    return CredorOut.model_validate(svc.credor_out(c))


@credores_router.get("/{credor_id}/dados-bancarios", response_model=CredorDadosBancariosOut)
async def get_dados_bancarios(credor_id: int,
                              _: Usuario = Depends(require_permission("pagamento_cadastro")),
                              tenant_id: int = Depends(require_tenant_id),
                              db: AsyncSession = Depends(get_db)):
    return await svc.dados_bancarios_credor(db, tenant_id=tenant_id, credor_id=credor_id)


@credores_router.post("", response_model=CredorOut, status_code=status.HTTP_201_CREATED)
async def create_credor(payload: CredorCreate,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    c = await svc.criar_credor(db, tenant_id=tenant_id, payload=payload)
    return CredorOut.model_validate(svc.credor_out(c))


@credores_router.put("/{credor_id}", response_model=CredorOut)
async def update_credor(credor_id: int, payload: CredorUpdate,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    c = await svc.atualizar_credor(db, tenant_id=tenant_id, credor_id=credor_id, payload=payload)
    return CredorOut.model_validate(svc.credor_out(c))


@credores_router.delete("/{credor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credor(credor_id: int,
                        _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                        tenant_id: int = Depends(require_tenant_id),
                        db: AsyncSession = Depends(get_db)):
    await svc.excluir_credor(db, tenant_id=tenant_id, credor_id=credor_id)
```

Registrar em `backend/app/main.py`: no import de `.routers` adicionar `pagamentos_cadastros`, e após os includes de `transporte_regulado`:
```python
app.include_router(pagamentos_cadastros.credores_router, prefix="/api/v2")
```
Adicionar `pagamentos` ao regex em `nginx/default.conf` (linha `location ~ ^/(...)`), depois `docker exec aprimora-py-nginx nginx -s reload`.

Gerar e setar a chave Fernet no ambiente do backend (compose): adicionar `DADOS_SENSIVEIS_ENCRYPTION_KEY` ao `docker-compose.yml` (service backend, env) ou `.env`. Gerar:
```bash
docker exec aprimora-py-backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Colocar o valor em `.env`/compose e `docker compose up -d backend`.

- [ ] **Step 5: Run test to verify it passes**

Run: `docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_cadastros.py -q`
Expected: PASS (2 passed). Se `db_conn` não existir como fixture, adaptar o segundo teste para consultar via `docker exec ... psql` num passo manual e remover a asserção de fixture, mantendo o primeiro teste verde.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/pagamentos_cadastros.py backend/app/routers/pagamentos_cadastros.py backend/app/main.py nginx/default.conf backend/tests/test_pagamentos_cadastros.py docker-compose.yml
git commit -m "feat(pagamentos): CRUD de credor com cifragem Fernet e reveal auditado"
```

---

### Task 6: Naturezas e Fontes (CRUD simples)

**Files:**
- Modify: `backend/app/services/pagamentos_cadastros.py` (adicionar funções)
- Modify: `backend/app/routers/pagamentos_cadastros.py` (adicionar routers)
- Modify: `backend/app/main.py` (registrar)
- Test: `backend/tests/test_pagamentos_cadastros.py` (adicionar)

**Interfaces:**
- Produces: serviços `*_natureza`/`*_fonte` (criar/listar/obter/atualizar/excluir) + `naturezas_router`, `fontes_router`.

- [ ] **Step 1: Teste**

Adicionar em `test_pagamentos_cadastros.py`:
```python
async def test_natureza_e_fonte_crud(client):
    r = await client.post("/api/v2/pagamentos/naturezas", json={"codigo": "3.3.90.30", "descricao": "Material de consumo"})
    assert r.status_code == 201
    r = await client.post("/api/v2/pagamentos/naturezas", json={"codigo": "3.3.90.30", "descricao": "dup"})
    assert r.status_code == 409  # código único
    r = await client.post("/api/v2/pagamentos/fontes", json={"codigo": "500", "descricao": "Recursos próprios", "grupos_despesa_permitidos": ["CUSTEIO", "INVESTIMENTO"]})
    assert r.status_code == 201
    assert r.json()["grupos_despesa_permitidos"] == ["CUSTEIO", "INVESTIMENTO"]
```

- [ ] **Step 2: Run — deve falhar** (`docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_cadastros.py::test_natureza_e_fonte_crud -q`) → FAIL (404).

- [ ] **Step 3: Implementar serviços** (append em `pagamentos_cadastros.py`):

```python
from ..models import NaturezaDespesa, FonteRecursos
from ..schemas.pagamentos import NaturezaCreate, NaturezaUpdate, FonteCreate, FonteUpdate


async def _codigo_unico(db, model, *, tenant_id, codigo, excluir_id=None):
    stmt = select(model.id).where(model.tenant_id == tenant_id, model.codigo == codigo, model.excluido.is_(False))
    if excluir_id is not None:
        stmt = stmt.where(model.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise PagamentoCadastroError(f"Já existe cadastro com o código '{codigo}'.", status.HTTP_409_CONFLICT)


async def obter_natureza(db, *, tenant_id, natureza_id) -> NaturezaDespesa:
    n = (await db.execute(select(NaturezaDespesa).where(NaturezaDespesa.id == natureza_id, NaturezaDespesa.tenant_id == tenant_id, NaturezaDespesa.excluido.is_(False)))).scalar_one_or_none()
    if n is None: raise PagamentoCadastroError("Natureza não encontrada", status.HTTP_404_NOT_FOUND)
    return n

async def listar_naturezas(db, *, tenant_id) -> list[NaturezaDespesa]:
    return list((await db.execute(select(NaturezaDespesa).where(NaturezaDespesa.tenant_id == tenant_id, NaturezaDespesa.excluido.is_(False)).order_by(NaturezaDespesa.codigo))).scalars().all())

async def criar_natureza(db, *, tenant_id, payload: NaturezaCreate) -> NaturezaDespesa:
    await _codigo_unico(db, NaturezaDespesa, tenant_id=tenant_id, codigo=payload.codigo)
    n = NaturezaDespesa(tenant_id=tenant_id, criado_em=_utcnow(), **payload.model_dump())
    db.add(n); await db.commit(); await db.refresh(n); return n

async def atualizar_natureza(db, *, tenant_id, natureza_id, payload: NaturezaUpdate) -> NaturezaDespesa:
    n = await obter_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id)
    dados = payload.model_dump(exclude_unset=True)
    if "codigo" in dados: await _codigo_unico(db, NaturezaDespesa, tenant_id=tenant_id, codigo=dados["codigo"], excluir_id=natureza_id)
    for k, v in dados.items(): setattr(n, k, v)
    n.atualizado_em = _utcnow(); await db.commit(); await db.refresh(n); return n

async def excluir_natureza(db, *, tenant_id, natureza_id) -> None:
    n = await obter_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id)
    n.excluido = True; n.atualizado_em = _utcnow(); await db.commit()


async def obter_fonte(db, *, tenant_id, fonte_id) -> FonteRecursos:
    f = (await db.execute(select(FonteRecursos).where(FonteRecursos.id == fonte_id, FonteRecursos.tenant_id == tenant_id, FonteRecursos.excluido.is_(False)))).scalar_one_or_none()
    if f is None: raise PagamentoCadastroError("Fonte não encontrada", status.HTTP_404_NOT_FOUND)
    return f

async def listar_fontes(db, *, tenant_id) -> list[FonteRecursos]:
    return list((await db.execute(select(FonteRecursos).where(FonteRecursos.tenant_id == tenant_id, FonteRecursos.excluido.is_(False)).order_by(FonteRecursos.codigo))).scalars().all())

async def criar_fonte(db, *, tenant_id, payload: FonteCreate) -> FonteRecursos:
    await _codigo_unico(db, FonteRecursos, tenant_id=tenant_id, codigo=payload.codigo)
    f = FonteRecursos(tenant_id=tenant_id, criado_em=_utcnow(),
                      codigo=payload.codigo, descricao=payload.descricao,
                      grupos_despesa_permitidos=[g for g in payload.grupos_despesa_permitidos])
    db.add(f); await db.commit(); await db.refresh(f); return f

async def atualizar_fonte(db, *, tenant_id, fonte_id, payload: FonteUpdate) -> FonteRecursos:
    f = await obter_fonte(db, tenant_id=tenant_id, fonte_id=fonte_id)
    dados = payload.model_dump(exclude_unset=True)
    if "codigo" in dados: await _codigo_unico(db, FonteRecursos, tenant_id=tenant_id, codigo=dados["codigo"], excluir_id=fonte_id)
    for k, v in dados.items(): setattr(f, k, v)
    f.atualizado_em = _utcnow(); await db.commit(); await db.refresh(f); return f

async def excluir_fonte(db, *, tenant_id, fonte_id) -> None:
    f = await obter_fonte(db, tenant_id=tenant_id, fonte_id=fonte_id)
    f.excluido = True; f.atualizado_em = _utcnow(); await db.commit()
```

- [ ] **Step 4: Routers** (append em `pagamentos_cadastros.py` router file) — seguir exatamente a forma do `credores_router` (5 endpoints cada), com `require_permission("pagamento_cadastro", ...)`, schemas `NaturezaOut`/`FonteOut`, prefixos `/pagamentos/naturezas` e `/pagamentos/fontes`. Registrar `naturezas_router` e `fontes_router` no `main.py`.

```python
naturezas_router = APIRouter(prefix="/pagamentos/naturezas", tags=["pagamentos-cadastros"])

@naturezas_router.get("", response_model=list[NaturezaOut])
async def list_naturezas(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                         tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return [NaturezaOut.model_validate(r) for r in await svc.listar_naturezas(db, tenant_id=tenant_id)]

@naturezas_router.post("", response_model=NaturezaOut, status_code=status.HTTP_201_CREATED)
async def create_natureza(payload: NaturezaCreate, _: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                          tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return NaturezaOut.model_validate(await svc.criar_natureza(db, tenant_id=tenant_id, payload=payload))

@naturezas_router.put("/{natureza_id}", response_model=NaturezaOut)
async def update_natureza(natureza_id: int, payload: NaturezaUpdate, _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                          tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return NaturezaOut.model_validate(await svc.atualizar_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id, payload=payload))

@naturezas_router.delete("/{natureza_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_natureza(natureza_id: int, _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                          tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    await svc.excluir_natureza(db, tenant_id=tenant_id, natureza_id=natureza_id)
```
(E o análogo `fontes_router` com `FonteOut`/`FonteCreate`/`FonteUpdate` e `svc.*_fonte`, incluindo um `GET /{fonte_id}`.) Import dos schemas novos no topo do router file.

- [ ] **Step 5: Run — deve passar** (`docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_cadastros.py -q`) → PASS.

- [ ] **Step 6: Commit** `feat(pagamentos): CRUD de natureza de despesa e fonte de recursos`.

---

### Task 7: Conta bancária (validação fonte × grupo)

**Files:**
- Modify: `backend/app/services/pagamentos_cadastros.py`, `backend/app/routers/pagamentos_cadastros.py`, `backend/app/main.py`
- Test: `backend/tests/test_pagamentos_cadastros.py`

**Interfaces:**
- Produces: `criar_conta`/`atualizar_conta`/... com validação de que `grupo_despesa` ∈ `fonte.grupos_despesa_permitidos` (ou lista vazia = todos); `contas_router`.

- [ ] **Step 1: Teste**

```python
async def test_conta_valida_fonte_grupo(client):
    f = await client.post("/api/v2/pagamentos/fontes", json={"codigo": "600", "descricao": "F", "grupos_despesa_permitidos": ["CUSTEIO"]})
    fid = f.json()["id"]
    # grupo compatível → 201
    ok = await client.post("/api/v2/pagamentos/contas", json={"nome": "Conta A", "banco": "001", "agencia": "1", "conta": "2", "id_fonte_recursos": fid, "grupo_despesa": "CUSTEIO"})
    assert ok.status_code == 201
    # grupo incompatível → 422
    bad = await client.post("/api/v2/pagamentos/contas", json={"nome": "Conta B", "banco": "001", "agencia": "1", "conta": "3", "id_fonte_recursos": fid, "grupo_despesa": "INVESTIMENTO"})
    assert bad.status_code == 422
```

- [ ] **Step 2: Run — falha** (404). 

- [ ] **Step 3: Implementar** (append no serviço):

```python
from ..models import ContaBancaria
from ..schemas.pagamentos import ContaCreate, ContaUpdate


async def _validar_fonte_grupo(db, *, tenant_id, id_fonte_recursos, grupo_despesa):
    fonte = await obter_fonte(db, tenant_id=tenant_id, fonte_id=id_fonte_recursos)
    permitidos = fonte.grupos_despesa_permitidos or []
    if permitidos and grupo_despesa not in permitidos:
        raise PagamentoCadastroError(
            f"Grupo '{grupo_despesa}' incompatível com a fonte '{fonte.codigo}'.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)

async def obter_conta(db, *, tenant_id, conta_id) -> ContaBancaria:
    c = (await db.execute(select(ContaBancaria).where(ContaBancaria.id == conta_id, ContaBancaria.tenant_id == tenant_id, ContaBancaria.excluido.is_(False)))).scalar_one_or_none()
    if c is None: raise PagamentoCadastroError("Conta não encontrada", status.HTTP_404_NOT_FOUND)
    return c

async def listar_contas(db, *, tenant_id) -> list[ContaBancaria]:
    return list((await db.execute(select(ContaBancaria).where(ContaBancaria.tenant_id == tenant_id, ContaBancaria.excluido.is_(False)).order_by(ContaBancaria.nome))).scalars().all())

async def criar_conta(db, *, tenant_id, payload: ContaCreate) -> ContaBancaria:
    await _validar_fonte_grupo(db, tenant_id=tenant_id, id_fonte_recursos=payload.id_fonte_recursos, grupo_despesa=payload.grupo_despesa)
    c = ContaBancaria(tenant_id=tenant_id, criado_em=_utcnow(), **payload.model_dump())
    db.add(c); await db.commit(); await db.refresh(c); return c

async def atualizar_conta(db, *, tenant_id, conta_id, payload: ContaUpdate) -> ContaBancaria:
    c = await obter_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    dados = payload.model_dump(exclude_unset=True)
    fonte = dados.get("id_fonte_recursos", c.id_fonte_recursos)
    grupo = dados.get("grupo_despesa", c.grupo_despesa)
    if "id_fonte_recursos" in dados or "grupo_despesa" in dados:
        await _validar_fonte_grupo(db, tenant_id=tenant_id, id_fonte_recursos=fonte, grupo_despesa=grupo)
    for k, v in dados.items(): setattr(c, k, v)
    c.atualizado_em = _utcnow(); await db.commit(); await db.refresh(c); return c

async def excluir_conta(db, *, tenant_id, conta_id) -> None:
    c = await obter_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    c.excluido = True; c.atualizado_em = _utcnow(); await db.commit()
```

- [ ] **Step 4: Router** `contas_router` (prefixo `/pagamentos/contas`, 5 endpoints + `GET /{id}`, schema `ContaOut`), registrar no `main.py`.

- [ ] **Step 5: Run — passa.**

- [ ] **Step 6: Commit** `feat(pagamentos): CRUD de conta bancária com validação fonte×grupo`.

---

### Task 8: Contrato e Alçada

**Files:**
- Modify: serviço, router, `main.py`; Test: `test_pagamentos_cadastros.py`

**Interfaces:**
- Produces: CRUD de `contrato` (unicidade `numero`; valida `id_credor` do tenant e `id_unidade` existente) e `alcada` (unique `(usuario, natureza)`); `contratos_router`, `alcadas_router`.

- [ ] **Step 1: Teste**

```python
async def test_contrato_e_alcada(client):
    cr = await client.post("/api/v2/pagamentos/credores", json={"tipo_pessoa": "JURIDICA", "cnpj_cpf": "99888777000166", "nome": "Fornecedor X"})
    cid = cr.json()["id"]
    # id_unidade: usar uma unidade existente do tenant (ver conftest/seed); aqui assume 1.
    ct = await client.post("/api/v2/pagamentos/contratos", json={"numero": "CT-001/2026", "id_credor": cid, "id_unidade": 1, "objeto": "Fornecimento", "vigencia_inicio": "2026-01-01", "vigencia_fim": "2026-12-31", "valor_total": "100000.00"})
    assert ct.status_code == 201, ct.text
    dup = await client.post("/api/v2/pagamentos/contratos", json={"numero": "CT-001/2026", "id_credor": cid, "id_unidade": 1, "objeto": "x", "vigencia_inicio": "2026-01-01", "vigencia_fim": "2026-12-31", "valor_total": "1.00"})
    assert dup.status_code == 409
    al = await client.post("/api/v2/pagamentos/alcadas", json={"id_usuario": 2, "valor_maximo": "500000.00"})
    assert al.status_code == 201
```
> `id_unidade` e `id_usuario`: usar valores que existam no tenant de teste (conferir seed/`conftest`; a unidade/usuário admin do tenant sobral). Ajustar os ids conforme o ambiente de testes real.

- [ ] **Step 2: Run — falha.**

- [ ] **Step 3: Implementar** contrato (valida credor do tenant via `obter_credor`; unicidade `numero` via `_codigo_unico` adaptado para campo `numero` — criar `_numero_unico` análogo) e alçada (valida usuário existe no tenant; unique parcial já no banco → capturar violação ou pré-checar). Espelhar a estrutura das Tasks 6/7 (obter/listar/criar/atualizar/excluir), com:

```python
from ..models import Contrato, Alcada, UnidadeTrabalho
from ..schemas.pagamentos import ContratoCreate, ContratoUpdate, AlcadaCreate, AlcadaUpdate

async def _numero_unico(db, *, tenant_id, numero, excluir_id=None):
    stmt = select(Contrato.id).where(Contrato.tenant_id == tenant_id, Contrato.numero == numero, Contrato.excluido.is_(False))
    if excluir_id is not None: stmt = stmt.where(Contrato.id != excluir_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise PagamentoCadastroError(f"Já existe contrato número '{numero}'.", status.HTTP_409_CONFLICT)

async def _validar_unidade(db, *, tenant_id, id_unidade):
    u = (await db.execute(select(UnidadeTrabalho.id).where(UnidadeTrabalho.id == id_unidade, UnidadeTrabalho.tenant_id == tenant_id, UnidadeTrabalho.excluido.is_(False)))).scalar_one_or_none()
    if u is None: raise PagamentoCadastroError("Unidade (órgão) inválida.", status.HTTP_422_UNPROCESSABLE_ENTITY)
```
Com `criar_contrato` validando `_numero_unico`, `obter_credor` (mesmo tenant) e `_validar_unidade`; `criar_alcada` validando `_alcada_unica(tenant, id_usuario, id_natureza)` análoga ao `_codigo_unico`. Demais funções (obter/listar/atualizar/excluir) idênticas em forma às Tasks 6/7.

- [ ] **Step 4: Routers** `contratos_router` e `alcadas_router` (5 endpoints + GET/{id}), registrar no `main.py`.

- [ ] **Step 5: Run — passa** (suíte inteira do arquivo).

- [ ] **Step 6: Commit** `feat(pagamentos): CRUD de contrato e alçada`.

---

### Task 9: Endpoint de enums + regressão backend

**Files:**
- Modify: `backend/app/routers/pagamentos_cadastros.py`, `backend/app/main.py`

**Interfaces:**
- Produces: `GET /pagamentos/enums` → `{"criticidade": [...], "grupo_despesa": [...]}` para popular selects.

- [ ] **Step 1: Implementar**

```python
enums_router = APIRouter(prefix="/pagamentos/enums", tags=["pagamentos-cadastros"])

@enums_router.get("")
async def get_enums(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                    __: int = Depends(require_tenant_id)):
    from ..models import Criticidade, GrupoDespesa
    return {"criticidade": [e.value for e in Criticidade], "grupo_despesa": [e.value for e in GrupoDespesa]}
```
Registrar no `main.py`.

- [ ] **Step 2: Rodar a suíte do módulo + regressão geral**

Run:
```bash
docker exec aprimora-py-backend python -m pytest tests/test_pagamentos_cadastros.py tests/test_crypto.py -q
docker exec aprimora-py-backend python -m pytest -q
```
Expected: módulo verde; suíte completa sem novas falhas.

- [ ] **Step 3: Commit** `feat(pagamentos): endpoint de enums + regressão`.

---

### Task 10: Frontend — API client

**Files:**
- Modify: `frontend/lib/api.ts`

**Interfaces:**
- Produces: `api.pagamentos.cadastros.{credores,naturezas,fontes,contas,contratos,alcadas}` com `list/get/create/update/remove`, `credores.dadosBancarios(id)`, `enums()`. Tipos TS por entidade.

- [ ] **Step 1: Tipos + seção da API**

Adicionar tipos (espelhando os `*Out` do backend) e a seção `pagamentos` no objeto `api`, seguindo o padrão de `templatesDocumento`/`minutas` já existentes (mesmo arquivo). Ex. do bloco credores:
```ts
export interface Credor {
  id: number; tipo_pessoa: "FISICA" | "JURIDICA"; cnpj_cpf: string; nome: string;
  situacao_cadastral: "REGULAR" | "PENDENTE" | "IRREGULAR"; motivo_pendencia: string | null;
  tem_dados_bancarios: boolean; criado_em: string; atualizado_em: string | null;
}
export interface DadosBancarios { banco: string | null; agencia: string | null; conta: string | null; chave_pix: string | null; }
// ... Natureza, Fonte, Conta, Contrato, Alcada análogos aos *Out

// dentro de `export const api = { ... }`:
  pagamentos: {
    cadastros: {
      credores: {
        list: (q?: string) => request<Credor[]>(`/pagamentos/credores${qs({ q })}`),
        get: (id: number) => request<Credor>(`/pagamentos/credores/${id}`),
        dadosBancarios: (id: number) => request<DadosBancarios>(`/pagamentos/credores/${id}/dados-bancarios`),
        create: (d: unknown) => request<Credor>("/pagamentos/credores", { method: "POST", body: JSON.stringify(d) }),
        update: (id: number, d: unknown) => request<Credor>(`/pagamentos/credores/${id}`, { method: "PUT", body: JSON.stringify(d) }),
        remove: (id: number) => request<void>(`/pagamentos/credores/${id}`, { method: "DELETE" }),
      },
      // naturezas, fontes, contas, contratos, alcadas: mesmo shape (sem dadosBancarios)
      enums: () => request<{ criticidade: string[]; grupo_despesa: string[] }>("/pagamentos/enums"),
    },
  },
```

- [ ] **Step 2: tsc** — `docker exec aprimora-py-frontend npx tsc --noEmit` → exit 0.

- [ ] **Step 3: Commit** `feat(pagamentos): API client dos cadastros`.

---

### Task 11: Frontend — telas admin + menu + rota nginx

**Files:**
- Create: `frontend/app/(app)/pagamentos/cadastros/{credores,naturezas,fontes,contas,contratos,alcadas}/page.tsx`
- Modify: `frontend/components/Sidebar.tsx`

**Interfaces:**
- Consumes: `api.pagamentos.cadastros.*` (Task 10).

- [ ] **Step 1: Páginas**

Para naturezas/fontes/contratos/alcadas: usar `CrudPage` (ver `app/(app)/assuntos/page.tsx`). Para `contas` (validação fonte×grupo, selects dependentes) e `credores` (dados bancários + reveal): página custom com `Dialog` + form, seguindo `templates-documento/page.tsx`. Exemplo mínimo (naturezas):
```tsx
"use client";
import { CrudPage } from "@/components/CrudPage";
import { api, type Natureza } from "@/lib/api";
export default function NaturezasPage() {
  return (
    <CrudPage<Natureza>
      title="Naturezas de despesa"
      queryKey={["pag-naturezas"]}
      fetchList={() => api.pagamentos.cadastros.naturezas.list()}
      createFn={api.pagamentos.cadastros.naturezas.create}
      updateFn={api.pagamentos.cadastros.naturezas.update}
      deleteFn={api.pagamentos.cadastros.naturezas.remove}
      emptyForm={{ codigo: "", descricao: "", criticidade_padrao: "MEDIA", ativa: true }}
      columns={[
        { header: "Código", render: (r) => r.codigo },
        { header: "Descrição", render: (r) => r.descricao },
        { header: "Ativa", render: (r) => (r.ativa ? "Sim" : "Não") },
      ]}
      fields={[
        { name: "codigo", label: "Código", required: true },
        { name: "descricao", label: "Descrição", required: true, colSpan: 2 },
        { name: "criticidade_padrao", label: "Criticidade", type: "select", options: [
          { value: "URGENTE", label: "Urgente" }, { value: "ALTA", label: "Alta" },
          { value: "MEDIA", label: "Média" }, { value: "BAIXA", label: "Baixa" } ] },
        { name: "ativa", label: "Ativa", type: "checkbox" },
      ]}
    />
  );
}
```
Credores/contas: página custom (reuso de `Dialog`, `Input`, `Select`, `useConfirm`, `useToast`) — credor com seção "Dados bancários" e botão "Revelar" que chama `dadosBancarios(id)`; conta com select de fonte + select de grupo (validar no submit; exibir erro 422 via toast).

- [ ] **Step 2: Menu** — em `Sidebar.tsx`, adicionar grupo:
```tsx
{
  title: "Pagamentos",
  defaultOpen: false,
  items: [
    { label: "Credores", href: "/pagamentos/cadastros/credores", icon: UserCircle, perm: "pagamento_cadastro" },
    { label: "Naturezas", href: "/pagamentos/cadastros/naturezas", icon: Layers, perm: "pagamento_cadastro" },
    { label: "Fontes de recursos", href: "/pagamentos/cadastros/fontes", icon: BookOpen, perm: "pagamento_cadastro" },
    { label: "Contas bancárias", href: "/pagamentos/cadastros/contas", icon: ClipboardList, perm: "pagamento_cadastro" },
    { label: "Contratos", href: "/pagamentos/cadastros/contratos", icon: FileText, perm: "pagamento_cadastro" },
    { label: "Alçadas", href: "/pagamentos/cadastros/alcadas", icon: Shield, perm: "pagamento_cadastro" },
  ],
},
```
(ícones já importados no arquivo).

- [ ] **Step 3: nginx** — confirmar `pagamentos` no regex de `nginx/default.conf` (feito na Task 5); `docker compose restart frontend` (Fast Refresh no Windows não pega arquivos/rotas novos sob bind mount).

- [ ] **Step 4: tsc** — `docker exec aprimora-py-frontend npx tsc --noEmit` → 0.

- [ ] **Step 5: Commit** `feat(pagamentos): telas de cadastros + item de menu`.

---

### Task 12: Verificação ponta-a-ponta

**Files:** nenhum (validação).

- [ ] **Step 1: Subir stack** — `docker compose up -d` + `docker start ged-saas-project-db-1`; aguardar health 200.

- [ ] **Step 2: Fluxo no browser** (login `admin@local.test`/`admin123`, tenant sobral via localhost:8090; usar Edge/Playwright `channel: "msedge"` a partir de `tests-e2e/` como já feito na sessão da minuta):
  - Menu "Pagamentos" visível; abrir cada tela.
  - Criar fonte (grupos CUSTEIO) → criar conta CUSTEIO (ok) → tentar conta INVESTIMENTO nessa fonte (erro 422 no toast).
  - Criar credor com dados bancários → listagem não mostra dados → "Revelar" decifra.
  - Criar natureza, contrato (com credor+unidade), alçada.

- [ ] **Step 3: Conferir cifragem no banco**
```bash
docker exec ged-saas-project-db-1 psql -U ged_user -d ged_saas_db -t -c "SELECT conta_cif FROM pagamentos.credor WHERE excluido=false LIMIT 1;"
```
Expected: valor Fernet (base64 `gAAAAA...`), não legível.

- [ ] **Step 4: Suíte + tsc final**
```bash
docker exec aprimora-py-backend python -m pytest -q
docker exec aprimora-py-frontend npx tsc --noEmit
```
Expected: tudo verde.

- [ ] **Step 5: Commit final (se houver ajustes)** `test(pagamentos): validação ponta-a-ponta do PAG-1`.

---

## Notas de integração

- **Chave Fernet**: adicionar `DADOS_SENSIVEIS_ENCRYPTION_KEY` ao `docker-compose.yml` (env do backend/worker) e documentar no RUNBOOK/.env. Sem ela, criar credor com dados bancários retorna 500 explícito (`CryptoConfigError`).
- **Migration em paralelo**: se ao mergear a branch o head tiver mudado (0043/0044 de outras branches entraram), rebasear `down_revision` da 0045 para o novo head e renumerar se necessário.
- **Fixtures de teste**: este plano assume o padrão de client/tenant de `tests/test_transporte_regulado_permissionario.py`. Confirmar os nomes reais das fixtures (`client`, `db_conn`, ids de unidade/usuário do seed) antes de rodar; ajustar os testes ao que existe, sem criar fixtures novas.
