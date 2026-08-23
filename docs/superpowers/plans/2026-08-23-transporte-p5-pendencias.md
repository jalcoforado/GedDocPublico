# Transporte Fase C — pendências do P5: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate de renovação de alvará para suspensos e notificação automática do recadastramento por job Celery (4 gatilhos), fechando as pendências registradas da P5.

**Architecture:** C1 é uma checagem de service em `renovar_alvara`. C2 é migration 0094 (id_usuario anulável + coluna gatilho + primeiros grants do worker no módulo), task Celery diária com idempotência por `(convocação, gatilho)`, e e-mail no ato para suspensão/reativação (router, pós-commit).

**Tech Stack:** FastAPI + SQLAlchemy 2 async, Alembic manual, Celery beat, pytest via docker exec.

**Spec:** `docs/superpowers/specs/2026-08-23-transporte-p5-pendencias-design.md`

## Global Constraints

- Idioma pt-BR; commits com `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Backend via `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest ...`; **toda task re-roda as guardas** (`tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py tests/test_guarda_link_url.py`) além dos alvos — lição da P7.
- TDD com evidência RED no relatório de cada task.
- Valores exatos: convocação suspensa = `SITUACAO_SUSPENSO` (constante existente do service — usar a constante, nunca literal novo); gatilhos = `convocacao|lembrete|atraso|suspensao|reativacao`.
- Migration 0094: `down_revision="0093"`, head único, downgrade reverte; grants ao worker ENUMERADOS (nunca cobertor).
- 404 cross-tenant; mensagens de 409 acionáveis (apontam o caminho de volta).
- Testes novos em `backend/tests/test_transporte_fase_c.py` (arquivo novo; fixtures/helpers moldados em `test_transporte_p5_3*`/`test_transporte_p6b_linhas.py` — conferir nomes reais com Glob).
- PowerShell 5.1: sem `&&`; commits via here-string sem aspas duplas (ou Bash heredoc).

---

### Task 1: C1 — gate de renovação

**Files:**
- Modify: `backend/app/services/transporte_regulado.py` (`renovar_alvara`, ~linha 1319)
- Test: `backend/tests/test_transporte_fase_c.py` (novo)

**Interfaces:**
- Consumes: `RecadastramentoConvocacao` (campos `id_permissionario`/`id_empresa`/`situacao`), constante `SITUACAO_SUSPENSO`, `suspender_convocacao`/`reativar_convocacao` existentes (para montar cenário nos testes — note que elas COMMITAM internamente).
- Produces: helper `_titular_tem_convocacao_suspensa(db, *, tenant_id, id_permissionario, id_empresa) -> bool` + a checagem no início de `renovar_alvara` (depois do `obter_alvara`), 409 com a mensagem da spec.

- [ ] **Step 1: testes RED**

```python
async def test_suspenso_nao_renova_alvara_e_a_mensagem_aponta_reativacao(admin_engine): ...
    # permissionário com convocação suspensa (montar via suspender_convocacao com prazo vencido);
    # renovar_alvara -> 409; "reativação" na mensagem (substring)
async def test_reativado_volta_a_renovar(admin_engine): ...
async def test_suspenso_ainda_emite_alvara_novo(admin_engine): ...   # ANTI-DERIVA: criar_alvara passa
async def test_empresa_suspensa_bloqueia_renovacao_do_alvara_da_empresa(admin_engine): ...
    # convocação de EMPRESA suspensa; alvará com id_empresa -> 409 (afirmar o valor exato da situacao gravada)
async def test_http_usuario_comum_toma_409_na_renovacao(admin_engine): ...
    # molde HTTP comum: contratar módulo + _cria_usuario_comum_transporte
```

- [ ] **Step 2: RED** (`pytest tests/test_transporte_fase_c.py -q` → falha por gate ausente: renovação passa onde deveria dar 409)
- [ ] **Step 3: implementar**

```python
async def _titular_tem_convocacao_suspensa(
    db: AsyncSession, *, tenant_id: int,
    id_permissionario: int | None, id_empresa: int | None,
) -> bool:
    """Fase C: qualquer convocação suspensa do titular, de qualquer ciclo,
    bloqueia a RENOVAÇÃO (só ela — emissão nova segue livre, e há teste
    anti-deriva). Suspensão tem saída (reativação), então o gate é reversível."""
    if id_permissionario is None and id_empresa is None:
        return False
    cond = [
        RecadastramentoConvocacao.tenant_id == tenant_id,
        RecadastramentoConvocacao.situacao == SITUACAO_SUSPENSO,
        RecadastramentoConvocacao.excluido.is_(False),
    ]
    alvo = []
    if id_permissionario is not None:
        alvo.append(RecadastramentoConvocacao.id_permissionario == id_permissionario)
    if id_empresa is not None:
        alvo.append(RecadastramentoConvocacao.id_empresa == id_empresa)
    cond.append(or_(*alvo))
    return (await db.scalar(select(RecadastramentoConvocacao.id).where(*cond).limit(1))) is not None
