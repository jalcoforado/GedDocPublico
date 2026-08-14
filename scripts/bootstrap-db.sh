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
SQL

# GRANT-cobertor: só no bootstrap de banco NOVO, e sempre ANTES do `upgrade
# head` (Passo 4) — SEC-01A. Numa RE-execução as tabelas já existem, e o
# cobertor então DESFARIA os `REVOKE` feitos por migration: a 0076 tira de
# `aprimora_app` a DML de entitlement (`tenant`, `tenant_modulo`, catálogo de
# módulo) e a mutação da trilha de auditoria, e daria DML nas tabelas de
# plataforma (`platform_principal`, `platform_audit_log`), que só
# `aprimora_platform` pode escrever (ADR-016 §2.3).
#
# Consequência desejada: os GRANTs das migrations são os FINAIS. Tabela nova
# sem `GRANT` explícito na própria migration deixa de ser coberta — disciplina
# que o CLAUDE.md já exige. `tests/test_platform_admin_identity.py` reprova se
# `aprimora_app` recuperar escrita nas tabelas de plataforma.
if [ "$SCHEMA_LOADED" = "0" ]; then
  log "Passo 3b: GRANT-cobertor do baseline (banco novo)"
  psql_db -v ON_ERROR_STOP=1 <<SQL >/dev/null
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA protocolos, utils, aprimora_py, public TO aprimora_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA protocolos, utils, aprimora_py, public TO aprimora_app;
SQL
else
  log "Passo 3b: GRANT-cobertor pulado (banco já existente — reparo no passo 4b)"
fi

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

# Robustez: em alguns ambientes (combinação de versões alembic/SQLAlchemy) o
# `upgrade` aplica todo o DDL mas NÃO persiste o bump de `alembic_version`
# (fica na baseline). Como o upgrade acima saiu 0 sob `set -e`, todas as
# migrations rodaram — então forçamos a versão pro head de forma determinística
# (via psql, que comita). Isso também torna re-execuções idempotentes: numa 2a
# rodada a versão já é o head e o upgrade acima é no-op.
HEAD_REV=$( cd "$REPO" && python -m alembic heads 2>/dev/null | awk 'NR==1{print $1}' )
if [ -n "$HEAD_REV" ]; then
  psql_db -v ON_ERROR_STOP=1 -c "UPDATE aprimora_py.alembic_version SET version_num = '$HEAD_REV'" >/dev/null
fi

# Passo 4b — reparo de grants em banco JÁ EXISTENTE
#
# Pular o cobertor no passo 3b é a decisão certa, mas ela deixava um buraco:
# banco criado ANTES de o 3b existir nunca recebeu o cobertor, e re-rodar o
# bootstrap não consertava — por decisão, não por bug. Ficava sem a DML de
# baseline em `protocolos.*` e `utils.*` para sempre, e o sintoma era ~21
# testes de RLS vermelhos SÓ na máquina, verdes no CI (que sempre parte de
# banco novo). Medido em 2026-08-13: 81/86 tabelas de `protocolos` e 86/86 de
# `utils` sem DML no dev local; a VPS estava correta.
#
# `reparar_grants` é o cobertor SEGURO de repetir: aplica e, na MESMA
# transação, reafirma todas as revogações declaradas pelas migrations
# (0076/0079/0080). `tests/test_guarda_reparar_grants.py` reprova se as duas
# listas divergirem.
#
# Roda DEPOIS do `upgrade head`, e não junto do 3b, porque precisa que
# `platform_principal` e as demais tabelas revogadas existam — num banco em
# revision anterior à 0076 o `REVOKE` morreria em "relation does not exist".
# Efeito colateral aceito: aqui o cobertor alcança tabela de `aprimora_py`
# criada por migration nova que tenha esquecido o próprio `GRANT`. Quem cobra
# essa disciplina é o CI, onde o cobertor continua rodando ANTES das migrations
# — e é o CI que gateia PR.
if [ "$SCHEMA_LOADED" = "1" ]; then
  log "Passo 4b: reparo idempotente de grants"
  ( cd "$REPO" && python -m app.cli.reparar_grants --aplicar )
fi

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
