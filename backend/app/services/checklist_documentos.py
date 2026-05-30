"""Checklist documental por processo (PR 4c).

Deriva o checklist em runtime de `servico.documentos_exigidos` + anexos do
processo agrupados por `anexo.documento_exigido_key`. Sem tabela nova. Processo
sem `id_servico` ou serviço sem documentos exigidos → status
`sem_documentos_exigidos` (não quebra).

PR 4d: anexa `complementacao_aberta` ao response (informativo). O
`status_documental` continua sendo um dos quatro do PR 4c — D-STATUS.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Anexo, AnexoProcesso, Processo, Servico
from ..schemas.checklist_documentos import (
    ChecklistAnexo,
    ChecklistDocumentosResponse,
    ChecklistItem,
    StatusDocumental,
)
from . import complementacao_documental as _comp_svc


def _calcular_status(itens: list[ChecklistItem]) -> tuple[StatusDocumental, int, int]:
    """Retorna (status, obrigatorios_total, obrigatorios_enviados)."""
    obrigatorios = [i for i in itens if i.obrigatorio]
    if not itens:
        return "sem_documentos_exigidos", 0, 0
    if not obrigatorios:
        # Só opcionais → nada a "faltar" — status final
        return "completo", 0, 0
    enviados = sum(1 for i in obrigatorios if i.enviado)
    if enviados == 0:
        st: StatusDocumental = "pendente"
    elif enviados < len(obrigatorios):
        st = "parcial"
    else:
        st = "completo"
    return st, len(obrigatorios), enviados


async def calcular_checklist(
    db: AsyncSession, *, processo_id: int, tenant_id: int
) -> ChecklistDocumentosResponse:
    """Carga o processo (tenant), resolve o serviço vinculado (se houver) e
    monta o checklist. 404 se processo fora do tenant ou excluído."""
    processo = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if processo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado"
        )

    # PR 4d — complementação aberta independe de status documental (D-STATUS).
    # Calculada uma vez aqui e usada em todos os retornos abaixo.
    aberta = await _comp_svc.obter_aberta(
        db, tenant_id=tenant_id, processo_id=processo.id
    )

    # Sem serviço vinculado → não há documentos exigidos.
    if processo.id_servico is None:
        return ChecklistDocumentosResponse(
            id_processo=processo.id,
            id_servico=None,
            status_documental="sem_documentos_exigidos",
            obrigatorios_total=0,
            obrigatorios_enviados=0,
            itens=[],
            complementacao_aberta=(
                await _comp_svc.montar_out(db, aberta) if aberta else None
            ),
        )

    servico = (
        await db.execute(
            select(Servico).where(
                Servico.id == processo.id_servico,
                Servico.tenant_id == tenant_id,
                Servico.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()

    documentos = (servico.documentos_exigidos if servico else None) or []
    if not documentos:
        return ChecklistDocumentosResponse(
            id_processo=processo.id,
            id_servico=processo.id_servico,
            status_documental="sem_documentos_exigidos",
            obrigatorios_total=0,
            obrigatorios_enviados=0,
            itens=[],
            complementacao_aberta=(
                await _comp_svc.montar_out(db, aberta) if aberta else None
            ),
        )

    # Anexos do processo agrupados por documento_exigido_key.
    anexos = (
        await db.execute(
            select(Anexo)
            .join(AnexoProcesso, AnexoProcesso.id_anexo == Anexo.id)
            .where(
                AnexoProcesso.id_processo == processo.id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
                Anexo.excluido.is_(False),
                Anexo.ativo.is_(True),
            )
        )
    ).scalars().all()
    por_key: dict[str, list[Anexo]] = {}
    for a in anexos:
        if a.documento_exigido_key:
            por_key.setdefault(a.documento_exigido_key, []).append(a)

    itens: list[ChecklistItem] = []
    for d in documentos:
        if not isinstance(d, dict) or not d.get("key"):
            # Defesa: item antigo sem key (não deveria ocorrer pós-0026).
            continue
        anexos_do_item = por_key.get(d["key"], [])
        itens.append(
            ChecklistItem(
                key=d["key"],
                nome=d.get("nome") or d["key"],
                obrigatorio=bool(d.get("obrigatorio", False)),
                descricao=d.get("descricao"),
                enviado=len(anexos_do_item) > 0,
                anexos=[
                    ChecklistAnexo(id_anexo=a.id, descricao=a.descricao)
                    for a in anexos_do_item
                ],
            )
        )

    status_doc, obrig_total, obrig_envs = _calcular_status(itens)

    # PR 4d — anexar complementação aberta (informativo; não muda status_doc).
    complementacao_out = None
    if aberta is not None:
        # Reusa o índice por_key já calculado acima como "anexos enviados".
        keys_enviadas = {k for k, lista in por_key.items() if lista}
        docs_idx = {
            d["key"]: d
            for d in documentos
            if isinstance(d, dict) and d.get("key")
        }
        complementacao_out = await _comp_svc.montar_out(
            db, aberta, docs_servico_idx=docs_idx, keys_enviadas=keys_enviadas
        )

    return ChecklistDocumentosResponse(
        id_processo=processo.id,
        id_servico=processo.id_servico,
        status_documental=status_doc,
        obrigatorios_total=obrig_total,
        obrigatorios_enviados=obrig_envs,
        itens=itens,
        complementacao_aberta=complementacao_out,
    )
