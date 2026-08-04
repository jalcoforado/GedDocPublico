# Transporte P5.1 — Ciclo de recadastramento e convocação: plano

> **Para agentes:** use `superpowers:subagent-driven-development` para executar tarefa a tarefa.

**Objetivo:** o município abre um ciclo de recadastramento, manda gerar, e vê **quem tem que vir e
quando**.

**Spec:** `docs/superpowers/specs/2026-08-04-transporte-p5-1-recadastramento-ciclo-design.md`.
Leia-a antes de qualquer tarefa — as decisões e o *porquê* de cada uma estão lá.

**Stack:** FastAPI + SQLAlchemy 2 async + Postgres (schema `transporte_regulado`), Next.js 15,
Alembic manual.

## Restrições globais

- **pt-BR** em código, comentário, docstring e commit.
- **`"ativo"` para permissionário, `"ativa"` para empresa.** Masculino e feminino. Filtrar `"ativo"`
  nos dois convoca zero empresas **sem erro nenhum**. É o defeito mais provável desta fatia.
- **Escalonamento por final do CPF/CNPJ**, nunca por `numero_permissao` ou `data_nascimento` — os
  dois são anuláveis e empresa não tem nascimento.
- **Vínculo com o regulado: duas FKs anuláveis, exatamente uma preenchida** (precedente do `Alvara`,
  que usa "ao menos uma"; aqui é "exatamente uma"). Nada de `(tipo, id)` polimórfico.
- **Boilerplate de RLS obrigatório** em tabela nova: `tenant_id` NOT NULL → `aprimora_py.tenant(id)`,
  índice `(tenant_id, …)`, `ENABLE + FORCE ROW LEVEL SECURITY`, as duas policies com
  `NULLIF(current_setting('app.tenant_id', true), '')::int`, `GRANT` na tabela e na sequence para
  `aprimora_app`. Molde pronto em `0071_pagamentos_checklist_documental.py` (funções `_enable_rls` e
  `_grant`). Os três detalhes que já custaram um módulo inteiro estão no `CLAUDE.md`.
- **Rota de segmento literal antes da paramétrica irmã.** `test_guarda_ordem_rotas.py` varre a app,
  mas o defeito já ocorreu três vezes neste mesmo arquivo.
- **Endpoint paginado → `request<Paginated<X>>` no `api.ts`.** `test_guarda_contrato_paginado.py`
  reprova o contrário.
- **Tela nova nasce em `app/(app)/m/transporte/`.** `__tests__/rotas-modulo.test.ts` reprova fora
  disso. **Sem mudança no nginx** — `/m` já está na regex.
- **Busca e paginação no servidor.** A fatia anterior consertou exatamente o oposto.
- Verde = `2 failed / N passed` com as duas pré-existentes de sempre
  (`test_jwt_compat::test_emitted_token_has_required_claims`,
  `test_pr5a_dashboard_servicos::test_http_dashboard_com_perm_acessa`). Baseline antes desta fatia:
  **1046 passed**.

---

### Tarefa 1: migration `0081` — as duas tabelas

**Arquivos:** criar `backend/alembic/versions/0081_transporte_recadastramento.py`; modificar
`backend/app/models/transporte_regulado.py`.

- [ ] **Confirme o head** com `docker exec aprimora-py-backend alembic heads`. Deve ser `0080`; se
      não for, construa sobre o real. Head único.
- [ ] `recadastramento_ciclo`: `nome` `String(120)`, `data_inicio`/`data_fim` `Date`,
      `criterio_escalonamento` `String(30)`, `situacao` `String(20)` default `rascunho`,
      `observacoes` `Text`, mais `criado_em`/`atualizado_em`/`excluido`.
- [ ] Índice único parcial `(tenant_id, nome) WHERE excluido = false`.
- [ ] `recadastramento_convocacao`: `id_ciclo` FK NOT NULL; `id_permissionario` e `id_empresa` FK
      **anuláveis**; `prazo` e `prazo_original` `Date` NOT NULL; `ajuste_justificativa` `Text`
      nullable; `ajustado_por` FK `utils.usuario.id` nullable; `ajustado_em` `DateTime` nullable;
      `situacao` `String(20)` default `convocado`.
- [ ] **Dois índices únicos parciais**: `(id_ciclo, id_permissionario) WHERE excluido = false AND
      id_permissionario IS NOT NULL` e o equivalente para `id_empresa`. São eles que tornam a
      geração idempotente **no banco**, não só no código — sem isso, duas execuções concorrentes
      duplicam.
- [ ] **CHECK de vínculo exclusivo** no banco:
      `(id_permissionario IS NOT NULL) <> (id_empresa IS NOT NULL)`. O service também valida, mas a
      constraint é a que não pode ser contornada por caminho novo.
- [ ] RLS + grants nas duas, pelo molde da `0071`.
- [ ] `downgrade()` derrubando as duas na ordem inversa.
- [ ] Modelos `RecadastramentoCiclo` e `RecadastramentoConvocacao`, reexportados em
      `models/__init__.py`.
- [ ] Rodar `alembic upgrade head`, depois `downgrade -1`, depois `upgrade head` de novo —
      reversibilidade exercitada, não presumida.
- [ ] Conferir no catálogo que as duas policies existem e que `aprimora_app` tem os grants.
- [ ] Commit.

### Tarefa 2: service — ciclo, escalonamento e geração

**Arquivos:** modificar `backend/app/services/transporte_regulado.py`; criar
`backend/tests/test_transporte_p5_recadastramento.py`.

- [ ] CRUD do ciclo: criar, obter, listar (paginado, com `q` por nome), atualizar, excluir
      (soft-delete). Validar `data_inicio <= data_fim` e `criterio_escalonamento` no conjunto
      conhecido.
