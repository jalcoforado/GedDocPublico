# Transporte P7 — Ocorrências: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ocorrências regulatórias com catálogo de tipos, máquina de estados com trilha append-only, telas de balcão, e denúncia do cidadão no portal com acompanhamento e e-mail na decisão.

**Architecture:** Três tabelas em `transporte_regulado` (migration 0093), service com máquina de estados, dois routers (realm municipal + realm cidadão), telas admin em `/m/transporte/ocorrencias` e portal em `/cidadao/denuncias`. Notificação por e-mail via `services/notificacoes.enviar` existente.

**Tech Stack:** FastAPI + SQLAlchemy 2 async, Alembic manual, pytest via docker exec, Next.js 15 + React Query + vitest.

**Spec:** `docs/superpowers/specs/2026-08-21-transporte-p7-ocorrencias-design.md`

## Global Constraints

- Idioma pt-BR; commits terminam com `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Backend: `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest ...` (bind-mount, sem rebuild). Frontend: vitest/tsc no host; **não rodar `npm run lint`**.
- Migration 0093: `down_revision="0092"`, head único, downgrade inverso, boilerplate RLS da 0084/0092 (`_rls()` idêntico: GUC `app.tenant_id`, `current_setting(..., true)`, ENABLE+FORCE, grants tabela+sequence a `aprimora_app`, sem worker).
- `tenant_id` do caller; 404 cross-tenant; FKs soft same-tenant + não-excluído; soft-delete; 409 em transição ilegal.
- Transação `transporte_regulado` no realm municipal (GET sem action, escrita com action); realm cidadão usa `get_current_cidadao` + `require_tenant_id`, NUNCA `require_permission`.
- Situações da ocorrência: `registrada`, `em_apuracao`, `procedente`, `improcedente`, `arquivada` (valores exatos). Origens: `fiscalizacao`, `denuncia`, `outro`. Atos: `registro`, `inicio_apuracao`, `anotacao`, `vinculo_alvo`, `decisao`.
- Rota literal antes de paramétrica (`/tipos` antes de `/{ocorrencia_id}`).
- Saída do realm cidadão é `DenunciaCidadaoOut` (schema próprio) — trilha/parecer/alvos NUNCA no JSON.
- Endpoint paginado → `request<Paginated<X>>` em api.ts.
- PowerShell 5.1: sem `&&`; commit via here-string `@'...'@` sem aspas duplas no corpo.
- **Todo teste listado numa task é obrigatório — inclusive o de RLS sob `app_session` (Task 3) e os do realm cidadão (Task 5). Na P6b, itens de teste da spec fora do brief causaram fix rounds; aqui a lista é exaustiva.**

---

### Task 1: Migration 0093 + modelos

**Files:**
- Create: `backend/alembic/versions/0093_transporte_ocorrencias.py`
- Modify: `backend/app/models/transporte_regulado.py` (fim), `backend/app/models/__init__.py`

**Interfaces:**
- Produces: tabelas `ocorrencia_tipo`, `ocorrencia`, `ocorrencia_andamento`; modelos `OcorrenciaTipo`, `Ocorrencia`, `OcorrenciaAndamento` exportados de `app.models`.

- [ ] **Step 1: Migration** — molde: `0092_transporte_linhas.py` (mesmo `_rls()`, docstring com o porquê). Colunas conforme a spec §Modelo, com estes detalhes exatos:

```python
# ocorrencia_tipo
sa.Column("nome", sa.String(150), nullable=False),
sa.Column("descricao", sa.Text(), nullable=True),
sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
# + tenant_id/criado_em/atualizado_em/excluido padrão; índice:
# CREATE UNIQUE INDEX ux_ocorrencia_tipo_nome ON transporte_regulado.ocorrencia_tipo
#   (tenant_id, lower(nome)) WHERE excluido = false

