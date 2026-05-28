#!/usr/bin/env bash
# E2E de assinatura (Playwright) via serviço `e2e` do docker-compose.
#
# Pré-requisitos:
#   - Docker + docker compose
#   - Stack de pé:            docker compose up -d
#   - Seed Sobral carregado:  admin@local.test / admin123, catálogos
#                             (id_assunto=1, id_manifestante=1, id_unidade=3,
#                              id_especie=2) e usar_nup_federal no tenant.
#
# Uso:
#   scripts/e2e-assinatura.sh                      # specs/assinatura-v2.spec.ts
#   scripts/e2e-assinatura.sh specs/balcao-flow.spec.ts
#
# O serviço `e2e` (profile "test") roda na rede do compose com PY_BASE=http://nginx.
set -euo pipefail
SPEC="${1:-specs/assinatura-v2.spec.ts}"
echo ">> e2e: ${SPEC} (serviço compose 'e2e', PY_BASE=http://nginx)"
docker compose --profile test run --rm e2e npx playwright test "${SPEC}"
