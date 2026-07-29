# Modularização F1 — catálogo, contratação e enforcement no RBAC

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado)
> ou superpowers:executing-plans para implementar tarefa a tarefa. Os passos usam checkbox (`- [ ]`).

**Goal:** Criar o conceito de módulo contratável por tenant e fazer o RBAC existente respeitá-lo,
sem que nada mude visualmente para o usuário.

**Architecture:** Três tabelas novas em `aprimora_py` (catálogo global de módulos, junção
módulo↔transação, contratação por tenant). `load_permissions()` passa a descartar transações de
módulo não contratado nos **dois** ramos (super-usuário e comum) — como `require_permission` já
chama essa função, os ~38 routers herdam o bloqueio sem serem tocados. `/modulos/me` é reescrito
para devolver contratado ∩ permitido, abandonando as tabelas legadas do PHP.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic (autogenerate DESLIGADO — migration escrita à
mão), Postgres 16, pytest/pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-07-28-modularizacao-launcher-design.md`

## Global Constraints

- Idioma: código, comentários, docstrings e mensagens de commit em **pt-BR**.
- Migration escrita **à mão**. `target_metadata = None` — nunca rodar autogenerate.
- Numeração `0073_modularizacao_catalogo.py`, `down_revision = "0072"`, **head único**.
- `downgrade()` desfaz o `upgrade()` na ordem inversa.
- Todo pytest roda com `-e PYTEST_DB_HOST=db`: `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest ...`
- Exclusão é **soft-delete** (`excluido=True`), nunca DELETE físico.
- `tenant_id` **sempre vem do caller**, nunca do payload.
- Carga por id filtra `tenant_id` + `excluido.is_(False)` e devolve **404 cross-tenant**, não 403.
- `app_name` do settings é `"sistemas"` — é o valor usado em `Sistema.app`.
- **Duas exceções deliberadas ao boilerplate de RLS**, já justificadas no spec §4.1: `tenant_modulo`
  não leva RLS (tabela de plataforma, escrita pelo platform admin sobre outros tenants — precedente:
  `aprimora_py.tenant`); `modulo` e `modulo_transacao` são catálogos globais sem `tenant_id`.
  **Não "corrigir" isso.**

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `backend/alembic/versions/0073_modularizacao_catalogo.py` | Cria as 3 tabelas + backfill de contratação |
| `backend/app/models/modulo.py` | **Modificar** — renomeia os models legados, adiciona os 3 novos |
| `backend/app/models/__init__.py` | **Modificar** — reexporta os novos nomes |
| `backend/app/schemas/modulo.py` | **Criar** — `ModuloOut`, `ModuloContratacaoIn`, `TenantModulosOut` |
| `backend/app/services/modulos.py` | **Criar** — catálogo, contratação, resolução do que o usuário vê |
| `backend/app/services/permissoes.py` | **Modificar** — filtro por contratação nos dois ramos |
| `backend/app/routers/modulos.py` | **Reescrever** — `/modulos/me` real |
| `backend/app/routers/admin_tenants.py` | **Modificar** — `GET/PUT /admin/tenants/{id}/modulos` |
| `backend/app/cli/seed_bootstrap.py` | **Modificar** — semeia catálogo + junção, idempotente |
| `backend/app/cli/tenant.py` | **Modificar** — `provisionar_tenant --modulos` |
| `backend/tests/test_modulos_*.py` | 4 arquivos de teste de comportamento |
| `backend/tests/test_permissoes_modulo.py` | O teste crítico do enforcement |
| `backend/tests/test_guarda_modularizacao.py` | 2 testes de regressão estrutural |

**Nota sobre `comum`:** o catálogo tem **seis** linhas, não cinco. As cinco de produto
(`protocolo`, `pagamentos`, `frota`, `transporte`, `administracao`) mais `comum`, com
`contratavel = false`. `comum` abriga as transações das telas transversais (dashboard, perfil,
busca), nunca aparece no launcher e nunca é bloqueada. Sem ela, o teste de transação órfã (Task 8)
reprovaria por causa de telas que, por decisão de design (spec §12), não pertencem a módulo nenhum.

---

### Task 1: Migration 0073 — as três tabelas e o backfill

**Files:**
- Create: `backend/alembic/versions/0073_modularizacao_catalogo.py`
- Test: `backend/tests/test_modulos_migration.py`

**Interfaces:**
- Consumes: nada (primeira task)
- Produces: tabelas `aprimora_py.modulo` (id, slug, nome, icone, ordem, contratavel, ativo),
  `aprimora_py.modulo_transacao` (id, id_modulo, id_transacao),
  `aprimora_py.tenant_modulo` (id, tenant_id, id_modulo, contratado_em, ativo, excluido).
  Seis slugs semeados: `protocolo`, `pagamentos`, `frota`, `transporte`, `administracao`, `comum`.

- [ ] **Step 1: Escrever a migration**

```python
"""Modularização F1 — catálogo de módulos, junção com transação e contratação por tenant.

Revision ID: 0073
Revises: 0072
Create Date: 2026-07-28

Três tabelas em aprimora_py:
- modulo: catálogo GLOBAL do produto (sem tenant_id, sem RLS).
- modulo_transacao: junção GLOBAL módulo <-> utils.transacao. Fica do NOSSO lado
  de propósito: `utils.*` é território do PHP legado e não é estendido aqui.
- tenant_modulo: contratação por tenant. SEM RLS por decisão (spec §4.1) — é
  tabela de plataforma, escrita pelo platform admin operando SOBRE outros
  tenants; uma policy em app.tenant_id bloquearia justamente esse caso de uso.
  Mesmo padrão de aprimora_py.tenant, que também não tem RLS.

O backfill contrata os 5 módulos de produto para TODOS os tenants existentes:
ninguém perde acesso no deploy. `comum` não é contratável.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0073"
down_revision: str | Sequence[str] | None = "0072"
branch_labels = None
depends_on = None
S = "aprimora_py"

MODULOS = [
    # (slug, nome, icone, ordem, contratavel)
    ("protocolo", "Protocolo", "FileText", 1, True),
    ("pagamentos", "Pagamentos", "Wallet", 2, True),
    ("frota", "Frota", "Truck", 3, True),
    ("transporte", "Transporte Regulado", "Bus", 4, True),
    ("administracao", "Administração", "Settings", 5, True),
    ("comum", "Comum", None, 99, False),
]


def upgrade() -> None:
    op.create_table(
        "modulo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(30), nullable=False),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("icone", sa.String(50), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contratavel", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.UniqueConstraint("slug", name="uq_modulo_slug"),
        schema=S,
    )
    op.execute(f"GRANT SELECT ON {S}.modulo TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.modulo_id_seq TO aprimora_app")

    op.create_table(
        "modulo_transacao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("id_modulo", sa.Integer(), sa.ForeignKey(f"{S}.modulo.id"), nullable=False),
        sa.Column("id_transacao", sa.Integer(), sa.ForeignKey("utils.transacao.id"), nullable=False),
        sa.UniqueConstraint("id_modulo", "id_transacao", name="uq_modulo_transacao"),
        schema=S,
    )
    op.create_index("ix_modulo_transacao_transacao", "modulo_transacao", ["id_transacao"], schema=S)
    op.execute(f"GRANT SELECT ON {S}.modulo_transacao TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.modulo_transacao_id_seq TO aprimora_app")

    op.create_table(
        "tenant_modulo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey(f"{S}.tenant.id"), nullable=False),
        sa.Column("id_modulo", sa.Integer(), sa.ForeignKey(f"{S}.modulo.id"), nullable=False),
        sa.Column("contratado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("excluido", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        schema=S,
    )
    op.create_index(
        "uq_tenant_modulo_vivo", "tenant_modulo", ["tenant_id", "id_modulo"],
        unique=True, postgresql_where=sa.text("excluido = false"), schema=S,
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.tenant_modulo TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.tenant_modulo_id_seq TO aprimora_app")

    modulo = sa.table(
        "modulo",
        sa.column("slug"), sa.column("nome"), sa.column("icone"),
        sa.column("ordem"), sa.column("contratavel"),
        schema=S,
    )
    op.bulk_insert(modulo, [
        {"slug": s, "nome": n, "icone": i, "ordem": o, "contratavel": c}
        for s, n, i, o, c in MODULOS
    ])

    # Backfill: todo tenant existente contrata os 5 módulos de produto.
    op.execute(f"""
        INSERT INTO {S}.tenant_modulo (tenant_id, id_modulo)
        SELECT t.id, m.id
          FROM {S}.tenant t
         CROSS JOIN {S}.modulo m
         WHERE m.contratavel = true
    """)


def downgrade() -> None:
    op.drop_table("tenant_modulo", schema=S)
    op.drop_index("ix_modulo_transacao_transacao", table_name="modulo_transacao", schema=S)
    op.drop_table("modulo_transacao", schema=S)
    op.drop_table("modulo", schema=S)
```

- [ ] **Step 2: Aplicar e conferir head único**

```bash
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic heads
```

Esperado: `upgrade` sem erro; `heads` imprime **uma** linha, `0073 (head)`.

- [ ] **Step 3: Escrever o teste de reversibilidade e de backfill**

```python
"""Migration 0073 — catálogo de módulos: estrutura e backfill."""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_catalogo_tem_seis_modulos(admin_session):
    linhas = (await admin_session.execute(
        text("SELECT slug, contratavel FROM aprimora_py.modulo ORDER BY ordem")
    )).all()
    slugs = [r[0] for r in linhas]
    assert slugs == ["protocolo", "pagamentos", "frota", "transporte",
                     "administracao", "comum"]
    contratavel = {r[0]: r[1] for r in linhas}
    assert contratavel["comum"] is False
    assert all(contratavel[s] for s in slugs if s != "comum")


@pytest.mark.asyncio
async def test_backfill_contratou_cinco_no_tenant_default(admin_session):
    # O backfill roda na migration, então só alcança tenants que já existiam.
    # O tenant default é o único garantido nessa condição.
    total = (await admin_session.execute(text("""
        SELECT COUNT(*) FROM aprimora_py.tenant_modulo tm
          JOIN aprimora_py.tenant t ON t.id = tm.tenant_id
         WHERE t.slug = 'sobral' AND tm.excluido = false
    """))).scalar_one()
    assert total == 5


@pytest.mark.asyncio
async def test_unicidade_parcial_ignora_excluido(admin_session):
    tid = (await admin_session.execute(
        text("SELECT id FROM aprimora_py.tenant WHERE slug = 'sobral'")
    )).scalar_one()
    mid = (await admin_session.execute(
        text("SELECT id FROM aprimora_py.modulo WHERE slug = 'frota'")
    )).scalar_one()
    # Marca o vínculo vivo como excluído e insere outro: o índice parcial
    # (WHERE excluido = false) tem que permitir a convivência.
    await admin_session.execute(text(
        "UPDATE aprimora_py.tenant_modulo SET excluido = true "
        "WHERE tenant_id = :t AND id_modulo = :m"), {"t": tid, "m": mid})
    await admin_session.execute(text(
        "INSERT INTO aprimora_py.tenant_modulo (tenant_id, id_modulo) "
        "VALUES (:t, :m)"), {"t": tid, "m": mid})
    await admin_session.flush()

    vivos = (await admin_session.execute(text(
        "SELECT COUNT(*) FROM aprimora_py.tenant_modulo "
        "WHERE tenant_id = :t AND id_modulo = :m AND excluido = false"
    ), {"t": tid, "m": mid})).scalar_one()
    total = (await admin_session.execute(text(
        "SELECT COUNT(*) FROM aprimora_py.tenant_modulo "
        "WHERE tenant_id = :t AND id_modulo = :m"
    ), {"t": tid, "m": mid})).scalar_one()
    assert vivos == 1, "deveria haver exatamente um vínculo vivo"
    assert total == 2, "o vínculo soft-deletado deveria continuar na tabela"
    await admin_session.rollback()
```

- [ ] **Step 4: Rodar os testes**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_migration.py -v
```

Esperado: 3 passed.

- [ ] **Step 5: Validar a reversibilidade**

```bash
docker exec aprimora-py-backend alembic downgrade -1
docker exec aprimora-py-backend alembic upgrade head
```

Esperado: os dois sem erro. Se `downgrade` falhar por FK, a ordem do `drop_table` está errada.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0073_modularizacao_catalogo.py backend/tests/test_modulos_migration.py
git commit -m "feat(modulos): migration 0073 — catálogo, junção e contratação por tenant"
```

---

### Task 2: Models

**Files:**
- Modify: `backend/app/models/modulo.py`
- Modify: `backend/app/models/__init__.py:48,132,152`

**Interfaces:**
- Consumes: tabelas da Task 1
- Produces: `Modulo` (slug, nome, icone, ordem, contratavel, ativo), `ModuloTransacao`
  (id_modulo, id_transacao), `TenantModulo` (tenant_id, id_modulo, ativo, excluido).
  Os models legados passam a se chamar `ModuloLegado` e `ConfiguracoesModulosLegado`.

O nome `Modulo` hoje pertence ao model da tabela legada `public.modulos`. Como F1 reescreve o único
consumidor (`routers/modulos.py`), renomear é seguro — foi verificado que as duas classes só são
referenciadas em `models/__init__.py` e nesse router.

- [ ] **Step 1: Reescrever `models/modulo.py`**

```python
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..database import Base


class Modulo(Base):
    """Catálogo GLOBAL de módulos do produto. Sem tenant_id de propósito."""

    __tablename__ = "modulo"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    icone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contratavel: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ModuloTransacao(Base):
    """Junção GLOBAL módulo <-> utils.transacao. Do nosso lado, não do legado."""

    __tablename__ = "modulo_transacao"
    __table_args__ = (
        UniqueConstraint("id_modulo", "id_transacao", name="uq_modulo_transacao"),
        {"schema": "aprimora_py"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_modulo: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.modulo.id"), nullable=False
    )
    id_transacao: Mapped[int] = mapped_column(
        ForeignKey("utils.transacao.id"), nullable=False
    )


class TenantModulo(Base):
    """Contratação de um módulo por um tenant. SEM RLS — ver spec §4.1."""

    __tablename__ = "tenant_modulo"
    __table_args__ = {"schema": "aprimora_py"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_modulo: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.modulo.id"), nullable=False
    )
    contratado_em: Mapped[object] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# --- Legado do PHP. Sai do ORM na fatia F4; ninguém deve passar a usar. ---


class ModuloLegado(Base):
    __tablename__ = "modulos"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    modulo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    icone: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ConfiguracoesModulosLegado(Base):
    __tablename__ = "configuracoes_modulos"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_configuracao: Mapped[int] = mapped_column(
        ForeignKey("public.configuracoes.id"), nullable=False
    )
    id_modulo: Mapped[int] = mapped_column(ForeignKey("public.modulos.id"), nullable=False)
    ambiente: Mapped[str | None] = mapped_column(
        Enum("desenvolvimento", "homologacao", "producao", name="ambiente"), nullable=True
    )
    url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ativo: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
```

- [ ] **Step 2: Ajustar `models/__init__.py`**

Trocar a linha 48 por:

```python
from .modulo import (
    ConfiguracoesModulosLegado,
    Modulo,
    ModuloLegado,
    ModuloTransacao,
    TenantModulo,
)
```

E no `__all__`, substituir `"ConfiguracoesModulos"` e `"Modulo"` por `"ConfiguracoesModulosLegado"`,
`"Modulo"`, `"ModuloLegado"`, `"ModuloTransacao"`, `"TenantModulo"` (mantendo a ordem alfabética do
arquivo).

- [ ] **Step 3: Verificar que o app ainda importa**

```bash
docker exec aprimora-py-backend python -c "from app.models import Modulo, ModuloTransacao, TenantModulo, ModuloLegado; print('ok')"
```

Esperado: `ok`. Se der `ImportError` em `routers/modulos.py`, é esperado — a Task 5 o reescreve.
Para destravar agora, ajuste o import daquele arquivo para `ModuloLegado, ConfiguracoesModulosLegado`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/modulo.py backend/app/models/__init__.py backend/app/routers/modulos.py
git commit -m "feat(modulos): models do catálogo; renomeia os legados para *Legado"
```

---

### Task 3: Semear catálogo e junção no `seed_bootstrap`

**Files:**
- Modify: `backend/app/cli/seed_bootstrap.py`
- Test: `backend/tests/test_modulos_seed.py`

**Interfaces:**
- Consumes: models da Task 2
- Produces: função `async def semear_modulos(db: AsyncSession) -> dict` — idempotente, devolve
  `{"modulos": int, "vinculos": int}`. Chamada de dentro de `seed(db)`.

O catálogo precisa ser garantido **a cada deploy**, como já se faz com `protocolos.acao`. Sem isso,
banco novo sobe com launcher vazio — o mesmo modo de falha que custou o PR #8.

O mapa abaixo é o ponto de partida. A autoridade é o teste da Task 8: se sobrar transação do nosso
sistema sem módulo, o CI reprova e o mapa é corrigido aqui.

- [ ] **Step 1: Escrever o teste primeiro**

```python
"""seed_bootstrap semeia o catálogo de módulos de forma idempotente."""
import pytest
from sqlalchemy import text

from app.cli.seed_bootstrap import semear_modulos


@pytest.mark.asyncio
async def test_semear_modulos_e_idempotente(admin_session):
    antes = (await admin_session.execute(
        text("SELECT COUNT(*) FROM aprimora_py.modulo_transacao")
    )).scalar_one()

    await semear_modulos(admin_session)
    await admin_session.flush()
    depois_1 = (await admin_session.execute(
        text("SELECT COUNT(*) FROM aprimora_py.modulo_transacao")
    )).scalar_one()

    await semear_modulos(admin_session)
    await admin_session.flush()
    depois_2 = (await admin_session.execute(
        text("SELECT COUNT(*) FROM aprimora_py.modulo_transacao")
    )).scalar_one()

    assert depois_1 >= antes
    assert depois_2 == depois_1, "segunda chamada duplicou vínculos"
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_transacao_inexistente_e_ignorada(admin_session):
    """Código que não existe em utils.transacao não pode explodir o seed."""
    await semear_modulos(admin_session)
    await admin_session.flush()
    orfas = (await admin_session.execute(text("""
        SELECT COUNT(*) FROM aprimora_py.modulo_transacao mt
         WHERE NOT EXISTS (SELECT 1 FROM utils.transacao t WHERE t.id = mt.id_transacao)
    """))).scalar_one()
    assert orfas == 0
    await admin_session.rollback()
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_seed.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'semear_modulos'`.

- [ ] **Step 3: Implementar `semear_modulos` em `seed_bootstrap.py`**

Adicionar no topo do arquivo, junto dos outros imports de model:

```python
from ..models import Modulo, ModuloTransacao, Transacao
```

E a função, antes de `async def seed(db)`:

```python
# Mapa módulo -> códigos de transação. Ponto de partida; a autoridade é o teste
# test_toda_transacao_tem_modulo (tests/test_guarda_modularizacao.py), que
# reprova o PR se sobrar transação do nosso sistema fora daqui.
MODULO_TRANSACOES: dict[str, tuple[str, ...]] = {
    "protocolo": (
        "processo", "catalogo", "assunto", "manifestante", "servico",
        "minuta_template", "cidade", "endereco", "workflow",
    ),
    "pagamentos": (
        "pagamento_cadastro", "pagamento_solicitar", "pagamento_autorizar",
        "pagamento_pagar", "pagamento_aprovar", "pagamento_validar",
        "pagamento_encaminhar", "pagamento_auditar",
    ),
    "frota": ("frota",),
    "transporte": ("transporte_regulado",),
    "administracao": ("usuario", "unidadeTrabalho", "configuracao"),
    "comum": ("dashboard",),
}


async def semear_modulos(db: AsyncSession) -> dict:
    """Garante o catálogo de módulos e os vínculos com as transações.

    Idempotente: roda a cada deploy. Código de transação que ainda não existe
    em `utils.transacao` é ignorado em silêncio — o vínculo entra no próximo
    deploy, depois que a transação for criada.
    """
    modulos = {
        m.slug: m
        for m in (await db.execute(select(Modulo))).scalars().all()
    }
    if not modulos:
        raise RuntimeError(
            "aprimora_py.modulo está vazia — rode `alembic upgrade head` "
            "antes do seed (a migration 0073 popula o catálogo)."
        )

    transacoes = {
        t.codigo: t.id
        for t in (await db.execute(
            select(Transacao).where(Transacao.excluido.is_(False))
        )).scalars().all()
    }

    existentes = {
        (row[0], row[1])
        for row in (await db.execute(
            select(ModuloTransacao.id_modulo, ModuloTransacao.id_transacao)
        )).all()
    }

    criados = 0
    for slug, codigos in MODULO_TRANSACOES.items():
        modulo = modulos.get(slug)
        if modulo is None:
            continue
        for codigo in codigos:
            id_transacao = transacoes.get(codigo)
            if id_transacao is None:
                continue
            if (modulo.id, id_transacao) in existentes:
                continue
            db.add(ModuloTransacao(id_modulo=modulo.id, id_transacao=id_transacao))
            existentes.add((modulo.id, id_transacao))
            criados += 1

    return {"modulos": len(modulos), "vinculos": criados}
```

- [ ] **Step 4: Chamar de dentro de `seed(db)`**

No fim de `async def seed(db)`, antes do `return`, acrescentar:

```python
    resultado_modulos = await semear_modulos(db)
```

E incluir `"modulos": resultado_modulos` no dicionário retornado.

- [ ] **Step 5: Rodar os testes**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_seed.py -v
```

Esperado: 2 passed.

- [ ] **Step 6: Rodar o seed de verdade e conferir idempotência**

```bash
docker exec aprimora-py-backend python -m app.cli.seed_bootstrap
docker exec aprimora-py-backend python -m app.cli.seed_bootstrap
```

Esperado: as duas execuções terminam sem erro; a segunda reporta `vinculos: 0`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/cli/seed_bootstrap.py backend/tests/test_modulos_seed.py
git commit -m "feat(modulos): seed_bootstrap garante catálogo e vínculos transação<->módulo"
```

---

### Task 3B: As nove transações que faltam e o vínculo com o sistema

*(Acrescentada em execução, 2026-07-28, por decisão do Jorge. Ver "Achado que motivou esta task".)*

**Files:**
- Create: `backend/alembic/versions/0074_transacoes_faltantes.py`
- Modify: `backend/app/cli/seed_bootstrap.py`
- Test: `backend/tests/test_transacoes_rbac.py`

**Interfaces:**
- Consumes: `MODULO_TRANSACOES` e `semear_modulos()` da Task 3
- Produces: as 23 transações que os routers exigem passam a existir em `utils.transacao` e a
  estar ligadas ao sistema do app via `utils.sistema_transacao`. Nova função
  `async def garantir_sistema_transacao(db: AsyncSession) -> int` no `seed_bootstrap`.

**Achado que motivou esta task.** As transações do sistema são criadas por migrations (0023, 0024,
0028, 0031, 0041, 0044, 0045, 0048, 0069) — não pelo dump legado. Num banco montado pelas nossas
migrations existem 14, mas os routers exigem 23 códigos distintos. Faltam nove: `processo`,
`usuario`, `catalogo`, `assunto`, `manifestante`, `cidade`, `endereco`, `workflow`,
`unidadeTrabalho`. E `utils.sistema_transacao` tem **uma linha só** (`dashboard`, da 0028).

Consequência pré-existente: usuário **não** super-usuário leva 403 em processos, usuários, assuntos
e cadastros — não por falta de permissão concedida, mas porque a transação não existe para ser
concedida. Ninguém percebeu porque o SU faz bypass antes de consultar a lista, e porque os testes
que precisam de uma transação a criam ali mesmo.

- [ ] **Step 1: Escrever o teste primeiro**

```python
"""Toda transação que os routers exigem existe e está ligada ao sistema do app."""
import re
from pathlib import Path

import pytest
from sqlalchemy import text

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"


def codigos_exigidos_pelos_routers() -> set[str]:
    """Extrai os códigos usados em require_permission/require_any_permission.

    `require_permission("codigo", "action")` tem a AÇÃO como segundo argumento —
    só o primeiro literal é código. `require_any_permission(*codigos)` só tem
    códigos. As tuplas de constante no topo dos módulos de pagamentos são
    passadas por *splat e por isso não aparecem na chamada.
    """
    codigos: set[str] = set()
    um_so = re.compile(r'require_permission\(\s*"([a-zA-Z_]+)"')
    varios = re.compile(r'require_any_permission\(\s*((?:"[a-zA-Z_]+"\s*,?\s*)+)')
    constante = re.compile(
        r'^(?:_LEITURA|PERMS_LEITURA|PERM_VALIDAR|PERM_ENCAMINHAR)\s*=\s*\(([^)]*)\)',
        re.MULTILINE,
    )
    for arquivo in ROUTERS.glob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        codigos.update(um_so.findall(texto))
        for bloco in varios.findall(texto):
            codigos.update(re.findall(r'"([a-zA-Z_]+)"', bloco))
        for bloco in constante.findall(texto):
            codigos.update(re.findall(r'"([a-zA-Z_]+)"', bloco))
    return codigos


ACOES = {"inserir", "atualizar", "excluir", "visualizar"}


@pytest.mark.asyncio
async def test_toda_transacao_exigida_existe(admin_session):
    exigidos = codigos_exigidos_pelos_routers()
    assert exigidos, "a extração não achou nenhum código — o regex quebrou"
    assert not (exigidos & ACOES), (
        f"a extração capturou ações como se fossem códigos: {sorted(exigidos & ACOES)} — "
        "o segundo argumento de require_permission é a ação, não um código"
    )

    existentes = set((await admin_session.execute(text(
        "SELECT codigo FROM utils.transacao WHERE excluido = false"
    ))).scalars().all())

    faltando = sorted(exigidos - existentes)
    assert not faltando, (
        f"Códigos exigidos por require_permission sem linha em utils.transacao: {faltando}. "
        "Usuário não-SU leva 403 nesses endpoints por ausência de cadastro, não de permissão."
    )


@pytest.mark.asyncio
async def test_toda_transacao_exigida_esta_no_sistema(admin_session):
    """Sem o vínculo, o ramo SU de load_permissions devolve lista vazia.

    O `app` vem de `get_settings().app_name`, nunca hardcoded: este banco tem
    DUAS linhas em `utils.sistema` (`aprimora` e `sistemas`) e o container de
    dev roda com `APP_NAME=aprimora` enquanto o compose versionado diz
    `sistemas`. Fixar o literal faria o teste consultar um sistema diferente
    do que `garantir_sistema_transacao` e `load_permissions` de fato usam.
    """
    from app.config import get_settings

    exigidos = codigos_exigidos_pelos_routers()
    app = get_settings().app_name
    ligados = set((await admin_session.execute(text("""
        SELECT t.codigo
          FROM utils.transacao t
          JOIN utils.sistema_transacao st ON st.id_transacao = t.id AND st.excluido = false
          JOIN utils.sistema s ON s.id = st.id_sistema AND s.app = :app
         WHERE t.excluido = false
    """), {"app": app})).scalars().all())

    faltando = sorted(exigidos - ligados)
    assert not faltando, (
        f"Transações sem vínculo em sistema_transacao: {faltando}. "
        "Rode `python -m app.cli.seed_bootstrap`."
    )
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transacoes_rbac.py -v
```

Esperado: os dois falham. O primeiro lista os nove códigos ausentes; o segundo lista praticamente
todos (só `dashboard` está ligado hoje).

- [ ] **Step 3: Escrever a migration 0074**

```python
"""Cria as transações que os routers exigem e nenhuma migration criou.

