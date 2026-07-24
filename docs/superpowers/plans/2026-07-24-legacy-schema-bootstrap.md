# Bootstrap do Schema Legado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o bootstrap de banco quebrado por um script idempotente que carrega o schema legado completo + roda as migrations + semeia o mínimo, validado local e aplicado no servidor.

**Architecture:** Um `scripts/bootstrap-db.sh` (fonte única) executa 6 passos espelhando o CI: stubs → dump completo `ci/legacy-schema.sql` → role RLS → baseline `alembic_version=0020` → `alembic upgrade head` (0021–0062) → seed via `python -m app.cli.seed_bootstrap`. Um service `bootstrap` (profile `init`) no compose chama o script; roda do container backend (com `postgresql-client`). Substitui `schema-init`/`db-init`.

**Tech Stack:** Bash, PostgreSQL 17, psql, Alembic 1.14, SQLAlchemy 2.0 async, Python 3.12, Docker Compose v2.

## Global Constraints

- Banco: `ged_saas_db`, user `ged_user`, senha `ged_password_secure_local` (dev).
- `alembic_version` mora no schema `aprimora_py` (ver `backend/alembic/env.py`).
- Baseline do dump = revision `0020`; head atual = `0062`.
- Admin: `admin@local.test` / senha dev `admin123`; tenant `sobral` (id=1).
- `Sistema.app` deve ser `'aprimora'` (bate com `settings.app_name`).
- Falha ruidosa: `set -euo pipefail` no script, `ON_ERROR_STOP=1` no psql do dump.
- Dump correto = `ci/legacy-schema.sql` (completo). NUNCA o `-filtered`.
- Bugs pré-requisito já corrigidos e commitados (env.py commit, guard 0062) — não refazer.

---

### Task 1: Arquivo de stubs `ci/bootstrap-stubs.sql`

Extrai os stubs cross-schema (hoje inline no CI) para um arquivo reutilizável, adicionando o stub `sistema_chamados.tipo_chamado` (o trigger legado `utils.copia_sistemas_tipochamados()` insere nele ao inserir em `utils.sistema`).

**Files:**
- Create: `ci/bootstrap-stubs.sql`

**Interfaces:**
- Produces: arquivo SQL idempotente aplicável com `psql -f ci/bootstrap-stubs.sql`.

- [ ] **Step 1: Criar `ci/bootstrap-stubs.sql`**

```sql
-- Pré-requisitos cross-schema para carregar ci/legacy-schema.sql.
-- O dump referencia objetos fora de utils/protocolos/aprimora_py.
-- Idempotente (IF NOT EXISTS / CREATE OR REPLACE).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE OR REPLACE FUNCTION public.trigger_set_timestamp()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE SCHEMA IF NOT EXISTS despesas;
CREATE TABLE IF NOT EXISTS despesas.feempliq (id integer PRIMARY KEY);

CREATE SCHEMA IF NOT EXISTS empresasimples;
CREATE TABLE IF NOT EXISTS empresasimples.cnae_subgrupos (id integer PRIMARY KEY);

CREATE SCHEMA IF NOT EXISTS agendamento;
CREATE TABLE IF NOT EXISTS agendamento.servico_informacao
  (id integer PRIMARY KEY, url varchar, label varchar, id_servico integer);
CREATE TABLE IF NOT EXISTS agendamento.servico_unidade_trabalho (id_servico integer);

-- O trigger legado utils.copia_sistemas_tipochamados() (presente no dump)
-- insere aqui ao inserir em utils.sistema — sem o stub o seed falha.
CREATE SCHEMA IF NOT EXISTS sistema_chamados;
CREATE TABLE IF NOT EXISTS sistema_chamados.tipo_chamado
  (id serial PRIMARY KEY, tipo varchar, permissao_acesso varchar, id_setor integer);
```

- [ ] **Step 2: Validar que aplica limpo num DB descartável**

