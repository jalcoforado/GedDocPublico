"""Tree de unidades + KPIs por unidade — visualização organograma.

Devolve uma lista plana com os pais via `id_unidade_pai` — o frontend
monta a árvore. Cada unidade carrega 4 KPIs já calculados pra evitar
N+1 do client.

KPIs (snapshot now):
- processos_ativos: processos `ativo=true, excluido=false` cuja
  `id_local_atual` é a unidade
- usuarios: usuários ativos lotados na unidade
- sla_pendentes: alertas SLA não resolvidos cujo processo está lotado na
  unidade (join workflow_instance → processo → id_local_atual)
- tempo_medio_dias: média de dias `NOW() - movimentacao.data_hora_movimentacao`
  pra movimentações da unidade nos últimos 30 dias (entrega aproximada da
  "permanência média" — métricas mais precisas viriam de pares
  recebimento↔próximo encaminhamento, fora do escopo)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Movimentacao,
    Processo,
    UnidadeTrabalho,
    Usuario,
    WorkflowInstance,
    WorkflowSlaAlerta,
)


async def tree(db: AsyncSession, *, tenant_id: int) -> list[dict[str, Any]]:
    # 1) Todas as unidades do tenant (RLS já filtra por tenant_id em prod;
    # aqui mantemos predicado explícito pra dev sem RLS)
    unidades = (
        await db.execute(
            select(UnidadeTrabalho).where(UnidadeTrabalho.tenant_id == tenant_id)
        )
    ).scalars().all()
    if not unidades:
        return []

    uids = [u.id for u in unidades]

    # 2) Count processos ativos por id_local_atual
    proc_rows = (
        await db.execute(
            select(
                Processo.id_local_atual,
                func.count(Processo.id),
            )
            .where(
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
                Processo.ativo.is_(True),
                Processo.id_local_atual.in_(uids),
            )
            .group_by(Processo.id_local_atual)
        )
    ).all()
    proc_por_unid = {uid: int(cnt) for uid, cnt in proc_rows}

    # 3) Count usuários ativos por id_unidade_trabalho
    user_rows = (
        await db.execute(
            select(Usuario.id_unidade_trabalho, func.count(Usuario.id))
            .where(
                Usuario.tenant_id == tenant_id,
                Usuario.ativo.is_(True),
                Usuario.excluido.is_(False),
                Usuario.id_unidade_trabalho.in_(uids),
            )
            .group_by(Usuario.id_unidade_trabalho)
        )
    ).all()
    user_por_unid = {uid: int(cnt) for uid, cnt in user_rows}

    # 4) SLA pendentes — join Alerta → Instance → Processo → id_local_atual
    sla_rows = (
        await db.execute(
            select(Processo.id_local_atual, func.count(WorkflowSlaAlerta.id))
            .select_from(WorkflowSlaAlerta)
            .join(
                WorkflowInstance,
                WorkflowInstance.id == WorkflowSlaAlerta.id_workflow_instance,
            )
            .join(Processo, Processo.id == WorkflowInstance.id_processo)
            .where(
                WorkflowSlaAlerta.tenant_id == tenant_id,
                WorkflowSlaAlerta.resolvido_em.is_(None),
                Processo.id_local_atual.in_(uids),
            )
            .group_by(Processo.id_local_atual)
        )
    ).all()
    sla_por_unid = {uid: int(cnt) for uid, cnt in sla_rows}

    # 5) Tempo médio (30d) — AVG(NOW() - data_hora_movimentacao) por unidade
    desde_30d = datetime.utcnow() - timedelta(days=30)
    tm_rows = (
        await db.execute(
            select(
                Movimentacao.id_unidade_responsavel,
                func.avg(
                    func.extract(
                        "epoch", datetime.utcnow() - Movimentacao.data_hora_movimentacao
                    )
                    / 86400.0
                ),
            )
            .where(
                Movimentacao.tenant_id == tenant_id,
                Movimentacao.data_hora_movimentacao >= desde_30d,
                Movimentacao.id_unidade_responsavel.in_(uids),
            )
            .group_by(Movimentacao.id_unidade_responsavel)
        )
    ).all()
    tm_por_unid = {uid: float(media) if media is not None else None for uid, media in tm_rows}

    return [
        {
            "id": u.id,
            "id_unidade_pai": u.id_unidade_pai,
            "unidade_trabalho": u.unidade_trabalho,
            "sigla": u.sigla,
            "processos_ativos": proc_por_unid.get(u.id, 0),
            "usuarios": user_por_unid.get(u.id, 0),
            "sla_pendentes": sla_por_unid.get(u.id, 0),
            "tempo_medio_dias": tm_por_unid.get(u.id),
        }
        for u in unidades
    ]
