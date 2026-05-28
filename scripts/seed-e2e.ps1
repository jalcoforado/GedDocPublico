# Carrega o seed e2e (ci/seed-e2e.sql) no Postgres da stack local.
# Idempotente — mesmo arquivo usado no CI (.github/workflows/e2e-assinatura.yml).
# Pré-requisito: stack local de pé (docker compose up -d).
param([string]$DbContainer = "ged-saas-project-db-1")
Write-Host ">> carregando ci/seed-e2e.sql em $DbContainer"
Get-Content -Raw ci/seed-e2e.sql | docker exec -i -e PGPASSWORD=ged_password_secure_local $DbContainer psql -U ged_user -d ged_saas_db -v ON_ERROR_STOP=1
Write-Host ">> seed e2e ok"
