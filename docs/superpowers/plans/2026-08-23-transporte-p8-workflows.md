# Transporte P8 — Workflows avançados: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Os três fluxos do transporte (ocorrências, alvará, recadastramento) passam a ser comandados pelo motor BPM via instância polimórfica, com fachadas preservando o contrato externo atual.

**Architecture:** `workflow_instance` ganha `(entidade_tipo, entidade_id)`; o engine ganha um registro de providers de contexto por tipo; cada ato de transporte vira fachada que muta a `situacao` (cache) na mesma sessão e delega a transição ao engine. Definições-semente espelham as máquinas atuais — dia 1 idêntico ao dia 0.

**Tech Stack:** FastAPI + SQLAlchemy 2 async, Alembic manual, simpleeval (DSL), Next.js 15 (painel), vitest/pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-transporte-p8-workflows-design.md`

## Global Constraints

- pt-BR em código, comentários, docs e commits.
- Migrations à mão, head único, downgrade reverte na ordem inversa; boilerplate RLS completo em tabela nova (nenhuma tabela nova neste plano — só ALTERs, que herdam RLS/grants).
- **Toda task backend re-roda as 3 guardas**: `tests/test_guarda_ordem_rotas.py`, `tests/test_guarda_modularizacao.py`, `tests/test_guarda_link_url.py` — e o relatório traz evidência RED do TDD.
- **Princípio reitor da fase**: as suítes existentes de P5/P6/P7/Fase C passam **sem edição semântica** (ajuste de substring de mensagem é permitido e deve ser listado no report; mudança de código HTTP ou de semântica é defeito do plano — escalar).
- `tenant_id` sempre do caller; carga por id filtra tenant + `excluido`; 404 cross-tenant; transição ilegal = 409; permissão = 403.
- Vocabulário: convocação `suspenso` (masc.), empresa `suspensa`/`ativa` (fem.) — asserções com valores exatos.
- Testes: e-mails `.test`, slugs prefixados + `uuid4().hex[:8]`, cleanup no teardown, nunca assumir banco vazio.
- Comando de teste backend: `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest <alvo> -q`. Frontend: `cd frontend; npx vitest run <alvo>` e `npx tsc --noEmit`.
- Engine: `executar_transicao` COMMITA internamente. Fachada muta a entidade **antes** de chamá-lo (mesma sessão) — o commit do engine persiste os dois atomicamente; exceção antes do commit deixa tudo pendente e o handler responde 409 sem efeito.
- Auto-encaminhamento (`_auto_encaminhar`) e qualquer acesso a `Processo` no engine ficam atrás de `if instance.entidade_tipo == "processo"`.

---

### Task 1: Migration 0095 + modelo — instância polimórfica

**Files:**
- Create: `backend/alembic/versions/0095_workflow_instance_polimorfica.py`
- Modify: `backend/app/models/workflow.py` (WorkflowInstance)
- Test: `backend/tests/test_transporte_p8_workflows.py` (novo arquivo; seção migration)

**Interfaces:**
- Produces: colunas `workflow_instance.entidade_tipo` (varchar(30) NOT NULL, CHECK in `('processo','ocorrencia','alvara','convocacao')`), `entidade_id` (int NOT NULL); `id_processo` NULLABLE; índice `ix_workflow_instance_entidade (tenant_id, entidade_tipo, entidade_id)`; índice único parcial `uq_workflow_instance_ativa_entidade (tenant_id, entidade_tipo, entidade_id) WHERE ativa`.
- Model: `WorkflowInstance.entidade_tipo: Mapped[str]`, `entidade_id: Mapped[int]`, `id_processo: Mapped[int | None]`.

- [ ] **Step 1: teste RED da migration** — em `test_transporte_p8_workflows.py`, teste que (via `admin_session`) insere `workflow_instance` com `entidade_tipo='ocorrencia'`, `entidade_id=<id qualquer>`, `id_processo=None` e lê de volta; e teste de unicidade por inversão: segunda instância **ativa** do mesmo `(tenant, tipo, id)` → `IntegrityError`; terceira com `ativa=false` → passa. Rodar: FALHA (coluna inexistente).
- [ ] **Step 2: migration 0095** — `down_revision` no head atual (conferir `alembic heads`). `upgrade()`:
  1. `ADD COLUMN entidade_tipo varchar(30)`; `ADD COLUMN entidade_id integer`;
  2. backfill `UPDATE aprimora_py.workflow_instance SET entidade_tipo='processo', entidade_id=id_processo`;
  3. `ALTER COLUMN entidade_tipo SET NOT NULL`, `ALTER COLUMN entidade_id SET NOT NULL`, CHECK `ck_workflow_instance_entidade_tipo`;
  4. `ALTER COLUMN id_processo DROP NOT NULL`;
  5. índices acima (o único parcial novo NÃO substitui o antigo por `id_processo`, se existir — deixá-lo; documentar no docstring).
  `downgrade()`: ordem inversa; antes de restaurar o NOT NULL de `id_processo`, `SELECT count(*) WHERE entidade_tipo != 'processo'` e `RAISE`/`Exception` se > 0 (falha alto, padrão 0094). ADD COLUMN herda RLS/grants — não repetir.
- [ ] **Step 3: modelo** — atualizar `WorkflowInstance` (3 campos). `alembic upgrade head` no container; rodar o teste do Step 1: PASSA. `alembic downgrade -1` + `upgrade head` para provar reversibilidade.
- [ ] **Step 4: varredura RLS + guardas** — `pytest tests/test_rls_papeis_minimos.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py tests/test_guarda_link_url.py -q` verdes. Regressão do motor: `pytest tests/ -k workflow -q` verde (caminhos de processo intactos).
- [ ] **Step 5: commit** — `feat(workflow): instancia polimorfica (entidade_tipo/entidade_id) — P8 D1`.

---

### Task 2: Engine generalizado — providers de contexto por tipo

**Files:**
- Modify: `backend/app/services/workflow_engine.py`
- Create: `backend/app/services/transporte_workflow.py` (providers + sementes; fachadas entram nas Tasks 3–5)
- Test: `backend/tests/test_transporte_p8_workflows.py` (seção engine)

**Interfaces:**
- Produces em `workflow_engine`:
  - `CONTEXT_PROVIDERS: dict[str, Callable[[AsyncSession, WorkflowInstance], Awaitable[dict[str, Any]]]]` com registro via `register_context_provider(tipo, fn)`;
  - `compute_contexto` despacha pelo `instance.entidade_tipo` (provider `processo` = código atual extraído para `_contexto_processo`); tipo sem provider → `WorkflowEngineError`;
  - `iniciar(db, *, tenant_id, id_workflow_definition, entidade_tipo, entidade_id, usuario_id, estado_inicial: str | None = None)` — `id_processo` preenchido quando tipo=`processo` (e a validação `_load_processo` só nesse caso); `estado_inicial` opcional sobrepõe o do DSL **se existir nos estados** (para a instanciação lazy no estado corrente da entidade; inexistente → erro); conflito de instância ativa checado pelo par polimórfico;
  - `executar_transicao`: `_auto_encaminhar` e auto-resolve de SLA continuam; o bloco de unidade responsável roda só com `entidade_tipo == "processo"`.
- Produces em `transporte_workflow`: `registrar_providers()` chamado no import de `main.py` (ou no `__init__` dos services — seguir o padrão de registro mais simples que funcione com o teste); providers:
  - `ocorrencia`: `dias_aberta`, `origem`, `id_tipo`, `tem_alvo`, `qtd_andamentos`, `situacao_atual`, `estado_atual`, `estado_anterior`;
  - `alvara`: `dias_para_vencer` (9999 sem validade; negativo vencido), `tipo_servico`, `eh_renovacao`, `titular_suspenso` (reusa `_titular_tem_convocacao_suspensa` — importar do service, tornando-a pública `titular_tem_convocacao_suspensa` com rename mecânico e alias antigo mantido? NÃO: rename simples + atualizar os 2 call sites, padrão da Task 4 da Fase C);
  - `convocacao`: `dias_para_prazo`, `situacao_atual`, `checklist_completo`, `tem_vistoria_aprovada` (`condicional` NÃO conta), `estado_atual`, `estado_anterior`.
  - `estado_atual`/`estado_anterior` são adicionados pelo engine após o provider (comuns a todo tipo) — provider não os duplica.
- Compatibilidade: chamadas existentes de `iniciar(id_processo=...)` em `workflow_integration.py`/routers são atualizadas para a assinatura nova no MESMO commit.

- [ ] **Step 1: testes RED** — (a) `compute_contexto` de instância `entidade_tipo='ocorrencia'` devolve as chaves do provider sem tocar em `Processo`; (b) `iniciar` polimórfico com `estado_inicial='em_apuracao'` cria instância nesse estado; (c) `iniciar` com `estado_inicial` inexistente no DSL → `WorkflowEngineError`; (d) `executar_transicao` numa instância de ocorrência com DSL mínimo transiciona e loga sem tentar carregar processo. Helpers de fixture criam definição de teste com DSL inline. Rodar: FALHA.
- [ ] **Step 2: implementar** — extrair `_contexto_processo`, criar o registry, generalizar `iniciar`/`executar_transicao`/`transicoes_disponiveis` conforme interface; criar `transporte_workflow.py` com os 3 providers e `registrar_providers()`; atualizar call sites de `iniciar`.
- [ ] **Step 3: beat de SLA seguro para tipo novo** — ler `verificar_sla_workflows` (task Celery): todo acesso a `Processo`/link de processo fica atrás de `entidade_tipo == "processo"`; alerta de SLA para instância de transporte é criado normalmente e a notificação (se houver) usa link `/m/transporte/...` por tipo — teste: instância de ocorrência com `sla_dias` estourado gera `WorkflowSlaAlerta` sem erro (RED antes do guard, VERDE depois).
- [ ] **Step 4: verde + regressão** — testes dos Steps 1 e 3 PASSAM; `pytest tests/ -k workflow -q` verde (regressão do motor de processo é a prova de que a extração não mudou comportamento).
- [ ] **Step 5: guardas + commit** — 3 guardas verdes; `feat(workflow): engine com providers de contexto por entidade — P8 D1`.

---

### Task 3: Ocorrências — semente + fachadas (piloto)

**Files:**
- Create: `backend/alembic/versions/0096_solta_checks_situacao_workflow.py`
- Modify: `backend/app/services/transporte_workflow.py` (sementes + helpers de fachada)
- Modify: `backend/app/services/transporte_regulado.py` (`registrar_ocorrencia`, `iniciar_apuracao`, `decidir_ocorrencia`)
- Modify: `backend/app/cli/seed_bootstrap.py` (seed das definições)
- Test: `backend/tests/test_transporte_p8_workflows.py` (seção ocorrências)

**Migration 0096** (spec §Situação↔estado): dropa os CHECKs de `situacao` de
`transporte_regulado.ocorrencia` e `transporte_regulado.recadastramento_convocacao` **se
existirem** (conferir nomes reais com `\d` no psql; o da ocorrência existe — "o CHECK do banco é a
rede" da P7 passa a ser o DSL). Downgrade recria os CHECKs originais e **falha alto** se houver
valor fora do conjunto original (estado novo de tenant impede o downgrade — documentar no
docstring). O CHECK de `situacao` de permissionário/empresa/vistoria NÃO é tocado — esses fluxos
não entram no workflow.

**Interfaces:**
- `SEMENTES: dict[str, dict]` em `transporte_workflow.py` — DSL por slug. `transporte-ocorrencia`:

```python
{
    "estado_inicial": "registrada",
    "estados": [
        {"slug": "registrada", "label": "Registrada"},
        {"slug": "em_apuracao", "label": "Em apuração"},
        {"slug": "procedente", "label": "Procedente", "final": True},
        {"slug": "improcedente", "label": "Improcedente", "final": True},
        {"slug": "arquivada", "label": "Arquivada", "final": True},
    ],
    "transicoes": [
        {"de": "registrada", "para": "em_apuracao", "label": "iniciar_apuracao"},
        {"de": "em_apuracao", "para": "procedente", "label": "decidir_procedente"},
        {"de": "em_apuracao", "para": "improcedente", "label": "decidir_improcedente"},
        {"de": "em_apuracao", "para": "arquivada", "label": "arquivar"},
    ],
}
```

- Helpers de fachada (usados pelas Tasks 3–5):
  - `async def obter_definicao(db, *, tenant_id, slug) -> WorkflowDefinition` — versão ativa; **se não existir, cria lazy** a partir de `SEMENTES[slug]` (versao=1, ativo=True) e commita via flush na sessão corrente;
  - `async def obter_ou_criar_instancia(db, *, tenant_id, slug, entidade_tipo, entidade_id, situacao_atual, usuario_id) -> WorkflowInstance` — busca ativa pelo par; ausente → `engine.iniciar(..., estado_inicial=situacao_atual)` (lazy no estado corrente). ATENÇÃO: `engine.iniciar` commita; chamar ANTES de mutar a entidade;
  - `async def transicionar(db, *, instancia, para, usuario_id, entidade, slug) -> None` — muta `entidade.situacao = para` e chama `engine.executar_transicao`; captura `WorkflowEngineError` e re-levanta o erro de domínio do transporte (`TransporteReguladoError`/equivalente usado pelos 409 atuais — conferir a classe no service) com: `f"O workflow '{slug}' não permite '{para}' a partir de '{instancia.estado_atual}'"` quando a transição não existe, e a mensagem de condição quando bloqueada.
- Seed: `seed_bootstrap` ganha passo idempotente que, para cada tenant com módulo `transporte` contratado, cria as definições dos 3 slugs **só se o slug não existir** (nunca sobrescreve edição do tenant).
- Fachadas (contrato preservado):
  - `registrar_ocorrencia`: após criar a ocorrência (flush para ter id), `obter_ou_criar_instancia(situacao_atual="registrada")`. Caminho do cidadão (portal) passa `usuario_id=None`;
  - `iniciar_apuracao`: instancia lazy + `transicionar(para="em_apuracao")` no lugar do `oc.situacao = "em_apuracao"` direto; validações de payload permanecem antes;
  - `decidir_ocorrencia`: `transicionar(para=<resultado>)`; a validação atual `situacao != "em_apuracao" → 409` SAI (o 409 vem do DSL); a mensagem muda — atualizar a substring nos testes P7 se afirmarem o texto antigo (listar no report).

- [ ] **Step 1: testes RED** — (a) registrar ocorrência cria instância ativa `('ocorrencia', id)` em `registrada`; (b) fluxo completo registrar→iniciar→decidir procedente: `situacao` e `estado_atual` sincronizados em cada passo, log com 2 transições, instância finalizada (`ativa=false`); (c) **lazy**: ocorrência criada direto no banco (sem instância, simulando estoque) sofre `iniciar_apuracao` → instância nasce em `registrada`? NÃO — nasce no estado corrente (`registrada`) e transiciona: afirmar estado final `em_apuracao` e UMA linha de log; (d) **409 do DSL**: editar a definição do tenant removendo `decidir_procedente` → `decidir_ocorrencia` responde 409 com a mensagem citando slug/label/estado; (e) decisão a partir de `registrada` → 409 (transição não existe no DSL); (f) definição lazy: tenant sem definição nenhuma + primeiro ato → definição criada com `slug='transporte-ocorrencia'`. Rodar: FALHA.
- [ ] **Step 2: implementar** — migration 0096 (upgrade/downgrade provados), sementes, helpers, seed e as 3 fachadas.
- [ ] **Step 3: verde + regressão P7** — Step 1 PASSA; `pytest tests/test_transporte_p7_ocorrencias*.py -q` (nome real — conferir com `ls tests/`) verde, ajustando SÓ substrings de mensagem se necessário; HTTP com usuário comum: reusar/adaptar um teste HTTP existente de ocorrência para passar pela fachada.
- [ ] **Step 4: guardas + commit** — `feat(transporte): ocorrencias comandadas pelo workflow (piloto P8 D1)`.

---

### Task 4: Alvará — migration situacao + semente + fachadas + revogação

**Files:**
- Create: `backend/alembic/versions/0097_alvara_situacao.py`
- Modify: `backend/app/models/transporte_regulado.py` (Alvara.situacao), `backend/app/schemas/transporte_regulado.py` (AlvaraOut.situacao; `AlvaraRevogar` com `motivo: str` obrigatório min_length=1), `backend/app/services/transporte_regulado.py` (criar/renovar + `revogar_alvara`), `backend/app/services/transporte_workflow.py` (semente), `backend/app/routers/transporte_regulado.py` (POST `/alvaras/{id}/revogar`)
- Test: `backend/tests/test_transporte_p8_workflows.py` (seção alvará)

**Interfaces:**
- Migration 0097: `ALTER TABLE transporte_regulado.alvara ADD COLUMN situacao varchar(30) NOT NULL DEFAULT 'vigente'`; sem CHECK (o guardião é o DSL). Downgrade dropa a coluna.
- Semente `transporte-alvara`:

```python
{
    "estado_inicial": "vigente",
    "estados": [
        {"slug": "vigente", "label": "Vigente"},
        {"slug": "renovado", "label": "Renovado", "final": True},
        {"slug": "revogado", "label": "Revogado", "final": True},
    ],
    "transicoes": [
        {"de": "vigente", "para": "renovado", "label": "renovar",
         "condicao": "not titular_suspenso"},
        {"de": "vigente", "para": "revogado", "label": "revogar"},
    ],
}
```

- Fachadas:
  - `criar_alvara`: instância nova em `vigente` (estado inicial do DSL — se o tenant configurou rito com etapas antes de `vigente`, a emissão entra no estado inicial DELE e `situacao` grava esse slug);
  - `renovar_alvara`: **o gate da Fase C roda ANTES, inalterado** (mesma mensagem, teste da Fase C intacto); depois: transiciona a instância do alvará de origem para `renovado` e cria alvará novo + instância nova no estado inicial do DSL. A condição `not titular_suspenso` na semente é espelho visível para o tenant — nunca a fonte do 409 desta rota;
  - `revogar_alvara(db, *, tenant_id, alvara_id, motivo, usuario_id)` — **ato novo**: carrega (tenant+excluido, 404), transiciona `vigente→revogado`; motivo vai em `observacoes` prefixado `"Revogado: "` e no `contexto_extra` da transição (aparece no snapshot do log). Router: POST `/alvaras/{alvara_id}/revogar`, `require_permission` com o MESMO código/action dos atos vizinhos de alvará (conferir no router) — rota literal nenhuma nova irmã de paramétrica (a guarda pega).
- `AlvaraOut` ganha `situacao: str`; `api.ts` (Task 6) espelha.

- [ ] **Step 1: teste RED da migration** (coluna + default `vigente` em linha antiga) e dos atos: (a) criar alvará → instância `('alvara', id)` em `vigente`, `situacao='vigente'`; (b) renovar → origem `renovado`/inativa, filho `vigente` com instância própria; (c) renovar com titular suspenso → 409 com a MENSAGEM DA FASE C (substring exata do teste existente); (d) revogar com motivo → `revogado`, instância finalizada, log com contexto contendo o motivo; (e) revogar sem motivo → 422; (f) renovar alvará revogado → 409 do DSL; (g) HTTP usuário comum revoga (payload motivo) → 200. Rodar: FALHA.
- [ ] **Step 2: migration + modelo + schema + semente + fachadas + rota.** `alembic upgrade head`; downgrade/upgrade provados.
- [ ] **Step 3: verde + regressões** — Step 1 PASSA; suíte da Fase C (`pytest tests/test_transporte_fase_c.py -q`) **verde sem edição**; regressão alvarás P2/P2.1 verde.
- [ ] **Step 4: guardas + commit** — `feat(transporte): alvara comandado pelo workflow + ato de revogacao (P8 D2)`.

---

### Task 5: Recadastramento — semente + fachadas

**Files:**
- Modify: `backend/app/services/transporte_workflow.py` (semente), `backend/app/services/transporte_regulado.py` (`decidir_recadastramento`, `suspender_convocacao`, `reativar_convocacao`, entrada em análise — conferir o ato real que grava `em_analise`)
- Test: `backend/tests/test_transporte_p8_workflows.py` (seção recadastramento)

**Interfaces:**
- Semente `transporte-recadastramento`:

```python
{
    "estado_inicial": "convocado",
    "estados": [
        {"slug": "convocado", "label": "Convocado"},
        {"slug": "em_analise", "label": "Em análise"},
        {"slug": "suspenso", "label": "Suspenso"},
        {"slug": "deferido", "label": "Deferido", "final": True},
        {"slug": "indeferido", "label": "Indeferido", "final": True},
    ],
    "transicoes": [
        {"de": "convocado", "para": "em_analise", "label": "iniciar_analise"},
        {"de": "em_analise", "para": "deferido", "label": "deferir",
         "condicao": "checklist_completo"},
        {"de": "em_analise", "para": "indeferido", "label": "indeferir"},
        {"de": "convocado", "para": "suspenso", "label": "suspender"},
        {"de": "em_analise", "para": "suspenso", "label": "suspender_analise"},
        {"de": "suspenso", "para": "convocado", "label": "reativar",
         "condicao": "estado_anterior == 'convocado'"},
        {"de": "suspenso", "para": "em_analise", "label": "reativar_analise",
         "condicao": "estado_anterior == 'em_analise'"},
    ],
}
```

- Fachadas (contrato preservado — MESMO padrão do gate C1 na Task 4: validações ricas com mensagem própria rodam ANTES no service; o DSL espelha):
  - `decidir_recadastramento`: a checagem de completude para deferir permanece no service (mensagem da P5.2 intacta); a transição é `deferir`/`indeferir`;
  - `suspender_convocacao`/`reativar_convocacao`: transições `suspender*`/`reativar*` conforme o estado; a reativação escolhe a transição cuja condição de `estado_anterior` casa (o engine avalia — a fachada tenta `reativar` e, em condição bloqueada, `reativar_analise`; encapsular num helper que percorre as duas). As notificações da Fase C (pós-commit no router) NÃO mudam;
  - Convocação em atraso: `situacao` de atraso hoje é derivada (P5.3 — conferir: se `atrasado` for VALOR gravado em `situacao`, ele entra como estado no DSL com as transições equivalentes; se for derivado de `prazo`, nada muda). O implementer confere no código e registra no report qual dos dois é — em caso de estado gravado, adicionar ao DSL espelhando as transições reais.
- Job da Fase C (`notificar_recadastramento`) e gate C1: intocados (leem `situacao`).

- [ ] **Step 1: testes RED** — (a) fluxo deferir com checklist completo: estados sincronizados, instância finalizada; (b) deferir incompleto → 409 com a mensagem da P5.2 (substring do teste existente); (c) suspender de `convocado` e reativar → volta a `convocado`; suspender de `em_analise` e reativar → volta a `em_analise` (o par de condições `estado_anterior`); (d) lazy sobre convocação do estoque em `em_analise`; (e) 409 do DSL removendo `indeferir`. Rodar: FALHA.
- [ ] **Step 2: implementar** semente + fachadas + helper de reativação.
- [ ] **Step 3: verde + regressões** — Step 1 PASSA; suítes P5.2/P5.3 e Fase C verdes sem edição semântica; guardas.
- [ ] **Step 4: commit** — `feat(transporte): recadastramento comandado pelo workflow (P8 D3)`.

---

### Task 6: Painel de workflow (frontend) + endpoint de leitura

**Files:**
- Modify: `backend/app/routers/transporte_regulado.py` (GET novo), `backend/app/schemas/transporte_regulado.py` (`WorkflowEntidadeOut`)
- Modify: `frontend/lib/api.ts` (tipo + método)
- Create: `frontend/components/transporte/WorkflowTimeline.tsx`
- Modify: as 3 telas — detalhe/painel de ocorrência, alvarás, recadastramento (localizar os componentes reais sob `frontend/app/(app)/m/transporte/` e `frontend/components/transporte/`)
- Test: `frontend/__tests__/WorkflowTimeline.test.tsx`; backend na seção HTTP de `test_transporte_p8_workflows.py`

**Interfaces:**
- GET `/api/v2/transporte-regulado/workflow/{entidade_tipo}/{entidade_id}` → `WorkflowEntidadeOut`:

```python
class WorkflowTransicaoOut(BaseModel):
    estado_de: str
    estado_para: str
    transicao_label: str
    executada_em: datetime
    id_usuario: int | None