# ocorrencia
sa.Column("id_tipo", sa.Integer(), sa.ForeignKey(f"{S}.ocorrencia_tipo.id"), nullable=False),
sa.Column("origem", sa.String(20), nullable=False),
sa.Column("data_fato", sa.Date(), nullable=False),
sa.Column("descricao", sa.Text(), nullable=False),
sa.Column("id_permissionario", sa.Integer(), sa.ForeignKey(f"{S}.permissionario.id"), nullable=True),
sa.Column("id_empresa", sa.Integer(), sa.ForeignKey(f"{S}.empresa.id"), nullable=True),
sa.Column("id_veiculo", sa.Integer(), sa.ForeignKey(f"{S}.veiculo.id"), nullable=True),
sa.Column("referencia_alvo", sa.String(200), nullable=True),
sa.Column("id_cidadao", sa.Integer(), sa.ForeignKey("utils.usuario_externo.id"), nullable=True),
sa.Column("situacao", sa.String(20), nullable=False, server_default="registrada"),
sa.Column("observacoes", sa.Text(), nullable=True),
sa.CheckConstraint("origem IN ('fiscalizacao', 'denuncia', 'outro')", name="ck_ocorrencia_origem"),
sa.CheckConstraint(
    "situacao IN ('registrada', 'em_apuracao', 'procedente', 'improcedente', 'arquivada')",
    name="ck_ocorrencia_situacao",
),
# SEM CHECK de alvo — regra de serviço, razão na spec (denúncia nasce sem alvo).
# Índices: ix_ocorrencia_tenant_situacao, ix_ocorrencia_tenant_tipo, ix_ocorrencia_tenant_cidadao