Revision ID: 0074
Revises: 0073
Create Date: 2026-07-28

Achado durante a fatia F1 da modularização: os routers exigem 23 códigos via
require_permission, mas só 14 existem em utils.transacao. Os nove ausentes
fazem usuário NÃO super-usuário tomar 403 por ausência de cadastro — o SU
mascarava o problema porque faz bypass antes de consultar a lista.

Idempotente por ON CONFLICT: em bancos que já receberam esses códigos por
outro caminho (dump do legado, inserção manual), a migration é no-op.
O vínculo com utils.sistema_transacao NÃO é feito aqui: a linha de
utils.sistema é criada pelo seed_bootstrap, que roda depois das migrations.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0074"
down_revision: str | Sequence[str] | None = "0073"
branch_labels = None
depends_on = None

TRANSACOES = [
    ("processo", "Processos"),
    ("usuario", "Usuários"),
    ("catalogo", "Catálogos do protocolo"),
    ("assunto", "Assuntos"),
    ("manifestante", "Manifestantes"),
    ("cidade", "Cidades"),
    ("endereco", "Endereços"),
    ("workflow", "Workflows"),
    ("unidadeTrabalho", "Unidades de trabalho"),
]


def upgrade() -> None:
    for codigo, rotulo in TRANSACOES:
        op.execute(
            "INSERT INTO utils.transacao (transacao, codigo, excluido) "
            f"VALUES ('{rotulo}', '{codigo}', false) "
            "ON CONFLICT (codigo) DO NOTHING"
        )


def downgrade() -> None:
    # Remove só o que esta migration poderia ter criado, e só se ninguém
    # tiver concedido a transação a um grupo — apagar um código em uso
    # arrancaria a permissão de usuários reais.
    codigos = ", ".join(f"'{c}'" for c, _ in TRANSACOES)
    op.execute(f"""
        DELETE FROM utils.transacao t
         WHERE t.codigo IN ({codigos})
           AND NOT EXISTS (
               SELECT 1 FROM utils.grupo_transacao gt WHERE gt.id_transacao = t.id
           )
           AND NOT EXISTS (
               SELECT 1 FROM utils.sistema_transacao st WHERE st.id_transacao = t.id
           )
           AND NOT EXISTS (
               SELECT 1 FROM aprimora_py.modulo_transacao mt WHERE mt.id_transacao = t.id
           )
    """)
```

- [ ] **Step 4: Aplicar e conferir head único**

```bash
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic heads
```

Esperado: head único `0074`.

- [ ] **Step 5: Implementar `garantir_sistema_transacao` no `seed_bootstrap`**

Acrescentar `SistemaTransacao` e `Sistema` aos imports de model do arquivo, e a função logo antes
de `semear_modulos`:

```python
async def garantir_sistema_transacao(db: AsyncSession) -> int:
    """Liga ao sistema do app toda transação que os módulos declaram.

    Sem esse vínculo o ramo de super-usuário do `load_permissions` devolve
    lista vazia — ele consulta `sistema_transacao`, não `transacao`. Só as
    transações declaradas em MODULO_TRANSACOES são ligadas: `utils.transacao`
    pode conter códigos do PHP legado que não são nossos.
    """
    sistema = (
        await db.execute(select(Sistema).where(Sistema.app == APP, Sistema.excluido.is_(False)))
    ).scalars().first()
    if sistema is None:
        raise RuntimeError(f"Nenhum utils.sistema com app='{APP}' — o seed roda fora de ordem.")

    declarados = {c for codigos in MODULO_TRANSACOES.values() for c in codigos}
    transacoes = {
        t.codigo: t.id
        for t in (await db.execute(
            select(Transacao).where(
                Transacao.excluido.is_(False), Transacao.codigo.in_(declarados)
            )
        )).scalars().all()
    }
    ja_ligadas = set((await db.execute(
        select(SistemaTransacao.id_transacao).where(
            SistemaTransacao.id_sistema == sistema.id,
            SistemaTransacao.excluido.is_(False),
        )
    )).scalars().all())

    criados = 0
    for id_transacao in transacoes.values():
        if id_transacao in ja_ligadas:
            continue
        db.add(SistemaTransacao(
            id_sistema=sistema.id, id_transacao=id_transacao, excluido=False
        ))
        criados += 1
    return criados
```

Chamar dentro de `seed(db)`, **antes** de `semear_modulos`, e incluir o resultado no dicionário
retornado:

```python
    vinculos_sistema = await garantir_sistema_transacao(db)
```

- [ ] **Step 6: Rodar o seed duas vezes e os testes**

```bash
docker exec aprimora-py-backend python -m app.cli.seed_bootstrap
docker exec aprimora-py-backend python -m app.cli.seed_bootstrap
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transacoes_rbac.py tests/test_modulos_seed.py -v
```

Esperado: segunda execução do seed reporta zero vínculos novos; 4 testes passam.

- [ ] **Step 7: Conferir que o ramo SU passou a significar algo**

O `app` tem de vir do settings, não de literal — ver a nota do teste acima:

```bash
APP=$(docker exec aprimora-py-backend python -c "from app.config import get_settings; print(get_settings().app_name)")
docker exec aprimora-py-db psql -U ged_user -d ged_saas_db -c "SELECT COUNT(*) FROM utils.sistema_transacao st JOIN utils.sistema s ON s.id = st.id_sistema AND s.app = '$APP' WHERE st.excluido = false;"
```

Esperado: 23 (ou mais, se o banco já tinha vínculos). Antes desta task era 1.

> **Deriva de ambiente conhecida, NÃO conserte aqui.** Este banco tem duas linhas em
> `utils.sistema`: `Aprimora` (app=`aprimora`, id 1) e `Sistemas` (app=`sistemas`, id 2). O
> container de dev roda com `APP_NAME=aprimora`, enquanto o `docker-compose.yml` versionado e o
> default de `config.py` dizem `sistemas`. Os dados de RBAC deste ambiente foram construídos sob
> `aprimora`; recriar o container realinharia para `sistemas` e derrubaria as permissões do admin
> local. É a mesma classe de bug que o CLAUDE.md registra como já tendo causado 403 geral. Está
> registrado no backlog — não é escopo do F1.

- [ ] **Step 8: Rodar a regressão de permissões**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_permissoes_matriz.py tests/test_pr5a_dashboard_servicos.py -v
```

Esperado: verde. Ligar transações ao sistema muda o que o ramo SU devolve — se algum teste
dependia da lista curta, ele aparece aqui.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/0074_transacoes_faltantes.py backend/app/cli/seed_bootstrap.py backend/tests/test_transacoes_rbac.py
git commit -m "fix(rbac): cria as 9 transações que os routers exigem e liga todas ao sistema"
```

---

### Task 4: Service de módulos

**Files:**
- Create: `backend/app/services/modulos.py`
- Test: `backend/tests/test_modulos_service.py`

**Interfaces:**
- Consumes: models da Task 2
- Produces:
  - `async def slugs_contratados(db, tenant_id: int) -> set[str]` — slugs contratados **mais**
    os não-contratáveis (`comum`), que são implícitos e nunca bloqueados.
  - `async def codigos_bloqueados(db, tenant_id: int) -> set[str]` — códigos de transação
    pertencentes a módulos **não** contratados. É o que `load_permissions` usa.
  - `async def modulos_do_tenant(db, tenant_id: int) -> list[Modulo]` — catálogo com flag de
    contratação, para o admin de plataforma.
  - `async def contratar(db, tenant_id: int, slugs: list[str]) -> None` — reconcilia: contrata os
    ausentes, marca `excluido=True` nos que saíram. Nunca apaga dado de negócio.

- [ ] **Step 1: Escrever os testes**

```python
"""Service de módulos — contratação e derivação de códigos bloqueados."""
import pytest
from sqlalchemy import text

from app.services.modulos import (
    codigos_bloqueados,
    contratar,
    modulos_do_tenant,
    slugs_contratados,
)


async def _contrata_tudo(session, tenant_id: int) -> None:
    await session.execute(text("""
        INSERT INTO aprimora_py.tenant_modulo (tenant_id, id_modulo)
        SELECT :t, id FROM aprimora_py.modulo WHERE contratavel = true
    """), {"t": tenant_id})
    await session.flush()


@pytest.mark.asyncio
async def test_comum_sempre_conta_como_contratado(admin_session, two_tenants):
    tid, _ = two_tenants
    # Tenant novo, nada contratado: 'comum' ainda assim aparece.
    assert await slugs_contratados(admin_session, tid) == {"comum"}


@pytest.mark.asyncio
async def test_contratar_e_descontratar_reconcilia(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota", "pagamentos"])
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {"frota", "pagamentos", "comum"}

    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {"frota", "comum"}

    # Descontratar é soft-delete: a linha continua lá.
    total = (await admin_session.execute(text(
        "SELECT COUNT(*) FROM aprimora_py.tenant_modulo WHERE tenant_id = :t"
    ), {"t": tid})).scalar_one()
    assert total == 2, "descontratar apagou a linha em vez de marcar excluido"
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_recontratar_reaproveita_a_linha(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    await contratar(admin_session, tid, [])
    await admin_session.flush()
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {"frota", "comum"}
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_codigos_bloqueados_lista_modulo_nao_contratado(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    bloqueados = await codigos_bloqueados(admin_session, tid)
    assert "frota" not in bloqueados, "módulo contratado não pode ser bloqueado"
    assert "dashboard" not in bloqueados, "transação de 'comum' nunca é bloqueada"
    assert "processo" in bloqueados, "protocolo não foi contratado, deveria bloquear"
    assert any(c.startswith("pagamento_") for c in bloqueados), (
        "pagamentos não foi contratado, suas transações deveriam estar bloqueadas"
    )
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_modulos_do_tenant_marca_contratacao(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    itens = await modulos_do_tenant(admin_session, tid)
    por_slug = {m["slug"]: m["contratado"] for m in itens}
    assert por_slug["frota"] is True
    assert por_slug["pagamentos"] is False
    assert "comum" not in por_slug, "módulo não-contratável não entra na tela de contratação"
    await admin_session.rollback()
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_service.py -v
```

Esperado: FAIL com `ModuleNotFoundError: No module named 'app.services.modulos'`.

- [ ] **Step 3: Implementar o service**

```python
"""Catálogo de módulos, contratação por tenant e derivação de bloqueios.

O catálogo (`Modulo`, `ModuloTransacao`) é GLOBAL — sem tenant_id, por decisão
de design: módulo é do produto, não da prefeitura. A contratação
(`TenantModulo`) é por tenant e NÃO tem RLS (spec §4.1): quem escreve é o
platform admin, operando sobre outros tenants. Por isso toda leitura aqui
filtra `tenant_id` explicitamente em código — é a única barreira que existe.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Modulo, ModuloTransacao, TenantModulo, Transacao


async def slugs_contratados(db: AsyncSession, tenant_id: int) -> set[str]:
    """Slugs disponíveis ao tenant: os contratados + os não-contratáveis.

    Módulo com `contratavel = false` (hoje só `comum`) é infraestrutura, não
    produto: está sempre disponível e nunca é bloqueado.
    """
    stmt = (
        select(Modulo.slug)
        .join(TenantModulo, TenantModulo.id_modulo == Modulo.id)
        .where(
            TenantModulo.tenant_id == tenant_id,
            TenantModulo.excluido.is_(False),
            TenantModulo.ativo.is_(True),
            Modulo.ativo.is_(True),
        )
    )
    contratados = set((await db.execute(stmt)).scalars().all())

    implicitos = set((await db.execute(
        select(Modulo.slug).where(
            Modulo.contratavel.is_(False), Modulo.ativo.is_(True)
        )
    )).scalars().all())

    return contratados | implicitos


async def codigos_bloqueados(db: AsyncSession, tenant_id: int) -> set[str]:
    """Códigos de transação de módulos NÃO disponíveis ao tenant.

    Transação sem vínculo de módulo NÃO entra aqui — é fail-open deliberado
    (spec §3, D8). O teste test_toda_transacao_tem_modulo garante que o
    esquecimento apareça no CI em vez de virar tela sumida em produção.
    """
    # Nunca vazio: os não-contratáveis ('comum') estão sempre lá.
    disponiveis = await slugs_contratados(db, tenant_id)
    stmt = (
        select(Transacao.codigo)
        .join(ModuloTransacao, ModuloTransacao.id_transacao == Transacao.id)
        .join(Modulo, Modulo.id == ModuloTransacao.id_modulo)
        .where(Modulo.slug.not_in(disponiveis))
    )
    return set((await db.execute(stmt)).scalars().all())


async def modulos_do_tenant(db: AsyncSession, tenant_id: int) -> list[dict]:
    """Catálogo contratável com a flag de contratação do tenant. Para o admin."""
    contratados = await slugs_contratados(db, tenant_id)
    modulos = (await db.execute(
        select(Modulo)
        .where(Modulo.contratavel.is_(True), Modulo.ativo.is_(True))
        .order_by(Modulo.ordem)
    )).scalars().all()
    return [
        {
            "id": m.id,
            "slug": m.slug,
            "nome": m.nome,
            "icone": m.icone,
            "ordem": m.ordem,
            "contratado": m.slug in contratados,
        }
        for m in modulos
    ]


async def contratar(db: AsyncSession, tenant_id: int, slugs: list[str]) -> None:
    """Reconcilia a contratação do tenant com a lista de slugs.

    Contrata o que falta (reaproveitando linha soft-deletada, se houver) e
    marca `excluido = True` no que saiu. Nunca apaga: descontratar suspende o
    acesso, não destrói o que o módulo produziu.
    """
    alvo = set(slugs)
    catalogo = {
        m.slug: m
        for m in (await db.execute(
            select(Modulo).where(Modulo.contratavel.is_(True))
        )).scalars().all()
    }
    desconhecidos = alvo - set(catalogo)
    if desconhecidos:
        raise ValueError(f"Módulo inexistente ou não contratável: {sorted(desconhecidos)}")

    vinculos = {
        v.id_modulo: v
        for v in (await db.execute(
            select(TenantModulo).where(TenantModulo.tenant_id == tenant_id)
        )).scalars().all()
    }

    for slug, modulo in catalogo.items():
        vinculo = vinculos.get(modulo.id)
        quer = slug in alvo
        if vinculo is None:
            if quer:
                db.add(TenantModulo(tenant_id=tenant_id, id_modulo=modulo.id))
        else:
            vinculo.excluido = not quer
            vinculo.ativo = quer
```

- [ ] **Step 4: Rodar os testes**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_service.py -v
```

Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/modulos.py backend/tests/test_modulos_service.py
git commit -m "feat(modulos): service de contratação e derivação de bloqueios"
```

---

### Task 5: Enforcement em `load_permissions`

**Files:**
- Modify: `backend/app/services/permissoes.py:42-131`
- Test: `backend/tests/test_permissoes_modulo.py`

**Interfaces:**
- Consumes: `codigos_bloqueados()` da Task 4
- Produces: `load_permissions()` com a mesma assinatura e o mesmo retorno `UserPermissions`,
  agora sem as transações de módulo não contratado — **nos dois ramos**.

Este é o teste crítico do design. Super-usuário bypassa permissão; **não** bypassa contratação.

- [ ] **Step 1: Escrever o teste**

```python
"""load_permissions respeita a contratação de módulos — inclusive para SU."""
import pytest
from sqlalchemy import text

from app.services.modulos import contratar
from app.services.permissoes import load_permissions


async def _cria_su(session, tenant_id: int) -> int:
    """Cria usuário + grupo nível 0 no sistema do app. Devolve o id do usuário."""
    sistema_id = (await session.execute(text(
        "SELECT id FROM utils.sistema WHERE app = 'sistemas' AND excluido = false LIMIT 1"
    ))).scalar_one()
    nivel_id = (await session.execute(text(
        "SELECT id FROM utils.nivel WHERE valor = 0 LIMIT 1"
    ))).scalar_one()
    uid = (await session.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo)
        VALUES (:t, 'SU Modulo', :email, '', '00000000000', true, false,
                'sistemas', 'interno')
        RETURNING id
    """), {"t": tenant_id, "email": f"su-mod-{tenant_id}@modulo.test"})).scalar_one()
    gid = (await session.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'SU Modulo', false) RETURNING id
    """), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await session.execute(text("""
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, 'sistemas')
    """), {"t": tenant_id, "u": uid, "g": gid})
    await session.flush()
    return uid


@pytest.mark.asyncio
async def test_su_nao_bypassa_contratacao(admin_session, two_tenants):
    """A decisão de segurança central: SU vê tudo do que foi contratado, e só."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    codigos = {p.codigo for p in perms.items}

    assert perms.is_super_usuario is True
    assert "frota" in codigos, "módulo contratado sumiu para o SU"
    assert not {c for c in codigos if c.startswith("pagamento_")}, (
        "SU enxergou transações de módulo NÃO contratado"
    )
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_transacao_de_modulo_comum_sobrevive(admin_session, two_tenants):
    """'comum' não é contratável e nunca pode ser filtrado."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid, [])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    assert "dashboard" in {p.codigo for p in perms.items}
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_contratar_tudo_nao_muda_nada(admin_session, two_tenants):
    """Regressão: com os 5 contratados, o resultado é o de antes da mudança."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid,
                    ["protocolo", "pagamentos", "frota", "transporte", "administracao"])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    codigos = {p.codigo for p in perms.items}
    assert "frota" in codigos
    assert "processo" in codigos
    assert "pagamento_autorizar" in codigos
    await admin_session.rollback()
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_permissoes_modulo.py -v
```

Esperado: `test_su_nao_bypassa_contratacao` FALHA no assert de `pagamento_` — hoje o SU vê tudo.

- [ ] **Step 3: Aplicar o filtro**

Em `backend/app/services/permissoes.py`, acrescentar o import no topo:

```python
from .modulos import codigos_bloqueados
```

E substituir o `return` final da função por:

```python
    bloqueados = await codigos_bloqueados(db, tenant_id)
    if bloqueados:
        items = [p for p in items if p.codigo not in bloqueados]

    return UserPermissions(
        is_super_usuario=is_su,
        nivel_valor=higher_nivel.valor,
        items=items,
    )
```

O filtro fica **depois** da bifurcação, num ponto só — assim vale para os dois ramos por
construção, sem chance de alguém aplicar num e esquecer do outro.

- [ ] **Step 4: Rodar os testes**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_permissoes_modulo.py -v
```

Esperado: 3 passed.

- [ ] **Step 5: Rodar a regressão de permissões**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_permissoes_matriz.py tests/test_rls_isolation.py -v
```

Esperado: tudo verde. Se algo quebrar aqui, o backfill da Task 1 não alcançou o tenant do teste.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/permissoes.py backend/tests/test_permissoes_modulo.py
git commit -m "feat(modulos): load_permissions filtra por contratação nos dois ramos"
```

---

### Task 6: `/modulos/me` reescrito

**Files:**
- Rewrite: `backend/app/routers/modulos.py`
- Create: `backend/app/schemas/modulo.py`
- Test: `backend/tests/test_modulos_me.py`

**Interfaces:**
- Consumes: `slugs_contratados()` da Task 4, `load_permissions()` da Task 5
- Produces: `GET /api/v2/modulos/me` → `{"itens": [{"slug", "nome", "icone", "ordem"}]}`,
  ordenado por `ordem`. Schemas `ModuloOut`, `ModulosMeResponse`, `ModuloAdminOut`,
  `ContratacaoIn`.

- [ ] **Step 1: Escrever o teste**

```python
"""GET /modulos/me devolve contratado ∩ permitido."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_me_exige_autenticacao():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v2/modulos/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_devolve_apenas_contratados(client_admin):
    """client_admin é o admin@local.test do tenant default (5 módulos contratados)."""
    r = await client_admin.get("/api/v2/modulos/me")
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["itens"]]
    assert "comum" not in slugs, "'comum' não é módulo de launcher"
    assert slugs == sorted(slugs, key=lambda s: [
        "protocolo", "pagamentos", "frota", "transporte", "administracao"
    ].index(s)), "itens fora da ordem do catálogo"
    assert set(slugs) <= {"protocolo", "pagamentos", "frota", "transporte", "administracao"}
```

> **Nota para quem implementa:** se não existir fixture `client_admin` em `conftest.py`, procure o
> padrão de cliente autenticado usado em `tests/test_pr5a_dashboard_servicos.py` e reuse-o. Não
> invente uma terceira forma de autenticar em teste.

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_me.py -v
```

Esperado: FAIL — a resposta ainda tem a forma antiga (`items`, com `id`/`modulo`/`url`).

- [ ] **Step 3: Criar `schemas/modulo.py`**

```python
from pydantic import BaseModel


class ModuloOut(BaseModel):
    slug: str
    nome: str
    icone: str | None = None
    ordem: int


class ModulosMeResponse(BaseModel):
    itens: list[ModuloOut]


class ModuloAdminOut(BaseModel):
    id: int
    slug: str
    nome: str
    icone: str | None = None
    ordem: int
    contratado: bool


class ContratacaoIn(BaseModel):
    slugs: list[str]
```

- [ ] **Step 4: Reescrever `routers/modulos.py`**

```python
"""Módulos disponíveis ao usuário logado.

Regra (spec §3, D1): módulo aparece se o TENANT o contratou E o usuário tem
alguma transação dele. As tabelas legadas do PHP (public.modulos,
public.configuracoes_modulos) não são mais lidas — saem do ORM na fatia F4.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import Modulo, ModuloTransacao, Transacao, Usuario
from ..schemas.modulo import ModuloOut, ModulosMeResponse
from ..services.modulos import slugs_contratados
from ..services.permissoes import load_permissions

router = APIRouter(prefix="/modulos", tags=["modulos"])


@router.get("/me", response_model=ModulosMeResponse)
async def me(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ModulosMeResponse:
    disponiveis = await slugs_contratados(db, tenant_id)
    perms = await load_permissions(db, user.id, tenant_id=tenant_id)
    codigos = {p.codigo for p in perms.items}

    # Slug -> códigos de transação daquele módulo.
    linhas = (await db.execute(
        select(Modulo, Transacao.codigo)
        .join(ModuloTransacao, ModuloTransacao.id_modulo == Modulo.id)
        .join(Transacao, Transacao.id == ModuloTransacao.id_transacao)
        .where(Modulo.contratavel.is_(True), Modulo.ativo.is_(True))
        .order_by(Modulo.ordem)
    )).all()

    vistos: dict[str, Modulo] = {}
    for modulo, codigo in linhas:
        if modulo.slug not in disponiveis:
            continue
        if codigo in codigos and modulo.slug not in vistos:
            vistos[modulo.slug] = modulo

    itens = [
        ModuloOut(slug=m.slug, nome=m.nome, icone=m.icone, ordem=m.ordem)
        for m in sorted(vistos.values(), key=lambda m: m.ordem)
    ]
    return ModulosMeResponse(itens=itens)
```

- [ ] **Step 5: Rodar os testes**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_me.py -v
```

Esperado: 2 passed.

- [ ] **Step 6: Atualizar o cliente do frontend**

Em `frontend/lib/api.ts`, substituir a interface `ModulosMeResponse` (linha ~62) e o método
`modulos()` (linha ~2127):

```typescript
export interface ModuloOut {
  slug: string;
  nome: string;
  icone: string | null;
  ordem: number;
}

export interface ModulosMeResponse {
  itens: ModuloOut[];
}
```

O método `modulos: () => request<ModulosMeResponse>("/modulos/me")` continua igual — só o tipo muda.
Remover a interface `ModuloItem` antiga se ela não for usada em mais nada.

- [ ] **Step 7: Type-check**

```bash
cd frontend && npx tsc --noEmit
```

Esperado: 0 erros. É gate obrigatório e o CI não cobre.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/modulos.py backend/app/schemas/modulo.py backend/tests/test_modulos_me.py frontend/lib/api.ts
git commit -m "feat(modulos): /modulos/me devolve contratado ∩ permitido"
```

---

### Task 7: Contratação pelo admin de plataforma

**Files:**
- Modify: `backend/app/routers/admin_tenants.py`
- Test: `backend/tests/test_modulos_admin.py`

**Interfaces:**
- Consumes: `modulos_do_tenant()` e `contratar()` da Task 4
- Produces: `GET /api/v2/admin/tenants/{tenant_id}/modulos` → `list[ModuloAdminOut]`;
  `PUT /api/v2/admin/tenants/{tenant_id}/modulos` recebendo `ContratacaoIn`. Ambos sob
  `require_platform_admin`.

- [ ] **Step 1: Escrever o teste**

```python
"""Contratação de módulos — só platform admin, e não vaza entre tenants."""
import pytest


@pytest.mark.asyncio
async def test_listar_exige_platform_admin(client_admin, tenant_id_default):
    """Admin comum do tenant NÃO é platform admin."""
    r = await client_admin.get(f"/api/v2/admin/tenants/{tenant_id_default}/modulos")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_platform_admin_lista_catalogo(client_plataforma, tenant_id_default):
    r = await client_plataforma.get(f"/api/v2/admin/tenants/{tenant_id_default}/modulos")
    assert r.status_code == 200
    itens = r.json()
    assert len(itens) == 5, "o catálogo contratável tem 5 módulos"
    assert all(i["contratado"] for i in itens), "backfill deveria ter contratado tudo"


@pytest.mark.asyncio
async def test_descontratar_e_recontratar(client_plataforma, tenant_id_default):
    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{tenant_id_default}/modulos",
        json={"slugs": ["protocolo", "frota", "transporte", "administracao"]},
    )
    assert r.status_code == 200
    por_slug = {i["slug"]: i["contratado"] for i in r.json()}
    assert por_slug["pagamentos"] is False

    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{tenant_id_default}/modulos",
        json={"slugs": ["protocolo", "pagamentos", "frota", "transporte", "administracao"]},
    )
    assert all(i["contratado"] for i in r.json())


@pytest.mark.asyncio
async def test_slug_inexistente_e_400(client_plataforma, tenant_id_default):
    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{tenant_id_default}/modulos",
        json={"slugs": ["nao-existe"]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_comum_nao_pode_ser_contratado(client_plataforma, tenant_id_default):
    r = await client_plataforma.put(
        f"/api/v2/admin/tenants/{tenant_id_default}/modulos",
        json={"slugs": ["comum"]},
    )
    assert r.status_code == 400
```

> **Nota:** as fixtures `client_plataforma` e `tenant_id_default` podem não existir. Verifique
> `conftest.py` e os testes já existentes de `admin_tenants` antes de criar — `require_platform_admin`
> usa allowlist por env, então a fixture provavelmente monkeypatcha essa configuração.

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_admin.py -v
```

Esperado: FAIL com 404 — as rotas não existem.

- [ ] **Step 3: Implementar os endpoints**

Em `backend/app/routers/admin_tenants.py`, acrescentar os imports:

```python
from ..schemas.modulo import ContratacaoIn, ModuloAdminOut
from ..services.modulos import contratar, modulos_do_tenant
```

E os dois endpoints, seguindo o padrão dos vizinhos no arquivo:

```python
@router.get("/{tenant_id}/modulos", response_model=list[ModuloAdminOut])
async def listar_modulos(
    tenant_id: int,
    _: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ModuloAdminOut]:
    return [ModuloAdminOut(**m) for m in await modulos_do_tenant(db, tenant_id)]


@router.put("/{tenant_id}/modulos", response_model=list[ModuloAdminOut])
async def definir_modulos(
    tenant_id: int,
    payload: ContratacaoIn,
    _: Usuario = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ModuloAdminOut]:
    try:
        await contratar(db, tenant_id, payload.slugs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return [ModuloAdminOut(**m) for m in await modulos_do_tenant(db, tenant_id)]
```

- [ ] **Step 4: Rodar os testes**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_admin.py -v
```

Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/admin_tenants.py backend/tests/test_modulos_admin.py
git commit -m "feat(modulos): endpoints de contratação no admin de plataforma"
```

---

### Task 8: As duas guardas estruturais

**Files:**
- Create: `backend/tests/test_guarda_modularizacao.py`

**Interfaces:**
- Consumes: tudo das tasks anteriores
- Produces: nada de runtime — dois testes que reprovam PRs com omissão.

Estes testes não verificam comportamento; verificam que ninguém esqueceu. São o preço combinado do
fail-open (spec §3, D8) e o fechamento da lacuna dos endpoints sem `require_permission` (spec §5.1).

- [ ] **Step 1: Escrever a guarda de transação órfã**

```python
"""Guardas estruturais da modularização — pegam omissão, não comportamento."""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_toda_transacao_do_sistema_tem_modulo(admin_session):
    """Transação nossa sem módulo = fail-open silencioso. Reprova aqui.

    Escopo: só as transações ligadas ao sistema do app (`sistema.app = 'sistemas'`).
    O dump legado traz transações do PHP que não são nossas e não devem ser
    mapeadas.

    Esta guarda só tem valor encadeada com as da Task 3B
    (`tests/test_transacoes_rbac.py`), que garantem que todo código exigido por
    `require_permission` existe em `utils.transacao` E está ligado ao sistema.
    Juntas as três dizem: todo código que o app de fato enforça tem módulo.
    Sozinha, esta aqui cobriria só o que estivesse ligado ao sistema — que antes
    da 3B era uma linha.

    Se este teste falhar: acrescente o código em MODULO_TRANSACOES, em
    backend/app/cli/seed_bootstrap.py, e rode o seed.
    """
    orfas = (await admin_session.execute(text("""
        SELECT t.codigo
          FROM utils.transacao t
          JOIN utils.sistema_transacao st ON st.id_transacao = t.id AND st.excluido = false
          JOIN utils.sistema s ON s.id = st.id_sistema AND s.app = 'sistemas'
         WHERE t.excluido = false
           AND NOT EXISTS (
               SELECT 1 FROM aprimora_py.modulo_transacao mt WHERE mt.id_transacao = t.id
           )
         ORDER BY t.codigo
    """))).scalars().all()
    assert not orfas, (
        f"Transações sem módulo: {orfas}. "
        "Mapeie em MODULO_TRANSACOES (app/cli/seed_bootstrap.py) e rode o seed."
    )
```

- [ ] **Step 2: Rodar e ver o que aparece**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_guarda_modularizacao.py::test_toda_transacao_do_sistema_tem_modulo -v
```

Esperado: **pode falhar**, listando códigos que o mapa da Task 3 não previu. Isso é o teste fazendo
o trabalho dele. Acrescente cada código a `MODULO_TRANSACOES` no módulo correto, rode
`python -m app.cli.seed_bootstrap`, e repita até passar. **Não** relaxe o teste para fazê-lo passar.

- [ ] **Step 3: Escrever a guarda de endpoint desprotegido**

```python
ENDPOINTS_TRANSVERSAIS: set[tuple[str, str]] = set()
# Preenchido no Step 4 com o resultado da varredura: (método, caminho) que
# legitimamente não exigem require_permission, um por linha e com justificativa
# em comentário. Legítimo é o que não pertence a módulo nenhum: login, health,
# perfil próprio, notificações do próprio usuário, /modulos/me.


def test_nenhum_endpoint_novo_sem_permissao():
    """Endpoint sem require_permission escapa do enforcement de módulo.

    A allowlist acima é a decisão humana registrada. Endpoint novo que caia
    fora dela reprova o PR — ou ganha require_permission, ou entra na lista
    com justificativa.
    """
    from app.main import app

    desprotegidos = set()
    for rota in app.routes:
        caminho = getattr(rota, "path", "")
        if not caminho.startswith("/api/v2"):
            continue
        deps = [
            d.call.__qualname__
            for d in getattr(getattr(rota, "dependant", None), "dependencies", [])
            if getattr(d, "call", None) is not None
        ]
        tem_perm = any("_check" in q or "require_permission" in q for q in deps)
        if not tem_perm:
            for metodo in getattr(rota, "methods", set()):
                desprotegidos.add((metodo, caminho))

    novos = desprotegidos - ENDPOINTS_TRANSVERSAIS
    assert not novos, (
        f"Endpoints sem require_permission fora da allowlist: {sorted(novos)}. "
        "Acrescente a dependência ou registre em ENDPOINTS_TRANSVERSAIS com justificativa."
    )
```

- [ ] **Step 4: Rodar a varredura e decidir endpoint a endpoint**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_guarda_modularizacao.py::test_nenhum_endpoint_novo_sem_permissao -v
```

O teste vai falhar listando todos os endpoints sem `require_permission`. Para **cada um**, decidir:

- **Transversal por natureza** (auth, health, perfil próprio, notificações próprias, `/modulos/me`)
  → entra em `ENDPOINTS_TRANSVERSAIS` com um comentário dizendo por quê.
- **Buraco** → acrescente `Depends(require_permission("<codigo>"))` no endpoint.

Este é o único passo do plano que exige julgamento por item. Não despeje a lista inteira na
allowlist para o teste passar — isso destrói o valor da guarda.

- [ ] **Step 5: Rodar as duas guardas**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_guarda_modularizacao.py -v
```

Esperado: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_guarda_modularizacao.py backend/app/cli/seed_bootstrap.py backend/app/routers/
git commit -m "test(modulos): guardas de transação órfã e endpoint sem permissão"
```

---

### Task 9: `provisionar_tenant --modulos` e fechamento

**Files:**
- Modify: `backend/app/cli/tenant.py`
- Test: `backend/tests/test_modulos_provisionamento.py`

**Interfaces:**
- Consumes: `contratar()` da Task 4
- Produces: `provisionar_tenant` aceita `--modulos protocolo,frota` (default: todos os
  contratáveis).

- [ ] **Step 1: Escrever o teste**

```python
"""Tenant provisionado nasce com módulos contratados."""
import pytest
from sqlalchemy import text

from app.services.modulos import slugs_contratados


@pytest.mark.asyncio
async def test_default_contrata_todos_os_contrataveis(admin_session, two_tenants):
    """Mudar esse default silenciosamente quebraria quem já usa o comando."""
    from app.cli.tenant import contratar_modulos_iniciais

    tid, _ = two_tenants
    await contratar_modulos_iniciais(admin_session, tid, None)
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {
        "protocolo", "pagamentos", "frota", "transporte", "administracao", "comum"
    }
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_lista_explicita_limita(admin_session, two_tenants):
    from app.cli.tenant import contratar_modulos_iniciais

    tid, _ = two_tenants
    await contratar_modulos_iniciais(admin_session, tid, "frota,transporte")
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {"frota", "transporte", "comum"}
    await admin_session.rollback()
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_provisionamento.py -v
```

Esperado: FAIL com `ImportError: cannot import name 'contratar_modulos_iniciais'`.

- [ ] **Step 3: Implementar em `cli/tenant.py`**

```python
async def contratar_modulos_iniciais(
    db: AsyncSession, tenant_id: int, modulos: str | None
) -> list[str]:
    """Contrata os módulos iniciais do tenant.

    `modulos` é a lista separada por vírgula vinda de `--modulos`. `None`
    significa "todos os contratáveis" — default deliberado: o comportamento
    histórico do comando é liberar tudo, e mudá-lo em silêncio quebraria quem
    já o usa.
    """
    from ..models import Modulo
    from ..services.modulos import contratar

    if modulos is None:
        slugs = list((await db.execute(
            select(Modulo.slug).where(Modulo.contratavel.is_(True))
        )).scalars().all())
    else:
        slugs = [s.strip() for s in modulos.split(",") if s.strip()]

    await contratar(db, tenant_id, slugs)
    return slugs
```

Acrescentar o argumento no `argparse` do comando, junto dos outros:

```python
    parser.add_argument(
        "--modulos",
        default=None,
        help="Lista separada por vírgula (ex.: protocolo,frota). Default: todos.",
    )
```

E chamar `await contratar_modulos_iniciais(db, tenant.id, args.modulos)` no fluxo de
provisionamento, depois de o tenant existir e antes do commit.

- [ ] **Step 4: Rodar os testes**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_modulos_provisionamento.py -v
```

Esperado: 2 passed.

- [ ] **Step 5: Rodar a suíte completa**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q
```

Esperado: tudo verde, ~8 min. Este é o critério de aceite da fatia F1.

- [ ] **Step 6: Conferir que o deploy é mesmo invisível**

```bash
docker exec aprimora-py-backend alembic heads
curl -s -H "Host: sobral.aprimora.local" http://localhost:8090/api/v2/modulos/me -H "Authorization: Bearer $TOKEN" | head -20
```

Esperado: head único `0073`; `/modulos/me` devolve os 5 módulos. Nenhuma tela do sistema mudou.

- [ ] **Step 7: Commit**

```bash
git add backend/app/cli/tenant.py backend/tests/test_modulos_provisionamento.py
git commit -m "feat(modulos): provisionar_tenant aceita --modulos"
```

---

## Critério de aceite da fatia F1

- `alembic heads` → head único em `0073`; `downgrade -1` seguido de `upgrade head` roda limpo
- Suíte completa verde (`pytest -q`)
- `npx tsc --noEmit` → 0 erros
- `seed_bootstrap` roda duas vezes seguidas sem duplicar vínculo
- **Nada muda visualmente para o usuário** — nenhuma rota, menu ou tela foi tocada
- As duas guardas da Task 8 passam com allowlist preenchida por decisão, não por conveniência

## Fora do escopo desta fatia

Launcher, shell por módulo, menus particionados, prefixo de URL, redirects, regex do nginx e a aba
Módulos no frontend do admin de plataforma. Tudo isso é F2/F3/F4 — ver spec §9.