class WorkflowEntidadeOut(BaseModel):
    estado_atual: str | None      # None = entidade do estoque sem instância ainda
    ativa: bool | None
    dias_no_estado: int | None
    sla_dias: int | None          # do estado atual no DSL, se configurado
    log: list[WorkflowTransicaoOut]
```

  `entidade_tipo` validado contra `{'ocorrencia','alvara','convocacao'}` (422 fora); a entidade é carregada com tenant+excluido (404 se não existe — autorização antes de resolver); gates: `require_modulo` + `require_permission` iguais aos GETs vizinhos do módulo (leitura sem action). Sem instância → `estado_atual=None` e log vazio (o painel mostra "fluxo ainda não iniciado") — NÃO cria lazy em leitura.
- `api.ts`: `WorkflowEntidadeOut` + `getTransporteWorkflow(entidadeTipo, entidadeId)` — tipo casa com o response_model (não é paginado).
- `WorkflowTimeline`: recebe `entidadeTipo`/`entidadeId`, busca no mount, renderiza estado atual (badge), dias no estado + SLA se houver, e a timeline do log (label, de→para, data). Só leitura. Estilo com tokens do design system (sem cor literal — a guarda `design:check` pega).

- [ ] **Step 1: teste RED backend** — GET de ocorrência com instância devolve log ordenado e estado; GET de entidade sem instância devolve `estado_atual=None`; GET cross-tenant → 404; usuário comum com módulo+leitura → 200. FALHA.
- [ ] **Step 2: endpoint + schema.** Verde. Guardas (a de leitura exige transação — o `require_permission` cobre; se optar por isenção, precisa de razão em `LEITURA_SEM_PERMISSAO_DECIDIDA` — NÃO optar).
- [ ] **Step 3: teste RED frontend** — vitest do `WorkflowTimeline` com fetch mockado: renderiza estado, "fluxo ainda não iniciado" quando `estado_atual=null`, linhas do log. FALHA → implementar componente + `api.ts` → PASSA.
- [ ] **Step 4: costurar nas 3 telas** — inserir o painel no detalhe de ocorrência, no modal/detalhe de alvará e na tela de atendimento da convocação. `npx tsc --noEmit` verde; `npx vitest run` verde (inclui `rotas-modulo`/`menus` — nenhuma página nova, então sem entrada de menu).
- [ ] **Step 5: commit** — `feat(transporte): painel de workflow nas telas de ocorrencia, alvara e recadastramento (P8 D3)`.

---

### Task 7: Docs + fechamento

**Files:**
- Modify: `docs/BACKLOG-PENDENCIAS.md` (§2.2: P8 entregue, bloco datado; registrar a pendência "transação `workflow` mora no módulo protocolo — mover para comum é decisão futura"), `CLAUDE.md` NÃO (nada de novo processo permanente).

- [ ] **Step 1: atualizar backlog** com o bloco P8 (o que entrou, decisões, pendência da transação `workflow`, ato novo de revogação).
- [ ] **Step 2: suíte completa solo** (`pytest -q`, ~17 min, SEM outra suíte concorrente) + `npx vitest run` + `npx tsc --noEmit`.
- [ ] **Step 3: commit** — `docs(transporte): fecha P8 no backlog (workflows avancados)`.
