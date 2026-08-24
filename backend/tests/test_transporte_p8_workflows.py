"""Transporte P8 — Workflows avançados.

Task 1 (D1): `workflow_instance` deixa de ser exclusivo de `processo` e
ganha `entidade_tipo`/`entidade_id` polimórficos. O engine (`workflow_engine.py`)
é a Task 2 — este arquivo cobre só a migration 0095 + modelo.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import WorkflowDefinition, WorkflowInstance, WorkflowSlaAlerta, WorkflowTransicaoLog
from app.schemas.transporte_regulado import AlvaraCreate, AlvaraRenovarInput, OcorrenciaCreate
from app.services import transporte_regulado as tr
from app.services import transporte_workflow  # noqa: F401 — registra os providers no import
from app.services.modulos import contratar
from app.services.workflow_engine import (
    WorkflowEngineError,
    compute_contexto,
    executar_transicao,
    iniciar,
)
from app.tasks.verificar_sla_workflows import _processar_tenant
from tests.test_transporte_p5_2_atendimento import (
    _as_user,
    _convocacao,
    _cria_usuario_comum_transporte,
    _permissionario,
    _provisionar,
    _sm,
    _um_usuario,
)
from tests.test_transporte_p5_3_atraso import _ciclo_vencido, _parecer
from tests.test_transporte_p7_ocorrencias import _operadores, _tipo

pytestmark = pytest.mark.asyncio


async def _provisionar_tenant_e_definicao(admin_session: AsyncSession) -> tuple[int, int]:
    """Cria um tenant e um workflow_definition mínimos, retorna seus ids."""
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now()

    res_t = await admin_session.execute(
        text(
            "INSERT INTO aprimora_py.tenant (slug, nome, ativo, plano, criado_em) "
            "VALUES (:slug, :nome, true, 'basico', :now) RETURNING id"
        ),
        {"slug": f"p8-wf-{suffix}", "nome": f"P8 WF {suffix}", "now": now},
    )
    tenant_id = int(res_t.scalar_one())

    res_d = await admin_session.execute(
        text(
            "INSERT INTO aprimora_py.workflow_definition "
            "(tenant_id, slug, nome, versao, ativo, dsl, criado_em) "
            "VALUES (:tenant_id, :slug, :nome, 1, true, '{}'::jsonb, :now) "
            "RETURNING id"
        ),
        {
            "tenant_id": tenant_id,
            "slug": f"def-{suffix}",
            "nome": "Definição de teste P8",
            "now": now,
        },
    )
    definicao_id = int(res_d.scalar_one())
    await admin_session.commit()
    return tenant_id, definicao_id


async def _limpar(admin_session: AsyncSession, tenant_id: int) -> None:
    async with admin_session.begin():
        await admin_session.execute(
            text(
                "DELETE FROM aprimora_py.workflow_instance WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )
        await admin_session.execute(
            text(
                "DELETE FROM aprimora_py.workflow_definition WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )
        await admin_session.execute(
            text("DELETE FROM aprimora_py.tenant WHERE id = :t"),
            {"t": tenant_id},
        )


async def test_workflow_instance_aceita_entidade_polimorfica(admin_session):
    """entidade_tipo/entidade_id existem, aceitam 'ocorrencia' e id_processo
    fica NULL — sem exigir vínculo de processo."""
    tenant_id, definicao_id = await _provisionar_tenant_e_definicao(admin_session)
    try:
        now = datetime.now()
        res = await admin_session.execute(
            text(
                "INSERT INTO aprimora_py.workflow_instance "
                "(tenant_id, id_workflow_definition, id_processo, "
                " entidade_tipo, entidade_id, estado_atual, ativa, iniciada_em) "
                "VALUES (:tenant_id, :def_id, NULL, 'ocorrencia', :entidade_id, "
                " 'inicial', true, :now) RETURNING id, entidade_tipo, entidade_id, id_processo"
            ),
            {
                "tenant_id": tenant_id,
                "def_id": definicao_id,
                "entidade_id": 42,
                "now": now,
            },
        )
        await admin_session.commit()
        row = res.one()
        assert row.entidade_tipo == "ocorrencia"
        assert row.entidade_id == 42
        assert row.id_processo is None
    finally:
        await _limpar(admin_session, tenant_id)


async def test_uma_instancia_ativa_por_entidade_por_inversao(admin_session):
    """Segunda instância ATIVA da mesma (tenant, entidade_tipo, entidade_id)
    viola o índice único parcial. Terceira com ativa=false passa — prova por
    inversão que a exclusividade é do índice, não de checagem de serviço."""
    tenant_id, definicao_id = await _provisionar_tenant_e_definicao(admin_session)
    try:
        now = datetime.now()

        async with admin_session.begin():
            await admin_session.execute(
                text(
                    "INSERT INTO aprimora_py.workflow_instance "
                    "(tenant_id, id_workflow_definition, id_processo, "
                    " entidade_tipo, entidade_id, estado_atual, ativa, iniciada_em) "
                    "VALUES (:tenant_id, :def_id, NULL, 'ocorrencia', 7, "
                    " 'inicial', true, :now)"
                ),
                {"tenant_id": tenant_id, "def_id": definicao_id, "now": now},
            )

        with pytest.raises(IntegrityError):
            async with admin_session.begin():
                await admin_session.execute(
                    text(
                        "INSERT INTO aprimora_py.workflow_instance "
                        "(tenant_id, id_workflow_definition, id_processo, "
                        " entidade_tipo, entidade_id, estado_atual, ativa, iniciada_em) "
                        "VALUES (:tenant_id, :def_id, NULL, 'ocorrencia', 7, "
                        " 'inicial', true, :now)"
                    ),
                    {"tenant_id": tenant_id, "def_id": definicao_id, "now": now},
                )
        await admin_session.rollback()

        async with admin_session.begin():
            await admin_session.execute(
                text(
                    "INSERT INTO aprimora_py.workflow_instance "
                    "(tenant_id, id_workflow_definition, id_processo, "
                    " entidade_tipo, entidade_id, estado_atual, ativa, iniciada_em) "
                    "VALUES (:tenant_id, :def_id, NULL, 'ocorrencia', 7, "
                    " 'finalizado', false, :now)"
                ),
                {"tenant_id": tenant_id, "def_id": definicao_id, "now": now},
            )
    finally:
        await _limpar(admin_session, tenant_id)


# ============================================================================
# Task 2 — engine generalizado (providers de contexto por entidade)
# ============================================================================
#
# DSL mínimo, reaproveitado pelos quatro testes de (a) a (d) do Step 1: um
# ciclo simples registrada -> em_apuracao -> concluida (final), com `sla_dias`
# acrescentado ad-hoc no teste de SLA (Step 3).

DSL_OCORRENCIA = {
    "estado_inicial": "registrada",
    "estados": [
        {"slug": "registrada"},
        {"slug": "em_apuracao"},
        {"slug": "concluida", "final": True},
    ],
    "transicoes": [
        {"de": "registrada", "para": "em_apuracao", "label": "Iniciar apuração"},
        {"de": "em_apuracao", "para": "concluida", "label": "Concluir"},
    ],
}


async def _definicao_ocorrencia(engine, tenant_id: int, *, dsl: dict | None = None) -> WorkflowDefinition:
    async with _sm(engine)() as db:
        wf = WorkflowDefinition(
            tenant_id=tenant_id,
            slug=f"wf-oc-{uuid.uuid4().hex[:8]}",
            nome="WF Ocorrência de teste (engine)",
            versao=1,
            ativo=True,
            dsl=dsl or DSL_OCORRENCIA,
            criado_em=datetime.utcnow(),
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)
        return wf


async def _ocorrencia(engine, tenant_id: int) -> int:
    tipo = await _tipo(engine, tenant_id)
    id_emp, _id_perm = await _operadores(engine, tenant_id)
    async with _sm(engine)() as db:
        oc = await tr.registrar_ocorrencia(
            db, tenant_id=tenant_id,
            payload=OcorrenciaCreate(
                id_tipo=tipo.id, origem="fiscalizacao",
                data_fato=date.today(), descricao="Fato de teste do engine P8",
                id_empresa=id_emp,
            ),
            id_usuario=None,
        )
    return oc.id


async def _remover_instancia_auto_criada(engine, tenant_id: int, oc_id: int) -> None:
    """A partir da Task 3, `registrar_ocorrencia` (chamado por `_ocorrencia`
    acima) já cria a `WorkflowInstance` automaticamente em
    `transporte-ocorrencia`. Os testes da seção Task 2 abaixo testam o
    engine genérico com um DSL AD HOC (`_definicao_ocorrencia`) e chamam
    `iniciar()` à mão — precisam da entidade "limpa" (sem instância prévia),
    senão `iniciar()` rejeita por já existir instância ativa para o par
    `('ocorrencia', oc_id)`."""
    async with _sm(engine)() as db:
        await db.execute(
            text(
                "DELETE FROM aprimora_py.workflow_instance "
                "WHERE tenant_id = :t AND entidade_tipo = 'ocorrencia' "
                "AND entidade_id = :id"
            ),
            {"t": tenant_id, "id": oc_id},
        )
        await db.commit()


async def _limpar_engine(engine, tenant_id: int) -> None:
    """Mesma ordem de `_encerrar_arreio` (test_transporte_p5_2_atendimento),
    acrescida das tabelas de workflow e ocorrência que este arquivo grava —
    `provisionar_tenant` cria usuário/unidade/tipo_manifestante/grupo, e sem
    apagá-los antes o DELETE do tenant esbarra em FK."""
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.workflow_sla_alerta WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.workflow_transicao_log WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.workflow_instance WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.workflow_definition WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ocorrencia_andamento WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ocorrencia WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ocorrencia_tipo WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.empresa WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.permissionario WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


async def test_compute_contexto_ocorrencia_usa_provider_sem_tocar_processo(admin_engine):
    """(a) `compute_contexto` de instância `entidade_tipo='ocorrencia'` devolve
    as chaves do provider — sem carregar `Processo` (a instância nasce com
    `id_processo=NULL`; se o engine ainda tentasse `_load_processo`, o teste
    quebraria com `WorkflowEngineError('Processo não encontrado')`)."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)
        await _remover_instancia_auto_criada(admin_engine, t.id, oc_id)
        wf = await _definicao_ocorrencia(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            inst = await iniciar(
                db, tenant_id=t.id, id_workflow_definition=wf.id,
                entidade_tipo="ocorrencia", entidade_id=oc_id, usuario_id=None,
            )
            contexto = await compute_contexto(db, inst)

        assert contexto["situacao_atual"] == "registrada"
        assert contexto["origem"] == "fiscalizacao"
        assert contexto["tem_alvo"] is True
        # `registrar_ocorrencia` já grava o primeiro ato da trilha (registro).
        assert contexto["qtd_andamentos"] == 1
        assert isinstance(contexto["dias_aberta"], int)
        assert "id_tipo" in contexto
        assert contexto["estado_atual"] == "registrada"
        assert contexto["estado_anterior"] is None
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_iniciar_com_estado_inicial_explicito_sobrepoe_dsl(admin_engine):
    """(b) `estado_inicial` explícito cria a instância nesse estado (não no
    `estado_inicial` do DSL) — a instanciação lazy no estado corrente."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)
        await _remover_instancia_auto_criada(admin_engine, t.id, oc_id)
        wf = await _definicao_ocorrencia(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            inst = await iniciar(
                db, tenant_id=t.id, id_workflow_definition=wf.id,
                entidade_tipo="ocorrencia", entidade_id=oc_id, usuario_id=None,
                estado_inicial="em_apuracao",
            )
        assert inst.estado_atual == "em_apuracao"
        assert inst.entidade_tipo == "ocorrencia"
        assert inst.entidade_id == oc_id
        assert inst.id_processo is None
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_iniciar_com_estado_inicial_inexistente_falha(admin_engine):
    """(c) `estado_inicial` que não existe nos `estados` do DSL → erro."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)
        await _remover_instancia_auto_criada(admin_engine, t.id, oc_id)
        wf = await _definicao_ocorrencia(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            with pytest.raises(WorkflowEngineError):
                await iniciar(
                    db, tenant_id=t.id, id_workflow_definition=wf.id,
                    entidade_tipo="ocorrencia", entidade_id=oc_id, usuario_id=None,
                    estado_inicial="nao_existe",
                )
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_executar_transicao_em_ocorrencia_transiciona_e_loga(admin_engine):
    """(d) `executar_transicao` numa instância de ocorrência transiciona e
    grava log, sem tentar carregar processo (bloco de unidade responsável só
    roda para `entidade_tipo == 'processo'`)."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)
        await _remover_instancia_auto_criada(admin_engine, t.id, oc_id)
        wf = await _definicao_ocorrencia(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            inst = await iniciar(
                db, tenant_id=t.id, id_workflow_definition=wf.id,
                entidade_tipo="ocorrencia", entidade_id=oc_id, usuario_id=None,
            )
            inst_id = inst.id

        async with _sm(admin_engine)() as db:
            inst = await db.get(WorkflowInstance, inst_id)
            inst = await executar_transicao(db, inst, para="em_apuracao", usuario_id=None)
        assert inst.estado_atual == "em_apuracao"

        async with _sm(admin_engine)() as db:
            logs = (
                await db.execute(
                    select(WorkflowTransicaoLog).where(
                        WorkflowTransicaoLog.id_workflow_instance == inst_id,
                    )
                )
            ).scalars().all()
        assert len(logs) == 1
        assert logs[0].estado_de == "registrada"
        assert logs[0].estado_para == "em_apuracao"
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_sla_ocorrencia_gera_alerta_sem_tocar_processo(admin_engine):
    """Step 3: instância de ocorrência com `sla_dias` estourado gera
    `WorkflowSlaAlerta` sem erro — `_notificar_alerta_sla` (100% processo) só
    é chamada para `entidade_tipo == 'processo'`."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)
        await _remover_instancia_auto_criada(admin_engine, t.id, oc_id)
        dsl_sla = {
            **DSL_OCORRENCIA,
            "estados": [
                {"slug": "registrada", "sla_dias": 1},
                {"slug": "em_apuracao"},
                {"slug": "concluida", "final": True},
            ],
        }
        wf = await _definicao_ocorrencia(admin_engine, t.id, dsl=dsl_sla)
        async with _sm(admin_engine)() as db:
            inst = await iniciar(
                db, tenant_id=t.id, id_workflow_definition=wf.id,
                entidade_tipo="ocorrencia", entidade_id=oc_id, usuario_id=None,
            )
            inst_id = inst.id
            # Backdate: `compute_dias_no_estado` conta a partir de
            # `iniciada_em`, e a instância acabou de nascer (0 dias).
            await db.execute(
                text(
                    "UPDATE aprimora_py.workflow_instance "
                    "SET iniciada_em = iniciada_em - interval '2 days' "
                    "WHERE id = :id"
                ),
                {"id": inst_id},
            )
            await db.commit()

        verificadas, criados = await _processar_tenant(_sm(admin_engine), t.id)
        assert verificadas == 1
        assert criados == 1

        async with _sm(admin_engine)() as db:
            alerta = (
                await db.execute(
                    select(WorkflowSlaAlerta).where(
                        WorkflowSlaAlerta.id_workflow_instance == inst_id,
                    )
                )
            ).scalar_one_or_none()
        assert alerta is not None
        assert alerta.estado == "registrada"
    finally:
        await _limpar_engine(admin_engine, t.id)


# ============================================================================
# Task 3 — ocorrências comandadas pelo workflow (sementes + fachadas, piloto)
# ============================================================================
#
# Reaproveita `_ocorrencia`/`_limpar_engine` da Task 2. `_ocorrencia` cria a
# ocorrência via `tr.registrar_ocorrencia` — que, a partir desta task, já
# ganha `WorkflowInstance` automaticamente (sem chamar o engine à mão).


async def test_registrar_ocorrencia_cria_instancia_ativa_em_registrada(admin_engine):
    """(a) `registrar_ocorrencia` cria a instância ativa `('ocorrencia', id)`
    já em `registrada` — sem chamada explícita ao engine."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            inst = (
                await db.execute(
                    select(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == t.id,
                        WorkflowInstance.entidade_tipo == "ocorrencia",
                        WorkflowInstance.entidade_id == oc_id,
                    )
                )
            ).scalar_one()
        assert inst.ativa is True
        assert inst.estado_atual == "registrada"
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_fluxo_completo_registrar_iniciar_decidir_procedente_sincroniza(admin_engine):
    """(b) `situacao` da ocorrência e `estado_atual` da instância andam juntos
    em cada passo; o log acumula as 2 transições; a instância finaliza."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)

        async with _sm(admin_engine)() as db:
            inst = (
                await db.execute(
                    select(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == t.id,
                        WorkflowInstance.entidade_tipo == "ocorrencia",
                        WorkflowInstance.entidade_id == oc_id,
                    )
                )
            ).scalar_one()
        inst_id = inst.id
        assert inst.estado_atual == "registrada"

        async with _sm(admin_engine)() as db:
            oc = await tr.iniciar_apuracao(
                db, tenant_id=t.id, ocorrencia_id=oc_id, id_usuario=None,
            )
        assert oc.situacao == "em_apuracao"
        async with _sm(admin_engine)() as db:
            inst = await db.get(WorkflowInstance, inst_id)
        assert inst.estado_atual == "em_apuracao"

        async with _sm(admin_engine)() as db:
            oc = await tr.decidir_ocorrencia(
                db, tenant_id=t.id, ocorrencia_id=oc_id,
                resultado="procedente", parecer="Confirmado", id_usuario=None,
            )
        assert oc.situacao == "procedente"

        async with _sm(admin_engine)() as db:
            inst = await db.get(WorkflowInstance, inst_id)
            logs = (
                await db.execute(
                    select(WorkflowTransicaoLog).where(
                        WorkflowTransicaoLog.id_workflow_instance == inst_id,
                    )
                )
            ).scalars().all()
        assert inst.estado_atual == "procedente"
        assert inst.ativa is False
        assert len(logs) == 2
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_ocorrencia_de_estoque_sem_instancia_ganha_workflow_lazy(admin_engine):
    """(c) Ocorrência criada direto no banco (sem instância — simulando dado
    de antes do P8) sofre `iniciar_apuracao`: a instância nasce lazy no
    ESTADO CORRENTE da ocorrência (`registrada`, não algum default do DSL) e
    já transiciona no mesmo ato — UMA linha de log, estado final
    `em_apuracao`."""
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _id_perm = await _operadores(admin_engine, t.id)
        agora = datetime.utcnow()
        async with admin_engine.begin() as conn:
            res = await conn.execute(
                text(
                    "INSERT INTO transporte_regulado.ocorrencia "
                    "(tenant_id, id_tipo, origem, data_fato, descricao, "
                    " id_empresa, situacao, criado_em, excluido) "
                    "VALUES (:t, :tipo, 'fiscalizacao', :data, "
                    " 'Ocorrência de estoque (sem instância)', :emp, "
                    " 'registrada', :agora, false) RETURNING id"
                ),
                {
                    "t": t.id, "tipo": tipo.id, "data": date.today(),
                    "emp": id_emp, "agora": agora,
                },
            )
            oc_id = res.scalar_one()

        async with _sm(admin_engine)() as db:
            nenhuma = (
                await db.execute(
                    select(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == t.id,
                        WorkflowInstance.entidade_tipo == "ocorrencia",
                        WorkflowInstance.entidade_id == oc_id,
                    )
                )
            ).first()
        assert nenhuma is None

        async with _sm(admin_engine)() as db:
            oc = await tr.iniciar_apuracao(
                db, tenant_id=t.id, ocorrencia_id=oc_id, id_usuario=None,
            )
        assert oc.situacao == "em_apuracao"

        async with _sm(admin_engine)() as db:
            inst = (
                await db.execute(
                    select(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == t.id,
                        WorkflowInstance.entidade_tipo == "ocorrencia",
                        WorkflowInstance.entidade_id == oc_id,
                    )
                )
            ).scalar_one()
            logs = (
                await db.execute(
                    select(WorkflowTransicaoLog).where(
                        WorkflowTransicaoLog.id_workflow_instance == inst.id,
                    )
                )
            ).scalars().all()
        assert inst.estado_atual == "em_apuracao"
        assert len(logs) == 1
        assert logs[0].estado_de == "registrada"
        assert logs[0].estado_para == "em_apuracao"
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_decidir_procedente_409_quando_dsl_do_tenant_nao_permite(admin_engine):
    """(d) Tenant edita a própria definição removendo a transição
    `decidir_procedente` — `decidir_ocorrencia` responde 409 com mensagem
    citando slug, estado destino e estado de origem."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            await tr.iniciar_apuracao(
                db, tenant_id=t.id, ocorrencia_id=oc_id, id_usuario=None,
            )

        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE aprimora_py.workflow_definition SET dsl = jsonb_set("
                    "  dsl, '{transicoes}', "
                    "  (SELECT jsonb_agg(elem) FROM jsonb_array_elements(dsl->'transicoes') elem "
                    "   WHERE elem->>'label' != 'decidir_procedente')"
                    ") WHERE tenant_id = :t AND slug = 'transporte-ocorrencia'"
                ),
                {"t": t.id},
            )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=oc_id,
                    resultado="procedente", parecer="Confirmado", id_usuario=None,
                )
        assert e.value.status_code == 409
        msg = str(e.value.detail)
        assert "transporte-ocorrencia" in msg
        assert "procedente" in msg
        assert "em_apuracao" in msg
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_decidir_a_partir_de_registrada_409_transicao_nao_existe(admin_engine):
    """(e) Decidir sem antes iniciar apuração: `registrada -> improcedente`
    não existe no DSL, 409 vindo do engine (a validação antiga de service
    `situacao != 'em_apuracao'` saiu)."""
    t = await _provisionar(admin_engine)
    try:
        oc_id = await _ocorrencia(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=oc_id,
                    resultado="improcedente", parecer="Direto", id_usuario=None,
                )
        assert e.value.status_code == 409
    finally:
        await _limpar_engine(admin_engine, t.id)


async def test_definicao_lazy_criada_com_slug_transporte_ocorrencia(admin_engine):
    """(f) Tenant sem nenhuma definição: o primeiro ato cria uma
    `WorkflowDefinition` com `slug='transporte-ocorrencia'`, versão 1, ativa."""
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            nenhuma = (
                await db.execute(
                    select(WorkflowDefinition).where(
                        WorkflowDefinition.tenant_id == t.id,
                        WorkflowDefinition.slug == "transporte-ocorrencia",
                    )
                )
            ).first()
        assert nenhuma is None

        await _ocorrencia(admin_engine, t.id)

        async with _sm(admin_engine)() as db:
            wf = (
                await db.execute(
                    select(WorkflowDefinition).where(
                        WorkflowDefinition.tenant_id == t.id,
                        WorkflowDefinition.slug == "transporte-ocorrencia",
                    )
                )
            ).scalar_one()
        assert wf.ativo is True
        assert wf.versao == 1
        assert wf.dsl.get("estado_inicial") == "registrada"
    finally:
        await _limpar_engine(admin_engine, t.id)


# ============================================================================
# Task 4 — alvará comandado pelo workflow (semente `transporte-alvara`, P8 D2)
# ============================================================================
#
# `renovar_alvara` (Fase C) segue exigindo `data_validade` vencida — os
# alvarás de teste aqui nascem sempre vencidos para poderem ser renovados.

HOJE_ALVARA = date.today()


async def _alvara(
    engine, tenant_id: int, *, id_permissionario=None, id_empresa=None,
    data_validade=None, numero=None,
):
    async with _sm(engine)() as db:
        return await tr.criar_alvara(
            db,
            tenant_id=tenant_id,
            payload=AlvaraCreate(
                numero_alvara=numero or f"ALV-P8-{uuid.uuid4().hex[:8]}",
                data_validade=data_validade,
                tipo_servico="taxi",
                id_permissionario=id_permissionario,
                id_empresa=id_empresa,
            ),
        )


async def _limpar_alvara_e_engine(engine, tenant_id: int) -> None:
    """`_limpar_engine` (Task 2/3) não conhece `alvara` nem `recadastramento_*`
    (só o teste (c), com convocação suspensa, usa a segunda) — sem apagá-las
    antes, o DELETE de permissionario/empresa dentro de `_limpar_engine`
    esbarra na FK. Apagar tabela sem linha nenhuma é no-op, seguro para os
    outros testes desta seção."""
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM transporte_regulado.recadastramento_decisao WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.recadastramento_marca WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.recadastramento_item WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.recadastramento_convocacao WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.recadastramento_ciclo WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.alvara WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()
    await _limpar_engine(engine, tenant_id)


async def test_criar_alvara_cria_instancia_ativa_em_vigente(admin_engine):
    """(a) `criar_alvara` cria a instância ativa `('alvara', id)` já em
    `vigente` — `situacao` do alvará espelha o mesmo slug do DSL."""
    t = await _provisionar(admin_engine)
    try:
        id_emp, _id_perm = await _operadores(admin_engine, t.id)
        a = await _alvara(admin_engine, t.id, id_empresa=id_emp)
        assert a.situacao == "vigente"

        async with _sm(admin_engine)() as db:
            inst = (
                await db.execute(
                    select(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == t.id,
                        WorkflowInstance.entidade_tipo == "alvara",
                        WorkflowInstance.entidade_id == a.id,
                    )
                )
            ).scalar_one()
        assert inst.ativa is True
        assert inst.estado_atual == "vigente"
    finally:
        await _limpar_alvara_e_engine(admin_engine, t.id)


async def test_renovar_alvara_transiciona_origem_e_cria_filho_vigente(admin_engine):
    """(b) `renovar_alvara` transiciona a instância de ORIGEM para `renovado`
    (inativa) e cria alvará + instância NOVOS, próprios, em `vigente`."""
    t = await _provisionar(admin_engine)
    try:
        id_emp, _id_perm = await _operadores(admin_engine, t.id)
        original = await _alvara(
            admin_engine, t.id, id_empresa=id_emp,
            data_validade=HOJE_ALVARA - timedelta(days=1),
        )
        async with _sm(admin_engine)() as db:
            novo = await tr.renovar_alvara(
                db, tenant_id=t.id, alvara_id=original.id,
                payload=AlvaraRenovarInput(data_validade=HOJE_ALVARA + timedelta(days=365)),
            )
        assert novo.id != original.id
        assert novo.renovado_de == original.id
        assert novo.situacao == "vigente"

        async with _sm(admin_engine)() as db:
            origem_recarregada = await tr.obter_alvara(
                db, tenant_id=t.id, alvara_id=original.id
            )
            inst_origem = (
                await db.execute(
                    select(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == t.id,
                        WorkflowInstance.entidade_tipo == "alvara",
                        WorkflowInstance.entidade_id == original.id,
                    )
                )
            ).scalar_one()
            inst_filho = (
                await db.execute(
                    select(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == t.id,
                        WorkflowInstance.entidade_tipo == "alvara",
                        WorkflowInstance.entidade_id == novo.id,
                    )
                )
            ).scalar_one()
        assert origem_recarregada.situacao == "renovado"
        assert inst_origem.ativa is False
        assert inst_origem.estado_atual == "renovado"
        assert inst_filho.ativa is True
        assert inst_filho.estado_atual == "vigente"
        assert inst_filho.id != inst_origem.id
    finally:
        await _limpar_alvara_e_engine(admin_engine, t.id)


async def test_renovar_alvara_titular_suspenso_409_mensagem_fase_c(admin_engine):
    """(c) Titular com convocação suspensa continua barrado pelo gate da Fase
    C ANTES da transição — MESMA mensagem ("reativação"), sem edição naquele
    teste (`tests/test_transporte_fase_c.py`)."""
    t = await _provisionar(admin_engine)
    try:
        perm = await _permissionario(admin_engine, t.id)
        ciclo = await _ciclo_vencido(admin_engine, t.id)
        _c, conv = await _convocacao(admin_engine, t.id, perm, ciclo=ciclo)
        uid = await _um_usuario(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            await tr.suspender_convocacao(
                db, tenant_id=t.id, convocacao_id=conv.id,
                payload=_parecer(), usuario_id=uid,
            )

        alvara = await _alvara(
            admin_engine, t.id, id_permissionario=perm.id,
            data_validade=HOJE_ALVARA - timedelta(days=1),
        )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.renovar_alvara(
                    db, tenant_id=t.id, alvara_id=alvara.id,
                    payload=AlvaraRenovarInput(data_validade=HOJE_ALVARA + timedelta(days=365)),
                )
        assert e.value.status_code == 409
        assert "reativação" in e.value.detail
    finally:
        await _limpar_alvara_e_engine(admin_engine, t.id)


async def test_revogar_alvara_com_motivo(admin_engine):
    """(d) Revoga com motivo: `situacao='revogado'`, instância finalizada, log
    com o motivo no `contexto_snapshot` — e `observacoes` prefixado."""
    t = await _provisionar(admin_engine)
    try:
        id_emp, _id_perm = await _operadores(admin_engine, t.id)
        alvara = await _alvara(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            revogado = await tr.revogar_alvara(
                db, tenant_id=t.id, alvara_id=alvara.id,
                motivo="Irregularidade constatada em vistoria",
                usuario_id=None,
            )
        assert revogado.situacao == "revogado"
        assert revogado.observacoes == "Revogado: Irregularidade constatada em vistoria"

        async with _sm(admin_engine)() as db:
            inst = (
                await db.execute(
                    select(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == t.id,
                        WorkflowInstance.entidade_tipo == "alvara",
                        WorkflowInstance.entidade_id == alvara.id,
                    )
                )
            ).scalar_one()
            log = (
                await db.execute(
                    select(WorkflowTransicaoLog)
                    .where(WorkflowTransicaoLog.id_workflow_instance == inst.id)
                    .order_by(WorkflowTransicaoLog.executada_em.desc())
                )
            ).scalars().first()
        assert inst.ativa is False
        assert inst.estado_atual == "revogado"
        assert log.contexto_snapshot.get("motivo") == "Irregularidade constatada em vistoria"
    finally:
        await _limpar_alvara_e_engine(admin_engine, t.id)


async def test_http_revogar_sem_motivo_422(admin_engine):
    """(e) Payload sem `motivo` (schema `AlvaraRevogar`, `min_length=1`) →
    422 — a validação nunca chega ao service."""
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, t.id, ["transporte"])
            await s.commit()
        id_emp, _id_perm = await _operadores(admin_engine, t.id)
        alvara = await _alvara(admin_engine, t.id, id_empresa=id_emp)

        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                f"/api/v2/transporte-regulado/alvaras/{alvara.id}/revogar",
                json={"motivo": ""},
            )
        assert r.status_code == 422, r.text
    finally:
        await _limpar_alvara_e_engine(admin_engine, t.id)


async def test_renovar_alvara_revogado_409_dsl(admin_engine):
    """(f) Alvará já revogado: `revogado -> renovado` não existe no DSL —
    409 vindo do engine, não do gate da Fase C."""
    t = await _provisionar(admin_engine)
    try:
        id_emp, _id_perm = await _operadores(admin_engine, t.id)
        alvara = await _alvara(
            admin_engine, t.id, id_empresa=id_emp,
            data_validade=HOJE_ALVARA - timedelta(days=1),
        )
        async with _sm(admin_engine)() as db:
            await tr.revogar_alvara(
                db, tenant_id=t.id, alvara_id=alvara.id,
                motivo="Fiscalização", usuario_id=None,
            )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.renovar_alvara(
                    db, tenant_id=t.id, alvara_id=alvara.id,
                    payload=AlvaraRenovarInput(data_validade=HOJE_ALVARA + timedelta(days=365)),
                )
        assert e.value.status_code == 409
    finally:
        await _limpar_alvara_e_engine(admin_engine, t.id)


async def test_http_usuario_comum_revoga_alvara_200(admin_engine):
    """(g) POST `/alvaras/{id}/revogar` com payload de motivo → 200 para
    usuário comum com a transação `transporte_regulado`."""
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, t.id, ["transporte"])
            await s.commit()
        id_emp, _id_perm = await _operadores(admin_engine, t.id)
        alvara = await _alvara(admin_engine, t.id, id_empresa=id_emp)

        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                f"/api/v2/transporte-regulado/alvaras/{alvara.id}/revogar",
                json={"motivo": "Fiscalização flagrou irregularidade"},
            )
        assert r.status_code == 200, r.text
        assert r.json()["situacao"] == "revogado"
    finally:
        await _limpar_alvara_e_engine(admin_engine, t.id)
