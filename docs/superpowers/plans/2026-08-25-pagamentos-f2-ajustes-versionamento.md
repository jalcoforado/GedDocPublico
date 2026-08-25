# Pagamentos F2 — Ajustes e Versionamento — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o pedido de ajuste de string em entidade (`pedido_ajuste`), versionar alterações materiais (`debito_versao` + `CAMPOS_MATERIAIS`), invalidar aprovações quando o mérito muda, anexar documentos ao débito (`anexo_debito`) e expor tudo no detalhe e na caixa de trabalho.

**Architecture:** Três tabelas novas no schema `pagamentos` com o boilerplate RLS completo; serviços novos (`pagamentos_ajustes.py`, `pagamentos_versionamento.py`, `pagamentos_anexos.py`) por cima do motor de transição existente (`_registrar_transicao`/`_carregar_para_decisao` de `pagamentos_debitos.py`); a transição `responder_ajuste` vira o "reenvio", que resolve os pedidos e escolhe o destino pela materialidade; frontend estende o detalhe (`solicitacoes/[id]/page.tsx`) e a caixa (`m/pagamentos/page.tsx`).

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic (migration 0105), Next.js 15 + `lib/api.ts`, pytest via `docker exec -e PYTEST_DB_HOST=db aprimora-py-backend`, vitest no host.

**Spec:** `docs/superpowers/specs/2026-08-06-pagamentos-fluxo-design.md` — seções §4.3 (tabelas), §4.5 (backfill sintético), §8 (auditoria), §9-F2 (aceite).

## Global Constraints

- Idioma pt-BR em código, comentários, docs e commits. Commits terminam com `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Migration nova = **0105**, `down_revision="0104"`, head único, `downgrade()` na ordem inversa. Tabela nova: `tenant_id NOT NULL` → `aprimora_py.tenant(id)`, `ENABLE + FORCE ROW LEVEL SECURITY`, policies com `NULLIF(current_setting('app.tenant_id', true), '')::int`, `GRANT SELECT,INSERT,UPDATE,DELETE` na tabela + `GRANT USAGE, SELECT` na sequence para `aprimora_app` (modelo: `0102_sistema_integrado_idempotencia.py:59-71`). Sem grant de worker (nenhuma task Celery toca as tabelas).
- `tenant_id` sempre do caller (`require_tenant_id`), nunca do payload. 404 cross-tenant. Soft-delete onde há exclusão.
- **Nunca gravar `Debito.status` diretamente** — só via `_sincronizar_status_legado` (dentro de `_registrar_transicao`); `test_guarda_status_legado.py` reprova por AST.
- Rota literal antes da paramétrica irmã (`test_guarda_ordem_rotas.py` varre).
- GET novo exige `require_permission` (guarda `test_leitura_sem_permissao_nao_cresce_sem_decisao`); todo endpoint sob `require_modulo` já herdado dos routers existentes.
- Teste HTTP com **usuário comum** (não-SU) em toda rota nova — padrão `_criar_usuario` de `test_pagamentos_fluxo_gestor.py:45-56` + tenant com módulo `pagamentos` contratado.
- Nada de id de FK cravado em teste (CI roda em banco limpo). E-mails `.test`, slugs com sufixo `uuid4().hex[:8]`, cleanup no teardown.
- Toda guarda estrutural nova é **provada por inversão** (quebrar de propósito e ver vermelho) antes do commit.
- Suítes por task: `pytest tests/test_pagamentos_*.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py tests/test_guarda_link_url.py -q` no mínimo; frontend `npx tsc --noEmit` + vitest quando tocar frontend. NUNCA rodar duas suítes simultâneas no mesmo banco. Comandos pytest sempre FOREGROUND.
- `Paginated<X>` em `api.ts` onde o `response_model` for paginado; tipo casa com o `response_model` sempre.

## Rulings de planejamento (vinculantes)

1. **Backfill sintético** (§4.5): a spec cita `acao IN ('DEVOLVIDO','SUSPENSO')`, mas a F1 (posterior à spec) grava `acao='AJUSTE_SOLICITADO'`. O backfill usa `acao IN ('AJUSTE_SOLICITADO','DEVOLVIDO','SUSPENSO')` — cobre débitos migrados pela 0087 e débitos que passaram pelo fluxo novo.
2. **Resolução no reenvio**: responder um pedido o deixa `RESPONDIDO`; o ato de reenviar o débito (transição `responder_ajuste`, endpoint `/responder-ajuste` mantido) exige todos os pedidos da etapa `RESPONDIDO` ou `CANCELADO` e marca os `RESPONDIDO` como `RESOLVIDO` (`resolvido_em=now`). É isso que satisfaz "a tramitação só avança quando todos estão RESOLVIDO".
3. **Materialidade no reenvio**: houve alteração material ⇔ `debito.versao > min(pedido.versao_debito)` dos pedidos resolvidos nesse reenvio (versão só incrementa por alteração material). Material → destino `AGUARDANDO_GESTOR` + invalidação; não material → `_RETORNO_DO_AJUSTE[situacao_atual]` (comportamento F1).
4. **Invalidação de aprovações** = zerar `id_gestor_decisor` e `id_validador` + linha de histórico `acao='APROVACOES_INVALIDADAS'` com justificativa `"invalidadas pela versão N"`. Nada é apagado do histórico.
5. **`DebitoHistorico` ganha** `versao_debito` + `situacao_tramitacao_anterior/nova`, `situacao_fila_anterior/nova`, `situacao_pagamento_anterior/nova` (todas nullable) na 0105; `_registrar_transicao` passa a preenchê-las. Cumpre §8 sem tocar linhas antigas.
6. **`audit.log()`** entra só nos atos novos da F2: `debito.ajuste_solicitado`, `debito.ajuste_respondido`, `debito.versao_criada`, `debito.aprovacoes_invalidadas`, `anexo_debito.incluido`, `anexo_debito.removido`. Retrofit dos atos da F1 fica para F5.
7. **Edição em `AJUSTE_*`**: `atualizar_debito` passa a aceitar `situacao_tramitacao IN (RASCUNHO, AJUSTE_GESTOR, AJUSTE_VALIDACAO, AJUSTE_AUTORIDADE)` (hoje a checagem é `d.status != "RASCUNHO"` → migra para checar `situacao_tramitacao`). Versionamento só quando NÃO é `RASCUNHO`.
8. **Autorização de download de anexo de débito** (premissa §4.3): vínculo ativo em `anexo_debito` do tenant (404 se não houver) + `require_permission(PERMS_LEITURA)` + gate de módulo. Sem sigilo de processo (débito não tem processo). Carregador cru `get_anexo_path` continua proibido em router.
9. **Pedido adicional**: com o débito já em `AJUSTE_<etapa>`, quem tem a permissão da mesma etapa pode abrir outro pedido (`POST /{id}/pedidos-ajuste`) sem nova transição. Abrir pedido de OUTRA etapa → 409.

---

## Estrutura de arquivos

| Arquivo | Papel |
|---|---|
| `backend/alembic/versions/0105_pedido_ajuste_versao_anexo.py` | Create: 3 tabelas + colunas em `debito_historico` + backfill sintético |
| `backend/app/models/pagamentos.py` | Modify: classes `PedidoAjuste`, `DebitoVersao`, `AnexoDebito`; colunas novas em `DebitoHistorico` |
| `backend/app/services/pagamentos_versionamento.py` | Create: `CAMPOS_MATERIAIS`, `CAMPOS_NAO_MATERIAIS`, `CAMPOS_CONTROLE`, `campos_materiais_alterados`, `congelar_versao` |
| `backend/app/services/pagamentos_ajustes.py` | Create: criar/listar/responder/cancelar pedido; `pendencias_para_usuario` |
| `backend/app/services/pagamentos_anexos.py` | Create: upload/listar/excluir/path-autorizado de anexo de débito |
| `backend/app/services/pagamentos_debitos.py` | Modify: `solicitar_ajuste` (cria pedido), `responder_ajuste` (reenvio §rulings 2-4), `atualizar_debito` (edição em AJUSTE_* + versionamento), `_registrar_transicao` (colunas novas do histórico) |
| `backend/app/services/anexos.py` | Modify: extrair helper privado de persistência de arquivo reutilizável |
| `backend/app/routers/pagamentos_debitos.py` | Modify: payload rico de solicitar-ajuste; endpoints de pedidos, versões e anexos; minha-fila com pendências |
| `backend/app/schemas/pagamentos.py` (ou onde vivem os schemas de débito) | Modify: `PedidoAjusteCreate/RespostaIn/Out`, `DebitoVersaoOut`, `AnexoDebitoOut`, `SolicitarAjusteIn` estendido |
| `backend/tests/test_pagamentos_f2_ajustes.py` | Create: pedidos + reenvio + invalidação |
| `backend/tests/test_pagamentos_f2_versionamento.py` | Create: CAMPOS_MATERIAIS + versões |
| `backend/tests/test_pagamentos_f2_anexos.py` | Create: anexos de débito |
| `frontend/lib/api.ts` | Modify: tipos + métodos |
| `frontend/app/(app)/m/pagamentos/solicitacoes/[id]/page.tsx` | Modify: seções Pendências, Versões, Documentos; form de ajuste rico |
| `frontend/app/(app)/m/pagamentos/page.tsx` | Modify: bloco de pendências endereçadas ao usuário |
| `frontend/__tests__/pagamentos-f2.test.tsx` | Create: vitest das seções novas |

---

### Task 1: Migration 0105 + modelos

**Files:**
- Create: `backend/alembic/versions/0105_pedido_ajuste_versao_anexo.py`
- Modify: `backend/app/models/pagamentos.py` (após `DebitoHistorico`, ~linha 251)
- Test: `backend/tests/test_pagamentos_f2_versionamento.py` (só o teste de migration/backfill desta task)

**Interfaces:**
- Consumes: `Debito` (`models/pagamentos.py:161`), `DebitoHistorico` (`:238`), boilerplate `_rls` da `0102`.
- Produces: modelos `PedidoAjuste`, `DebitoVersao`, `AnexoDebito` (nomes de coluna EXATOS abaixo — Tasks 2-6 dependem); colunas novas em `DebitoHistorico`: `versao_debito: int | None`, `situacao_tramitacao_anterior/nova`, `situacao_fila_anterior/nova`, `situacao_pagamento_anterior/nova` (todas `str | None`).

- [ ] **Step 1: Escrever a migration 0105** com upgrade na ordem: (a) três tabelas; (b) colunas de `debito_historico`; (c) RLS+grants das três tabelas; (d) backfill sintético. DDL das tabelas (schema `pagamentos`, todas com `id` PK identity, `tenant_id int NOT NULL` FK `aprimora_py.tenant(id)`):

```python
# pedido_ajuste
op.create_table(
    "pedido_ajuste",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
    sa.Column("id_debito", sa.Integer, sa.ForeignKey("pagamentos.debito.id"), nullable=False),
    sa.Column("versao_debito", sa.Integer, nullable=False),
    sa.Column("etapa_solicitante", sa.String(15), nullable=False),   # GESTOR | VALIDACAO | AUTORIDADE
    sa.Column("id_usuario_solicitante", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
    sa.Column("motivo", sa.String(255), nullable=False),
    sa.Column("descricao", sa.Text, nullable=False),
    sa.Column("transacao_responsavel", sa.String(50), nullable=False),
    sa.Column("tipo", sa.String(15), nullable=False),                # MATERIAL | NAO_MATERIAL
    sa.Column("prazo", sa.Date, nullable=True),
    sa.Column("campos_relacionados", postgresql.JSONB, nullable=True),
    sa.Column("situacao", sa.String(15), nullable=False),            # ABERTO | RESPONDIDO | RESOLVIDO | CANCELADO
    sa.Column("resposta", sa.Text, nullable=True),
    sa.Column("id_usuario_resposta", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
    sa.Column("respondido_em", sa.DateTime, nullable=True),
    sa.Column("resolvido_em", sa.DateTime, nullable=True),
    sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    schema="pagamentos",
)
op.create_index("ix_pedido_ajuste_tenant_debito", "pedido_ajuste",
                ["tenant_id", "id_debito"], schema="pagamentos")
op.create_index("ix_pedido_ajuste_tenant_situacao_transacao", "pedido_ajuste",
                ["tenant_id", "situacao", "transacao_responsavel"], schema="pagamentos")

# debito_versao (append-only)
op.create_table(
    "debito_versao",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
    sa.Column("id_debito", sa.Integer, sa.ForeignKey("pagamentos.debito.id"), nullable=False),
    sa.Column("versao", sa.Integer, nullable=False),                 # a versão CONGELADA (anterior)
    sa.Column("dados", postgresql.JSONB, nullable=False),            # snapshot dos campos materiais
    sa.Column("id_pedido_ajuste", sa.Integer, sa.ForeignKey("pagamentos.pedido_ajuste.id"), nullable=True),
    sa.Column("motivo", sa.String(255), nullable=False),
    sa.Column("id_usuario", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
    sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    schema="pagamentos",
)
op.create_unique_constraint("uq_debito_versao_tenant_debito_versao", "debito_versao",
                            ["tenant_id", "id_debito", "versao"], schema="pagamentos")

# anexo_debito (vínculo, soft-delete)
op.create_table(
    "anexo_debito",
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("tenant_id", sa.Integer, sa.ForeignKey("aprimora_py.tenant.id"), nullable=False),
    sa.Column("id_debito", sa.Integer, sa.ForeignKey("pagamentos.debito.id"), nullable=False),
    sa.Column("id_anexo", sa.Integer, sa.ForeignKey("protocolos.anexo.id"), nullable=False),
    sa.Column("id_usuario", sa.Integer, sa.ForeignKey("utils.usuario.id"), nullable=True),
    sa.Column("versao_debito", sa.Integer, nullable=False),
    sa.Column("id_pedido_ajuste", sa.Integer, sa.ForeignKey("pagamentos.pedido_ajuste.id"), nullable=True),
    sa.Column("criado_em", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    sa.Column("excluido", sa.Boolean, nullable=False, server_default=sa.text("false")),
    schema="pagamentos",
)
op.create_index("ix_anexo_debito_tenant_debito", "anexo_debito",
                ["tenant_id", "id_debito"], schema="pagamentos")
```

Colunas de `debito_historico` (todas nullable, sem backfill de linhas antigas):

```python
for col in [
    sa.Column("versao_debito", sa.Integer, nullable=True),
    sa.Column("situacao_tramitacao_anterior", sa.String(30), nullable=True),
    sa.Column("situacao_tramitacao_nova", sa.String(30), nullable=True),
    sa.Column("situacao_fila_anterior", sa.String(30), nullable=True),
    sa.Column("situacao_fila_nova", sa.String(30), nullable=True),
    sa.Column("situacao_pagamento_anterior", sa.String(20), nullable=True),
    sa.Column("situacao_pagamento_nova", sa.String(20), nullable=True),
]:
    op.add_column("debito_historico", col, schema="pagamentos")
```

RLS/grants: replicar a função `_rls(tabela)` da `0102` para as três tabelas (`ADD COLUMN` em `debito_historico` herda RLS — não repetir).

Backfill sintético (§4.5 + Ruling 1) — SQL puro no upgrade:

```python
op.execute("""
    INSERT INTO pagamentos.pedido_ajuste
        (tenant_id, id_debito, versao_debito, etapa_solicitante, id_usuario_solicitante,
         motivo, descricao, transacao_responsavel, tipo, situacao, criado_em)
    SELECT d.tenant_id, d.id, d.versao,
           CASE d.situacao_tramitacao
                WHEN 'AJUSTE_GESTOR' THEN 'GESTOR'
                WHEN 'AJUSTE_VALIDACAO' THEN 'VALIDACAO'
                WHEN 'AJUSTE_AUTORIDADE' THEN 'AUTORIDADE' END,
           h.id_usuario,
           COALESCE(left(h.justificativa, 255), 'Ajuste solicitado antes da F2'),
           COALESCE(h.justificativa, 'Pedido sintético criado pela migration 0105 (F2).'),
           'pagamento_solicitar', 'NAO_MATERIAL', 'ABERTO', COALESCE(h.criado_em, now())
    FROM pagamentos.debito d
    LEFT JOIN LATERAL (
        SELECT id_usuario, justificativa, criado_em
        FROM pagamentos.debito_historico h
        WHERE h.id_debito = d.id AND h.tenant_id = d.tenant_id
          AND h.acao IN ('AJUSTE_SOLICITADO', 'DEVOLVIDO', 'SUSPENSO')
        ORDER BY h.criado_em DESC, h.id DESC LIMIT 1
    ) h ON true
    WHERE d.situacao_tramitacao IN ('AJUSTE_GESTOR', 'AJUSTE_VALIDACAO', 'AJUSTE_AUTORIDADE')
      AND d.excluido = false
""")
```

`downgrade()`: drop das colunas de `debito_historico`, depois `anexo_debito`, `debito_versao`, `pedido_ajuste` (ordem inversa das FKs). O backfill morre com a tabela — nada mais a desfazer.

- [ ] **Step 2: Modelos** em `models/pagamentos.py`, espelhando o DDL coluna a coluna (`PedidoAjuste`, `DebitoVersao`, `AnexoDebito`; `Mapped[...]` no padrão do arquivo). Acrescentar as 7 colunas novas em `DebitoHistorico`. Conferir que `models/__init__.py` reexporta (padrão do arquivo).

- [ ] **Step 3: Teste do backfill (RED antes da migration aplicar)** em `test_pagamentos_f2_versionamento.py`:

```python
async def test_backfill_sintetico_cobre_debitos_em_ajuste(admin_engine, two_tenants):
    # cria débito em AJUSTE_VALIDACAO com linha de histórico acao='AJUSTE_SOLICITADO'
    # (via SQL direto, simulando estado pré-0105), roda a migration no CI-like…
    # Na prática do repo: como a migration já terá rodado no banco de dev,
    # o teste valida a PROPRIEDADE equivalente: todo débito em AJUSTE_* tem
    # >= 1 pedido_ajuste não-CANCELADO. Criar o débito em AJUSTE_* SEM pedido
    # é impossível pós-Task 3; aqui, inserir via SQL e afirmar que a consulta
    # de pendências (Task 3) o encontraria órfão → este teste nasce como o
    # teste de invariante: nenhum débito em AJUSTE_* sem pedido aberto no tenant de teste.
    ...
```

Concretamente (sem depender de rodar migration dentro do teste): inserir via `admin_engine` um débito em `AJUSTE_VALIDACAO` + pedido `ABERTO` e afirmar a invariante `SELECT count(*) FROM debito d WHERE situacao_tramitacao LIKE 'AJUSTE%' AND NOT EXISTS (pedido não-cancelado)` = 0 no tenant da fixture. O exercício real do backfill acontece no CI (banco limpo, `alembic upgrade head` passa pela 0105 com a tabela vazia — o backfill roda e insere zero linhas, provando que o SQL é válido).

- [ ] **Step 4: Aplicar e validar**

```bash
docker exec aprimora-py-backend alembic upgrade head
docker exec aprimora-py-backend alembic heads          # 0105, único
docker exec aprimora-py-backend alembic downgrade -1   # reversibilidade
docker exec aprimora-py-backend alembic upgrade head
```

Conferir no banco: os 4 débitos em `AJUSTE_*` do dev ganharam pedido sintético (`SELECT count(*) FROM pagamentos.pedido_ajuste`≥4... o downgrade+upgrade duplica? NÃO: o segundo upgrade re-insere porque o downgrade dropou a tabela — ok, sem duplicata possível).

- [ ] **Step 5: Guardas e commit**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_rls_papeis_minimos.py tests/test_pagamentos_f2_versionamento.py -q
git add backend/alembic/versions/0105_pedido_ajuste_versao_anexo.py backend/app/models/pagamentos.py backend/tests/test_pagamentos_f2_versionamento.py
git commit -m "feat(pagamentos): migration 0105 — pedido_ajuste, debito_versao, anexo_debito + backfill sintético (F2)"
```

---

### Task 2: `CAMPOS_MATERIAIS` + versionamento no `atualizar_debito`

**Files:**
- Create: `backend/app/services/pagamentos_versionamento.py`
- Modify: `backend/app/services/pagamentos_debitos.py:210-247` (`atualizar_debito`)
- Test: `backend/tests/test_pagamentos_f2_versionamento.py`

**Interfaces:**
- Consumes: `Debito`, `DebitoVersao` (Task 1); `est.TR_RASCUNHO/TR_AJUSTE_*` de `pagamentos_estados.py:22-32`.
- Produces (Tasks 3-4 e 7 dependem):

```python
# pagamentos_versionamento.py
CAMPOS_MATERIAIS: frozenset[str]      # §4.3: id_fornecedor, valor_total, numero_nf, numero_ne,
                                      # id_fonte_recursos, id_contrato, descricao, data_liquidacao, id_unidade
CAMPOS_NAO_MATERIAIS: frozenset[str]  # id_natureza, id_conta, id_conta_pagadora, competencia,
                                      # criticidade, urgente, justificativa_urgencia, liquidacao_confirmada
CAMPOS_CONTROLE: frozenset[str]       # id, tenant_id, status, situacao_*, versao, lock_version,
                                      # id_gestor_decisor, id_validador, id_usuario_solicitante,
                                      # criado_em, atualizado_em, excluido

def campos_materiais_alterados(debito: Debito, payload: dict) -> set[str]: ...
async def congelar_versao(db, *, debito: Debito, motivo: str, usuario_id: int,
                          id_pedido_ajuste: int | None = None) -> DebitoVersao:
    # grava snapshot dos CAMPOS_MATERIAIS atuais como versão `debito.versao`,
    # incrementa debito.versao, retorna a linha. NÃO commita.
```

- [ ] **Step 1: Teste da guarda de materialidade (RED)** — toda coluna de `Debito` classificada:

```python
def test_toda_coluna_de_debito_tem_decisao_de_materialidade():
    from app.models.pagamentos import Debito
    from app.services import pagamentos_versionamento as pv
    colunas = {c.key for c in Debito.__table__.columns}
    classificadas = pv.CAMPOS_MATERIAIS | pv.CAMPOS_NAO_MATERIAIS | pv.CAMPOS_CONTROLE
    assert colunas - classificadas == set(), (
        f"Colunas sem decisão de materialidade: {colunas - classificadas}. "
        "Coluna nova em Debito exige classificação explícita em pagamentos_versionamento.py"
    )
    assert pv.CAMPOS_MATERIAIS & pv.CAMPOS_NAO_MATERIAIS == set()
```

Rodar, ver falhar com `ModuleNotFoundError`. Implementar o módulo. Ver verde. **Provar por inversão**: comentar `"descricao"` de `CAMPOS_MATERIAIS` e conferir vermelho; restaurar.

- [ ] **Step 2: Teste de `congelar_versao` + edição material em AJUSTE (RED)**:

```python
async def test_alteracao_material_em_ajuste_cria_versao_e_incrementa(app_session, two_tenants):
    # débito em AJUSTE_VALIDACAO (montado pelo fluxo real: criar→enviar→gestor_autorizar→
    # solicitar_ajuste), então atualizar_debito mudando valor_total
    # → DebitoVersao criada com versao=1 e dados contendo o valor_total ANTIGO
    # → debito.versao == 2
async def test_alteracao_nao_material_nao_cria_versao(...):
    # mudar criticidade em AJUSTE_VALIDACAO → sem linha em debito_versao, versao == 1
async def test_edicao_em_rascunho_nao_versiona(...):
    # mudar valor_total em RASCUNHO → sem versão (versionamento só pós-etapa)
async def test_edicao_fora_de_rascunho_e_ajuste_e_409(...):
    # débito AGUARDANDO_GESTOR → atualizar_debito → 409 (comportamento preservado)
```

- [ ] **Step 3: Implementar.** Em `atualizar_debito` (`pagamentos_debitos.py:210`): trocar a checagem `d.status != "RASCUNHO"` por `d.situacao_tramitacao not in (est.TR_RASCUNHO, est.TR_AJUSTE_GESTOR, est.TR_AJUSTE_VALIDACAO, est.TR_AJUSTE_AUTORIDADE)` → 409. Antes de aplicar o payload, se não-RASCUNHO: `alterados = campos_materiais_alterados(d, payload_dict)`; se `alterados`, chamar `congelar_versao(...)` com `motivo=f"Alteração material: {', '.join(sorted(alterados))}"` e `audit.log(acao="debito.versao_criada", entidade="debito", ...)`. `campos_materiais_alterados` compara só chaves presentes no payload (exclude_unset) cujo valor difere do atual.

- [ ] **Step 4: Rodar e commitar**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_f2_versionamento.py tests/test_pagamentos_fluxo_gestor.py tests/test_guarda_status_legado.py -q
git add backend/app/services/pagamentos_versionamento.py backend/app/services/pagamentos_debitos.py backend/tests/test_pagamentos_f2_versionamento.py
git commit -m "feat(pagamentos): CAMPOS_MATERIAIS + versionamento na edição em ajuste (F2)"
```

---

### Task 3: Serviço e endpoints de pedido de ajuste

**Files:**
- Create: `backend/app/services/pagamentos_ajustes.py`
- Modify: `backend/app/services/pagamentos_debitos.py:410-452` (`solicitar_ajuste`), `backend/app/routers/pagamentos_debitos.py` (payload + endpoints), schemas de pagamentos
- Test: `backend/tests/test_pagamentos_f2_ajustes.py`

**Interfaces:**
- Consumes: `PedidoAjuste` (Task 1); `_carregar_para_decisao` (`pagamentos_debitos.py:329`); padrão de checagem dinâmica de permissão por etapa (`routers/pagamentos_debitos.py:296-308`); `load_permissions`.
- Produces (Task 4 e 7 dependem):

```python
# pagamentos_ajustes.py
ETAPA_POR_SITUACAO = {est.TR_AJUSTE_GESTOR: "GESTOR", est.TR_AJUSTE_VALIDACAO: "VALIDACAO",
                      est.TR_AJUSTE_AUTORIDADE: "AUTORIDADE"}

async def criar_pedido(db, *, tenant_id, debito: Debito, usuario_id, etapa: str,
                       motivo: str, descricao: str, transacao_responsavel: str,
                       tipo: str, prazo=None, campos_relacionados=None) -> PedidoAjuste
    # valida transacao_responsavel ∈ códigos de pagamentos em MODULO_TRANSACOES (422 senão);
    # tipo ∈ (MATERIAL, NAO_MATERIAL); situacao=ABERTO; NÃO commita.
async def listar_pedidos(db, *, tenant_id, debito_id) -> list[PedidoAjuste]
async def responder_pedido(db, *, tenant_id, debito_id, pedido_id, usuario_id,
                           resposta: str) -> PedidoAjuste           # ABERTO→RESPONDIDO; 409 senão
async def cancelar_pedido(db, *, tenant_id, debito_id, pedido_id, usuario_id) -> PedidoAjuste
    # ABERTO→CANCELADO; 409 senão
async def pedidos_pendentes_da_etapa(db, *, tenant_id, debito_id, etapa) -> list[PedidoAjuste]
    # situacao == ABERTO da etapa (RESPONDIDO não bloqueia reenvio — Ruling 2)
```

Schemas: `PedidoAjusteOut` (todas as colunas), `SolicitarAjusteIn` estendido: `{lock_version:int, etapa:str, motivo:str(≤255), descricao:str, transacao_responsavel:str, tipo:Literal["MATERIAL","NAO_MATERIAL"], prazo:date|None, campos_relacionados:list[str]|None}` (o antigo campo `justificativa` morre — o frontend é atualizado na Task 7 no mesmo branch), `PedidoAjusteCreate` (idem sem lock_version/etapa — etapa vem da situação atual), `PedidoAjusteResponderIn {resposta:str}`.

- [ ] **Step 1: Testes RED** em `test_pagamentos_f2_ajustes.py` (montar débitos pelo fluxo real com usuários distintos — padrão `_criar_usuario`/`_provisionar` de `test_pagamentos_fluxo_gestor.py`):

```python
async def test_solicitar_ajuste_cria_pedido_estruturado(...):
    # validar etapa VALIDACAO: solicitar_ajuste(motivo=..., descricao=..., transacao_responsavel=
    # 'pagamento_solicitar', tipo='NAO_MATERIAL') → débito AJUSTE_VALIDACAO + 1 PedidoAjuste ABERTO
    # com versao_debito == debito.versao e etapa_solicitante == 'VALIDACAO'
async def test_pedido_adicional_na_mesma_etapa(...):
    # débito em AJUSTE_VALIDACAO → POST pedidos-ajuste → 2º pedido ABERTO, sem transição
async def test_pedido_adicional_de_outra_etapa_e_409(...):
async def test_transacao_responsavel_desconhecida_e_422(...):
async def test_responder_pedido_grava_resposta(...):
    # responder → RESPONDIDO, resposta, id_usuario_resposta, respondido_em preenchidos
async def test_responder_pedido_ja_respondido_e_409(...):
async def test_cancelar_pedido_pelo_solicitante(...):
async def test_http_usuario_comum_lista_pedidos(...):
    # GET /pagamentos/debitos/{id}/pedidos-ajuste com usuário comum (perm leitura) → 200
async def test_http_pedido_cross_tenant_e_404(...):
```

- [ ] **Step 2: Implementar serviço + integrar.** `solicitar_ajuste` (`pagamentos_debitos.py:410`) ganha os parâmetros novos e, após a transição, chama `criar_pedido(...)` + `audit.log(acao="debito.ajuste_solicitado", ...)`. Endpoints em `debitos_router` (bloco das linhas 283-325):
  - `POST /{debito_id}/solicitar-ajuste` — payload novo (permissão por etapa: lógica existente 296-308 preservada)
  - `GET /{debito_id}/pedidos-ajuste` — `require_permission` com `PERMS_LEITURA`, `response_model=list[PedidoAjusteOut]`
  - `POST /{debito_id}/pedidos-ajuste` — pedido adicional; permissão da etapa atual do débito (mesma lógica dinâmica); 409 se débito não está em `AJUSTE_*`
  - `POST /{debito_id}/pedidos-ajuste/{pedido_id}/responder` — quem tem a `transacao_responsavel` DO PEDIDO (checagem dinâmica via `load_permissions`; 403 senão) + `audit.log("debito.ajuste_respondido")`
  - `POST /{debito_id}/pedidos-ajuste/{pedido_id}/cancelar` — permissão da etapa solicitante do pedido

- [ ] **Step 3: Rodar, guardas, commit**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_f2_ajustes.py tests/test_guarda_ordem_rotas.py tests/test_guarda_modularizacao.py -q
git add -A backend/app backend/tests/test_pagamentos_f2_ajustes.py
git commit -m "feat(pagamentos): pedido de ajuste como entidade — criar, responder, cancelar (F2)"
```

---

### Task 4: Reenvio com retorno correto + invalidação de aprovações

**Files:**
- Modify: `backend/app/services/pagamentos_debitos.py:454-469` (`responder_ajuste`), `_registrar_transicao` (:67-97) para as colunas novas do histórico
- Test: `backend/tests/test_pagamentos_f2_ajustes.py`

**Interfaces:**
- Consumes: `pedidos_pendentes_da_etapa`, `ETAPA_POR_SITUACAO` (Task 3); `debito.versao` vs `pedido.versao_debito` (Ruling 3); `_RETORNO_DO_AJUSTE` (`pagamentos_debitos.py:322-326`).
- Produces: `responder_ajuste` com a semântica final de reenvio (Task 7 consome o mesmo endpoint `/responder-ajuste`).

- [ ] **Step 1: Testes RED** (os dois primeiros são o **aceite da F2** e o segundo é a regra dura do §4.3):

```python
async def test_reenvio_nao_material_volta_a_etapa_que_pediu(...):
    # AJUSTE_VALIDACAO, responder pedido, reenviar → AGUARDANDO_VALIDACAO; pedido RESOLVIDO
async def test_reenvio_com_alteracao_material_volta_ao_gestor(...):
    # AJUSTE_AUTORIDADE (passou por gestor+validação), alterar valor_total (versiona),
    # responder, reenviar → AGUARDANDO_GESTOR; id_gestor_decisor is None; id_validador is None;
    # histórico contém acao='APROVACOES_INVALIDADAS' com "invalidadas pela versão 2"
async def test_reenvio_com_pedido_aberto_e_409(...):
    # pedido ABERTO não respondido → responder_ajuste → 409 com a lista dos pendentes
async def test_reenvio_resolve_os_respondidos(...):
    # 2 pedidos: 1 RESPONDIDO + 1 CANCELADO → reenvio passa; o RESPONDIDO vira RESOLVIDO
async def test_historico_registra_dimensoes_e_versao(...):
    # qualquer transição pós-F2 → DebitoHistorico.situacao_tramitacao_anterior/nova e
    # versao_debito preenchidos
async def test_versao_anterior_recuperavel(...):
    # após material: GET /debitos/{id}/versoes devolve a versão 1 com o valor_total antigo
```

- [ ] **Step 2: Implementar.** `_registrar_transicao`: preencher `versao_debito=debito.versao` e os pares `situacao_*_anterior/nova` (capturar antes/depois de aplicar). `responder_ajuste`:

```python
etapa = ajs.ETAPA_POR_SITUACAO[d.situacao_tramitacao]        # 409 se não está em AJUSTE_*
abertos = await ajs.pedidos_pendentes_da_etapa(db, tenant_id=tenant_id, debito_id=debito_id, etapa=etapa)
if abertos:
    raise TransicaoInvalidaError(...)                        # 409, lista motivo+id dos abertos
respondidos = [p for p in todos_da_etapa if p.situacao == "RESPONDIDO"]
# materialidade (Ruling 3): alguma alteração material desde a abertura de algum pedido respondido
material = bool(respondidos) and d.versao > min(p.versao_debito for p in respondidos)
# se todos os pedidos foram CANCELADOS (respondidos vazio), destino = retorno padrão
destino = est.TR_AGUARDANDO_GESTOR if material else _RETORNO_DO_AJUSTE[d.situacao_tramitacao]
if material:
    d.id_gestor_decisor = None
    d.id_validador = None
    # linha de histórico própria acao='APROVACOES_INVALIDADAS' (via INSERT direto de
    # DebitoHistorico, sem transição) + audit.log("debito.aprovacoes_invalidadas")
# transição via _registrar_transicao(acao='REENVIADO', tramitacao=destino, ...)
for p in respondidos:
    p.situacao = "RESOLVIDO"; p.resolvido_em = agora
```

Atenção: `_RETORNO_DO_AJUSTE` e o grafo `est.transicao_permitida` precisam aceitar `AJUSTE_AUTORIDADE → AGUARDANDO_GESTOR` e `AJUSTE_VALIDACAO → AGUARDANDO_GESTOR` (arestas novas do grafo em `pagamentos_estados.py` — conferir e acrescentar se faltarem; `test_pagamentos_estados.py` pode ter tabela a atualizar).

Endpoint novo nesta task: `GET /pagamentos/debitos/{debito_id}/versoes` → `response_model=list[DebitoVersaoOut]` (`{id, versao, dados, id_pedido_ajuste, motivo, id_usuario, criado_em}`), `require_permission` com `PERMS_LEITURA` — é ele que prova "versão anterior recuperável" e que a Task 7 consome como `listarVersoes`.

- [ ] **Step 3: Rodar a família inteira de fluxo + commit**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_f2_ajustes.py tests/test_pagamentos_fluxo_gestor.py tests/test_pagamentos_fluxo_validacao_autoridade.py tests/test_pagamentos_estados.py tests/test_pagamentos_status_derivado.py tests/test_pagamentos_segregacao.py tests/test_guarda_status_legado.py -q
git add -A backend/app backend/tests
git commit -m "feat(pagamentos): reenvio resolve pedidos e retorna à etapa correta; alteração material invalida aprovações (F2)"
```

---

### Task 5: Anexos de débito (backend)

**Files:**
- Create: `backend/app/services/pagamentos_anexos.py`
- Modify: `backend/app/services/anexos.py` (extrair helper privado de persistência do `upload_anexo:38-50` — a parte que salva arquivo e cria a linha `Anexo`, sem o vínculo com processo), `backend/app/routers/pagamentos_debitos.py`, schemas
- Test: `backend/tests/test_pagamentos_f2_anexos.py`

**Interfaces:**
- Consumes: `Anexo` (`models/processo.py:221`), `AnexoDebito` (Task 1), helper extraído de `anexos.py`.
- Produces (Task 7 consome os endpoints):

```python
# pagamentos_anexos.py
async def anexar_ao_debito(db, *, tenant_id, tenant_slug, debito_id, usuario_id,
                           file: UploadFile, descricao: str | None,
                           id_pedido_ajuste: int | None = None) -> AnexoDebito
async def listar_anexos_debito(db, *, tenant_id, debito_id) -> list[AnexoDebito]  # excluido=False
async def get_anexo_debito_path_autorizado(db, *, tenant_id, anexo_debito_id) -> tuple[Path, Anexo]
    # 1º: vínculo ativo do tenant (404 se não) — autorização ANTES de resolver o recurso
async def remover_anexo_debito(db, *, tenant_id, debito_id, anexo_debito_id, usuario_id) -> None
    # soft-delete do vínculo; audit.log("anexo_debito.removido")
```

Endpoints (permissões: upload/remover = `pagamento_solicitar`; listar/download = `PERMS_LEITURA`):
- `POST /pagamentos/debitos/{debito_id}/anexos` (multipart; grava `versao_debito=d.versao`, `id_pedido_ajuste` opcional; débito em estado terminal → 409; `audit.log("anexo_debito.incluido")`)
- `GET /pagamentos/debitos/{debito_id}/anexos` → `list[AnexoDebitoOut]` (id, id_anexo, nome/tamanho/tipo do Anexo, versao_debito, id_pedido_ajuste, id_usuario, criado_em)
- `GET /pagamentos/anexos-debito/{anexo_debito_id}/download` → `FileResponse`
- `DELETE /pagamentos/debitos/{debito_id}/anexos/{anexo_debito_id}`

- [ ] **Step 1: Testes RED**:

```python
async def test_upload_e_download_de_anexo_de_debito(...):        # HTTP, usuário comum
async def test_download_cross_tenant_e_404(...):                 # vínculo de outro tenant
async def test_download_de_vinculo_excluido_e_404(...):
async def test_upload_em_debito_terminal_e_409(...):             # CANCELADA
async def test_anexo_em_resposta_a_pedido_referencia_o_pedido(...):
```

- [ ] **Step 2: Implementar** (helper extraído mantém `upload_anexo` de processos intacto — a suíte de anexos de processo continua verde). Router: rota literal `anexos-debito` não colide com paramétrica; conferir com a guarda.

- [ ] **Step 3: Rodar + commit**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_f2_anexos.py tests/test_anexos*.py tests/test_guarda_anexo_sigiloso.py tests/test_guarda_ordem_rotas.py -q
git add -A backend/app backend/tests/test_pagamentos_f2_anexos.py
git commit -m "feat(pagamentos): anexos de débito reaproveitando o armazenamento de protocolos (F2)"
```

---

### Task 6: Pendências na minha-fila

**Files:**
- Modify: `backend/app/routers/pagamentos_debitos.py:596` (`GET /pagamentos/minha-fila`) e o service que o alimenta
- Test: `backend/tests/test_pagamentos_f2_ajustes.py`

**Interfaces:**
- Consumes: `PedidoAjuste` + índice `(tenant_id, situacao, transacao_responsavel)` (Task 1); `load_permissions` do usuário.
- Produces: `MinhaFila` ganha `pendencias_ajuste: list[PendenciaAjusteOut]` — `{id_pedido, id_debito, descricao_debito, motivo, prazo, criado_em, etapa_solicitante}` — pedidos `ABERTO` cuja `transacao_responsavel` ∈ transações do usuário no tenant. Task 7 consome.

- [ ] **Step 1: Teste RED**: usuário comum com `pagamento_solicitar` vê na minha-fila o pedido aberto endereçado a essa transação; usuário sem a transação NÃO vê; pedido `RESPONDIDO` some da lista.
- [ ] **Step 2: Implementar** (query com `tenant_filter`, join em `Debito` para descrição, `excluido=False`).
- [ ] **Step 3:**

```bash
docker exec -e PYTEST_DB_HOST=db aprimora-py-backend pytest tests/test_pagamentos_f2_ajustes.py -q
git add -A backend/app backend/tests
git commit -m "feat(pagamentos): minha-fila lista pedidos de ajuste endereçados às transações do usuário (F2)"
```

---

### Task 7: Frontend — pendências, versões e form de ajuste rico

**Files:**
- Modify: `frontend/lib/api.ts` (interfaces `PedidoAjusteOut`, `DebitoVersaoOut`, `PendenciaAjusteOut`, `MinhaFila` + métodos), `frontend/app/(app)/m/pagamentos/solicitacoes/[id]/page.tsx`, `frontend/app/(app)/m/pagamentos/page.tsx`
- Test: `frontend/__tests__/pagamentos-f2.test.tsx`

**Interfaces:**
- Consumes: endpoints das Tasks 3-4-6 (tipos casando 1:1 com os `*Out` do backend — conferir contra os schemas reais antes de declarar).
- Produces: `api.pagamentos.debitos.{listarPedidosAjuste, criarPedidoAjuste, responderPedidoAjuste, cancelarPedidoAjuste, solicitarAjuste (payload novo), responderAjuste (reenvio), listarVersoes}`.

- [ ] **Step 1: `api.ts`** — tipos + métodos; `solicitarAjuste` muda o payload (motivo/descricao/transacao_responsavel/tipo/prazo) — atualizar TODOS os call-sites (grep por `solicitarAjuste`).
- [ ] **Step 2: Detalhe** (`solicitacoes/[id]/page.tsx`): seção **Pendências** — lista os pedidos (situação com ícone+texto, nunca só cor; motivo, descrição, responsável, prazo, resposta); form de responder para quem pode; botão de reenvio ("Reenviar para análise") desabilitado-com-motivo enquanto houver pedido `ABERTO`. Seção **Versões** quando `versao > 1`: lista `debito_versao` com dados congelados legíveis. Dialog de **Solicitar ajustes** com o form rico (transação responsável = select das transações de pagamentos com rótulo em português). 409 de lock_version → recarregar e mostrar o estado, não repetir a ação.
- [ ] **Step 3: Caixa** (`m/pagamentos/page.tsx`): bloco "Pendências para você responder" a partir de `minhaFila().pendencias_ajuste`, linkando para o detalhe.
- [ ] **Step 4: vitest** — render das seções com dados mock (pedido aberto bloqueia reenvio; pendência aparece na caixa); `cd frontend && npx tsc --noEmit && npx vitest run __tests__/pagamentos-f2.test.tsx`.
- [ ] **Step 5: Commit** `feat(pagamentos): pendências de ajuste e versões no detalhe e na caixa de trabalho (F2)`.

---

### Task 8: Frontend — documentos do débito

**Files:**
- Modify: `frontend/lib/api.ts` (`AnexoDebitoOut` + métodos upload/list/download/remove), `frontend/app/(app)/m/pagamentos/solicitacoes/[id]/page.tsx`
- Test: `frontend/__tests__/pagamentos-f2.test.tsx`

- [ ] **Step 1:** Seção **Documentos** no detalhe: upload (multipart — seguir o padrão de upload existente no app, grep por `FormData` em `lib/api.ts`), lista com nome/tamanho/quem/quando/versão, download (link para o endpoint), remoção com confirmação por resumo de impacto. Upload em resposta a pedido: quando o form de responder está aberto, o upload carrega `id_pedido_ajuste`.
- [ ] **Step 2:** vitest da seção + `npx tsc --noEmit`.
- [ ] **Step 3:** Commit `feat(pagamentos): documentos do débito no detalhe (F2)`.

---

### Task 9: Documentação e fechamento (executada pelo controlador, inline)

- [ ] Bloco F2 no `docs/BACKLOG-PENDENCIAS.md` §2.1 (entregue + pendências residuais datadas).
- [ ] Linha da migration 0105 na tabela do `README.md` (se a tabela existir — seguir o padrão das 0099-0104).
- [ ] Suítes completas solo (backend inteira + frontend inteira + tsc) antes do review final da branch.

## Aceite da fatia (spec §9-F2)

- Alteração material cria versão e invalida aprovações ✔ (Tasks 2+4)
- Versão anterior recuperável ✔ (Task 4, `GET /versoes`)
- Pendência chega a quem tem a transação designada ✔ (Tasks 3+6+7)
- Nenhum débito em `AJUSTE_*` fica sem pedido ✔ (Task 1, backfill + invariante)
