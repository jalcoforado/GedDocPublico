"""Integração Processo ↔ Workflow — Fase 20b.

Hooks que conectam o ciclo de vida do `Processo` (abertura, encaminhamento,
recebimento) com a engine de workflow. Tudo opt-in:

- `auto_iniciar_workflow_se_aplicavel(processo)`: se o `tipo_processo` do
  processo tem mapeamento em `tipo_processo_workflow`, busca o workflow
  ativo com aquele slug e cria uma `WorkflowInstance` no estado_inicial.
- `disparar_evento(processo, evento)`: busca a `WorkflowInstance` ATIVA do
  processo (se existir) e tenta executar a primeira transição saindo do
  estado atual cujo campo `evento` bate e cuja `condicao` é truthy.

**Falhas são silenciadas** (logadas em `workflow.integration`): o ciclo do
Processo NUNCA deve quebrar por causa do workflow. Workflow é uma camada
extra; processos que não têm workflow seguem normais.

Eventos suportados:
- `abertura`     — disparado logo após auto_iniciar (estado_inicial → ...).
- `encaminhamento` — disparado dentro de `acoes_processo.encaminhar`.
- `recebimento`  — disparado dentro de `acoes_processo.receber`.
- `manual`       — não disparado por hook; só via API `/transicao`.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Assunto,
    Processo,
    TipoProcessoWorkflow,
    WorkflowDefinition,
    WorkflowInstance,
)
from .workflow_dsl import WorkflowExprError, evaluate_expr
from .workflow_engine import (
    WorkflowEngineError,
    compute_contexto,
    executar_transicao,
    iniciar,
)

logger = logging.getLogger("workflow.integration")


async def _resolve_workflow_para_processo(
    db: AsyncSession, processo: Processo
) -> WorkflowDefinition | None:
    """Dado um Processo, encontra a WorkflowDefinition ATIVA mapeada
    para seu tipo_processo (via assunto.id_tipo_processo → tipo_processo_workflow).
    """
    row = (
        await db.execute(
            select(Assunto.id_tipo_processo)
            .where(
                Assunto.id == processo.id_assunto,
                Assunto.tenant_id == processo.tenant_id,
            )
        )
    ).first()
    if row is None or row[0] is None:
        return None
    id_tipo_processo = row[0]

    mapeamento = (
        await db.execute(
            select(TipoProcessoWorkflow).where(
                TipoProcessoWorkflow.tenant_id == processo.tenant_id,
                TipoProcessoWorkflow.id_tipo_processo == id_tipo_processo,
            )
        )
    ).scalar_one_or_none()
    if mapeamento is None:
        return None

    wf = (
        await db.execute(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.tenant_id == processo.tenant_id,
                WorkflowDefinition.slug == mapeamento.slug_workflow,
                WorkflowDefinition.ativo.is_(True),
            )
            .order_by(WorkflowDefinition.versao.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return wf


async def auto_iniciar_workflow_se_aplicavel(
    db: AsyncSession, processo: Processo, usuario_id: int | None
) -> WorkflowInstance | None:
    """Tenta auto-instanciar o workflow associado ao tipo_processo. Retorna
    a instance ou None. Falha silenciosamente.
    """
    try:
        wf = await _resolve_workflow_para_processo(db, processo)
        if wf is None:
            return None
        inst = await iniciar(
            db,
            tenant_id=processo.tenant_id,
            id_workflow_definition=wf.id,
            id_processo=processo.id,
            usuario_id=usuario_id,
        )
        logger.info(
            "workflow_auto_iniciado",
            extra={
                "processo_id": processo.id,
                "workflow_slug": wf.slug,
                "instance_id": inst.id,
            },
        )
        # Dispara evento "abertura" pra avançar do estado_inicial se houver transição auto
        await disparar_evento(db, processo, "abertura", usuario_id)
        # Recarrega instance (pode ter avançado de estado)
        await db.refresh(inst)
        return inst
    except WorkflowEngineError as e:
        logger.warning(
            "workflow_auto_iniciar_falhou",
            extra={"processo_id": processo.id, "erro": str(e)},
        )
        return None
    except Exception:
        logger.exception(
            "workflow_auto_iniciar_erro_inesperado",
            extra={"processo_id": processo.id},
        )
        return None


async def validar_acao_strict(
    db: AsyncSession,
    processo: Processo,
    *,
    acao: str,
    id_unidade_destino: int | None = None,
) -> tuple[bool, str | None]:
    """Em strict mode, valida se a ação solicitada respeita o workflow ativo.

    `acao`: "encaminhar" | "receber" | "cancelar_encaminhamento" | "arquivar"

    Regras:
    - Se processo não tem instance ativa OU o workflow não é strict → libera (ok=True).
    - Se acao=encaminhar: deve existir transição saindo do estado atual com
      `evento in (encaminhamento, manual)` cujo estado destino tem
      `id_unidade_responsavel == id_unidade_destino`. Se estado destino tem
      `id_unidade_responsavel=null` (livre), libera.
    - Se acao=receber: deve existir transição com `evento=recebimento` saindo
      do estado atual.
    - Se acao=cancelar_encaminhamento: bloqueado se o encaminhamento veio de
      transição automática do workflow (auditoria mostra).
    - Se acao=arquivar: bloqueado a menos que `estado_atual` seja final.

    Retorna `(ok, motivo_bloqueio)`. Quando ok=False, `motivo` é a mensagem
    pra incluir no HTTP 400.
    """
    inst = (
        await db.execute(
            select(WorkflowInstance).where(
                WorkflowInstance.id_processo == processo.id,
                WorkflowInstance.tenant_id == processo.tenant_id,
                WorkflowInstance.ativa.is_(True),
            )
        )
    ).scalar_one_or_none()
    if inst is None:
        return True, None

    wf = (
        await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == inst.id_workflow_definition,
                WorkflowDefinition.tenant_id == processo.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if wf is None or not wf.dsl.get("strict", False):
        return True, None

    estado_atual = inst.estado_atual
    estados = {e["slug"]: e for e in wf.dsl.get("estados", [])}
    transicoes = wf.dsl.get("transicoes", [])

    if acao == "encaminhar":
        # Procura transição manual/encaminhamento saindo do estado atual
        # cujo destino aceita o id_unidade_destino solicitado.
        for t in transicoes:
            if t.get("de") != estado_atual:
                continue
            if t.get("evento", "manual") not in ("manual", "encaminhamento"):
                continue
            dest_estado = estados.get(t.get("para", ""))
            if dest_estado is None:
                continue
            unid_esperada = dest_estado.get("id_unidade_responsavel")
            if unid_esperada is None or id_unidade_destino is None:
                return True, None
            if int(unid_esperada) == int(id_unidade_destino):
                return True, None
        return False, (
            f"Workflow strict: estado '{estado_atual}' não permite encaminhamento "
            f"para essa unidade. Use uma das transições disponíveis ou peça override "
            f"a um super-usuário."
        )

    if acao == "receber":
        for t in transicoes:
            if t.get("de") != estado_atual:
                continue
            if t.get("evento", "manual") == "recebimento":
                return True, None
        # Sem transição de recebimento configurada — libera (o recebimento físico
        # não modifica estado de workflow nesse caso, mas tampouco é ofensa).
        return True, None

    if acao == "cancelar_encaminhamento":
        # Cancelar é sempre permitido em strict (representa rollback humano).
        # Caveat: o encaminhamento gerado por auto-transição cria movimentação
        # ligada ao log — frontend pode mostrar warning.
        return True, None

    if acao == "arquivar":
        estado = estados.get(estado_atual, {})
        if estado.get("final", False):
            return True, None
        return False, (
            f"Workflow strict: processo está no estado '{estado_atual}' que não "
            f"é final. Conclua o fluxo antes de arquivar."
        )

    # Ação desconhecida — não bloqueia (defensivo)
    return True, None


async def disparar_evento(
    db: AsyncSession,
    processo: Processo,
    evento: str,
    usuario_id: int | None,
    contexto_extra: dict[str, Any] | None = None,
) -> WorkflowInstance | None:
    """Busca instance ATIVA do processo, procura transição saindo do estado
    atual cujo campo `evento` bate e cuja condição é truthy. Executa a
    primeira que casa. Retorna a instance atualizada ou None se nada
    aplicável.
    """
    inst = (
        await db.execute(
            select(WorkflowInstance).where(
                WorkflowInstance.id_processo == processo.id,
                WorkflowInstance.tenant_id == processo.tenant_id,
                WorkflowInstance.ativa.is_(True),
            )
        )
    ).scalar_one_or_none()
    if inst is None:
        return None

    wf = (
        await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == inst.id_workflow_definition,
                WorkflowDefinition.tenant_id == processo.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if wf is None:
        logger.warning(
            "workflow_definition_ausente",
            extra={"instance_id": inst.id, "wf_def_id": inst.id_workflow_definition},
        )
        return None

    contexto = await compute_contexto(db, inst, contexto_extra)
    candidatas = [
        t for t in wf.dsl.get("transicoes", [])
        if t.get("de") == inst.estado_atual
        and t.get("evento", "manual") == evento
    ]
    # Filtra por condição truthy
    selecionada = None
    for t in candidatas:
        cond = t.get("condicao")
        if cond is None or not str(cond).strip():
            selecionada = t
            break
        try:
            if bool(evaluate_expr(cond, contexto)):
                selecionada = t
                break
        except WorkflowExprError:
            continue

    if selecionada is None:
        return None

    try:
        inst = await executar_transicao(
            db,
            inst,
            para=selecionada["para"],
            usuario_id=usuario_id,
            contexto_extra=contexto_extra,
        )
        logger.info(
            "workflow_transicao_automatica",
            extra={
                "instance_id": inst.id,
                "evento": evento,
                "para": selecionada["para"],
            },
        )
        return inst
    except WorkflowEngineError as e:
        logger.warning(
            "workflow_transicao_automatica_falhou",
            extra={"instance_id": inst.id, "evento": evento, "erro": str(e)},
        )
        return None
    except Exception:
        logger.exception(
            "workflow_transicao_automatica_erro_inesperado",
            extra={"instance_id": inst.id, "evento": evento},
        )
        return None
