#!/usr/bin/env bash
# Carrega o seed e2e (ci/seed-e2e.sql) no Postgres da stack local.
# Idempotente (ON CONFLICT DO NOTHING) — mesmo arquivo usado no CI
# (.github/workflows/e2e-assinatura.yml).
#
# Pré-requisito: stack local de pé (docker compose up -d).
# O container do banco pode ser ajustado via env DB_CONTAINER.
set -euo pipefail
DB_CONTAINER="${DB_CONTAINER:-ged-saas-project-db-1}"
echo ">> carregando ci/seed-e2e.sql em ${DB_CONTAINER}"
docker exec -i -e PGPASSWORD=ged_password_secure_local "${DB_CONTAINER}" \
  psql -U ged_user -d ged_saas_db -v ON_ERROR_STOP=1 < ci/seed-e2e.sql
echo ">> seed e2e ok"
