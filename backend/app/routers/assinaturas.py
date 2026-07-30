from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id, require_tenant_slug
from ..auth.perms import require_permission
from ..config import validacao_publica_url
from ..database import get_db
from ..models import Usuario
from ..services.pdf_comprovante_assinatura import gerar_comprovante_assinatura_pdf
from ..services.sigilo import SigiloAcessoError
from ..schemas.assinatura import (
    AssinarRequest,
    EvidenciasOut,
    PendenciaAssinatura,
    RecusarRequest,
    RevogarValidacaoPublicaRequest,
    SolicitacaoOut,
    SolicitarAssinaturaRequest,
    ValidacaoOut,
)
from ..services.assinaturas import (
    AssinaturaCredencialLegadaError,
    AssinaturaError,
    AssinaturaThrottleError,
    assinar,
    cancelar_solicitacao,
    consultar_evidencias,
    listar_do_processo,
    listar_minhas_pendentes,
    recusar_assinatura,
    solicitar_assinatura,
    validar_assinatura,
)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None

router = APIRouter(tags=["assinaturas"])


@router.post(
    "/processos/{processo_id}/solicitacoes-assinatura",
    response_model=SolicitacaoOut,
    status_code=status.HTTP_201_CREATED,
)
async def solicitar_endpoint(
    processo_id: int,
    payload: SolicitarAssinaturaRequest,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoOut:
    try:
        solic = await solicitar_assinatura(
            db,
            processo_id,
            payload,
            tenant_id=tenant_id,
            usuario_id=current.id,
            unidade_solicitante_id=current.id_unidade_trabalho,
        )
    except AssinaturaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    lista = await listar_do_processo(db, processo_id, tenant_id=tenant_id)
    return next(s for s in lista if s.id == solic.id)


@router.get(
    "/processos/{processo_id}/solicitacoes-assinatura",
    response_model=list[SolicitacaoOut],
)
async def listar_do_processo_endpoint(
    processo_id: int,
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[SolicitacaoOut]:
    return await listar_do_processo(db, processo_id, tenant_id=tenant_id)


@router.get(
    "/solicitacoes-assinatura/me/pendentes",
    response_model=list[PendenciaAssinatura],
)
async def minhas_pendentes_endpoint(
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[PendenciaAssinatura]:
    return await listar_minhas_pendentes(db, current.id, tenant_id=tenant_id)


@router.post("/assinaturas/{assinatura_anexo_id}/assinar", response_model=SolicitacaoOut)
async def assinar_endpoint(
    assinatura_anexo_id: int,
    payload: AssinarRequest,
    request: Request,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoOut:
    try:
        aa = await assinar(
            db,
            assinatura_anexo_id,
            tenant_id=tenant_id,
            usuario_id=current.id,
            senha=payload.senha,
            tenant_slug=tenant_slug,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AssinaturaThrottleError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except AssinaturaCredencialLegadaError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AssinaturaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    from sqlalchemy import select
    from ..models import SolicitacaoAssinatura, UsuarioAssinatura

    solic_id = (
        await db.execute(
            select(SolicitacaoAssinatura.id)
            .join(
                UsuarioAssinatura,
                UsuarioAssinatura.id_solicitacao_assinatura == SolicitacaoAssinatura.id,
            )
            .where(
                UsuarioAssinatura.id == aa.id_usuario_assinatura,
                SolicitacaoAssinatura.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    processo_id = (
        await db.execute(
            select(SolicitacaoAssinatura.id_processo).where(
                SolicitacaoAssinatura.id == solic_id,
                SolicitacaoAssinatura.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    lista = await listar_do_processo(db, processo_id, tenant_id=tenant_id)
    return next(s for s in lista if s.id == solic_id)


@router.post(
    "/solicitacoes-assinatura/{solicitacao_id}/cancelar",
    response_model=SolicitacaoOut,
)
async def cancelar_endpoint(
    solicitacao_id: int,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoOut:
    try:
        solic = await cancelar_solicitacao(
            db, solicitacao_id, tenant_id=tenant_id, usuario_id=current.id
        )
    except AssinaturaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    lista = await listar_do_processo(db, solic.id_processo, tenant_id=tenant_id)
    return next(s for s in lista if s.id == solic.id)


@router.post(
    "/solicitacoes-assinatura/{solicitacao_id}/recusar",
    response_model=SolicitacaoOut,
)
async def recusar_endpoint(
    solicitacao_id: int,
    payload: RecusarRequest,
    # Espelho de POST /assinaturas/{id}/assinar, que exige o mesmo código:
    # recusar altera o estado da solicitação sobre o processo.
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> SolicitacaoOut:
    try:
        await recusar_assinatura(
            db,
            solicitacao_id,
            tenant_id=tenant_id,
            usuario_id=current.id,
            motivo=payload.motivo,
        )
    except AssinaturaError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    from sqlalchemy import select as _select
    from ..models import SolicitacaoAssinatura as _Solic

    processo_id = (
        await db.execute(
            _select(_Solic.id_processo).where(
                _Solic.id == solicitacao_id, _Solic.tenant_id == tenant_id
            )
        )
    ).scalar_one()
    lista = await listar_do_processo(db, processo_id, tenant_id=tenant_id)
    return next(s for s in lista if s.id == solicitacao_id)


@router.get("/assinaturas/{assinatura_anexo_id}/validar", response_model=ValidacaoOut)
async def validar_endpoint(
    assinatura_anexo_id: int,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> ValidacaoOut:
    try:
        return await validar_assinatura(
            db,
            assinatura_anexo_id,
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            usuario=current,
        )
    except (AssinaturaError, SigiloAcessoError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/assinaturas/{assinatura_anexo_id}/evidencias", response_model=EvidenciasOut)
async def evidencias_endpoint(
    assinatura_anexo_id: int,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> EvidenciasOut:
    try:
        return await consultar_evidencias(
            db, assinatura_anexo_id, tenant_id=tenant_id, usuario=current,
            tenant_slug=tenant_slug,
        )
    except (AssinaturaError, SigiloAcessoError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/assinaturas/{assinatura_anexo_id}/revogar-validacao-publica")
async def revogar_validacao_publica_endpoint(
    assinatura_anexo_id: int,
    payload: RevogarValidacaoPublicaRequest,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    from ..services.validacao_publica import (
        ValidacaoPublicaError,
        revogar_validacao_publica,
    )

    try:
        aa = await revogar_validacao_publica(
            db,
            assinatura_anexo_id,
            tenant_id=tenant_id,
            usuario=current,
            motivo=payload.motivo,
        )
    except (ValidacaoPublicaError, SigiloAcessoError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"id_assinatura_anexo": aa.id, "validacao_publica_revogada": True}


@router.get("/assinaturas/{assinatura_anexo_id}/comprovante.pdf")
async def comprovante_endpoint(
    assinatura_anexo_id: int,
    current: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
):
    try:
        evidencias = await consultar_evidencias(
            db, assinatura_anexo_id, tenant_id=tenant_id, usuario=current,
            tenant_slug=tenant_slug,
        )
        validacao = await validar_assinatura(
            db, assinatura_anexo_id, tenant_id=tenant_id,
            tenant_slug=tenant_slug, usuario=current,
        )
    except (AssinaturaError, SigiloAcessoError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    url_validacao = (
        validacao_publica_url(tenant_slug, evidencias.codigo_validacao)
        if evidencias.codigo_validacao
        else None
    )
    pdf = gerar_comprovante_assinatura_pdf(evidencias, validacao, url_validacao=url_validacao)
    fname = f"comprovante-assinatura-{assinatura_anexo_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )
