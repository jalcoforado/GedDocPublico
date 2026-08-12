from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db, tenant_filter
from ..models import Grupo, GrupoTransacao, Usuario
from ..schemas.grupo import (
    GrupoCreate,
    GrupoOut,
    GrupoTransacaoOut,
    GrupoTransacoesUpdate,
    GrupoUpdate,
)

router = APIRouter(prefix="/grupos", tags=["grupos"])


async def _get_grupo_or_404(db: AsyncSession, grupo_id: int, tenant_id: int) -> Grupo:
    g = (
        await db.execute(
            select(Grupo).where(
                Grupo.id == grupo_id,
                Grupo.tenant_id == tenant_id,
                Grupo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if g is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grupo não encontrado")
    return g


@router.get(
    "",
    response_model=list[GrupoOut],
    dependencies=[Depends(require_modulo("administracao")), Depends(require_permission("usuario"))],
)
async def list_grupos(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[GrupoOut]:
    stmt = select(Grupo).where(Grupo.excluido.is_(False))
    stmt = tenant_filter(stmt, Grupo, tenant_id).order_by(Grupo.grupo)
    return [GrupoOut.model_validate(g) for g in (await db.execute(stmt)).scalars().all()]


@router.get(
    "/{grupo_id}",
    response_model=GrupoOut,
    dependencies=[Depends(require_modulo("administracao")), Depends(require_permission("usuario"))],
)
async def get_grupo(
    grupo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> GrupoOut:
    g = await _get_grupo_or_404(db, grupo_id, tenant_id)
    return GrupoOut.model_validate(g)


@router.post("", response_model=GrupoOut, status_code=status.HTTP_201_CREATED)
async def create_grupo(
    payload: GrupoCreate,
    _: Usuario = Depends(require_permission("usuario", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> GrupoOut:
    g = Grupo(**payload.model_dump(), tenant_id=tenant_id, excluido=False)
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return GrupoOut.model_validate(g)


@router.put("/{grupo_id}", response_model=GrupoOut)
async def update_grupo(
    grupo_id: int,
    payload: GrupoUpdate,
    _: Usuario = Depends(require_permission("usuario", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> GrupoOut:
    g = await _get_grupo_or_404(db, grupo_id, tenant_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    await db.commit()
    await db.refresh(g)
    return GrupoOut.model_validate(g)


@router.get(
    "/{grupo_id}/transacoes",
    response_model=list[GrupoTransacaoOut],
    dependencies=[Depends(require_modulo("administracao")), Depends(require_permission("usuario"))],
)
async def list_grupo_transacoes(
    grupo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[GrupoTransacaoOut]:
    stmt = select(GrupoTransacao).where(
        GrupoTransacao.id_grupo == grupo_id,
        GrupoTransacao.tenant_id == tenant_id,
        GrupoTransacao.excluido.is_(False),
    )
    return [
        GrupoTransacaoOut.model_validate(gt)
        for gt in (await db.execute(stmt)).scalars().all()
    ]


@router.put("/{grupo_id}/transacoes", response_model=list[GrupoTransacaoOut])
async def set_grupo_transacoes(
    grupo_id: int,
    payload: GrupoTransacoesUpdate,
    _: Usuario = Depends(require_permission("usuario", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[GrupoTransacaoOut]:
    await _get_grupo_or_404(db, grupo_id, tenant_id)

    await db.execute(
        delete(GrupoTransacao).where(
            GrupoTransacao.id_grupo == grupo_id,
            GrupoTransacao.tenant_id == tenant_id,
        )
    )
    for t in payload.transacoes:
        db.add(
            GrupoTransacao(
                id_grupo=grupo_id,
                id_transacao=t.id_transacao,
                tenant_id=tenant_id,
                inserir=t.inserir,
                atualizar=t.atualizar,
                excluir=t.excluir,
                excluido=False,
            )
        )
    await db.commit()

    stmt = select(GrupoTransacao).where(
        GrupoTransacao.id_grupo == grupo_id,
        GrupoTransacao.tenant_id == tenant_id,
        GrupoTransacao.excluido.is_(False),
    )
    return [
        GrupoTransacaoOut.model_validate(gt)
        for gt in (await db.execute(stmt)).scalars().all()
    ]