- [ ] `prazo_do_regulado(documento, ciclo)` — pura, testável sem banco. Último **caractere** de
      `cpf`/`cnpj`; se não for dígito, faixa final (`data_fim`). Dez faixas iguais em
      `[data_inicio, data_fim]`; o prazo é o fim da faixa. `sem_escalonamento` devolve `data_fim`.
- [ ] `gerar_convocacoes(ciclo_id)` — idempotente. Busca permissionários `situacao == "ativo"` e
      empresas `situacao == "ativa"`, não excluídos, **sem convocação naquele ciclo**. Devolve
      `{criadas, ja_existentes}`. Recusa (409) ciclo `encerrado`; permite `rascunho`.
- [ ] `ajustar_prazo(convocacao_id, prazo, justificativa)` — justificativa obrigatória (400 sem
      ela), prazo dentro da janela (400 fora), 409 em ciclo encerrado. Grava `ajustado_por`,
      `ajustado_em`, preserva `prazo_original`. Prazo no passado é **permitido**.
- [ ] Listagem de convocações do ciclo, paginada, com `q` (nome do permissionário ou razão social
      da empresa) e filtro por tipo de regulado. **Condições montadas uma vez** e aplicadas à
      consulta e à contagem — duplicar é como `total` passa a divergir de `items`.
- [ ] Testes conforme a tabela da §6 da spec. **Cada negativa com controle positivo na mesma
      sessão.**
- [ ] **O teste do masculino/feminino é o mais importante:** um permissionário `ativo` e uma empresa
      `ativa` no mesmo tenant; a geração tem de convocar **os dois**. Um teste que só olhe o total
      passaria com o filtro errado.
- [ ] **Prova por inversão obrigatória**, no mínimo em três: troque o filtro de empresa para
      `"ativo"` e veja vermelho; remova o índice único e rode a geração duas vezes; tire a
      obrigatoriedade da justificativa. Desfaça cada uma e confirme verde.
- [ ] Commit.

### Tarefa 3: router, schemas e cliente

**Arquivos:** modificar `backend/app/routers/transporte_regulado.py`,
`backend/app/schemas/transporte_regulado.py`, `backend/app/main.py` (se criar router novo),
`frontend/lib/api.ts`.

- [ ] Schemas `CicloCreate/Update/Out` e `ConvocacaoOut`, `ConvocacaoAjustePrazo`. `tenant_id`,
      `id`, `excluido`, `prazo_original`, `ajustado_*` **nunca** em schema de entrada.
- [ ] Router com prefixo `/transporte-regulado/recadastramento`. **Rotas literais antes da
      paramétrica**: `/ciclos/{id}/gerar-convocacoes` e `/convocacoes/{id}/prazo` precisam vir na
      ordem certa em relação a `/ciclos/{id}`.
- [ ] GETs com `require_modulo("transporte")`; escritas com
      `require_permission("transporte_regulado", "inserir"|"atualizar"|"excluir")`. **Sem
      `"visualizar"`** — não é uma `Action` válida e produz 500 para usuário comum.
- [ ] Registrar em `main.py` com `prefix="/api/v2"` se for router novo.
- [ ] `api.ts`: tipos e métodos, listagens como `request<Paginated<X>>`.
- [ ] **Teste HTTP com usuário comum** (não-SU), padrão de
      `_cria_usuario_comum_transporte`. Lembre que o tenant precisa contratar `transporte`, senão o
      gate barra antes e o teste não chega onde importa.
- [ ] `npx tsc --noEmit` limpo.
- [ ] Commit.

### Tarefa 4: telas

**Arquivos:** criar `frontend/app/(app)/m/transporte/recadastramento/page.tsx` e
`.../recadastramento/[id]/page.tsx`; modificar `frontend/lib/menus/transporte.ts`,
`frontend/lib/transporte-hub.ts`, `frontend/__tests__/menus.test.tsx`.

- [ ] Lista de ciclos com criar/editar; badge de situação.
- [ ] Detalhe: cabeçalho do ciclo, botão **Gerar convocações** mostrando `criadas`/`já existentes`,
      tabela de convocados com nome, tipo, prazo e marca de ajustado.
- [ ] **Busca server-side com debounce**, `q` indo para a API. Estado vazio distinguindo "nenhuma
      convocação" de "a busca não achou" — o segundo não oferece ação de criar.
- [ ] Diálogo de ajuste de prazo com justificativa obrigatória no formulário.
- [ ] Item no menu de transporte com `perm: "transporte_regulado"`, e `PERMISSOES_ESPERADAS`
      atualizada em `__tests__/menus.test.tsx`.
- [ ] Card no hub de transporte (`lib/transporte-hub.ts`), com href `/m/transporte/recadastramento`.
      `__tests__/transporte-hub.test.tsx` exige que card pronto esteja no menu do módulo.
- [ ] `npx tsc --noEmit` limpo; `npm test` verde.
- [ ] Commit.

### Tarefa 5: fecho

- [ ] Suíte completa do backend; a diferença sobre 1046 tem de ser exatamente o número de testes
      novos, e as duas falhas as de sempre.
- [ ] Atualizar o item 2.2 do `docs/BACKLOG-PENDENCIAS.md`: P5 deixa de ser "não implementado" e
      passa a "P5.1 entregue; P5.2 e P5.3 abertas".
- [ ] `CLAUDE.md` só se algo desta fatia mudar regra geral — não force.
- [ ] Commit.

## Critério de aceite

Município cria ciclo, gera convocações, vê a lista com prazos escalonados, ajusta um prazo com
justificativa e a alteração fica registrada com autor e data. Segunda geração não duplica e alcança
quem entrou depois. Empresa aparece na lista junto com permissionário.
