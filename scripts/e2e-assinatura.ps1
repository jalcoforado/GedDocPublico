# E2E de assinatura (Playwright) via serviço `e2e` do docker-compose.
#
# Pré-requisitos:
#   - Docker + docker compose
#   - Stack de pé:            docker compose up -d
#   - Seed Sobral carregado:  admin@local.test / admin123 + catálogos
#                             (id_assunto=1, id_manifestante=1, id_unidade=3, id_especie=2)
#
# Uso:
#   scripts\e2e-assinatura.ps1
#   scripts\e2e-assinatura.ps1 -Spec specs/balcao-flow.spec.ts
param([string]$Spec = "specs/assinatura-v2.spec.ts", [switch]$NoSeed)
if (-not $NoSeed) { & "$PSScriptRoot/seed-e2e.ps1" }
Write-Host ">> e2e: $Spec (serviço compose 'e2e', PY_BASE=http://nginx)"
docker compose --profile test run --rm e2e npx playwright test $Spec
