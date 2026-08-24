"""Transporte P8 — Workflows avançados.

Task 1 (D1): `workflow_instance` deixa de ser exclusivo de `processo` e
ganha `entidade_tipo`/`entidade_id` polimórficos. O engine (`workflow_engine.py`)
é a Task 2 — este arquivo cobre só a migration 0095 + modelo.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import WorkflowDefinition, WorkflowInstance, WorkflowSlaAlerta, WorkflowTransicaoLog
from app.schemas.transporte_regulado import OcorrenciaCreate
from app.services import transporte_regulado as tr
from app.services import transporte_workflow  # noqa: F401 — registra os providers no import
from app.services.workflow_engine import (
    WorkflowEngineError,
    compute_contexto,
    executar_transicao,
    iniciar,
)
from app.tasks.verificar_sla_workflows import _processar_tenant
from tests.test_transporte_p5_2_atendimento import _provisionar, _sm
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
        async with db.begin():
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
