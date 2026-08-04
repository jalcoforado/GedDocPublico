# Transporte P5.2 — Atendimento e fechamento: plano

**Objetivo:** o servidor abre um convocado, confere os documentos, vê a situação das vistorias, e
**defere ou indefere com parecer**.

**Spec:** `docs/superpowers/specs/2026-08-04-transporte-p5-2-recadastramento-atendimento-design.md`.
Leia-a antes de qualquer tarefa — as decisões (D6–D9), as duas assunções (A1, A2) e o *porquê* de
cada uma estão lá.

**Stack:** FastAPI + SQLAlchemy 2 async + Postgres (schema `transporte_regulado`), Next.js 15,
Alembic manual.

## Restrições globais

- **pt-BR** em código, comentário, docstring e commit.
- **`Empresa.situacao` é feminino (`ativa`); permissionário e VEÍCULO são masculinos (`ativo`).**
  A P5.2 volta a filtrar regulados por tipo. Constantes já existem em
  `services/transporte_regulado.py`: `SITUACAO_PERMISSIONARIO_ATIVO`, `SITUACAO_EMPRESA_ATIVA`.
- **`condicional` NÃO é `aprovado`.** A amarra da vistoria exige `aprovado`.
- **`{"campo": null}` chega em todo schema `Update`** — todo campo é opcional. Em coluna `NOT NULL`
  isso vira HTTP 500 num erro de entrada. Molde do descarte: `NAO_ANULAVEIS_DO_CICLO` +
  o laço em `atualizar_ciclo`. **Vale para `recadastramento_item`.**
- **Id de FK nunca cravado em teste.** O CI roda em banco limpo; `usuario_id=1` estourou
  `ForeignKeyViolationError` na P5.1. Use `_um_usuario()`, que já existe em
  `tests/test_transporte_p5_recadastramento.py` (copie — os arquivos são independentes).
- **`provisionar_tenant` JÁ contrata os módulos iniciais.** Cenário "sem módulo" precisa
  descontratar de propósito.
- **Boilerplate de RLS obrigatório** em tabela nova. Molde pronto na `0081` (funções `_enable_rls` e
  `_grant`). Os três detalhes que já custaram um módulo estão no `CLAUDE.md`.
- **Rota de segmento literal antes da paramétrica irmã.** `test_guarda_ordem_rotas.py` varre a app.
- **Endpoint paginado → `request<Paginated<X>>` no `api.ts`.** `test_guarda_contrato_paginado.py`
  reprova o contrário.
- **Tela nova nasce em `app/(app)/m/transporte/`.** `__tests__/rotas-modulo.test.ts` reprova fora
  disso. **Sem mudança no nginx.**
- Verde = `2 failed / N passed` com as duas pré-existentes de sempre
  (`test_jwt_compat::test_emitted_token_has_required_claims`,
  `test_pr5a_dashboard_servicos::test_http_dashboard_com_perm_acessa`). **Baseline antes desta
  fatia: 1105 passed.** No CI as duas passam e o total é 1107 + 4 da guarda do portão.

---

### Tarefa 1: migration `0082` — as três tabelas

**Arquivos:** criar `backend/alembic/versions/0082_transporte_recadastramento_atendimento.py`;
modificar `backend/app/models/transporte_regulado.py` e `backend/app/models/__init__.py`.

- [ ] **Confirme o head** com `docker exec aprimora-py-backend alembic heads`. Deve ser `0081`.
- [ ] `recadastramento_item`: `descricao` `String(200)`, `aplica_a` `String(20)`, `obrigatorio`
      `Boolean` default true, `ordem` `Integer` default 0, `ativo` `Boolean` default true, mais
      `criado_em`/`atualizado_em`/`excluido`.
- [ ] `CHECK` em `aplica_a IN ('permissionario','empresa','ambos')` — o serviço também valida, mas a
      constraint alcança o script de correção.
- [ ] Índice único parcial `(tenant_id, descricao) WHERE excluido = false`.
- [ ] `recadastramento_marca`: `id_convocacao` FK NOT NULL, `id_item` FK NOT NULL, `marcado`
      `Boolean` NOT NULL, `observacao` `String(255)` nullable, `id_usuario` FK `utils.usuario`
      nullable, `criado_em`. **SEM índice único em `(id_convocacao, id_item)`** — seria o oposto de
      append-only. Índice de leitura `(tenant_id, id_convocacao)`.
- [ ] `recadastramento_decisao`: `id_convocacao` FK NOT NULL, `tipo` `String(20)` NOT NULL com
      `CHECK IN ('deferimento','indeferimento','reabertura')`, `parecer` `Text` NOT NULL,
      `id_usuario` FK **NOT NULL** (decisão sem autor não é decisão), `criado_em`. Índice
      `(tenant_id, id_convocacao)`.
- [ ] RLS + grants nas três, pelo molde da `0081`.
- [ ] `downgrade()` derrubando as três na ordem inversa.
- [ ] Modelos reexportados em `models/__init__.py` **e em `__all__`**.
- [ ] `alembic upgrade head` → `downgrade -1` → `upgrade head`: reversibilidade exercitada.
- [ ] **Conferir no catálogo** que as duas policies existem em cada tabela, que `relforcerowsecurity`
      é true e que `aprimora_app` tem os grants. Não presumir.
- [ ] Commit.

### Tarefa 2: service — catálogo, marcação e amarra da vistoria

**Arquivos:** modificar `backend/app/services/transporte_regulado.py` e
`backend/app/schemas/transporte_regulado.py`; criar
`backend/tests/test_transporte_p5_2_atendimento.py`.