# ocorrencia_andamento — append-only, sem atualizado_em
sa.Column("id_ocorrencia", sa.Integer(), sa.ForeignKey(f"{S}.ocorrencia.id"), nullable=False),
sa.Column("ato", sa.String(20), nullable=False),
sa.Column("parecer", sa.Text(), nullable=True),
sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("utils.usuario.id"), nullable=True),
sa.CheckConstraint(
    "ato IN ('registro', 'inicio_apuracao', 'anotacao', 'vinculo_alvo', 'decisao')",
    name="ck_ocorrandamento_ato",
),
# Índice: ix_ocorrandamento_tenant_ocorrencia (tenant_id, id_ocorrencia)
```

`_rls()` nas três. Downgrade inverso (andamento → ocorrencia → tipo).

- [ ] **Step 2: Validar** — `alembic heads` (0093 único) / `upgrade head` / `downgrade -1` / `upgrade head`, todos sem erro.
- [ ] **Step 3: Modelos** — espelhar as colunas (molde: classes `Linha*` no mesmo arquivo; `OcorrenciaAndamento` sem `atualizado_em`, docstring dizendo por quê — ato não se edita). Reexportar os três em `models/__init__.py`.
- [ ] **Step 4: Smoke RLS** — `pytest tests/test_rls_papeis_minimos.py -q` → PASS (a varredura pega as tabelas novas).
- [ ] **Step 5: Commit** — `feat(transporte): tabelas de ocorrencia (P7, Tarefa 1)`.

---

### Task 2: Schemas + service — catálogo e registro

**Files:**
- Modify: `backend/app/schemas/transporte_regulado.py` (fim), `backend/app/services/transporte_regulado.py` (fim)
- Test: `backend/tests/test_transporte_p7_ocorrencias.py` (novo; molde de fixtures/helpers: `test_transporte_p6b_linhas.py` — `_provisionar`, `_operadores`, `_limpar` adaptados)

**Interfaces:**
- Produces:
  - Schemas: `OcorrenciaTipoCreate/Update/Out`; `OcorrenciaCreate` (id_tipo, origem, data_fato, descricao, alvos opcionais, referencia_alvo, observacoes), `OcorrenciaOut` (tudo + `tipo_nome`, `alvo_resumo: str | None`, `situacao`, datas; `andamentos: list[OcorrenciaAndamentoOut]` no detalhe), `OcorrenciaAndamentoOut` (id, ato, parecer, id_usuario, usuario_nome, criado_em).
  - Service: `listar_tipos_ocorrencia`, `criar_tipo_ocorrencia`, `atualizar_tipo_ocorrencia`, `excluir_tipo_ocorrencia` (409 se em uso), `obter_ocorrencia`, `listar_ocorrencias(db, *, tenant_id, q, situacao, origem, id_tipo, limit, offset)`, `registrar_ocorrencia(db, *, tenant_id, payload, id_usuario, exigir_alvo: bool = True)` — cria a ocorrência + ato `registro` na trilha, na MESMA transação. `exigir_alvo=False` é a porta da P7.2 (denúncia).

- [ ] **Step 1: Testes RED** (assinaturas; corpos seguem os análogos do arquivo-molde):

```python
async def test_nome_de_tipo_e_unico_por_tenant(admin_engine): ...          # 409, caixa diferente
async def test_excluir_tipo_em_uso_da_409(admin_engine): ...
async def test_tipo_inativo_permanece_em_ocorrencia_antiga(admin_engine): ...  # listar_tipos com flag; ocorrência antiga resolve tipo_nome
async def test_registrar_no_balcao_sem_alvo_da_422(admin_engine): ...      # exigir_alvo=True
async def test_registrar_com_alvo_cross_tenant_da_404(admin_engine): ...
async def test_registrar_cria_ato_registro_na_trilha(admin_engine): ...    # situacao exata "registrada" + 1 andamento ato="registro"
async def test_listar_ocorrencias_filtros_e_contagem(admin_engine): ...    # q por descricao E por referencia_alvo; total == len(rows) nos dois; filtro situacao
async def test_ocorrencia_de_outro_tenant_da_404(admin_engine): ...
```

- [ ] **Step 2: RED** — rodar; falha por ImportError/AttributeError.
- [ ] **Step 3: Schemas + service GREEN** — validações no padrão P6b (`func.lower` p/ unicidade → 409; FK soft → helper `_validar_alvos_ocorrencia(db, *, tenant_id, id_permissionario, id_empresa, id_veiculo)` com 404 por alvo inexistente/cross-tenant/excluído; `exigir_alvo=True` sem nenhum → `HTTPException(422, "Informe ao menos um alvo (permissionário, empresa ou veículo)")`). `listar_ocorrencias`: condições construídas UMA vez para consulta e contagem; `q` com `or_(Ocorrencia.descricao.ilike, Ocorrencia.referencia_alvo.ilike)`. `registrar_ocorrencia` grava `Ocorrencia` + `OcorrenciaAndamento(ato="registro", id_usuario=id_usuario)` com um único `flush`.
- [ ] **Step 4: GREEN** — suite do arquivo verde.
- [ ] **Step 5: Commit** — `feat(transporte): catalogo e registro de ocorrencias (P7, Tarefa 2)`.

---

### Task 3: Service — máquina de estados + RLS

**Files:**
- Modify: `backend/app/services/transporte_regulado.py`
- Test: `backend/tests/test_transporte_p7_ocorrencias.py`

**Interfaces:**
- Consumes: `obter_ocorrencia`, modelos.
- Produces: `iniciar_apuracao(db, *, tenant_id, ocorrencia_id, id_usuario)`, `anotar_ocorrencia(..., parecer)`, `vincular_alvo_ocorrencia(..., id_permissionario=None, id_empresa=None, id_veiculo=None)`, `decidir_ocorrencia(..., resultado, parecer)` (resultado ∈ procedente|improcedente|arquivada), `excluir_ocorrencia(...)` (só `registrada`), `listar_andamentos(db, *, tenant_id, ocorrencia_id)`.

- [ ] **Step 1: Testes RED**:

```python
async def test_maquina_de_estados_caminho_feliz(admin_engine): ...
    # registrada -> apurar -> em_apuracao (exato) -> decidir improcedente; trilha com 3 atos na ordem
