"""Checklist documental parametrizável (RF-VAL-01/06).

Itens de checklist (templates) por tenant, opcionalmente escopados por natureza.
Para um débito, os itens aplicáveis são os globais + os da sua natureza; o estado
atual de cada item é a marcação mais recente (log append-only em
debito_checklist_marca). `checklist_pendente` alimenta a guarda de validação.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ChecklistItem, Debito, DebitoChecklistMarca
from ..schemas.pagamentos import (
    ChecklistDebitoItemOut, ChecklistItemCreate, ChecklistItemUpdate,
)


def _utcnow() -> datetime:
    return datetime.utcnow()


class ChecklistError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


# ---------------- templates (parametrização) ----------------
async def listar_itens(db: AsyncSession, *, tenant_id: int) -> list[ChecklistItem]:
    return list((await db.execute(select(ChecklistItem).where(
        ChecklistItem.tenant_id == tenant_id, ChecklistItem.excluido.is_(False))
        .order_by(ChecklistItem.ordem, ChecklistItem.id))).scalars().all())


async def obter_item(db: AsyncSession, *, tenant_id: int, item_id: int) -> ChecklistItem:
    it = (await db.execute(select(ChecklistItem).where(
        ChecklistItem.id == item_id, ChecklistItem.tenant_id == tenant_id,
        ChecklistItem.excluido.is_(False)))).scalar_one_or_none()
    if it is None:
        raise ChecklistError("Item de checklist não encontrado", status.HTTP_404_NOT_FOUND)
    return it


async def criar_item(db: AsyncSession, *, tenant_id: int, payload: ChecklistItemCreate) -> ChecklistItem:
    it = ChecklistItem(tenant_id=tenant_id, criado_em=_utcnow(), **payload.model_dump())
    db.add(it); await db.commit(); await db.refresh(it)
    return it


async def atualizar_item(db: AsyncSession, *, tenant_id: int, item_id: int,
                         payload: ChecklistItemUpdate) -> ChecklistItem:
    it = await obter_item(db, tenant_id=tenant_id, item_id=item_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(it, k, v)
    it.atualizado_em = _utcnow(); await db.commit(); await db.refresh(it)
    return it


async def excluir_item(db: AsyncSession, *, tenant_id: int, item_id: int) -> None:
    it = await obter_item(db, tenant_id=tenant_id, item_id=item_id)
    it.excluido = True; it.atualizado_em = _utcnow(); await db.commit()


# ---------------- checklist por débito ----------------
async def _debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> Debito:
    d = (await db.execute(select(Debito).where(
        Debito.id == debito_id, Debito.tenant_id == tenant_id,
        Debito.excluido.is_(False)))).scalar_one_or_none()
    if d is None:
        raise ChecklistError("Débito não encontrado", status.HTTP_404_NOT_FOUND)
    return d


async def _itens_aplicaveis(db: AsyncSession, *, tenant_id: int, id_natureza: int) -> list[ChecklistItem]:
    """Itens ativos globais (id_natureza NULL) + os da natureza do débito."""
    return list((await db.execute(select(ChecklistItem).where(
        ChecklistItem.tenant_id == tenant_id, ChecklistItem.ativo.is_(True),
        ChecklistItem.excluido.is_(False),
        or_(ChecklistItem.id_natureza.is_(None), ChecklistItem.id_natureza == id_natureza))
        .order_by(ChecklistItem.ordem, ChecklistItem.id))).scalars().all())


async def _ultimas_marcas(db: AsyncSession, *, tenant_id: int, debito_id: int) -> dict[int, DebitoChecklistMarca]:
    rows = (await db.execute(select(DebitoChecklistMarca).where(
        DebitoChecklistMarca.tenant_id == tenant_id, DebitoChecklistMarca.id_debito == debito_id)
        .order_by(DebitoChecklistMarca.id.desc()))).scalars().all()
    out: dict[int, DebitoChecklistMarca] = {}
    for m in rows:  # ordenado desc → a primeira vista de cada item é a mais recente
        out.setdefault(m.id_checklist_item, m)
    return out


async def checklist_do_debito(db: AsyncSession, *, tenant_id: int,
                              debito_id: int) -> list[ChecklistDebitoItemOut]:
    d = await _debito(db, tenant_id=tenant_id, debito_id=debito_id)
    itens = await _itens_aplicaveis(db, tenant_id=tenant_id, id_natureza=d.id_natureza)
    marcas = await _ultimas_marcas(db, tenant_id=tenant_id, debito_id=debito_id)
    saida: list[ChecklistDebitoItemOut] = []
    for it in itens:
        m = marcas.get(it.id)
        saida.append(ChecklistDebitoItemOut(
            id_checklist_item=it.id, descricao=it.descricao, obrigatorio=it.obrigatorio,
            marcado=bool(m and m.marcado), observacao=m.observacao if m else None,
            atualizado_em=m.criado_em if m else None))
    return saida


async def checklist_pendente(db: AsyncSession, *, tenant_id: int, debito_id: int) -> list[str]:
    """Descrições dos itens OBRIGATÓRIOS aplicáveis ainda não marcados (RF-VAL-01)."""
    itens = await checklist_do_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    return [i.descricao for i in itens if i.obrigatorio and not i.marcado]


async def marcar(db: AsyncSession, *, tenant_id: int, debito_id: int, id_checklist_item: int,
                 marcado: bool, observacao: str | None, usuario_id: int | None) -> None:
    await _debito(db, tenant_id=tenant_id, debito_id=debito_id)
    await obter_item(db, tenant_id=tenant_id, item_id=id_checklist_item)  # valida item do tenant
    db.add(DebitoChecklistMarca(
        tenant_id=tenant_id, id_debito=debito_id, id_checklist_item=id_checklist_item,
        marcado=marcado, observacao=observacao, id_usuario=usuario_id, criado_em=_utcnow()))
    await db.commit()