```

Em `renovar_alvara`, após `obter_alvara`:

```python
    if await _titular_tem_convocacao_suspensa(
        db, tenant_id=tenant_id,
        id_permissionario=original.id_permissionario, id_empresa=original.id_empresa,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Titular com recadastramento suspenso — a renovação fica bloqueada "
                "até a reativação (Recadastramento → atendimento da convocação)"
            ),
        )
```

- [ ] **Step 4: GREEN + guardas + regressão de alvará** (`pytest tests/test_transporte_fase_c.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py tests/test_guarda_link_url.py -q` + o arquivo de testes de alvará existente — localizar com Glob `test_transporte*alvara*`)
- [ ] **Step 5: Commit** — `feat(transporte): suspensao bloqueia renovacao de alvara (Fase C1)`

---

### Task 2: Migration 0094 + modelo

**Files:**
- Create: `backend/alembic/versions/0094_recadastramento_notificacao_automacao.py`
- Modify: `backend/app/models/transporte_regulado.py` (`RecadastramentoNotificacao`)

**Interfaces:**
- Produces: `RecadastramentoNotificacao.id_usuario` nullable (NULL = automação), coluna `gatilho: str | None` (CHECK dos 5 valores, NULL = linhas manuais antigas); grants ao `aprimora_worker`.

- [ ] **Step 1: migration** (molde 0092/0093 para o estilo; SEM tabela nova → sem RLS novo):

```python
def upgrade() -> None:
    # NULL = envio do sistema (job). O NOT NULL original dizia "envio é ato de
    # operador"; a automação da Fase C é o segundo autor legítimo.
    op.alter_column(
        "recadastramento_notificacao", "id_usuario",
        existing_type=sa.Integer(), nullable=True, schema=S,
    )
    # Chave da idempotência do job: no máximo um envio por (convocacao, gatilho).
    # NULL = linha manual da P5.3, que não sabia seu gatilho.
    op.add_column(
        "recadastramento_notificacao",
        sa.Column("gatilho", sa.String(30), nullable=True),
        schema=S,
    )
    op.create_check_constraint(
        "ck_recadnotif_gatilho", "recadastramento_notificacao",
        "gatilho IS NULL OR gatilho IN "
        "('convocacao', 'lembrete', 'atraso', 'suspensao', 'reativacao')",
        schema=S,
    )
    # Primeiros grants do worker neste módulo — enumerados, nunca cobertor.
    for t in ("recadastramento_ciclo", "recadastramento_convocacao",
              "permissionario", "empresa"):
        op.execute(f"GRANT SELECT ON {S}.{t} TO aprimora_worker")
    op.execute(f"GRANT SELECT, INSERT ON {S}.recadastramento_notificacao TO aprimora_worker")
    op.execute(f"GRANT USAGE, SELECT ON {S}.recadastramento_notificacao_id_seq TO aprimora_worker")
    # O motor de notificações grava e atualiza enviado_em/erro:
    op.execute("GRANT SELECT, INSERT, UPDATE ON aprimora_py.notificacao TO aprimora_worker")
    op.execute("GRANT USAGE, SELECT ON aprimora_py.notificacao_id_seq TO aprimora_worker")
```

Downgrade: revogar os grants, dropar o CHECK e a coluna; `id_usuario` volta a NOT NULL **somente** se não houver linha NULL (documentar; se houver, o downgrade falha alto — melhor que apagar autoria). **Conferir antes** (uma consulta no banco de dev) se `aprimora_worker` já tem algum grant em `aprimora_py.notificacao` — se tiver, não duplicar; ajustar o par GRANT/REVOKE à realidade e dizer no relatório.

- [ ] **Step 2: validar** — `alembic heads` (0094 único) / upgrade / downgrade -1 / upgrade; `pytest tests/test_rls_papeis_minimos.py -q` (a varredura de RLS continua verde; se o teste de tabelas-de-plataforma reclamar do grant em `aprimora_py.notificacao`, ler a mensagem — `notificacao` NÃO é `platform_*`, não deve reclamar).
- [ ] **Step 3: modelo** — `id_usuario: Mapped[int | None]`, `gatilho: Mapped[str | None]`; atualizar o docstring (o "NOT NULL: envio é ato de operador" vira "NULL = automação da Fase C").
- [ ] **Step 4: teste de grant** — em `test_transporte_fase_c.py`: sob engine do papel `aprimora_worker` (montar como o `app_session` do conftest monta o `aprimora_app` — mesma senha/host), `SELECT` nas 4 tabelas + `INSERT` em `recadastramento_notificacao` com `id_usuario=None, gatilho='atraso'` funciona (com `SET LOCAL app.tenant_id`).
- [ ] **Step 5: Commit** — `feat(transporte): migration 0094 — notificacao com gatilho e worker (Fase C2)`

---

### Task 3: Task Celery + beat

**Files:**
- Create: `backend/app/tasks/notificar_recadastramento.py`
- Modify: `backend/app/tasks/celery_app.py` (beat entry)
- Test: `backend/tests/test_transporte_fase_c.py`

**Interfaces:**
- Consumes: `_task_db` (sessão do worker — LER `backend/app/tasks/_task_db.py` e uma task existente que varre tenants, ex. `verificar_sla_workflows`, e copiar o padrão de sessão/loop de tenant/SET LOCAL); `notificacoes.enviar` + `Destinatario`; modelo da Task 2.
- Produces: função async `notificar_recadastramento(dias_antes: int = 5)` exposta como task Celery `run`; por tenant, por convocação aberta, decide NO MÁXIMO um gatilho por rodada na precedência **atraso > lembrete > convocacao**, deduplicando por existência de `RecadastramentoNotificacao(id_convocacao, gatilho)`; envia e-mail ao titular (permissionário.email ou empresa.email); sem e-mail → pula sem registro; grava o registro com `id_usuario=None` apontando a `Notificacao` criada. Beat entry conforme a spec (`crontab(hour=7, minute=0)`, kwargs `{"dias_antes": 5}`).

- [ ] **Step 1: testes RED** (chamando a função da task diretamente com sessão de teste — não via Celery):

```python
async def test_job_convocacao_vencida_ganha_atraso(admin_engine): ...
async def test_job_rodar_duas_vezes_nao_duplica(admin_engine): ...
async def test_job_prazo_proximo_ganha_lembrete_nao_atraso(admin_engine): ...
async def test_job_recem_gerada_ganha_convocacao(admin_engine): ...
async def test_job_precedencia_um_aviso_por_rodada(admin_engine): ...
    # vencida E nunca avisada -> SÓ 'atraso' nesta rodada