- [ ] CRUD do catálogo: criar, obter, listar (paginado, `q` por descrição, filtro `ativo`),
      atualizar, excluir. **Descarte do `null` explícito** nas colunas NOT NULL, como
      `atualizar_ciclo` faz.
- [ ] `itens_aplicaveis(tenant_id, tipo_regulado)` — itens `ativo`, não excluídos, com
      `aplica_a in (tipo, "ambos")`, ordenados por `ordem, id`.
- [ ] `marcar_item(convocacao_id, item_id, marcado, observacao, usuario_id)` — **insere** linha
      nova, nunca atualiza. Recusa (409) ciclo encerrado e convocação já decidida. Passa a
      convocação para `em_analise` quando ela estiver em `convocado`.
- [ ] `estado_do_checklist(convocacao_id)` — para cada item aplicável, a marca **mais recente**
      (`ORDER BY criado_em DESC, id DESC` — desempate por `id` porque duas marcas no mesmo segundo
      são possíveis). Devolve item + `marcado` + `observacao` + quem/quando.
- [ ] `situacao_vistorias(tenant_id, convocacao)` — devolve
      `{veiculos_ativos, pendentes, satisfeita}`, conforme §4 da spec. **Três campos, não um
      booleano:** é o que permite a tela distinguir A1 de "todos em dia".
- [ ] Testes conforme a tabela da §6 da spec.
- [ ] **Prova por inversão obrigatória** em pelo menos três: inverta o filtro de `aplica_a`; inverta
      a ordenação da marca mais recente; aceite `condicional` como aprovado. Desfaça cada uma e
      confirme verde.
- [ ] Commit.

### Tarefa 3: service — decisão, e o router inteiro

**Arquivos:** modificar `services/`, `schemas/`, `routers/transporte_regulado.py`,
`frontend/lib/api.ts`; estender o arquivo de testes da Tarefa 2.

- [ ] `pode_deferir(convocacao_id)` — devolve `{pode, itens_pendentes, vistorias}`. A tela precisa do
      motivo, não só do booleano.
- [ ] `decidir(convocacao_id, tipo, parecer, usuario_id)` — **deferir exige completude (409 sem
      ela); indeferir não.** Parecer obrigatório nos dois (400 sem). Insere em
      `recadastramento_decisao` e atualiza `convocacao.situacao`.
- [ ] `reabrir(convocacao_id, parecer, usuario_id)` — só de `deferido`/`indeferido`; volta para
      `em_analise`; registra `tipo="reabertura"`. Preserva as decisões anteriores.
- [ ] Router: catálogo sob `/transporte-regulado/recadastramento/itens`; atendimento sob
      `/recadastramento/convocacoes/{id}/checklist`, `.../marcar`, `.../decisao`, `.../reabrir`.
      **`/itens` é literal e precisa vir antes de qualquer paramétrica irmã.**
- [ ] Leitura com `require_permission("transporte_regulado")`; escrita com
      `"inserir"|"atualizar"|"excluir"`. **Nunca `"visualizar"`** — não é `Action` válida e vira 500
      para usuário comum.
- [ ] `api.ts`: tipos e métodos; listagens como `request<Paginated<X>>`.
- [ ] **Teste HTTP com usuário comum** percorrendo o rito: marcar → tentar deferir incompleto (409)
      → completar → deferir (200) → reabrir (200). Um teste que só faça o caminho feliz não
      exercita a assimetria.
- [ ] `npx tsc --noEmit` limpo.
- [ ] Commit.

### Tarefa 4: telas

**Arquivos:** criar `frontend/app/(app)/m/transporte/recadastramento/itens/page.tsx` e
`.../recadastramento/[id]/convocacao/[convocacaoId]/page.tsx`; modificar
`recadastramento/[id]/page.tsx` (link para o atendimento), `lib/menus/transporte.ts` se necessário,
`__tests__/rotas-modulo.test.ts`.

- [ ] Catálogo: CRUD com `aplica_a`, `obrigatorio`, `ordem`, `ativo`. Busca server-side.
- [ ] Atendimento: checklist com observação por item; painel de vistorias com os **três estados
      distintos** (todos em dia / nenhum veículo cadastrado / lista de pendentes).
- [ ] **Deferir desabilitado com o motivo ao lado; Indeferir nunca desabilita.**
- [ ] Diálogo de parecer, obrigatório, nos três atos.
- [ ] Histórico de decisões visível na tela — é o que torna a reabertura auditável.
- [ ] `npx tsc --noEmit` limpo; `npm test` verde (as guardas de menu/hub reprovam href esquecido).
- [ ] Commit.

### Tarefa 5: fecho

- [ ] Suíte completa do backend; a diferença sobre 1105 tem de ser exatamente o número de testes
      novos, e as duas falhas as de sempre.
- [ ] Atualizar o item 2.2 do `docs/BACKLOG-PENDENCIAS.md`: P5.2 entregue, P5.3 aberta.
- [ ] `CLAUDE.md` só se algo mudar regra geral — não force.
- [ ] Commit. **Um push só, ao fim da fatia.**

## Critério de aceite

O servidor abre um convocado, marca os documentos, vê que um veículo está sem vistoria válida e o
botão Deferir explica por quê. Indefere com parecer; a decisão aparece no histórico com autor e
data. Reabre, completa o que faltava, e defere. Item que se aplica só a empresa não aparece na
ficha de um permissionário.
