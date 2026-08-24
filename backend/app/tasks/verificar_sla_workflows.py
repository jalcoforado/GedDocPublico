"""Task beat: detecta SLA estourado em workflows ativos — Fase 21.

Para cada tenant ativo, para cada WorkflowInstance ATIVA, verifica se o
estado atual tem `sla_dias` definido no DSL e se `dias_no_estado` excede.
Se sim, insere um `WorkflowSlaAlerta` (dedup por índice parcial único
em `(id_workflow_instance, estado) WHERE resolvido_em IS NULL`).

Falhas em um tenant individual NÃO interrompem o varrimento — a task
loga e continua. Notificações reais virão na Fase 17 (motor de
notificações); aqui o alerta nasce no banco e fica disponível para a UI
e para um futuro hook que dispare email/whatsapp.
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Processo,
    Tenant,
    Usuario,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowSlaAlerta,
)
from ..services.notificacoes import Destinatario, enviar as notificar_enviar
from ..services.workflow_engine import compute_dias_no_estado
from ._task_db import task_session_scope
from .celery_app import celery_app

logger = logging.getLogger("workflow.sla")


@celery_app.task(name="app.tasks.verificar_sla_workflows.run", bind=True)
def run(self, tenant_id: int | None = None) -> str:
    """tenant_id=None → varre todos os tenants ativos (modo beat).
    tenant_id=int → restringe a um tenant (dispatch manual / testes)."""
    return asyncio.run(_run_async(tenant_id))


def _estado_sla_map(dsl: dict) -> dict[str, int]:
    """Extrai {estado_slug: sla_dias} de estados que têm SLA definido."""
    out: dict[str, int] = {}
    for est in dsl.get("estados", []):
        sla = est.get("sla_dias")
        if isinstance(sla, int) and sla >= 1:
            out[est["slug"]] = sla
    return out


async def _processar_tenant(
    session_factory, tenant_id: int
) -> tuple[int, int]:
    """Retorna (instances_verificadas, alertas_criados)."""
    verificadas = 0
    criados = 0

    async with session_factory() as db:
        instances = (
            await db.execute(
                select(WorkflowInstance).where(
                    WorkflowInstance.tenant_id == tenant_id,
                    WorkflowInstance.ativa.is_(True),
                )
            )
        ).scalars().all()

        if not instances:
            return 0, 0

        # Cache de DSLs por definition_id para evitar refetch
        defs_ids = {i.id_workflow_definition for i in instances}
        defs = (
            await db.execute(
                select(WorkflowDefinition).where(WorkflowDefinition.id.in_(defs_ids))
            )
        ).scalars().all()
        dsl_por_def = {d.id: d.dsl for d in defs}

    # Para cada instance, abre sessão fresca (tenant_id setado via listener)
    for inst in instances:
        verificadas += 1
        dsl = dsl_por_def.get(inst.id_workflow_definition)
        if not dsl:
            continue
        sla_map = _estado_sla_map(dsl)
        sla_dias = sla_map.get(inst.estado_atual)
        if sla_dias is None:
            continue

        async with session_factory() as db:
            dias = await compute_dias_no_estado(db, inst)
            if dias < sla_dias:
                continue

            # INSERT ... ON CONFLICT DO NOTHING para deixar o índice
            # parcial único fazer o dedup atômico.
            stmt = pg_insert(WorkflowSlaAlerta).values(
                tenant_id=inst.tenant_id,
                id_workflow_instance=inst.id,
                estado=inst.estado_atual,
                sla_dias=sla_dias,
                dias_no_estado=dias,
                criado_em=datetime.utcnow(),
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["id_workflow_instance", "estado"],
                index_where=WorkflowSlaAlerta.resolvido_em.is_(None),
            )
            result = await db.execute(stmt)
            await db.commit()
            if not (result.rowcount and result.rowcount > 0):
                # Alerta já existia (dedup) — não notifica de novo
                continue
            criados += 1

            # Fase 17 — dispara notificação para os responsáveis pela
            # unidade atual do processo. Falha silenciosa: alerta já existe
            # no banco; notificação é cherry on top.
            #
            # P8 D1: `_notificar_alerta_sla` é 100% processo (carrega
            # `Processo`, resolve unidade pelo processo, grava
            # `link_url=/m/protocolo/processos/...`) — só chama para
            # `entidade_tipo == "processo"`. Para as demais entidades o
            # alerta já foi criado acima; notificação por tipo é trabalho das
            # Tasks 3–5, não desta guarda.
            if inst.entidade_tipo == "processo":
                try:
                    await _notificar_alerta_sla(db, inst, sla_dias, dias)
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "sla_notificacao_falhou",
                        extra={
                            "instance_id": inst.id,
                            "estado": inst.estado_atual,
                            "erro": str(e),
                        },
                    )

    return verificadas, criados


async def _notificar_alerta_sla(
    db: AsyncSession, instance: WorkflowInstance, sla_dias: int, dias: int
) -> None:
    """Cria notificações in-app para usuários alocados na unidade atual do
    processo associado ao workflow. Marca o alerta correspondente com
    `notificado_em`.
    """
    from sqlalchemy import select, update as sql_update

    # Resolve unidade atual do processo
    processo = (
        await db.execute(
            select(Processo).where(
                Processo.id == instance.id_processo,
                Processo.tenant_id == instance.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        return

    unidade_id = processo.id_local_atual or processo.id_unidade_proprietaria
    if unidade_id is None:
        return

    # Usuários cuja unidade primária é a do processo. Não buscamos lotações
    # secundárias (UsuarioUnidadeTrabalho) pra evitar spam — só os "donos".
    usuarios = (
        await db.execute(
            select(Usuario.id).where(
                Usuario.tenant_id == instance.tenant_id,
                Usuario.id_unidade_trabalho == unidade_id,
                Usuario.ativo.is_(True),
            )
        )
    ).all()
    if not usuarios:
        return

    destinatarios = [Destinatario(id_usuario=uid) for (uid,) in usuarios]
    await notificar_enviar(
        db,
        tenant_id=instance.tenant_id,
        destinatarios=destinatarios,
        # Todos os canais — `enviar()` filtra por preferência por canal (17b),
        # e por falta de endereço (email/telefone ausente). Email só sai se
        # SMTP_HOST configurado; whatsapp só se provider!=stub na prática útil.
        canais=["in_app", "email", "whatsapp"],
        tipo="sla_estourado",
        titulo=f"SLA estourado: {processo.numero_processo}",
        mensagem=(
            f"O processo {processo.numero_processo} está há {dias} dia(s) no "
            f"estado '{instance.estado_atual}' (SLA: {sla_dias} dia(s))."
        ),
        # Prefixo `/m/<slug>` desde a F4. Até aqui a notificação nascia com
        # `/processos/{id}`, que só funciona porque a F3 deixou um 308 vivo
        # para a URL antiga — e `notificacao.link_url` é registro histórico
        # PERMANENTE, então cada linha gravada assim é um salto extra e uma
        # URL velha na barra, para sempre. O redirect existe para o que já
        # foi gravado, não para o que ainda vai ser.
        link_url=f"/m/protocolo/processos/{processo.id}",
        payload={
            "id_processo": processo.id,
            "id_workflow_instance": instance.id,
            "estado": instance.estado_atual,
            "sla_dias": sla_dias,
            "dias_no_estado": dias,
        },
        prioridade="alta",
    )

    # Marca o alerta como notificado
    await db.execute(
        sql_update(WorkflowSlaAlerta)
        .where(
            WorkflowSlaAlerta.id_workflow_instance == instance.id,
            WorkflowSlaAlerta.tenant_id == instance.tenant_id,
            WorkflowSlaAlerta.estado == instance.estado_atual,
            WorkflowSlaAlerta.resolvido_em.is_(None),
            WorkflowSlaAlerta.notificado_em.is_(None),
        )
        .values(notificado_em=datetime.utcnow())
    )
    await db.commit()


async def _run_async(tenant_id_filter: int | None) -> str:
    # Sessão SEM tenant (super) só pra listar tenants ativos
    async with task_session_scope() as (_engine, raw_factory):
        async with raw_factory() as db:
            stmt = select(Tenant.id, Tenant.slug).where(Tenant.ativo.is_(True))
            if tenant_id_filter is not None:
                stmt = stmt.where(Tenant.id == tenant_id_filter)
            tenants = (await db.execute(stmt)).all()

    total_inst = 0
    total_alertas = 0
    erros: list[str] = []

    for tid, slug in tenants:
        try:
            async with task_session_scope(tenant_id=tid) as (_e, factory):
                v, c = await _processar_tenant(factory, tid)
                total_inst += v
                total_alertas += c
                logger.info(
                    "sla_check_tenant",
                    extra={
                        "tenant_id": tid,
                        "tenant_slug": slug,
                        "instances_verificadas": v,
                        "alertas_criados": c,
                    },
                )
        except Exception as e:  # noqa: BLE001
            erros.append(f"tenant {slug} ({tid}): {e}")
            logger.warning(
                "sla_check_falhou_tenant",
                extra={"tenant_id": tid, "tenant_slug": slug, "erro": str(e)},
            )
            logger.debug(traceback.format_exc())

    sumario = (
        f"SLA check concluído — {len(tenants)} tenant(s)\n"
        f"Instances verificadas: {total_inst}\n"
        f"Alertas novos criados: {total_alertas}\n"
    )
    if erros:
        sumario += "Erros:\n" + "\n".join(f"  - {e}" for e in erros) + "\n"
    return sumario
