# Transporte P6b — Linhas e Itinerários: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cadastro de linhas distritais/escolares com outorga (empresa e/ou permissionário), itinerário como paradas ordenadas e grade de horários — a metade que a P6 deixou por fazer.

**Architecture:** Três tabelas novas em `transporte_regulado` (migration 0092), service + router no padrão do módulo, duas telas (`/m/transporte/linhas` e `/[id]`) com costura de hub/menu/palette no mesmo PR. Exclusividades moram em índices do banco, com prova por inversão.

**Tech Stack:** FastAPI + SQLAlchemy 2 async, Alembic manual, pytest (via docker exec), Next.js 15 + React Query + vitest.

**Spec:** `docs/superpowers/specs/2026-08-21-transporte-p6b-linhas-design.md`

## Global Constraints

- Idioma pt-BR em código, comentários, docs e commits.
- Commits terminam com `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Backend testa via `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest ...` (bind-mount: sem rebuild).
- Frontend: `cd frontend && npx vitest run` e `npx tsc --noEmit` no host. **Não rodar `npm run lint`.**
- Migration nova: head único, `down_revision="0091"`, downgrade reverte na ordem inversa. GUC `app.tenant_id`, `current_setting(..., true)`, `ENABLE + FORCE` RLS, grants a `aprimora_app` (tabela + sequence). Sem grant a `aprimora_worker` (nenhuma task escreve aqui).
- `tenant_id` sempre do caller, nunca do payload; 404 cross-tenant; FKs soft validadas same-tenant no serviço; soft-delete sempre.
- Transação `transporte_regulado` (a mesma do módulo — nada muda em `MODULO_TRANSACOES`). GET sem action; escrita com action. Nenhuma rota do transporte usa `require_modulo` — não inaugurar divergência.
- `situacao` da linha: `ativa`/`inativa` (**feminino** — lição `ativo`×`ativa` da P5.1; testes afirmam o valor exato).
- Rota de segmento literal antes da paramétrica irmã (`/paradas/ordem` antes de `/paradas/{parada_id}`).
- Endpoint paginado → `request<Paginated<X>>` em `api.ts`, tela consome `.items`.
- PowerShell 5.1: sem `&&`; mensagens de commit via here-string `@'...'@` **sem aspas duplas no corpo**.

---

### Task 1: Migration 0092 + modelos

**Files:**
- Create: `backend/alembic/versions/0092_transporte_linhas.py`
- Modify: `backend/app/models/transporte_regulado.py` (fim do arquivo, após `PontoOcupacao`)
- Modify: `backend/app/models/__init__.py` (reexportar `Linha`, `LinhaParada`, `LinhaHorario`)

**Interfaces:**
- Produces: tabelas `transporte_regulado.linha|linha_parada|linha_horario`; modelos `Linha`, `LinhaParada`, `LinhaHorario` importáveis de `app.models`.

- [ ] **Step 1: Escrever a migration**

Seguir `0084_transporte_pontos.py` como molde (mesmo `_rls()`, mesmo estilo de docstring). Conteúdo:

```python
"""Transporte Regulado P6b — linhas e itinerários.

Revision ID: 0092
Revises: 0091
Create Date: 2026-08-21

Spec: `docs/superpowers/specs/2026-08-21-transporte-p6b-linhas-design.md`.

Três tabelas. O que carrega a fatia:

- `ck_linha_tem_operador` — ao menos um operador (empresa e/ou permissionário),
  no banco e não só no serviço.
- `ux_linha_nome` — duas linhas com o mesmo nome no mesmo município são erro
  de digitação.
- `ux_linha_horario` — mesmo horário duas vezes no mesmo dia é erro de
  digitação, e a exclusividade mora no banco (lição P5.1/P6): duas requisições
  concorrentes passariam as duas por uma checagem de serviço.

`linha_parada.ordem` NÃO tem índice único, de propósito: um único parcial em
(id_linha, ordem) tornaria reordenar uma dança de colisões. A leitura ordena
por (ordem, id) — estável — e ordem duplicada é inofensiva.

Boilerplate de RLS completo nas três (GUC `app.tenant_id`, `current_setting`
com `true`, ENABLE + FORCE — os três detalhes da 0078). Sem GRANT para
`aprimora_worker`: nenhuma task Celery escreve aqui.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0092"
down_revision: str | Sequence[str] | None = "0091"
branch_labels = None
depends_on = None

S = "transporte_regulado"

GUC = "NULLIF(current_setting('app.tenant_id', true), '')::int"


def _rls(tabela: str) -> None:
    """Boilerplate de RLS + grants. Idêntico para as três tabelas."""
    op.execute(f"ALTER TABLE {S}.{tabela} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.{tabela} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_select ON {S}.{tabela} "
        f"FOR SELECT USING (tenant_id = {GUC})"
    )
    op.execute(
        f"CREATE POLICY tenant_isolation_modify ON {S}.{tabela} "
        f"FOR ALL USING (tenant_id = {GUC}) WITH CHECK (tenant_id = {GUC})"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {S}.{tabela} TO aprimora_app")
    op.execute(f"GRANT USAGE, SELECT ON {S}.{tabela}_id_seq TO aprimora_app")


def upgrade() -> None:
    # ------------------------------------------------------------- linha
    op.create_table(
        "linha",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("codigo", sa.String(40), nullable=True),
        # Sem CHECK, igual ao resto do módulo: vocabulário imposto pelo
        # Literal `TipoServico` na borda.
        sa.Column("tipo_servico", sa.String(30), nullable=False),
        # FKs "soft" para operador — coerência de tenant é do serviço.
        sa.Column(
            "id_empresa", sa.Integer(),
            sa.ForeignKey(f"{S}.empresa.id"), nullable=True,
        ),
        sa.Column(
            "id_permissionario", sa.Integer(),
            sa.ForeignKey(f"{S}.permissionario.id"), nullable=True,
        ),
        sa.Column("origem", sa.String(150), nullable=False),
        sa.Column("destino", sa.String(150), nullable=False),
        # Feminino: linha ativa/inativa. Lição ativo×ativa da P5.1.
        sa.Column(
            "situacao", sa.String(20), nullable=False, server_default="ativa",
        ),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "id_empresa IS NOT NULL OR id_permissionario IS NOT NULL",
            name="ck_linha_tem_operador",
        ),
        sa.CheckConstraint(
            "situacao IN ('ativa', 'inativa')", name="ck_linha_situacao",
        ),
        schema=S,
    )
    op.create_index("ix_linha_tenant", "linha", ["tenant_id"], schema=S)
    op.create_index(
        "ix_linha_tenant_tipo", "linha", ["tenant_id", "tipo_servico"], schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_linha_nome ON {S}.linha "
        f"(tenant_id, lower(nome)) WHERE excluido = false"
    )
    _rls("linha")

    # ------------------------------------------------------- linha_parada
    op.create_table(
        "linha_parada",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_linha", sa.Integer(),
            sa.ForeignKey(f"{S}.linha.id"), nullable=False,
        ),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.String(200), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("atualizado_em", sa.DateTime(), nullable=True),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint("ordem > 0", name="ck_linhaparada_ordem_positiva"),
        schema=S,
    )
    op.create_index(
        "ix_linhaparada_tenant_linha", "linha_parada",
        ["tenant_id", "id_linha"], schema=S,
    )
    _rls("linha_parada")

    # ------------------------------------------------------ linha_horario
    op.create_table(
        "linha_horario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("aprimora_py.tenant.id"), nullable=False,
        ),
        sa.Column(
            "id_linha", sa.Integer(),
            sa.ForeignKey(f"{S}.linha.id"), nullable=False,
        ),
        # 0=segunda … 6=domingo.
        sa.Column("dia_semana", sa.SmallInteger(), nullable=False),
        sa.Column("partida", sa.Time(), nullable=False),
        # Sem atualizado_em: horário não se edita, se apaga e recria.
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "excluido", sa.Boolean(), nullable=False, server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "dia_semana BETWEEN 0 AND 6", name="ck_linhahorario_dia",
        ),
        schema=S,
    )
    op.create_index(
        "ix_linhahorario_tenant_linha", "linha_horario",
        ["tenant_id", "id_linha"], schema=S,
    )
    op.execute(
        f"CREATE UNIQUE INDEX ux_linha_horario ON {S}.linha_horario "
        f"(id_linha, dia_semana, partida) WHERE excluido = false"
    )
    _rls("linha_horario")


def downgrade() -> None:
    # Ordem inversa: filhas antes da mãe.
    op.execute(f"DROP INDEX IF EXISTS {S}.ux_linha_horario")
    op.drop_index("ix_linhahorario_tenant_linha", table_name="linha_horario", schema=S)
    op.drop_table("linha_horario", schema=S)

    op.drop_index("ix_linhaparada_tenant_linha", table_name="linha_parada", schema=S)
    op.drop_table("linha_parada", schema=S)

    op.execute(f"DROP INDEX IF EXISTS {S}.ux_linha_nome")
    op.drop_index("ix_linha_tenant_tipo", table_name="linha", schema=S)
    op.drop_index("ix_linha_tenant", table_name="linha", schema=S)
    op.drop_table("linha", schema=S)
```

- [ ] **Step 2: Validar head único + upgrade + reversibilidade**

```bash
docker exec aprimora-py-backend alembic heads          # 0092, único
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic downgrade -1
docker exec aprimora-py-backend alembic upgrade head
```

Expected: sem erro nas quatro chamadas.

- [ ] **Step 3: Modelos SQLAlchemy**

Ao fim de `backend/app/models/transporte_regulado.py` (após `PontoOcupacao`). `Time` e `SmallInteger` entram no import de `sqlalchemy` no topo do arquivo; `time` entra no import de `datetime`:

```python
class Linha(Base):
    """Linha de transporte distrital/escolar — trajeto nomeado, outorgado.

    P6b. Táxi/mototáxi têm ponto (P6); distrital e escolar têm linha, com
    itinerário (paradas ordenadas) e grade de horários.

    Outorga a empresa E/OU permissionário — ao menos um, e o CHECK
    `ck_linha_tem_operador` mora no banco (a família P5/P6 já provou que
    regra só no serviço não segura acesso direto). Coerência de tenant das
    FKs é do serviço, como sempre.

    `situacao` é FEMININA (`ativa`/`inativa`): a lição ativo×ativa da P5.1 é
    que o vocabulário segue o gênero da entidade, e filtro com o gênero errado
    seleciona zero linhas sem erro nenhum.
    """

    __tablename__ = "linha"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tipo_servico: Mapped[str] = mapped_column(String(30), nullable=False)
    id_empresa: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.empresa.id"), nullable=True
    )
    id_permissionario: Mapped[int | None] = mapped_column(
        ForeignKey("transporte_regulado.permissionario.id"), nullable=True
    )
    origem: Mapped[str] = mapped_column(String(150), nullable=False)
    destino: Mapped[str] = mapped_column(String(150), nullable=False)
    situacao: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ativa"
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LinhaParada(Base):
    """Parada do itinerário — referência textual ordenada, sem geo (como a P6).

    `ordem` NÃO tem índice único, de propósito: um único parcial tornaria
    reordenar uma dança de colisões. A leitura ordena por (ordem, id) —
    estável — e o endpoint de reordenação renumera 1..N numa transação.
    """

    __tablename__ = "linha_parada"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_linha: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.linha.id"), nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class LinhaHorario(Base):
    """Partida da grade: (dia_semana 0=seg…6=dom, hora). Não se edita — se
    apaga e recria (por isso não há `atualizado_em`). A exclusividade
    `(id_linha, dia_semana, partida)` mora no índice `ux_linha_horario`, não
    num `if`: duas requisições concorrentes passariam as duas pela checagem
    do serviço. O serviço checa só para devolver 409 com mensagem útil.
    """

    __tablename__ = "linha_horario"
    __table_args__ = {"schema": "transporte_regulado"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("aprimora_py.tenant.id"), nullable=False
    )
    id_linha: Mapped[int] = mapped_column(
        ForeignKey("transporte_regulado.linha.id"), nullable=False
    )
    dia_semana: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    partida: Mapped[time] = mapped_column(Time, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    excluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

Em `backend/app/models/__init__.py`, acrescentar `Linha`, `LinhaParada`, `LinhaHorario` ao import de `transporte_regulado` (seguir a linha onde `Ponto, PontoOcupacao` já estão).

- [ ] **Step 4: Smoke — a suíte RLS varre as tabelas novas**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_rls_papeis_minimos.py -q
```

Expected: PASS — `test_toda_tabela_com_rls_responde_sob_aprimora_app` inclui as três tabelas novas automaticamente. Se falhar, o boilerplate da migration está errado (GUC, `true`, FORCE ou grant).

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/0092_transporte_linhas.py backend/app/models/transporte_regulado.py backend/app/models/__init__.py
git commit  # "feat(transporte): tabelas de linha, parada e horario (P6b, Tarefa 1)"
```

---

### Task 2: Schemas + service de linha (CRUD)

**Files:**
- Modify: `backend/app/schemas/transporte_regulado.py` (fim do arquivo, após os schemas de Ponto)
- Modify: `backend/app/services/transporte_regulado.py` (fim do arquivo)
- Test: `backend/tests/test_transporte_p6b_linhas.py` (novo)

**Interfaces:**
- Consumes: modelos da Task 1; `TipoServico` Literal existente; helpers do módulo (`_now()` se existir — conferir como `criar_ponto` marca `criado_em` e copiar).
- Produces:
  - Schemas: `LinhaCreate`, `LinhaUpdate`, `LinhaOut` (com `paradas: list[LinhaParadaOut]` e `horarios: list[LinhaHorarioOut]` opcionais), `LinhaParadaCreate`, `LinhaParadaUpdate`, `LinhaParadaOut`, `LinhaHorarioCreate`, `LinhaHorarioOut`, `LinhaParadasOrdemInput`.
  - Service: `obter_linha(db, *, tenant_id, linha_id) -> Linha` (404), `listar_linhas(db, *, tenant_id, q, tipo_servico, situacao, limit, offset) -> tuple[list[Linha], int]`, `criar_linha(db, *, tenant_id, payload) -> Linha`, `atualizar_linha(db, *, tenant_id, linha_id, payload) -> Linha`, `excluir_linha(db, *, tenant_id, linha_id) -> None`.

- [ ] **Step 1: Escrever os testes que falham (CRUD)**

Novo arquivo `backend/tests/test_transporte_p6b_linhas.py`. Cabeçalho e helpers seguem `test_transporte_p6_pontos.py` (mesmos imports, `two_tenants`, `admin_engine`, limpeza no teardown; e-mails `.test`, slugs com sufixo `uuid4().hex[:8]`). Helper local:

```python
async def _operadores(engine, tenant_id: int):
    """Cria uma empresa e um permissionário mínimos e devolve (id_emp, id_perm)."""
    sufixo = uuid.uuid4().hex[:8]
    async with engine.begin() as conn:
        r1 = await conn.execute(text(
            "INSERT INTO transporte_regulado.empresa "
            "(tenant_id, razao_social, cnpj, tipo_servico, situacao, criado_em) "
            "VALUES (:t, :rs, :c, 'transporte_distrital', 'ativa', NOW()) RETURNING id"
        ), {"t": tenant_id, "rs": f"Empresa {sufixo}", "c": sufixo[:8].ljust(14, "0")})
        r2 = await conn.execute(text(
            "INSERT INTO transporte_regulado.permissionario "
            "(tenant_id, nome, cpf, tipo_servico, situacao, criado_em) "
            "VALUES (:t, :n, :c, 'transporte_escolar', 'ativo', NOW()) RETURNING id"
        ), {"t": tenant_id, "n": f"Perm {sufixo}", "c": sufixo[:8].ljust(11, "0")})
        return r1.scalar_one(), r2.scalar_one()
```

Testes desta task (assinaturas; corpo segue o padrão dos análogos de ponto no mesmo diretório):

```python
async def test_criar_linha_com_empresa(admin_engine): ...
    # criar_linha com id_empresa; afirmar situacao == "ativa" (valor EXATO)

async def test_nome_de_linha_e_unico_por_tenant(admin_engine): ...
    # segunda linha com o mesmo nome (caixa diferente) -> HTTPException 409

async def test_linha_sem_operador_e_recusada_no_schema(): ...
    # LinhaCreate(nome=..., origem=..., destino=..., tipo_servico=...,
    #             id_empresa=None, id_permissionario=None)
    # -> pytest.raises(ValidationError)

async def test_operador_de_outro_tenant_da_404(admin_engine): ...
    # empresa do tenant B usada em linha do tenant A -> 404

async def test_operador_excluido_e_recusado(admin_engine): ...
    # empresa soft-deletada -> 404 (FK do Postgres não filtra excluido)

async def test_linha_de_outro_tenant_da_404(admin_engine): ...

async def test_excluir_linha_nao_cascateia_filhas(admin_engine): ...
    # excluir linha; SELECT direto nas filhas: excluido continua false
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transporte_p6b_linhas.py -q
```

Expected: FAIL com `ImportError`/`AttributeError` (schemas e service não existem).

- [ ] **Step 3: Schemas**

Fim de `backend/app/schemas/transporte_regulado.py`:

```python
# ------------------------------------------------------------- P6b: linhas

LinhaSituacao = Literal["ativa", "inativa"]


class LinhaBase(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    codigo: str | None = Field(default=None, max_length=40)
    tipo_servico: TipoServico
    id_empresa: int | None = None
    id_permissionario: int | None = None
    origem: str = Field(min_length=1, max_length=150)
    destino: str = Field(min_length=1, max_length=150)
    situacao: LinhaSituacao = "ativa"
    observacoes: str | None = None

    @model_validator(mode="after")
    def _tem_operador(self) -> "LinhaBase":
        # Espelha o CHECK ck_linha_tem_operador: 422 na borda, o banco é a rede.
        if self.id_empresa is None and self.id_permissionario is None:
            raise ValueError("Informe a empresa ou o permissionário responsável pela linha.")
        return self


class LinhaCreate(LinhaBase):
    pass


class LinhaUpdate(BaseModel):
    # Parcial: o "ao menos um operador" do estado final é conferido no serviço,
    # porque só lá o payload encontra a linha existente.
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    codigo: str | None = Field(default=None, max_length=40)
    tipo_servico: TipoServico | None = None
    id_empresa: int | None = None
    id_permissionario: int | None = None
    origem: str | None = Field(default=None, min_length=1, max_length=150)
    destino: str | None = Field(default=None, min_length=1, max_length=150)
    situacao: LinhaSituacao | None = None
    observacoes: str | None = None


class LinhaParadaOut(BaseModel):
    id: int
    ordem: int
    descricao: str
    observacoes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LinhaHorarioOut(BaseModel):
    id: int
    dia_semana: int
    partida: time

    model_config = ConfigDict(from_attributes=True)


class LinhaOut(LinhaBase):
    id: int
    # Desnormalizados para a listagem (nome do operador, tamanho da grade).
    operador_nome: str | None = None
    total_horarios: int = 0
    criado_em: datetime
    atualizado_em: datetime | None = None
    paradas: list[LinhaParadaOut] = []
    horarios: list[LinhaHorarioOut] = []

    model_config = ConfigDict(from_attributes=True)


class LinhaParadaCreate(BaseModel):
    descricao: str = Field(min_length=1, max_length=200)
    observacoes: str | None = None


class LinhaParadaUpdate(BaseModel):
    descricao: str | None = Field(default=None, min_length=1, max_length=200)
    observacoes: str | None = None


class LinhaParadasOrdemInput(BaseModel):
    # A lista COMPLETA de ids na nova ordem — id faltando ou sobrando é 422
    # no serviço (payload não bate com o estado: cliente desatualizado).
    ids: list[int] = Field(min_length=1)


class LinhaHorarioCreate(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    partida: time
```

`time` entra no import de `datetime` no topo; `model_validator` no import de `pydantic` (conferir se já está).

**Nota (LinhaOut herda o validador):** `LinhaOut` estende `LinhaBase`, então o `_tem_operador` roda também na saída — inofensivo, pois linha persistida sempre satisfaz o CHECK.

- [ ] **Step 4: Service (CRUD)**

Fim de `backend/app/services/transporte_regulado.py`. Copiar o formato dos análogos de ponto no mesmo arquivo (409/404 via `HTTPException`, `func.lower` para unicidade, `_now()`/`datetime.utcnow()` conforme o padrão vigente ali — **ler `criar_ponto` e usar o mesmo**):

```python
# ------------------------------------------------------------- P6b: linhas

async def _validar_operadores_linha(
    db: AsyncSession, *, tenant_id: int,
    id_empresa: int | None, id_permissionario: int | None,
) -> None:
    """FK soft: same-tenant e não excluído, senão 404 (não 403 — cross-tenant
    não confirma existência)."""
    if id_empresa is not None:
        emp = await db.scalar(
            select(Empresa.id).where(
                Empresa.id == id_empresa,
                Empresa.tenant_id == tenant_id,
                Empresa.excluido.is_(False),
            )
        )
        if emp is None:
            raise HTTPException(404, "Empresa não encontrada")
    if id_permissionario is not None:
        perm = await db.scalar(
            select(Permissionario.id).where(
                Permissionario.id == id_permissionario,
                Permissionario.tenant_id == tenant_id,
                Permissionario.excluido.is_(False),
            )
        )
        if perm is None:
            raise HTTPException(404, "Permissionário não encontrado")


async def _validar_nome_linha_unico(
    db: AsyncSession, *, tenant_id: int, nome: str, alem_de: int | None = None,
) -> None:
    stmt = select(Linha.id).where(
        Linha.tenant_id == tenant_id,
        func.lower(Linha.nome) == nome.lower(),
        Linha.excluido.is_(False),
    )
    if alem_de is not None:
        stmt = stmt.where(Linha.id != alem_de)
    if await db.scalar(stmt) is not None:
        raise HTTPException(409, f"Já existe uma linha chamada '{nome}'")


async def obter_linha(db: AsyncSession, *, tenant_id: int, linha_id: int) -> Linha:
    linha = await db.scalar(
        select(Linha).where(
            Linha.id == linha_id,
            Linha.tenant_id == tenant_id,
            Linha.excluido.is_(False),
        )
    )
    if linha is None:
        raise HTTPException(404, "Linha não encontrada")
    return linha


async def listar_linhas(
    db: AsyncSession, *, tenant_id: int,
    q: str | None = None, tipo_servico: str | None = None,
    situacao: str | None = None, limit: int = 50, offset: int = 0,
) -> tuple[list[Linha], int]:
    # Condições construídas UMA vez e usadas na consulta E na contagem — a
    # divergência entre as duas já mordeu duas vezes neste módulo.
    cond = [Linha.tenant_id == tenant_id, Linha.excluido.is_(False)]
    if q:
        padrao = f"%{q.strip()}%"
        cond.append(or_(Linha.nome.ilike(padrao), Linha.codigo.ilike(padrao)))
    if tipo_servico:
        cond.append(Linha.tipo_servico == tipo_servico)
    if situacao:
        cond.append(Linha.situacao == situacao)
    total = await db.scalar(select(func.count(Linha.id)).where(*cond)) or 0
    rows = await db.scalars(
        select(Linha).where(*cond).order_by(Linha.nome).limit(limit).offset(offset)
    )
    return list(rows), total


async def criar_linha(db: AsyncSession, *, tenant_id: int, payload) -> Linha:
    await _validar_nome_linha_unico(db, tenant_id=tenant_id, nome=payload.nome)
    await _validar_operadores_linha(
        db, tenant_id=tenant_id,
        id_empresa=payload.id_empresa, id_permissionario=payload.id_permissionario,
    )
    linha = Linha(
        tenant_id=tenant_id, criado_em=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(linha)
    await db.flush()
    return linha


async def atualizar_linha(
    db: AsyncSession, *, tenant_id: int, linha_id: int, payload,
) -> Linha:
    linha = await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    dados = payload.model_dump(exclude_unset=True)
    if "nome" in dados:
        await _validar_nome_linha_unico(
            db, tenant_id=tenant_id, nome=dados["nome"], alem_de=linha.id
        )
    # O estado FINAL precisa manter ao menos um operador (o CHECK é a rede).
    id_emp = dados.get("id_empresa", linha.id_empresa)
    id_perm = dados.get("id_permissionario", linha.id_permissionario)
    if id_emp is None and id_perm is None:
        raise HTTPException(
            422, "A linha precisa de uma empresa ou um permissionário responsável"
        )
    await _validar_operadores_linha(
        db, tenant_id=tenant_id,
        id_empresa=dados.get("id_empresa"),
        id_permissionario=dados.get("id_permissionario"),
    )
    for campo, valor in dados.items():
        setattr(linha, campo, valor)
    linha.atualizado_em = datetime.utcnow()
    await db.flush()
    return linha


async def excluir_linha(db: AsyncSession, *, tenant_id: int, linha_id: int) -> None:
    """Soft-delete SÓ da linha — paradas e horários ficam intactos e
    invisíveis (toda leitura entra pela linha). Restaurar a linha um dia
    restaura o itinerário de graça."""
    linha = await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    linha.excluido = True
    linha.atualizado_em = datetime.utcnow()
    await db.flush()
```

Ajustar imports do topo do arquivo (`Linha`, `LinhaParada`, `LinhaHorario` de `..models`; `or_` de `sqlalchemy` se ainda não estiver).

- [ ] **Step 5: Rodar e ver passar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transporte_p6b_linhas.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/transporte_regulado.py backend/app/services/transporte_regulado.py backend/tests/test_transporte_p6b_linhas.py
git commit  # "feat(transporte): schemas e service de linha (P6b, Tarefa 2)"
```

---

### Task 3: Service de paradas e horários

**Files:**
- Modify: `backend/app/services/transporte_regulado.py`
- Test: `backend/tests/test_transporte_p6b_linhas.py` (acrescentar)

**Interfaces:**
- Consumes: `obter_linha` da Task 2; modelos `LinhaParada`, `LinhaHorario`.
- Produces: `listar_paradas(db, *, tenant_id, linha_id) -> list[LinhaParada]` (ordena `(ordem, id)`), `criar_parada(db, *, tenant_id, linha_id, payload) -> LinhaParada`, `atualizar_parada(db, *, tenant_id, linha_id, parada_id, payload) -> LinhaParada`, `excluir_parada(db, *, tenant_id, linha_id, parada_id) -> None`, `reordenar_paradas(db, *, tenant_id, linha_id, ids: list[int]) -> list[LinhaParada]`, `listar_horarios(db, *, tenant_id, linha_id) -> list[LinhaHorario]`, `criar_horario(db, *, tenant_id, linha_id, payload) -> LinhaHorario`, `excluir_horario(db, *, tenant_id, linha_id, horario_id) -> None`.

- [ ] **Step 1: Testes que falham**

Acrescentar ao arquivo de teste:

```python
async def test_parada_nova_entra_no_fim(admin_engine): ...
    # duas paradas -> ordem 1 e 2

async def test_reordenar_renumera_1_a_n(admin_engine): ...
    # criar A,B,C; reordenar([C,A,B]) -> ordens 1,2,3 na nova sequência

async def test_reordenar_com_id_faltando_ou_sobrando_da_422(admin_engine): ...
    # lista parcial -> 422; lista com id alheio -> 422

async def test_leitura_ordena_por_ordem_e_id_com_duplicata_plantada(admin_engine): ...
    # UPDATE direto forçando duas paradas com ordem=1 -> listar devolve
    # determinístico (ordem, id); nada explode

async def test_horario_duplicado_da_409(admin_engine): ...

async def test_horario_apagado_libera_o_par(admin_engine): ...
    # criar, excluir (soft), criar o mesmo par de novo -> passa

async def test_o_banco_barra_horario_duplicado_sem_passar_pelo_servico(admin_engine): ...
    # INSERT direto do par duplicado via SQL -> IntegrityError
    # (mesmo formato de test_o_banco_barra_sem_passar_pelo_servico da P6)
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transporte_p6b_linhas.py -q
```

Expected: FAIL — funções não existem.

- [ ] **Step 3: Implementar**

```python
# ---------------------------------------------------- P6b: paradas e horários

async def listar_paradas(
    db: AsyncSession, *, tenant_id: int, linha_id: int,
) -> list[LinhaParada]:
    await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    rows = await db.scalars(
        select(LinhaParada)
        .where(
            LinhaParada.tenant_id == tenant_id,
            LinhaParada.id_linha == linha_id,
            LinhaParada.excluido.is_(False),
        )
        # (ordem, id): estável mesmo com ordem duplicada — ver docstring do modelo.
        .order_by(LinhaParada.ordem, LinhaParada.id)
    )
    return list(rows)


async def criar_parada(
    db: AsyncSession, *, tenant_id: int, linha_id: int, payload,
) -> LinhaParada:
    await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    ultima = await db.scalar(
        select(func.max(LinhaParada.ordem)).where(
            LinhaParada.tenant_id == tenant_id,
            LinhaParada.id_linha == linha_id,
            LinhaParada.excluido.is_(False),
        )
    )
    parada = LinhaParada(
        tenant_id=tenant_id, id_linha=linha_id,
        ordem=(ultima or 0) + 1, criado_em=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(parada)
    await db.flush()
    return parada


async def _obter_parada(
    db: AsyncSession, *, tenant_id: int, linha_id: int, parada_id: int,
) -> LinhaParada:
    parada = await db.scalar(
        select(LinhaParada).where(
            LinhaParada.id == parada_id,
            LinhaParada.tenant_id == tenant_id,
            LinhaParada.id_linha == linha_id,
            LinhaParada.excluido.is_(False),
        )
    )
    if parada is None:
        raise HTTPException(404, "Parada não encontrada")
    return parada


async def atualizar_parada(
    db: AsyncSession, *, tenant_id: int, linha_id: int, parada_id: int, payload,
) -> LinhaParada:
    parada = await _obter_parada(
        db, tenant_id=tenant_id, linha_id=linha_id, parada_id=parada_id
    )
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(parada, campo, valor)
    parada.atualizado_em = datetime.utcnow()
    await db.flush()
    return parada


async def excluir_parada(
    db: AsyncSession, *, tenant_id: int, linha_id: int, parada_id: int,
) -> None:
    parada = await _obter_parada(
        db, tenant_id=tenant_id, linha_id=linha_id, parada_id=parada_id
    )
    parada.excluido = True
    parada.atualizado_em = datetime.utcnow()
    await db.flush()


async def reordenar_paradas(
    db: AsyncSession, *, tenant_id: int, linha_id: int, ids: list[int],
) -> list[LinhaParada]:
    """Recebe a lista COMPLETA de ids na nova ordem e renumera 1..N na mesma
    transação. Id faltando ou sobrando é 422: o payload não bate com o estado,
    o cliente está desatualizado — renumerar por cima esconderia isso."""
    atuais = await listar_paradas(db, tenant_id=tenant_id, linha_id=linha_id)
    por_id = {p.id: p for p in atuais}
    if sorted(ids) != sorted(por_id):
        raise HTTPException(
            422, "A lista de paradas não corresponde ao estado atual — recarregue a página"
        )
    agora = datetime.utcnow()
    for nova_ordem, parada_id in enumerate(ids, start=1):
        parada = por_id[parada_id]
        if parada.ordem != nova_ordem:
            parada.ordem = nova_ordem
            parada.atualizado_em = agora
    await db.flush()
    return await listar_paradas(db, tenant_id=tenant_id, linha_id=linha_id)


async def listar_horarios(
    db: AsyncSession, *, tenant_id: int, linha_id: int,
) -> list[LinhaHorario]:
    await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    rows = await db.scalars(
        select(LinhaHorario)
        .where(
            LinhaHorario.tenant_id == tenant_id,
            LinhaHorario.id_linha == linha_id,
            LinhaHorario.excluido.is_(False),
        )
        .order_by(LinhaHorario.dia_semana, LinhaHorario.partida)
    )
    return list(rows)


async def criar_horario(
    db: AsyncSession, *, tenant_id: int, linha_id: int, payload,
) -> LinhaHorario:
    await obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    # Checagem para devolver 409 legível; quem garante é ux_linha_horario.
    existe = await db.scalar(
        select(LinhaHorario.id).where(
            LinhaHorario.id_linha == linha_id,
            LinhaHorario.dia_semana == payload.dia_semana,
            LinhaHorario.partida == payload.partida,
            LinhaHorario.excluido.is_(False),
        )
    )
    if existe is not None:
        raise HTTPException(409, "Esse horário já está na grade para esse dia")
    horario = LinhaHorario(
        tenant_id=tenant_id, id_linha=linha_id, criado_em=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(horario)
    await db.flush()
    return horario


async def excluir_horario(
    db: AsyncSession, *, tenant_id: int, linha_id: int, horario_id: int,
) -> None:
    horario = await db.scalar(
        select(LinhaHorario).where(
            LinhaHorario.id == horario_id,
            LinhaHorario.tenant_id == tenant_id,
            LinhaHorario.id_linha == linha_id,
            LinhaHorario.excluido.is_(False),
        )
    )
    if horario is None:
        raise HTTPException(404, "Horário não encontrado")
    horario.excluido = True
    await db.flush()
```

- [ ] **Step 4: Rodar e ver passar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transporte_p6b_linhas.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/transporte_regulado.py backend/tests/test_transporte_p6b_linhas.py
git commit  # "feat(transporte): itinerario e grade de horarios (P6b, Tarefa 3)"
```

---

### Task 4: Router + HTTP com usuário comum

**Files:**
- Modify: `backend/app/routers/transporte_regulado.py` (fim do arquivo, após `pontos_router`)
- Modify: `backend/app/main.py` (após a linha 132, `pontos_router`)
- Test: `backend/tests/test_transporte_p6b_linhas.py` (acrescentar)

**Interfaces:**
- Consumes: service da Task 2/3; schemas da Task 2; `_cria_usuario_comum_transporte` de `tests/test_transporte_p5_2_atendimento.py`; `contratar` de `app.services.modulos`.
- Produces: `linhas_router` com as 11 rotas da spec, prefixo `/transporte-regulado/linhas`, registrado em `main.py` sob `/api/v2`.

- [ ] **Step 1: Testes HTTP que falham**

```python
async def test_http_usuario_comum_cria_linha_e_le_detalhe(admin_engine): ...
    # Mesmo esqueleto de test_http_usuario_comum_ocupa_e_le_o_mapa (P6):
    # tenant da fixture CONTRATA o módulo transporte (services.modulos.contratar),
    # _cria_usuario_comum_transporte, AsyncClient com ASGITransport(app),
    # POST /api/v2/transporte-regulado/linhas (201) com id_empresa,
    # GET /api/v2/transporte-regulado/linhas/{id} -> paradas=[] horarios=[]

async def test_http_reordenar_paradas(admin_engine): ...
    # POST 2 paradas, PUT /linhas/{id}/paradas/ordem com ids invertidos ->
    # GET detalhe devolve na nova ordem. Prova de passagem que a rota literal
    # /ordem não foi engolida por /{parada_id} (senão 422 aqui).

async def test_alvara_continua_emitindo_para_operador_de_linha(admin_engine): ...
    # O teste do NÃO-gate: criar linha para permissionário, emitir alvará
    # para ele -> continua funcionando; inativar a linha -> situacao do
    # permissionário inalterada.
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transporte_p6b_linhas.py -q -k http
```

Expected: FAIL — 404 nas rotas (router não existe).

- [ ] **Step 3: Router**

Fim de `backend/app/routers/transporte_regulado.py`:

```python
linhas_router = APIRouter(
    prefix="/transporte-regulado/linhas", tags=["transporte-regulado"]
)


async def _linha_out(db, linha, *, com_filhas: bool, tenant_id: int) -> LinhaOut:
    saida = LinhaOut.model_validate(linha)
    if linha.id_empresa is not None:
        emp = await db.get(Empresa, linha.id_empresa)
        saida.operador_nome = emp.razao_social if emp else None
    elif linha.id_permissionario is not None:
        perm = await db.get(Permissionario, linha.id_permissionario)
        saida.operador_nome = perm.nome if perm else None
    horarios = await tr_svc.listar_horarios(
        db, tenant_id=tenant_id, linha_id=linha.id
    )
    saida.total_horarios = len(horarios)
    if com_filhas:
        saida.horarios = [LinhaHorarioOut.model_validate(h) for h in horarios]
        saida.paradas = [
            LinhaParadaOut.model_validate(p)
            for p in await tr_svc.listar_paradas(
                db, tenant_id=tenant_id, linha_id=linha.id
            )
        ]
    return saida


@linhas_router.get("", response_model=Paginated[LinhaOut])
async def list_linhas(
    q: str | None = Query(None, description="Busca por nome ou código (substring)"),
    tipo_servico: str | None = None,
    situacao: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[LinhaOut]:
    offset = (page - 1) * page_size
    rows, total = await tr_svc.listar_linhas(
        db, tenant_id=tenant_id, q=q, tipo_servico=tipo_servico,
        situacao=situacao, limit=page_size, offset=offset,
    )
    return Paginated(
        items=[
            await _linha_out(db, l, com_filhas=False, tenant_id=tenant_id)
            for l in rows
        ],
        total=total, page=page, page_size=page_size,
    )


@linhas_router.post("", response_model=LinhaOut, status_code=status.HTTP_201_CREATED)
async def create_linha(
    payload: LinhaCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaOut:
    linha = await tr_svc.criar_linha(db, tenant_id=tenant_id, payload=payload)
    await db.commit()
    await db.refresh(linha)
    return await _linha_out(db, linha, com_filhas=True, tenant_id=tenant_id)


@linhas_router.get("/{linha_id}", response_model=LinhaOut)
async def get_linha(
    linha_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaOut:
    linha = await tr_svc.obter_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    return await _linha_out(db, linha, com_filhas=True, tenant_id=tenant_id)


@linhas_router.put("/{linha_id}", response_model=LinhaOut)
async def update_linha(
    linha_id: int,
    payload: LinhaUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaOut:
    linha = await tr_svc.atualizar_linha(
        db, tenant_id=tenant_id, linha_id=linha_id, payload=payload
    )
    await db.commit()
    return await _linha_out(db, linha, com_filhas=True, tenant_id=tenant_id)


@linhas_router.delete("/{linha_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_linha(
    linha_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "excluir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_linha(db, tenant_id=tenant_id, linha_id=linha_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@linhas_router.post(
    "/{linha_id}/paradas",
    response_model=LinhaParadaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_parada(
    linha_id: int,
    payload: LinhaParadaCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaParadaOut:
    parada = await tr_svc.criar_parada(
        db, tenant_id=tenant_id, linha_id=linha_id, payload=payload
    )
    await db.commit()
    return LinhaParadaOut.model_validate(parada)


# ATENÇÃO à ordem: `/paradas/ordem` é literal irmã de `/paradas/{parada_id}` e
# TEM de vir antes — a paramétrica engoliria a literal com 422 sem chegar ao
# handler. Esse defeito já ocorreu TRÊS vezes neste arquivo;
# `tests/test_guarda_ordem_rotas.py` varre e reprova.
@linhas_router.put("/{linha_id}/paradas/ordem", response_model=list[LinhaParadaOut])
async def reordenar_paradas(
    linha_id: int,
    payload: LinhaParadasOrdemInput,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[LinhaParadaOut]:
    paradas = await tr_svc.reordenar_paradas(
        db, tenant_id=tenant_id, linha_id=linha_id, ids=payload.ids
    )
    await db.commit()
    return [LinhaParadaOut.model_validate(p) for p in paradas]


@linhas_router.put("/{linha_id}/paradas/{parada_id}", response_model=LinhaParadaOut)
async def update_parada(
    linha_id: int,
    parada_id: int,
    payload: LinhaParadaUpdate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaParadaOut:
    parada = await tr_svc.atualizar_parada(
        db, tenant_id=tenant_id, linha_id=linha_id,
        parada_id=parada_id, payload=payload,
    )
    await db.commit()
    return LinhaParadaOut.model_validate(parada)


@linhas_router.delete(
    "/{linha_id}/paradas/{parada_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_parada(
    linha_id: int,
    parada_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_parada(
        db, tenant_id=tenant_id, linha_id=linha_id, parada_id=parada_id
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@linhas_router.post(
    "/{linha_id}/horarios",
    response_model=LinhaHorarioOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_horario(
    linha_id: int,
    payload: LinhaHorarioCreate,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LinhaHorarioOut:
    horario = await tr_svc.criar_horario(
        db, tenant_id=tenant_id, linha_id=linha_id, payload=payload
    )
    await db.commit()
    return LinhaHorarioOut.model_validate(horario)


@linhas_router.delete(
    "/{linha_id}/horarios/{horario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_horario(
    linha_id: int,
    horario_id: int,
    _: Usuario = Depends(require_permission("transporte_regulado", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await tr_svc.excluir_horario(
        db, tenant_id=tenant_id, linha_id=linha_id, horario_id=horario_id
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Acrescentar os schemas novos ao import de `..schemas.transporte_regulado` no topo do arquivo. Em `backend/app/main.py`, logo após a linha do `pontos_router`:

```python
app.include_router(transporte_regulado.linhas_router, prefix="/api/v2")
```

- [ ] **Step 4: Rodar e ver passar + guardas de rota**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_transporte_p6b_linhas.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py -q
```

Expected: PASS nos três. Se `test_guarda_modularizacao` reclamar de GET novo sem gate, a rota está sem `require_permission` — corrigir a rota, nunca a guarda.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/transporte_regulado.py backend/app/main.py backend/tests/test_transporte_p6b_linhas.py
git commit  # "feat(transporte): endpoints de linhas (P6b, Tarefa 4)"
```

---

### Task 5: Cliente `api.ts`

**Files:**
- Modify: `frontend/lib/api.ts` (tipos após o bloco `P6: pontos` ~linha 1970; métodos após `pontos:` ~linha 3335)

**Interfaces:**
- Consumes: endpoints da Task 4; `Paginated<T>`, `qs()`, `request<T>()` existentes.
- Produces: tipos `LinhaTransporte`, `LinhaTransporteCreate`, `LinhaTransporteUpdate`, `LinhaSituacao`, `LinhaParada`, `LinhaHorario`; namespace `api.linhasTransporte` com `list/get/create/update/remove/addParada/updateParada/removeParada/reordenarParadas/addHorario/removeHorario`.

- [ ] **Step 1: Tipos**

```typescript
// ------------------------------------------------------------- P6b: linhas

export type LinhaSituacao = "ativa" | "inativa";

export interface LinhaParada {
  id: number;
  ordem: number;
  descricao: string;
  observacoes: string | null;
}

export interface LinhaHorario {
  id: number;
  /** 0=segunda … 6=domingo. */
  dia_semana: number;
  /** "HH:MM:SS" — o backend serializa `time` assim. */
  partida: string;
}

// "LinhaTransporte", não "Linha": neste arquivo "linha" já significa linha
// de tabela em vários contextos.
export interface LinhaTransporte {
  id: number;
  nome: string;
  codigo: string | null;
  tipo_servico: TipoServico;
  id_empresa: number | null;
  id_permissionario: number | null;
  origem: string;
  destino: string;
  situacao: LinhaSituacao;
  observacoes: string | null;
  operador_nome: string | null;
  total_horarios: number;
  criado_em: string;
  atualizado_em: string | null;
  paradas: LinhaParada[];
  horarios: LinhaHorario[];
}

export type LinhaTransporteCreate = Omit<
  LinhaTransporte,
  | "id"
  | "operador_nome"
  | "total_horarios"
  | "criado_em"
  | "atualizado_em"
  | "paradas"
  | "horarios"
>;
export type LinhaTransporteUpdate = Partial<LinhaTransporteCreate>;
```

- [ ] **Step 2: Métodos**

Depois do bloco `pontos:`:

```typescript
  linhasTransporte: {
    // Paginado no backend -> Paginated<> aqui. Declarar LinhaTransporte[]
    // deixaria o tsc verde e estouraria no navegador (11 dias no transporte).
    list: (params?: {
      q?: string;
      tipo_servico?: string;
      situacao?: string;
      page?: number;
      page_size?: number;
    }) =>
      request<Paginated<LinhaTransporte>>(
        `/transporte-regulado/linhas${qs(params ?? {})}`,
      ),
    get: (id: number) =>
      request<LinhaTransporte>(`/transporte-regulado/linhas/${id}`),
    create: (data: LinhaTransporteCreate) =>
      request<LinhaTransporte>("/transporte-regulado/linhas", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: LinhaTransporteUpdate) =>
      request<LinhaTransporte>(`/transporte-regulado/linhas/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    remove: (id: number) =>
      request<void>(`/transporte-regulado/linhas/${id}`, { method: "DELETE" }),
    addParada: (linhaId: number, data: { descricao: string; observacoes?: string | null }) =>
      request<LinhaParada>(`/transporte-regulado/linhas/${linhaId}/paradas`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    updateParada: (
      linhaId: number,
      paradaId: number,
      data: { descricao?: string; observacoes?: string | null },
    ) =>
      request<LinhaParada>(
        `/transporte-regulado/linhas/${linhaId}/paradas/${paradaId}`,
        { method: "PUT", body: JSON.stringify(data) },
      ),
    removeParada: (linhaId: number, paradaId: number) =>
      request<void>(
        `/transporte-regulado/linhas/${linhaId}/paradas/${paradaId}`,
        { method: "DELETE" },
      ),
    reordenarParadas: (linhaId: number, ids: number[]) =>
      request<LinhaParada[]>(
        `/transporte-regulado/linhas/${linhaId}/paradas/ordem`,
        { method: "PUT", body: JSON.stringify({ ids }) },
      ),
    addHorario: (linhaId: number, data: { dia_semana: number; partida: string }) =>
      request<LinhaHorario>(`/transporte-regulado/linhas/${linhaId}/horarios`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    removeHorario: (linhaId: number, horarioId: number) =>
      request<void>(
        `/transporte-regulado/linhas/${linhaId}/horarios/${horarioId}`,
        { method: "DELETE" },
      ),
  },
```

- [ ] **Step 3: Type-check**

```powershell
cd c:\projetos\aprimora-py\frontend; npx tsc --noEmit
```

Expected: 0 erros.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api.ts
git commit  # "feat(transporte): cliente de linhas em api.ts (P6b, Tarefa 5)"
```

---

### Task 6: Telas — lista e detalhe

**Files:**
- Create: `frontend/app/(app)/m/transporte/linhas/page.tsx`
- Create: `frontend/app/(app)/m/transporte/linhas/[id]/page.tsx`

**Interfaces:**
- Consumes: `api.linhasTransporte.*` (Task 5); `api.empresas.list({q})` e `api.permissionarios.list({q})` (busca no servidor, existem desde a P6); primitivos `ui/` (PageHeader, Table, Dialog, Combobox, Badge, Button, EmptyState, useToast, useConfirm).
- Produces: as duas rotas; nenhum componente exportado para fora.

- [ ] **Step 1: Lista (`linhas/page.tsx`)**

Espelhar `pontos/page.tsx` (mesma estrutura: filtros com debounce de 300ms e busca NO SERVIDOR, React Query com queryKey `["tr-linhas", ...]`, dialog de criar/editar, confirm de exclusão). Diferenças:

- `TIPOS` restrito ao que o formulário sugere (o banco não impõe): `transporte_distrital`, `transporte_escolar`, `outro`.
- Formulário: nome, código, tipo, origem, destino, situação (`ativa`/`inativa` — rótulos "Ativa"/"Inativa"), observações, e o **operador** em dois `Combobox` com busca no servidor (padrão do seletor de ocupante da P6, `pontos/[id]/page.tsx`):

```tsx
// Operador: empresa E/OU permissionário — ao menos um (o backend devolve 422
// com mensagem se nenhum vier; o submit também valida para orientar antes).
const [buscaEmp, setBuscaEmp] = useState("");
const empresasQ = useQuery({
  queryKey: ["tr-empresas-busca", buscaEmp],
  queryFn: () => api.empresas.list({ q: buscaEmp || undefined }),
  enabled: dialogOpen,
});
// idem para permissionários com api.permissionarios.list
```

- Colunas da tabela: Linha (nome + código, link para `/m/transporte/linhas/${l.id}`), Trajeto (`{l.origem} → {l.destino}`), Tipo, Operador (`l.operador_nome ?? "—"`), Horários/semana (`l.total_horarios`), Situação (Badge `success`/`neutral`), Ações (Editar/Excluir gated por `can("transporte_regulado", ...)`).
- `EmptyState`: com busca ativa não oferece "cadastrar" (mesma razão comentada na P6).
- PageHeader: icon `Route` (lucide), title "Linhas e Itinerários", breadcrumbs `Transporte Regulado → Linhas`.

- [ ] **Step 2: Detalhe (`linhas/[id]/page.tsx`)**

`useParams()` para o id; `useQuery({ queryKey: ["tr-linha", id], queryFn: () => api.linhasTransporte.get(id) })`. Três seções em `Card`:

1. **Dados** — nome/código/trajeto/tipo/operador/situação + botão Editar (mesmo dialog da lista, extraído localmente ou duplicado enxuto — sem criar componente compartilhado prematuro).
2. **Itinerário** — lista ordenada das paradas; cada item com `descricao`, botões ▲/▼ (**botões, não drag** — teclado de graça, sem dependência nova), Editar (dialog com descrição/observações) e Remover. Mover chama:

```tsx
function mover(idx: number, delta: -1 | 1) {
  const ids = paradas.map((p) => p.id);
  const alvo = idx + delta;
  if (alvo < 0 || alvo >= ids.length) return;
  [ids[idx], ids[alvo]] = [ids[alvo], ids[idx]];
  reordenarM.mutate(ids); // api.linhasTransporte.reordenarParadas(id, ids)
}
```

   No `onError` do reordenar, mostrar a mensagem do servidor (o 422 de "recarregue a página" é acionável) e invalidar a query.
3. **Grade de horários** — tabela com uma coluna por dia (`Seg…Dom`, `DIAS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]`), horários de cada dia em badges com × para remover (gated por `canEdit`); form inline "dia + hora" (`<Select>` de dia + `<Input type="time">`) que chama `addHorario` com `partida: valor + ":00"`. Exibição corta os segundos: `h.partida.slice(0, 5)`.

Adicionar/remover parada e horário invalidam `["tr-linha", id]`.

- [ ] **Step 3: Type-check + suíte (a guarda de órfã DEVE falhar agora)**

```powershell
cd c:\projetos\aprimora-py\frontend; npx tsc --noEmit; npx vitest run __tests__/rotas-modulo.test.ts
```

Expected: `tsc` 0 erros; **`rotas-modulo.test.ts` FALHA** acusando `/m/transporte/linhas` como página órfã — é o RED da Task 7, e a prova de que a guarda enxerga a tela nova. Se ela passar aqui, PARE: a guarda não está vendo a página, investigar antes de seguir.

- [ ] **Step 4: Commit**

```bash
git add "frontend/app/(app)/m/transporte/linhas"
git commit  # "feat(transporte): telas de linhas e itinerarios (P6b, Tarefa 6)"
```

(Commit com a guarda vermelha é aceitável aqui porque a Task 7 é o GREEN dela no mesmo PR; não empurrar antes da Task 7.)

---

### Task 7: Costura — hub, menu, palette + validação final

**Files:**
- Modify: `frontend/lib/transporte-hub.ts` (card "Linhas e Itinerários" ganha `href` + `ready: true`)
- Modify: `frontend/lib/menus/transporte.ts` (item novo após "Pontos e Vagas")
- Modify: `frontend/components/CommandPalette.tsx` ou onde vive `KEYWORDS_POR_HREF` (conferir com grep) — chaves para `/m/transporte/linhas`
- Modify: `frontend/__tests__/transporte-hub.test.tsx` (lista de cards sem href: sai "Linhas e Itinerários", fica só `["Ocorrências"]`)
- Modify: `frontend/__tests__/menus.test.tsx` (tabela `PERMISSOES_ESPERADAS`: item novo com `perm: "transporte_regulado"`)

**Interfaces:**
- Consumes: rotas da Task 6.
- Produces: navegação completa; guardas verdes.

- [ ] **Step 1: RED — atualizar os testes de costura primeiro**

Em `transporte-hub.test.tsx`, trocar a expectativa:

```tsx
expect(semHref).toEqual(["Ocorrências"]);
```

Em `menus.test.tsx`, acrescentar a linha do item novo à tabela `PERMISSOES_ESPERADAS` (copiar o formato da linha de "Pontos e Vagas"). Rodar:

```powershell
cd c:\projetos\aprimora-py\frontend; npx vitest run __tests__/transporte-hub.test.tsx __tests__/menus.test.tsx
```

Expected: FAIL nos dois (hub ainda traceja o card; menu não tem o item).

- [ ] **Step 2: GREEN — hub, menu e palette**

`lib/transporte-hub.ts` — o card existente vira:

```typescript
  {
    href: "/m/transporte/linhas",
    icon: Route,
    title: "Linhas e Itinerários",
    desc: "Linhas distritais e escolares, com itinerário e horários.",
    ready: true,
  },
```

`lib/menus/transporte.ts` — após "Pontos e Vagas":

```typescript
        {
          label: "Linhas e Itinerários",
          href: "/m/transporte/linhas",
          icon: Route,
          perm: "transporte_regulado",
        },
```

(`Route` entra no import de `lucide-react` dos dois arquivos.)

`KEYWORDS_POR_HREF` — localizar com `grep -n "KEYWORDS_POR_HREF" frontend/` e acrescentar:

```typescript
  "/m/transporte/linhas": ["linha", "itinerario", "horario", "distrital", "escolar"],
```

- [ ] **Step 3: Validação final completa**

```powershell
cd c:\projetos\aprimora-py\frontend; npx tsc --noEmit; npx vitest run
```

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest -q
```

Expected: tudo verde (suíte frontend inteira, incluindo `rotas-modulo` — o RED da Task 6 vira GREEN aqui — e a suíte backend completa, ~8 min).

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/transporte-hub.ts frontend/lib/menus/transporte.ts frontend/__tests__/transporte-hub.test.tsx frontend/__tests__/menus.test.tsx
# + o arquivo do KEYWORDS_POR_HREF
git commit  # "feat(transporte): costura de linhas no hub, menu e palette (P6b, Tarefa 7)"
```

- [ ] **Step 5: Atualizar `docs/BACKLOG-PENDENCIAS.md`**

Na seção 2.2, marcar a metade de linha/itinerário do P6 como entregue (com data e as decisões-chave: operador ao-menos-um no CHECK, ordem sem único, horário único no banco), no estilo dos blocos das fases anteriores. Commit `docs(transporte): fecha linhas e itinerarios (P6b) no backlog`.

---

## Self-review (feito na escrita)

- **Cobertura da spec:** modelo (T1), regras+CRUD (T2), paradas/horários com as três exclusividades e provas por inversão (T3), superfície HTTP com ordem de rotas e usuário comum e não-gate (T4), api.ts (T5), telas (T6), costura+guardas (T7). Assunções da spec não geram task (são documentação).
- **Sem placeholders:** todo step de código tem o código; os testes de T2/T3/T4 têm assinatura + conteúdo descrito com referência a análogo concreto no mesmo arquivo-molde (`test_transporte_p6_pontos.py`), que o executor DEVE ler antes.
- **Consistência de tipos:** `LinhaOut.paradas/horarios` ↔ `_linha_out(com_filhas=...)` ↔ `LinhaTransporte.paradas/horarios`; `reordenarParadas(ids)` ↔ `LinhaParadasOrdemInput.ids`; `partida` `time` ↔ string `"HH:MM:SS"` no front (corte `.slice(0,5)` na exibição, sufixo `":00"` no envio).
