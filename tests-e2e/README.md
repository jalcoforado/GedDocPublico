# Playwright smoke (Fase 9.4)

Suite mínima E2E que valida os pontos críticos do cutover:

- **routing.spec.ts** — cada rota cai no upstream correto (`X-Aprimora-Backend`)
- **auth.spec.ts** — login admin Python + PHP legacy continua vivo
- **cidadao-flow.spec.ts** — ciclo completo do cidadão + isolamento

## Como rodar

Pré-requisitos: containers `backend`, `frontend`, `nginx` e o PHP legacy
(`aprimora-protocolo`) precisam estar UP.

```bash
docker compose --profile test run --rm e2e
```

Relatório HTML em `tests-e2e/report/index.html`.

## Variáveis

- `PY_BASE` (default `http://nginx`) — entry point do Strangler
- `PHP_BASE` (default `http://protocolo`) — PHP legacy via DNS interno
