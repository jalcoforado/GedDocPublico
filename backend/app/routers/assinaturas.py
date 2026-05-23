from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..database import get_db
from ..models import Usuario
from ..schemas.assinatura import (
    AssinarRequest,
    PendenciaAssinatura,
    SolicitacaoOut,
    SolicitarAssinaturaRequest,
)
from ..services.assinaturas import (
    AssinaturaError,
    assinar,
    cancelar_solicitacao,
    listar_do_processo,
    listar_minhas_pendentes,
    solicitar_assinatura,
)

router = APIRouter(tags=["assinaturas"])


@router.post(
    "/processos/{processo_id}/solicitacoes-assinatura",
    response_model=SolicitacaoOut,
    status_code=status.HTTP_201_CREATED,
)
async def solicitar_endpoint(
    processo_id: int,
    payload: SolicitarAssinaturaRequest,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoOut:
    try:
        solic = await solicitar_assinatura(
            db,
            processo_id,
            payload,
            usuario_id=current.id,
            unidade_solicitante_id=current.id_unidade_trabalho,
        )
    except AssinaturaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    lista = await listar_do_processo(db, processo_id)
    return next(s for s in lista if s.id == solic.id)


@router.get(
    "/processos/{processo_id}/solicitacoes-assinatura",
    response_model=list[SolicitacaoOut],
)
async def listar_do_processo_endpoint(
    processo_id: int,
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SolicitacaoOut]:
    return await listar_do_processo(db, processo_id)


@router.get(
    "/solicitacoes-assinatura/me/pendentes",
    response_model=list[PendenciaAssinatura],
)
async def minhas_pendentes_endpoint(
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PendenciaAssinatura]:
    return await listar_minhas_pendentes(db, current.id)


@router.post("/assinaturas/{assinatura_anexo_id}/assinar", response_model=SolicitacaoOut)
async def assinar_endpoint(
    assinatura_anexo_id: int,
    payload: AssinarRequest,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoOut:
    try:
        aa = await assinar(
            db, assinatura_anexo_id, usuario_id=current.id, senha=payload.senha
        )
    except AssinaturaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Devolve a solicitação atualizada (mais útil que retornar só o item).
    from ..models import SolicitacaoAssinatura, UsuarioAssinatura
    from sqlalchemy import select

    solic_id = (
        await db.execute(
            select(SolicitacaoAssinatura.id)
            .join(
                UsuarioAssinatura,
                UsuarioAssinatura.id_solicitacao_assinatura == SolicitacaoAssinatura.id,
            )
            .where(UsuarioAssinatura.id == aa.id_usuario_assinatura)
        )
    ).scalar_one()
    processo_id = (
        await db.execute(
            select(SolicitacaoAssinatura.id_processo).where(
                SolicitacaoAssinatura.id == solic_id
            )
        )
    ).scalar_one()
    lista = await listar_do_processo(db, processo_id)
    return next(s for s in lista if s.id == solic_id)


@router.post(
    "/solicitacoes-assinatura/{solicitacao_id}/cancelar",
    response_model=SolicitacaoOut,
)
async def cancelar_endpoint(
    solicitacao_id: int,
    current: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoOut:
    try:
        solic = await cancelar_solicitacao(
            db, solicitacao_id, usuario_id=current.id
        )
    except AssinaturaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    lista = await listar_do_processo(db, solic.id_processo)
    return next(s for s in lista if s.id == solic.id)
