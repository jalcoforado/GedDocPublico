"""Providers de contexto do workflow para as entidades de transporte — P8 D1
(Task 2). Fachadas (`iniciar_workflow_de_ocorrencia` etc.) entram nas Tasks
3–5; este módulo cobre só o registro dos providers de `compute_contexto`.

Cada provider recebe `(db, instance)` e devolve o dicionário de variáveis
disponíveis para as condições do DSL — `estado_atual`/`estado_anterior` são
comuns a todo tipo e acrescentados pelo engine depois do provider (não
duplicar aqui, ver `workflow_engine.compute_contexto`).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Ocorrencia, OcorrenciaAndamento, WorkflowInstance
from ..models.transporte_regulado import Alvara
from .transporte_regulado import (
    estado_do_checklist,
    obter_convocacao,
    situacao_vistorias,
    titular_tem_convocacao_suspensa,
)
from .workflow_engine import WorkflowEngineError, register_context_provider


async def _contexto_ocorrencia(
    db: AsyncSession, instance: WorkflowInstance
) -> dict[str, Any]:
    oc = (
        await db.execute(
            select(Ocorrencia).where(
                Ocorrencia.id == instance.entidade_id,
                Ocorrencia.tenant_id == instance.tenant_id,
                Ocorrencia.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if oc is None:
        raise WorkflowEngineError("Ocorrência não encontrada")

    dias_aberta = max(0, (datetime.utcnow() - oc.criado_em).days)
    qtd_andamentos = (
        await db.execute(
            select(func.count(OcorrenciaAndamento.id)).where(
                OcorrenciaAndamento.id_ocorrencia == oc.id,
                OcorrenciaAndamento.tenant_id == instance.tenant_id,
                OcorrenciaAndamento.excluido.is_(False),
            )
        )
    ).scalar_one() or 0

    return {
        "dias_aberta": dias_aberta,
        "origem": oc.origem,
        "id_tipo": oc.id_tipo,
        "tem_alvo": bool(oc.id_permissionario or oc.id_empresa or oc.id_veiculo),
        "qtd_andamentos": int(qtd_andamentos),
        "situacao_atual": oc.situacao,
    }


async def _contexto_alvara(
    db: AsyncSession, instance: WorkflowInstance
) -> dict[str, Any]:
    alv = (
        await db.execute(
            select(Alvara).where(
                Alvara.id == instance.entidade_id,
                Alvara.tenant_id == instance.tenant_id,
                Alvara.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if alv is None:
        raise WorkflowEngineError("Alvará não encontrado")

    if alv.data_validade is None:
        # Sem validade cadastrada não é "vence amanhã" — 9999 sinaliza ao DSL
        # que não há prazo a vigiar, em vez de um número pequeno arbitrário.
        dias_para_vencer = 9999
    else:
        dias_para_vencer = (alv.data_validade - date.today()).days

    titular_suspenso = await titular_tem_convocacao_suspensa(
        db,
        tenant_id=instance.tenant_id,
        id_permissionario=alv.id_permissionario,
        id_empresa=alv.id_empresa,
    )

    return {
        "dias_para_vencer": dias_para_vencer,
        "tipo_servico": alv.tipo_servico,
        "eh_renovacao": alv.renovado_de is not None,
        "titular_suspenso": titular_suspenso,
    }


async def _contexto_convocacao(
    db: AsyncSession, instance: WorkflowInstance
) -> dict[str, Any]:
    conv = await obter_convocacao(
        db, tenant_id=instance.tenant_id, convocacao_id=instance.entidade_id
    )
    dias_para_prazo = (conv.prazo - date.today()).days

    itens = await estado_do_checklist(
        db, tenant_id=instance.tenant_id, convocacao_id=conv.id
    )
    checklist_completo = all(
        i["marcado"] is True for i in itens if i["obrigatorio"]
    )

    vistorias = await situacao_vistorias(db, tenant_id=instance.tenant_id, conv=conv)

    return {
        "dias_para_prazo": dias_para_prazo,
        "situacao_atual": conv.situacao,
        "checklist_completo": checklist_completo,
        # `condicional` não conta — só `situacao_vistorias` (que exige
        # `resultado == "aprovado"`) decide isso; nada aqui reimplementa.
        "tem_vistoria_aprovada": bool(vistorias["satisfeita"]),
    }


def registrar_providers() -> None:
    """Registra os providers de `ocorrencia`/`alvara`/`convocacao` no engine.

    Idempotente (reatribuição de chave de dict) — seguro chamar mais de uma
    vez, inclusive no import deste módulo (linha abaixo) e de novo em
    `main.py`, se algum dia for explicitado lá.
    """
    register_context_provider("ocorrencia", _contexto_ocorrencia)
    register_context_provider("alvara", _contexto_alvara)
    register_context_provider("convocacao", _contexto_convocacao)


# Registro no import — é o "padrão mais simples que funciona com o teste":
# qualquer teste/rota que importe este módulo (direta ou indiretamente via
# `app.main`) já enxerga os três providers em `CONTEXT_PROVIDERS`.
registrar_providers()