async def test_job_sem_email_pula_sem_registro_e_recupera_depois(admin_engine): ...
async def test_job_suspensa_nao_recebe_lembrete_nem_atraso(admin_engine): ...
async def test_job_isola_tenants(admin_engine): ...
    # dois tenants com convocações; cada Notificacao criada tem o tenant certo
```

- [ ] **Step 2: RED**; **Step 3: implementar** (estrutura: por tenant → carregar convocações abertas + suspensas fora; para cada, resolver gatilho pela precedência; lote de registros existentes por `(id_convocacao, gatilho)` numa query só — não uma por convocação); **Step 4: GREEN + guardas**; **Step 5: Commit** — `feat(transporte): job diario de notificacao do recadastramento (Fase C2)`

---

### Task 4: E-mail no ato (suspensão/reativação) + backlog

**Files:**
- Modify: `backend/app/routers/transporte_regulado.py` (rotas de suspender/reativar convocação — localizar com Grep)
- Modify: `docs/BACKLOG-PENDENCIAS.md` §2.2
- Test: `backend/tests/test_transporte_fase_c.py`

**Interfaces:**
- Consumes: `suspender_convocacao`/`reativar_convocacao` (COMMITAM internamente — a notificação vem depois do retorno, padrão pós-commit da P7: try/except com `await db.rollback()` no except + log; falha de e-mail nunca desfaz o ato); `notificacoes.enviar`; modelo da Task 2.
- Produces: nos dois routers, após o ato: e-mail ao titular **com o parecer no corpo** (aqui o destinatário é o próprio suspenso) + `RecadastramentoNotificacao(gatilho='suspensao'|'reativacao', id_usuario=<operador>)`. Sem e-mail → só loga.

- [ ] **Step 1: testes RED**

```python
async def test_suspensao_via_http_notifica_com_parecer(admin_engine): ...
    # POST suspender -> Notificacao canal email, destinatario = email do titular,
    # parecer contido na mensagem; registro com gatilho='suspensao' e id_usuario do operador
async def test_reativacao_via_http_notifica(admin_engine): ...
async def test_suspensao_sem_email_nao_explode(admin_engine): ...
```

- [ ] **Step 2: RED**; **Step 3: implementar**; **Step 4: validação final da fase** — `pytest tests/test_transporte_fase_c.py tests/test_transporte_p5_3_atraso_suspensao.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py tests/test_guarda_link_url.py -q` (conferir o nome real do arquivo P5.3 com Glob) + `cd frontend; npx tsc --noEmit` (nada de frontend mudou — confirmação barata).
- [ ] **Step 5: backlog** — §2.2: as duas pendências do recadastramento saem da lista aberta; bloco `>` com as decisões (gate só na renovação com anti-deriva testado; job com precedência e idempotência por gatilho; primeiros grants do worker; e-mail no ato com parecer). Commits: `feat(transporte): email no ato de suspensao e reativacao (Fase C2)` e `docs(transporte): fecha pendencias do P5 no backlog`.

---

## Self-review (feito na escrita)

- **Cobertura da spec:** C1 inteiro na T1 (incl. anti-deriva e HTTP comum); migration+grants na T2 com teste de grant; job com os 8 cenários da spec na T3; ato+parecer na T4; backlog na T4.
- **Placeholders:** nenhum; código novo (helper do gate, migration) inline; task Celery especificada por contrato + molde nominal (`_task_db`, task de SLA).
- **Consistência:** `SITUACAO_SUSPENSO` reutilizada; services que commitam → notificação pós-retorno; `gatilho` NULL para linhas antigas casa com o CHECK `IS NULL OR IN (...)`; dedupe do job usa o mesmo par `(id_convocacao, gatilho)` que a T2 cria.