async def test_decidir_direto_de_registrada_da_409(admin_engine): ...
async def test_decidir_duas_vezes_da_409(admin_engine): ...
async def test_anotar_em_situacao_final_da_409(admin_engine): ...
async def test_decidir_sem_parecer_da_422(admin_engine): ...
async def test_procedente_sem_alvo_da_409(admin_engine): ...
    # denúncia (exigir_alvo=False) apurada; decidir procedente -> 409; vincular_alvo -> decidir -> passa
async def test_vincular_alvo_grava_na_ocorrencia_e_na_trilha(admin_engine): ...
async def test_excluir_fora_de_registrada_da_409(admin_engine): ...
async def test_alvara_continua_emitindo_com_ocorrencia_procedente(admin_engine): ...  # NÃO-GATE
async def test_rls_filtra_as_tres_tabelas_sob_aprimora_app(admin_engine, app_session, two_tenants): ...
    # molde EXATO: test_rls_filtra_as_tres_tabelas_sob_aprimora_app em test_transporte_p6b_linhas.py
    # (semeia p/ dois tenants via admin; SET LOCAL + SELECT na mesma transação; ids concretos presentes/ausentes)
```

- [ ] **Step 2: RED**; **Step 3: implementar** — esqueleto da transição:

```python
SITUACOES_FINAIS_OCORRENCIA = {"procedente", "improcedente", "arquivada"}
RESULTADOS_DECISAO = SITUACOES_FINAIS_OCORRENCIA  # o CHECK do banco é a rede

async def _ato(db, oc, *, ato: str, parecer: str | None, id_usuario: int | None) -> None:
    db.add(OcorrenciaAndamento(
        tenant_id=oc.tenant_id, id_ocorrencia=oc.id, ato=ato,
        parecer=parecer, id_usuario=id_usuario, criado_em=datetime.utcnow(),
    ))

async def decidir_ocorrencia(db, *, tenant_id, ocorrencia_id, resultado, parecer, id_usuario):
    if resultado not in RESULTADOS_DECISAO:
        raise HTTPException(422, "Resultado inválido")
    if not (parecer or "").strip():
        raise HTTPException(422, "A decisão exige parecer")
    oc = await obter_ocorrencia(db, tenant_id=tenant_id, ocorrencia_id=ocorrencia_id)
    if oc.situacao != "em_apuracao":
        raise HTTPException(409, "Só se decide ocorrência em apuração")
    if resultado == "procedente" and not (oc.id_permissionario or oc.id_empresa or oc.id_veiculo):
        raise HTTPException(409, "Procedência exige alvo vinculado — vincule o alvo antes de decidir")
    oc.situacao = resultado
    oc.atualizado_em = datetime.utcnow()
    await _ato(db, oc, ato="decisao", parecer=parecer, id_usuario=id_usuario)
    await db.flush()
    return oc
```

`iniciar_apuracao`: só de `registrada` (senão 409). `anotar`: parecer obrigatório (422), permitido em `registrada`/`em_apuracao` (senão 409). `vincular_alvo`: mesmas situações; valida alvos via `_validar_alvos_ocorrencia`; grava ids não-nulos na ocorrência (não apaga os existentes ao passar None) + ato. `excluir`: só `registrada` (senão 409), soft.

- [ ] **Step 4: GREEN**; **Step 5: Commit** — `feat(transporte): maquina de estados da ocorrencia (P7, Tarefa 3)`.

---

### Task 4: Router municipal + HTTP usuário comum

**Files:**
- Modify: `backend/app/routers/transporte_regulado.py` (fim), `backend/app/main.py` (após `linhas_router`)
- Test: `backend/tests/test_transporte_p7_ocorrencias.py`

**Interfaces:**
- Produces: `ocorrencias_router` (prefixo `/transporte-regulado/ocorrencias`) com as 12 rotas da spec §Superfície P7.1, `/tipos*` declaradas ANTES de `/{ocorrencia_id}`. Molde: `linhas_router` no mesmo arquivo (deps, Paginated, commits). Corpos de ação: `POST /{id}/apurar|anotar|vincular-alvo|decidir` com schemas `OcorrenciaAnotarInput(parecer)`, `OcorrenciaVincularInput(id_permissionario/id_empresa/id_veiculo opcionais)`, `OcorrenciaDecidirInput(resultado, parecer)`. `registrar` passa `id_usuario=user.id` (trocar `_: Usuario` por `user: Usuario` nas rotas de escrita que gravam trilha). Detalhe (`GET /{id}`) devolve `OcorrenciaOut` com `andamentos` (resolvendo `usuario_nome`) e alvos resolvidos (`alvo_resumo`: nome do permissionário / razão social / placa — o primeiro não-nulo, concatenados se mais de um).

- [ ] **Step 1: Testes HTTP RED** (molde: `test_http_usuario_comum_cria_linha_e_le_detalhe`):

```python
async def test_http_usuario_comum_registra_apura_e_decide(admin_engine): ...
    # contratar módulo; usuário comum; POST raiz (alvo=permissionário) 201;
    # POST apurar 200; POST decidir improcedente + parecer 200; GET detalhe: trilha com 3 atos
