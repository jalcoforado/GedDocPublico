"""Transporte P8 — Workflows avançados.

Task 1 (D1): `workflow_instance` deixa de ser exclusivo de `processo` e
ganha `entidade_tipo`/`entidade_id` polimórficos. O engine (`workflow_engine.py`)
é a Task 2 — este arquivo cobre só a migration 0095 + modelo.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