Run:
```bash
docker exec aprimora-py-db psql -U ged_user -d ged_saas_db -c 'DROP DATABASE IF EXISTS ged_stub_test;'
docker exec aprimora-py-db psql -U ged_user -d ged_saas_db -c 'CREATE DATABASE ged_stub_test;'
cat ci/bootstrap-stubs.sql | docker exec -i aprimora-py-db psql -U ged_user -d ged_stub_test -v ON_ERROR_STOP=1
docker exec aprimora-py-db psql -U ged_user -d ged_saas_db -c 'DROP DATABASE ged_stub_test;'
```
Expected: sem erros; termina em `CREATE TABLE`.

- [ ] **Step 3: Commit**

```bash
git add ci/bootstrap-stubs.sql
git commit -m "feat(ci): stubs cross-schema reutilizaveis para bootstrap do legado"
```

---

### Task 2: Seed CLI `app.cli.seed_bootstrap`

CLI idempotente que semeia o mínimo para o sistema logar com todos os módulos: catálogo global (`Sistema` app=aprimora, `Nivel` valor=0), tenant Sobral, admin super-usuário, JWT.

**Files:**
- Create: `backend/app/cli/seed_bootstrap.py`
- Test: `backend/tests/test_seed_bootstrap.py`

**Interfaces:**
- Consumes: `app.database.SessionLocal`, `app.auth.password.hash_password`, models `Tenant, Sistema, Nivel, Grupo, Usuario, UsuarioGrupo`.
- Produces: `python -m app.cli.seed_bootstrap` (exit 0); função `async def seed(db) -> dict` retornando contagens `{"tenant_id": int, "usuario_id": int, "is_super": bool}`.

- [ ] **Step 1: Escrever o teste falho**

