# P6 — pontos e vagas: plano de implementação

Spec: `docs/superpowers/specs/2026-08-05-transporte-p6-pontos-design.md`.

Cinco tarefas, um commit cada, na ordem. Cada uma fecha com a sua verificação; nenhuma depende de
tarefa posterior.

---

## Tarefa 1 — migration 0084 e models

**Arquivos:** `backend/alembic/versions/0084_transporte_pontos.py`,
`backend/app/models/transporte_regulado.py`, `backend/app/models/__init__.py`.

Duas tabelas com o boilerplate completo de RLS: `ENABLE` **+** `FORCE`, as duas policies com
`NULLIF(current_setting('app.tenant_id', true), '')::int`, `GRANT` na tabela e na sequence para
`aprimora_app`. Sem grant para `aprimora_worker` — nenhuma task escreve aqui.

Os dois índices únicos parciais da spec, e o `CHECK (vagas_total > 0)` / `CHECK (numero_vaga > 0)`.

`downgrade()` desfaz na ordem inversa: ocupação antes de ponto.

**Verificação:** `alembic upgrade head` e `downgrade -1` e `upgrade head` de novo; `alembic heads`
com head único.

---

## Tarefa 2 — service e testes

**Arquivos:** `backend/app/services/transporte_regulado.py`,
`backend/tests/test_transporte_p6_pontos.py`.

`criar_ponto`, `listar_pontos`, `obter_ponto`, `atualizar_ponto`, `excluir_ponto`,
`mapa_de_vagas`, `listar_ocupacoes`, `ocupar_vaga`, `liberar_vaga`.

Regras, todas com teste: faixa da vaga, vaga ocupada → 409, permissionário já lotado → 409 **com o
ponto atual na mensagem**, redução de `vagas_total` abaixo do maior ocupado → 409, exclusão de ponto
ocupado → 409, inativação permitida, isolamento cross-tenant, e o teste do não-gate (alvará para
permissionário sem vaga continua emitindo).

**A prova do índice:** um teste que insere a segunda ocupação da mesma vaga **direto pelo banco**,
sem passar pelo serviço, e espera `IntegrityError`. Sem ele, a checagem do serviço poderia ser toda
a garantia sem ninguém perceber.

**Verificação:** `pytest tests/test_transporte_p6_pontos.py -v` verde, e cada guarda nova invertida
uma vez.

---

## Tarefa 3 — router e cliente

**Arquivos:** `backend/app/routers/transporte_regulado.py`, `backend/app/schemas/transporte_regulado.py`,
`backend/app/main.py`, `frontend/lib/api.ts`.

Nove rotas da spec em `pontos_router`. **Registrar em `main.py`** com `prefix="/api/v2"`.

Tipos e métodos em `api.ts`: endpoint paginado → `request<Paginated<X>>`, tela consumindo `.items`.
Nada de desembrulhar dentro do `api.ts`.

**Verificação:** `pytest tests/test_guarda_ordem_rotas.py tests/test_guarda_contrato_paginado.py`
com `CI=1`; um teste HTTP com **usuário comum**, não SU.

---

## Tarefa 4 — telas

**Arquivos:** `frontend/app/(app)/m/transporte/pontos/page.tsx`,
`frontend/app/(app)/m/transporte/pontos/[id]/page.tsx`, hub do transporte, `lib/menus/transporte.ts`.

Lista com busca/filtros e coluna `ocupadas/total`; detalhe com o mapa de vagas em grade e o
histórico.

**O link a partir do hub entra neste mesmo commit** — a guarda de página órfã reprova, e é ela que
existe para impedir a tela pronta e inalcançável que a P2/P4 teve por meses.

**Verificação:** `npx tsc --noEmit` limpo e `npm test` verde, rodados de dentro de `frontend/`.

---

## Tarefa 5 — fecho

Suíte completa (`2 failed, N passed` — as duas conhecidas), backlog fechando a P6 na seção 2.2, e
`CLAUDE.md` **só se alguma regra do repositório mudar**. Não mudou até onde a spec alcança.

Commit: `docs(transporte): fecha a P6 no backlog`.