async def test_http_tipos_nao_engolida_pela_parametrica(admin_engine): ...
    # GET /tipos com usuário comum -> 200 (nunca 422); prova da ordem literal/paramétrica
```

- [ ] **Step 2: RED (404)**; **Step 3: router + include em main.py**; **Step 4: GREEN + guardas** — `pytest tests/test_transporte_p7_ocorrencias.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py -q`.
- [ ] **Step 5: Commit** — `feat(transporte): endpoints de ocorrencias (P7, Tarefa 4)`.

---

### Task 5: Realm cidadão + notificação na decisão

**Files:**
- Modify: `backend/app/schemas/transporte_regulado.py` (`DenunciaCidadaoCreate`, `DenunciaCidadaoOut`), `backend/app/services/transporte_regulado.py`, `backend/app/routers/transporte_regulado.py` (novo `cidadao_denuncias_router`), `backend/app/main.py`
- Test: `backend/tests/test_transporte_p7_ocorrencias.py`

**Interfaces:**
- Consumes: `registrar_ocorrencia(exigir_alvo=False)`; `get_current_cidadao`/`require_tenant_id` de `app.auth.deps`; `services.notificacoes.enviar` + `Destinatario` (ler `backend/app/services/notificacoes.py:46-95` antes — `enviar` faz commit PRÓPRIO).
- Produces:
  - `DenunciaCidadaoCreate(id_tipo, descricao, referencia_alvo=None, data_fato)`; `DenunciaCidadaoOut(id, tipo_nome, descricao, referencia_alvo, situacao, data_fato, criado_em)` — **schema fechado, nada de herdar de OcorrenciaOut**.
  - Service: `registrar_denuncia_cidadao(db, *, tenant_id, cidadao, payload)` (origem `denuncia`, `id_cidadao=cidadao.id`, sem alvo, tipo tem de estar ativo → 422 se inativo/inexistente do tenant), `listar_denuncias_do_cidadao(db, *, tenant_id, id_cidadao)`.
  - Router: `cidadao_denuncias_router = APIRouter(prefix="/cidadao/denuncias", tags=["cidadao"])` — `GET /tipos` (só ativos), `POST ""` (201), `GET ""` (lista as do token). Molde de deps: `backend/app/routers/cidadao.py` (`get_current_cidadao` + `require_tenant_id`).
  - Notificação: em `decidir_ocorrencia` NÃO (o service faz flush, não commit). A notificação sai do **router** `POST /{id}/decidir`: após `await db.commit()`, se `oc.id_cidadao` → carregar `UsuarioExterno`; se tiver e-mail → `await notificacoes.enviar(db, tenant_id=..., destinatarios=[Destinatario(email=cidadao.email)], canais=["email"], tipo="denuncia_decidida", titulo="Sua denúncia foi analisada", mensagem="A denúncia nº {id} foi analisada. Acompanhe a situação no portal do cidadão.", link_url="/cidadao/denuncias")` num `try/except` com log — **falha de e-mail nunca desfaz a decisão** (ela já está commitada). Texto neutro: sem resultado, sem dados do apurado.

- [ ] **Step 1: Testes RED**:

```python
async def test_cidadao_registra_denuncia_sem_alvo(admin_engine): ...
async def test_denuncia_com_tipo_inativo_da_422(admin_engine): ...
async def test_cidadao_so_ve_as_suas(admin_engine): ...           # dois cidadãos no mesmo tenant
async def test_saida_do_cidadao_nao_vaza_campos_internos(admin_engine): ...
    # HTTP GET /api/v2/cidadao/denuncias com token real; assert sobre o CONJUNTO
    # de chaves do JSON: {"id","tipo_nome","descricao","referencia_alvo","situacao","data_fato","criado_em"}
    # — nada de "andamentos", "parecer", "id_permissionario", "id_empresa", "id_veiculo"
