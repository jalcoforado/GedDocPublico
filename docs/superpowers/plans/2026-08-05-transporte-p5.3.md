# Plano de implementação — Transporte P5.3

Spec: `docs/superpowers/specs/2026-08-05-transporte-p5.3-atraso-suspensao-design.md`.
Head Alembic ao começar: **`0082`**.

## Restrições globais

- pt-BR em código, comentários, docs e commits.
- Nenhuma transação nova em `utils.transacao` → `MODULO_TRANSACOES` não muda.
- Rota literal antes da paramétrica irmã; `tests/test_guarda_ordem_rotas.py` reprova.
- Tela nova precisa de `href` no mesmo PR; `__tests__/rotas-modulo.test.ts` reprova página órfã.
- Tipo em `api.ts` casa com o `response_model`: endpoint paginado → `Paginated<X>`.
- Toda guarda nova entra com a inversão feita e registrada.
- Pelo menos um teste HTTP com **usuário comum**, não super-usuário.

---

## Tarefa 1 — migration `0083`

**Descoberta que encolhe a tarefa:** `recadastramento_convocacao.situacao` **não tem CHECK** (a
`0081` só criou `ck_recadconv_vinculo_exclusivo`). Os valores são impostos pelo serviço. Portanto
aceitar `suspenso` **não exige nada no banco** — e não vou acrescentar CHECK agora, porque mudaria a
premissa da P5.1 num PR que não é sobre isso. Fica registrado como observação, não como dívida
silenciosa.

Sobra:

1. `DROP` e recriar `ck_recaddecisao_tipo` com cinco valores:
   `deferimento`, `indeferimento`, `reabertura`, `suspensao`, `reativacao`.
2. Criar `transporte_regulado.recadastramento_notificacao` conforme a spec, com boilerplate de RLS
   completo: `tenant_id` NOT NULL → `aprimora_py.tenant(id)`, índice `(tenant_id, id_convocacao)`,
   `ENABLE + FORCE ROW LEVEL SECURITY`, as duas policies com
   `NULLIF(current_setting('app.tenant_id', true), '')::int`, `GRANT` na tabela e na sequence para
   `aprimora_app`. **Sem** índice único: é log.

`downgrade()` desfaz na ordem inversa e devolve o CHECK a três valores. Validar com
`alembic upgrade head` seguido de `downgrade -1` e `upgrade head` de novo.

Commit: `feat(transporte): tabela de notificacao e tipos de decisao da P5.3 (Tarefa 1)`

---

## Tarefa 2 — service

Em `services/transporte_regulado.py`, seção P5.3.

- `SITUACAO_SUSPENSO = "suspenso"`; acrescentar `suspensao` e `reativacao` a `TIPOS_DECISAO`.
- `esta_em_atraso(conv, hoje)` — pura: `prazo < hoje and situacao in SITUACOES_ABERTAS`.
- `listar_faltosos(...)` — consulta derivando o atraso em SQL, com KPIs e dias de atraso.
- `suspender_convocacao(...)` — 409 se não estiver aberta; 409 se o prazo **não** venceu, com a data
  na mensagem; grava decisão + muda situação.
- `reativar_convocacao(...)` — 409 se não estiver suspensa; grava decisão; volta a `convocado`.
- `notificar_faltosos(...)` — lote; por item devolve `enviada` ou `sem_contato`; grava uma linha por
  notificação criada. Não derruba o lote.
- `decidir_recadastramento`: `reabertura` recusa `suspenso` com mensagem apontando `reativar`.
- **Alterar as duas mensagens de 409** (`marcar_item_recadastramento` e `decidir_recadastramento`)
  para distinguir suspensa de decidida.

Testes de service com as inversões. Commit: `feat(transporte): atraso, suspensao e notificacao em lote (P5.3, Tarefa 2)`

---

## Tarefa 3 — router + `api.ts`

Os quatro endpoints da spec, mais tipos e métodos em `frontend/lib/api.ts`. Testes HTTP, incluindo o
de usuário comum. Commit: `feat(transporte): endpoints e cliente da P5.3 (Tarefa 3)`

---

## Tarefa 4 — telas

Selo de atraso e filtro na tela de convocados; ação de notificar em lote; tela de faltosos com
`href` a partir do ciclo; Suspender/Reativar no atendimento, com parecer obrigatório.
`npx tsc --noEmit` e `npm test`. Commit: `feat(transporte): telas de faltosos e suspensao (P5.3, Tarefa 4)`

---

## Tarefa 5 — fecho

Suíte completa (`2 failed / N passed`), `CLAUDE.md` se algo mudar de regra, backlog 2.2 fechando a
P5.3. Commit: `docs(transporte): fecha a P5.3 no backlog`