```python
# backend/tests/test_seed_bootstrap.py
import pytest
from sqlalchemy import text
from app.cli.seed_bootstrap import seed
from app.database import SessionLocal
from app.services.permissoes import load_permissions


@pytest.mark.asyncio
async def test_seed_bootstrap_cria_super_usuario():
    async with SessionLocal() as db:
        res = await seed(db)
        await db.commit()
    assert res["tenant_id"] == 1
    assert res["usuario_id"] > 0
    # A verificação real: load_permissions vê o admin como super-usuário.
    async with SessionLocal() as db:
        perms = await load_permissions(db, res["usuario_id"], tenant_id=1)
    assert perms.is_super_usuario is True


@pytest.mark.asyncio
async def test_seed_bootstrap_idempotente():
    async with SessionLocal() as db:
        await seed(db); await db.commit()
    async with SessionLocal() as db:
        res2 = await seed(db); await db.commit()  # 2a vez não duplica
    async with SessionLocal() as db:
        n = (await db.execute(text(
            "SELECT count(*) FROM utils.usuario WHERE email='admin@local.test'"
        ))).scalar_one()
    assert n == 1
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `docker exec aprimora-py-backend pytest tests/test_seed_bootstrap.py -v`
Expected: FAIL com `ModuleNotFoundError: app.cli.seed_bootstrap`.

- [ ] **Step 3: Implementar `backend/app/cli/seed_bootstrap.py`**

```python
"""Seed mínimo de bootstrap — sistema logável com todos os módulos.

Idempotente. Cria (get_or_create):
  1. Catálogo global: utils.sistema(app='aprimora') + utils.nivel(valor=0)
  2. Tenant Sobral (aprimora_py.tenant, id=1) — 0003 é pulada pelo baseline 0020
  3. Admin super-usuário admin@local.test (senha dev admin123)
  4. utils.grupo (nível 0, sistema aprimora) + utils.usuario_grupo (tenant 1)
  5. Segredo KEY_LOGIN_GLOBAL_JWT em utils.sistema_constante

Uso: docker exec aprimora-py-backend python -m app.cli.seed_bootstrap
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from ..database import SessionLocal
from ..models import Grupo, Nivel, Sistema, Tenant, Usuario, UsuarioGrupo

ADMIN_EMAIL = "admin@local.test"
ADMIN_SENHA = "admin123"
TENANT_SLUG = "sobral"


async def _set_local_tenant(db: AsyncSession, tenant_id: int) -> None:
    await db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))


async def seed(db: AsyncSession) -> dict:
    # 1. Catálogo global (sistema app=aprimora + nível 0). O stub
    # sistema_chamados.tipo_chamado (Task 1) deixa o trigger legado passar.
    sistema = (
        await db.execute(select(Sistema).where(Sistema.app == "aprimora"))
    ).scalars().first()
    if sistema is None:
        sistema = Sistema(sistema="Aprimora", app="aprimora", url="/", excluido=False)
        db.add(sistema)
        await db.flush()

    nivel = (
        await db.execute(select(Nivel).where(Nivel.valor == 0))
    ).scalars().first()
    if nivel is None:
        nivel = Nivel(nivel="Super Usuario", valor=0, excluido=False)
        db.add(nivel)
        await db.flush()

    # 2. Tenant Sobral
    tenant = (
        await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    ).scalars().first()
    if tenant is None:
        tenant = Tenant(
            slug=TENANT_SLUG,
            nome="Prefeitura de Sobral",
            plano="basico",
            ativo=True,
            criado_em=datetime.utcnow(),
        )
        db.add(tenant)
        await db.flush()
    tenant_id = tenant.id

    await _set_local_tenant(db, tenant_id)

    # 3. Admin super-usuário
    usuario = (
        await db.execute(
            select(Usuario).where(
                Usuario.email == ADMIN_EMAIL, Usuario.tenant_id == tenant_id
            )
        )
    ).scalars().first()
    if usuario is None:
        usuario = Usuario(
            tenant_id=tenant_id,
            nome="Admin Sobral",
            email=ADMIN_EMAIL,
            senha="",
            senha_bcrypt=hash_password(ADMIN_SENHA),
            cpf="00000000000",
            ativo=True,
            excluido=False,
            app="aprimora",
            nivel_acesso_sigilo="interno",
            must_change_password=False,
        )
        db.add(usuario)
        await db.flush()

    # 4. Grupo SU + vínculo
    grupo = (
        await db.execute(
            select(Grupo).where(
                Grupo.tenant_id == tenant_id,
                Grupo.id_nivel == nivel.id,
                Grupo.id_sistema == sistema.id,
            )
        )
    ).scalars().first()
    if grupo is None:
        grupo = Grupo(
            id_nivel=nivel.id,
            id_sistema=sistema.id,
            grupo="Administradores",
            tenant_id=tenant_id,
            excluido=False,
        )
        db.add(grupo)
        await db.flush()

    vinculo = (
        await db.execute(
            select(UsuarioGrupo).where(
                UsuarioGrupo.id_usuario == usuario.id,
                UsuarioGrupo.id_grupo == grupo.id,
            )
        )
    ).scalars().first()
    if vinculo is None:
        db.add(
            UsuarioGrupo(
                id_usuario=usuario.id,
                id_grupo=grupo.id,
                tenant_id=tenant_id,
                ativo=True,
                excluido=False,
            )
        )

    # 5. Segredo JWT
    jwt_exists = (
        await db.execute(
            text(
                "SELECT 1 FROM utils.sistema_constante "
                "WHERE constante='KEY_LOGIN_GLOBAL_JWT' LIMIT 1"
            )
        )
    ).first()
    if jwt_exists is None:
        await db.execute(
            text(
                "INSERT INTO utils.sistema_constante (constante, valor_padrao, excluido) "
                "VALUES ('KEY_LOGIN_GLOBAL_JWT', :v, false)"
            ),
            {"v": secrets.token_urlsafe(48)},
        )

    return {"tenant_id": tenant_id, "usuario_id": usuario.id, "is_super": True}


async def _main() -> int:
    async with SessionLocal() as db:
        res = await seed(db)
        await db.commit()
    print(f"[seed_bootstrap] OK: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
```

- [ ] **Step 4: Rodar os testes e ver passar**

Run: `docker exec aprimora-py-backend pytest tests/test_seed_bootstrap.py -v`
Expected: PASS (2 testes). Se falhar por coluna faltante num model, conferir os nomes reais em `backend/app/models/`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/seed_bootstrap.py backend/tests/test_seed_bootstrap.py
git commit -m "feat(cli): seed_bootstrap idempotente (tenant + admin super-usuario + JWT)"
```

---

### Task 3: Script orquestrador `scripts/bootstrap-db.sh`

O script que amarra os 6 passos. Roda do container backend (tem alembic/python; `postgresql-client` adicionado na Task 4).

**Files:**
- Create: `scripts/bootstrap-db.sh`

**Interfaces:**
- Consumes: `ci/bootstrap-stubs.sql` (Task 1), `ci/legacy-schema.sql`, `python -m app.cli.seed_bootstrap` (Task 2).
- Produces: DB pronto em `alembic=0062` + seed; script rodável com `bash scripts/bootstrap-db.sh`.

- [ ] **Step 1: Criar `scripts/bootstrap-db.sh`**

```bash
#!/usr/bin/env bash
# Bootstrap idempotente do banco: schema legado completo + migrations + seed.
# Roda do container backend (WORKDIR /app; repo montado). Requer psql + alembic.
set -euo pipefail

PGHOST="${PGHOST:-db}"
PGUSER="${PGUSER:-ged_user}"
PGDATABASE="${PGDATABASE:-ged_saas_db}"
export PGPASSWORD="${PGPASSWORD:-ged_password_secure_local}"
BASELINE="0020"
REPO="${REPO:-/app}"            # repo montado em /app no container backend
CI_DIR="${CI_DIR:-$REPO/../ci}" # ci/ é irmão de backend/ no repo

psql_db() { psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" "$@"; }

log() { echo "[bootstrap] $*"; }

# Passo 0 — guard de idempotência
if psql_db -tAc "SELECT to_regclass('protocolos.processo')" | grep -q .; then
  log "protocolos.processo já existe — schema já carregado, pulando passos 1-2."
  SCHEMA_LOADED=1
else
  SCHEMA_LOADED=0
fi

if [ "$SCHEMA_LOADED" = "0" ]; then
  # Passo 1 — stubs
  log "Passo 1: stubs cross-schema"
  psql_db -v ON_ERROR_STOP=1 -f "$CI_DIR/bootstrap-stubs.sql" >/dev/null

  # Passo 2 — dump completo (falha ruidosa)
  log "Passo 2: carregando ci/legacy-schema.sql (completo)"
  psql_db -v ON_ERROR_STOP=1 -f "$CI_DIR/legacy-schema.sql" >/dev/null
fi

# Passo 3 — role RLS (ANTES do upgrade: 0024 faz GRANT à role)
log "Passo 3: role aprimora_app + grants"
psql_db -v ON_ERROR_STOP=1 <<SQL >/dev/null
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aprimora_app') THEN
    CREATE ROLE aprimora_app LOGIN NOSUPERUSER NOBYPASSRLS
      PASSWORD 'ged_password_secure_local';
  END IF;
END \$\$;
GRANT CONNECT ON DATABASE $PGDATABASE TO aprimora_app;
GRANT USAGE ON SCHEMA protocolos, utils, aprimora_py, public TO aprimora_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA protocolos, utils, aprimora_py, public TO aprimora_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA protocolos, utils, aprimora_py, public TO aprimora_app;
SQL

# Passo 4 — baseline + migrations
log "Passo 4: baseline $BASELINE + alembic upgrade head"
psql_db -v ON_ERROR_STOP=1 <<SQL >/dev/null
CREATE SCHEMA IF NOT EXISTS aprimora_py;
CREATE TABLE IF NOT EXISTS aprimora_py.alembic_version (version_num varchar(32) NOT NULL);
INSERT INTO aprimora_py.alembic_version (version_num)
  SELECT '$BASELINE'
  WHERE NOT EXISTS (SELECT 1 FROM aprimora_py.alembic_version);
SQL
( cd "$REPO" && python -m alembic upgrade head )

# Passo 5 — seed mínimo
log "Passo 5: seed_bootstrap"
( cd "$REPO" && python -m app.cli.seed_bootstrap )

# Passo 6 — sanidade
log "Passo 6: sanidade"
VER=$(psql_db -tAc "SELECT version_num FROM aprimora_py.alembic_version")
PROC=$(psql_db -tAc "SELECT to_regclass('protocolos.processo') IS NOT NULL")
NTB=$(psql_db -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')")
log "alembic=$VER processo=$PROC tabelas=$NTB"
[ "$VER" = "0062" ] || { echo "[bootstrap] ERRO: alembic esperado 0062, obtido $VER"; exit 1; }
[ "$PROC" = "t" ]   || { echo "[bootstrap] ERRO: protocolos.processo ausente"; exit 1; }
log "OK — bootstrap completo."
```

- [ ] **Step 2: Tornar executável**

Run: `chmod +x scripts/bootstrap-db.sh`

- [ ] **Step 3: Commit**

```bash
git add scripts/bootstrap-db.sh
git commit -m "feat: scripts/bootstrap-db.sh — bootstrap idempotente do schema legado"
```

---

### Task 4: Wiring no compose + `postgresql-client` na imagem

Adiciona `postgresql-client` ao backend, cria o service `bootstrap` (profile `init`) e remove `schema-init`/`db-init`.

**Files:**
- Modify: `backend/Dockerfile` (bloco `apt-get install`)
- Modify: `docker-compose.yml` (services `schema-init`, `db-init` → `bootstrap`)

**Interfaces:**
- Consumes: `scripts/bootstrap-db.sh` (Task 3).
- Produces: `docker compose --profile init up bootstrap` executa o bootstrap.

- [ ] **Step 1: Adicionar `postgresql-client` ao `backend/Dockerfile`**

Modificar o bloco `apt-get install` (linhas ~8-13) para incluir `postgresql-client`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev postgresql-client \
      libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
      libffi-dev shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: Rebuild backend e confirmar psql presente**

Run:
```bash
docker compose build backend
docker compose run --rm --no-deps backend psql --version
```
Expected: imprime a versão do psql (ex.: `psql (PostgreSQL) 16.x`).

- [ ] **Step 3: Substituir `schema-init`/`db-init` por `bootstrap` no `docker-compose.yml`**

Remover os dois services (linhas ~26-51, os blocos `schema-init:` e `db-init:`) e inserir no lugar:

```yaml
  bootstrap:
    build: ./backend
    container_name: aprimora-py-bootstrap
    environment:
      <<: *backend-env
      PGHOST: db
      PGUSER: ged_user
      PGPASSWORD: ged_password_secure_local
      PGDATABASE: ged_saas_db
    volumes: *backend-volumes
    networks: *backend-networks
    working_dir: /app
    command: sh -c "bash /app/../scripts/bootstrap-db.sh"
    depends_on:
      db:
        condition: service_healthy
    profiles: ["init"]
```

> Nota: `*backend-volumes` monta `./backend:/app`. O script e o `ci/` estão na raiz do repo. Confirmar na Task 5 que o container enxerga `scripts/` e `ci/` — se o mount for só `./backend`, ajustar o `bootstrap` para montar a raiz do repo: adicionar `- ./scripts:/app/../scripts:ro` e `- ./ci:/app/../ci:ro`, ou montar `.:/repo` e usar `REPO=/repo/backend CI_DIR=/repo/ci`.

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile docker-compose.yml
git commit -m "feat(compose): service bootstrap (profile init) + postgresql-client; remove schema-init/db-init"
```

---

### Task 5: Validação local end-to-end

Rebuild limpo local usando o novo bootstrap e confirmar login + módulos.

**Files:** nenhum (validação).

**Interfaces:**
- Consumes: Tasks 1-4.

- [ ] **Step 1: Rebuild limpo local**

Run:
```bash
docker compose down -v
docker compose build backend
docker compose --profile init up bootstrap
```
Expected: termina com `[bootstrap] OK — bootstrap completo.` e exit 0. Se o container não achar `scripts/`/`ci/`, aplicar o ajuste de mount da Task 4 Step 3.

- [ ] **Step 2: Subir a stack**

Run: `docker compose up -d && sleep 10 && docker compose ps`
Expected: backend `healthy`, db `healthy`.

- [ ] **Step 3: Validar login + super-usuário**

Run:
```bash
TOKEN=$(curl -s -X POST http://localhost:8090/api/v2/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@local.test","senha":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s http://localhost:8090/api/v2/auth/me -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;d=json.load(sys.stdin);print('super:',d['is_super_usuario'])"
```
Expected: login retorna token; `super: True`.

- [ ] **Step 4: Validar que uma página de módulo NÃO dá 500**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8090/api/v2/servicos -H "Authorization: Bearer $TOKEN"`
Expected: `200` (antes dava 500 por tabela ausente).

- [ ] **Step 5: Commit (marca de validação)**

Sem mudança de código — se algum ajuste de mount foi necessário na Task 4, commitar aqui:
```bash
git add docker-compose.yml
git commit -m "fix(compose): ajusta mounts do bootstrap p/ enxergar scripts/ e ci/"
```

---

### Task 6: Rollout no servidor

Aplica o bootstrap corrigido no VPS (rebuild limpo, sem backup — sistema em testes).

**Files:** nenhum (deploy). Ver [[project_server_deploy]] para acesso SSH.

**Interfaces:**
- Consumes: Tasks 1-5 (merged em main).

- [ ] **Step 1: Push de tudo para main**

Run: `git push origin main`

- [ ] **Step 2: No servidor — pull + rebuild limpo**

Via SSH (103.230.142.69, ver método SSH_ASKPASS em [[project_server_deploy]]):
```bash
cd /root/GedDocPublico
git fetch origin main && git reset --hard origin/main
docker compose down -v
docker compose build backend
docker compose --profile init up bootstrap
```
Expected: `[bootstrap] OK — bootstrap completo.`

- [ ] **Step 3: Subir a stack + nginx no servidor**

```bash
docker compose up -d db redis backend worker beat frontend
docker compose up -d nginx
```

- [ ] **Step 4: Validar externamente**

Run (da máquina local):
```bash
curl -s -X POST http://103.230.142.69:8090/api/v2/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@local.test","senha":"admin123"}' -o /dev/null -w "login: %{http_code}\n"
curl -s -o /dev/null -w "servicos: %{http_code}\n" http://103.230.142.69:8090/api/v2/servicos
```
Expected: login `200`. (servicos sem token = 401/403, mas não 500.)

- [ ] **Step 5: Confirmar no browser**

Hard-refresh (`Ctrl+Shift+R`), login `admin@local.test`/`admin123`, navegar nos módulos (Protocolo, Transporte, Frota, Pagamentos) — sem 500.

- [ ] **Step 6: Atualizar memória**

Atualizar [[project_next_step]] e [[project_schema_bootstrap_blocker]]: bootstrap corrigido e aplicado; band-aids substituídos pela solução real.

---

## Self-Review

**Spec coverage:** Passos A (script, Tasks 1+3), A.1 (bugs — já commitados, citados em Global Constraints), B (wiring, Task 4), C (seed, Task 2), D (rollout, Tasks 5-6), E (validação, Tasks 5-6). ✅
**Placeholders:** nenhum "TBD"; código completo em cada passo. A única condicional é o ajuste de mount (Task 4 Step 3 / Task 5 Step 1) — documentado com a correção exata, não um placeholder.
**Type consistency:** `seed(db) -> dict` com `tenant_id/usuario_id/is_super` usado igual no teste (Task 2) e citado nas interfaces. `bootstrap-db.sh` consome `ci/bootstrap-stubs.sql`, `ci/legacy-schema.sql`, `python -m app.cli.seed_bootstrap` — todos definidos.

**Risco aberto conhecido:** o mount do container `bootstrap` precisa enxergar `scripts/` e `ci/` (não só `./backend`). Resolvido explicitamente na Task 4 Step 3 + Task 5 Step 1.