async def test_decisao_gera_email_neutro_ao_cidadao(admin_engine): ...
    # decidir via HTTP municipal; SELECT em aprimora_py.notificacao:
    # destinatario_email == email do cidadão, canal email, mensagem NÃO contém o resultado
async def test_cidadao_sem_email_nao_explode(admin_engine): ...   # decisão passa, zero notificação
async def test_http_cidadao_token_real(admin_engine): ...
    # token via build_cidadao_payload + encode_token (app/auth/jwt.py) com get_jwt_secret;
    # POST e GET no realm cidadão com header Authorization: Bearer
```

(Os testes HTTP do cidadão podem compartilhar um helper `_token_cidadao(engine, cidadao)`; criar `UsuarioExterno` como em `tests/test_pr4b_abertura_por_servico.py::_criar_cidadao`.)

- [ ] **Step 2: RED**; **Step 3: implementar**; **Step 4: GREEN**; **Step 5: Commit** — `feat(transporte): denuncia do cidadao com notificacao (P7, Tarefa 5)`.

---

### Task 6: Cliente `api.ts`

**Files:**
- Modify: `frontend/lib/api.ts`

**Interfaces:**
- Produces: tipos `OcorrenciaTipo`, `OcorrenciaTransporte` (com `tipo_nome`, `alvo_resumo`, `andamentos`), `OcorrenciaAndamento`, `OcorrenciaSituacao`, `DenunciaCidadao`; namespaces `api.ocorrenciasTransporte` (`tipos.list/create/update/remove`, `list` → `Paginated<OcorrenciaTransporte>`, `get`, `registrar`, `apurar`, `anotar`, `vincularAlvo`, `decidir`, `remove`) e `api.cidadaoDenuncias` (`tipos`, `list`, `create`). Molde: bloco `linhasTransporte` (P6b). O cliente do cidadão usa o MESMO `request<T>` (o cookie do cidadão vai junto; conferir como as chamadas existentes do portal em `api.ts` fazem — seguir igual).

- [ ] **Step 1: tipos + métodos**; **Step 2: `tsc --noEmit` → 0**; **Step 3: Commit** — `feat(transporte): cliente de ocorrencias em api.ts (P7, Tarefa 6)`.

---

### Task 7: Telas admin

**Files:**
- Create: `frontend/app/(app)/m/transporte/ocorrencias/page.tsx`, `.../ocorrencias/[id]/page.tsx`, `.../ocorrencias/tipos/page.tsx`

**Interfaces:**
- Consumes: `api.ocorrenciasTransporte.*`; moldes: `linhas/page.tsx` (lista+dialog+filtros), `linhas/[id]/page.tsx` (detalhe+seletores de alvo com busca no servidor — padrão Input+`q`, NUNCA Combobox com lista inteira), `pontos/page.tsx`.
- Produces: as três rotas. Lista: filtros situação/origem/tipo + busca; colunas nº/tipo/alvo-ou-referência/origem/data do fato/situação (Badges por situação: `registrada` neutral, `em_apuracao` warning, `procedente` danger, `improcedente`/`arquivada` neutral). Registro em dialog (tipo ativo, data_fato, descrição, alvos com busca no servidor — os três opcionais mas ao menos um, validado no submit). Detalhe: dados+alvos, trilha cronológica (ato, parecer, autor, data), botões de ação habilitados pela situação (apurar em `registrada`; anotar/vincular em `registrada|em_apuracao`; decidir em `em_apuracao` com select resultado+textarea parecer). Tipos: tabela simples criar/editar/inativar/excluir (409 de "em uso" mostra a mensagem do servidor).

- [ ] **Step 1: implementar**; **Step 2: `tsc` 0 + guarda de órfã VERMELHA acusando `/m/transporte/ocorrencias` (RED esperado — se passar, PARE e investigue); **Step 3: Commit** — `feat(transporte): telas de ocorrencias (P7, Tarefa 7)`.

---

### Task 8: Telas do portal + costura + validação final

**Files:**
- Create: `frontend/app/cidadao/denuncias/page.tsx`, `frontend/app/cidadao/denuncias/nova/page.tsx`
- Modify: `frontend/lib/transporte-hub.ts` (card Ocorrências → `href:"/m/transporte/ocorrencias"`, `ready:true`), `frontend/lib/menus/transporte.ts` (item novo, `perm:"transporte_regulado"`, ícone `AlertOctagon`), `KEYWORDS_POR_HREF` (chave `/m/transporte/ocorrencias`), `frontend/__tests__/transporte-hub.test.tsx` (`semHref` → `[]` — **o último tracejado sai; atualizar o comentário do teste para registrar o marco**), `frontend/__tests__/menus.test.tsx` (PERMISSOES_ESPERADAS), navegação do portal (`frontend/app/cidadao/` — layout/página inicial do portal ganha o link "Minhas denúncias"; conferir os moldes `cidadao/processos/page.tsx` para o padrão de página autenticada do cidadão)
- Modify: `docs/BACKLOG-PENDENCIAS.md` §2.2 (P7 entregue, decisões-chave)

**Interfaces:**
- Consumes: `api.cidadaoDenuncias.*`; auth do portal (`lib/cidadao-auth.tsx`, guard de rota em `middleware.ts` — conferir se `/cidadao/denuncias` já cai no guard existente de `/cidadao`; se o middleware enumerar rotas, acrescentar).

- [ ] **Step 1: RED costura** — atualizar `transporte-hub.test.tsx` (`toEqual([])`) e `menus.test.tsx`; rodar, ver falhar.
- [ ] **Step 2: GREEN** — hub/menu/keywords + telas do portal (lista das minhas com Badge de situação; formulário nova: select de tipo ativo, data do fato, descrição, referência; sucesso → toast + volta à lista). A guarda de órfã do `(app)` não cobre `app/cidadao/` — o link de navegação do portal é obrigação deste passo mesmo sem guarda; dizer no relatório onde o link entrou.
- [ ] **Step 3: Validação final** — `tsc` 0; `npx vitest run` inteira; `docker exec ... pytest -q` inteira (~8 min).
- [ ] **Step 4: Commits** — `feat(transporte): portal de denuncias e costura de ocorrencias (P7, Tarefa 8)` e `docs(transporte): fecha ocorrencias (P7) no backlog`.

---

## Self-review (feito na escrita)

- **Cobertura da spec:** modelo (T1), catálogo+registro com fail-modes (T2), máquina de estados + não-gate + RLS app_session (T3), superfície municipal + ordem de rotas + usuário comum (T4), realm cidadão + contorno do JSON + e-mail neutro + token real (T5), cliente (T6), telas admin (T7), portal + costura + hub `semHref=[]` + backlog (T8).
- **Placeholders:** nenhum "TBD"; testes têm assinatura + conteúdo com molde nominal; código novo (máquina de estados, notificação) está inline.
- **Consistência:** `exigir_alvo` liga T2→T5; `decidir_ocorrencia` faz flush e o **router** commita antes de notificar (T5), coerente com o commit-próprio de `enviar`; `DenunciaCidadaoOut` fechado em T5 e afirmado por teste de chaves.
