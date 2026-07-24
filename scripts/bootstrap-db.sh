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
-- Equivalente a `alembic stamp 0020`: INSERT direto evita segunda invocação do alembic e garante determinismo.
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
HEAD_REV=$( cd "$REPO" && python -m alembic heads 2>/dev/null | awk 'NR==1{print $1}' )
VER=$(psql_db -tAc "SELECT version_num FROM aprimora_py.alembic_version ORDER BY 1 DESC LIMIT 1")
PROC=$(psql_db -tAc "SELECT to_regclass('protocolos.processo') IS NOT NULL")
NTB=$(psql_db -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')")
log "alembic=$VER (head=$HEAD_REV) processo=$PROC tabelas=$NTB"
[ -n "$VER" ] && [ "$VER" = "$HEAD_REV" ] || { echo "[bootstrap] ERRO: alembic esperado head '$HEAD_REV', obtido '$VER'"; exit 1; }
[ "$PROC" = "t" ]   || { echo "[bootstrap] ERRO: protocolos.processo ausente"; exit 1; }
log "OK — bootstrap completo."
