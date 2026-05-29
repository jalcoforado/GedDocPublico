"""Endpoints públicos do cidadão (usuário externo).

Fase 13a: todas as rotas usam `require_tenant_id` — o portal cidadão é
escopado por tenant (cidadão acessa via `cidadao.{slug}.aprimora.app`).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_cidadao, require_tenant_id, require_tenant_slug
from ..auth.jwt import build_cidadao_payload, encode_token, get_jwt_secret
from ..config import get_settings
from ..database import get_db, tenant_filter
from ..models import Assunto, Manifestante, Processo, TipoProcesso, UsuarioExterno
from ..schemas.cidadao import (
    AbrirPorServicoRequest,
    AbrirProcessoCidadaoRequest,
    AnexoCidadaoOut,
    CadastroCidadaoRequest,
    CidadaoMeResponse,
    EspecieCidadaoOut,
    LoginCidadaoRequest,
    LoginCidadaoResponse,
    ProcessoCidadaoDetail,
    ProcessoCidadaoListItem,
)
from ..services.anexos import AnexoError, upload_anexo
from ..services.cidadao_auth import (
    CidadaoAuthError,
    cadastrar,
    login,
)
from ..services.cidadao_processos import (
    CidadaoProcessoError,
    abrir_processo_cidadao,
    abrir_processo_por_servico,
    get_meu_detail,
    listar_especies_cidadao,
    listar_meus,
)
from ..services.servico import obter_servico_solicitavel

settings = get_settings()
router = APIRouter(prefix="/cidadao", tags=["cidadao"])


@router.post(
    "/cadastrar",
    response_model=CidadaoMeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def cadastrar_endpoint(
    payload: CadastroCidadaoRequest,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> CidadaoMeResponse:
    try:
        cidadao = await cadastrar(
            db, payload, tenant_id=tenant_id, app=settings.app_name
        )
    except CidadaoAuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return CidadaoMeResponse.model_validate(cidadao)


@router.post("/login", response_model=LoginCidadaoResponse)
async def login_endpoint(
    payload: LoginCidadaoRequest,
    response: Response,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> LoginCidadaoResponse:
    try:
        cidadao = await login(
            db, tenant_id=tenant_id, cpf_cnpj=payload.cpf_cnpj, senha=payload.senha
        )
    except CidadaoAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    secret = await get_jwt_secret(db)
    token_payload = build_cidadao_payload(
        cidadao.id, cidadao.cpf_cnpj or "", tenant_id=tenant_id
    )
    token = encode_token(token_payload, secret)

    response.set_cookie(
        key="aprimora_cidadao_token",
        value=token,
        max_age=settings.jwt_ttl_seconds,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return LoginCidadaoResponse(
        access_token=token,
        expires_in=settings.jwt_ttl_seconds,
        cidadao=CidadaoMeResponse.model_validate(cidadao),
    )


@router.post("/logout")
async def logout_endpoint() -> Response:
    resp = Response(status_code=status.HTTP_204_NO_CONTENT)
    resp.delete_cookie(key="aprimora_cidadao_token", path="/")
    return resp


@router.get("/me", response_model=CidadaoMeResponse)
async def me_endpoint(
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
) -> CidadaoMeResponse:
    return CidadaoMeResponse.model_validate(cidadao)


@router.get("/especies", response_model=list[EspecieCidadaoOut])
async def especies_publico(
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[EspecieCidadaoOut]:
    """Espécies documentais expostas no portal cidadão."""
    return await listar_especies_cidadao(db, tenant_id=tenant_id)


@router.get("/assuntos")
async def assuntos_publico(
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Catálogo de assuntos do tenant atual para o cidadão escolher."""
    stmt = (
        select(
            Assunto.id,
            Assunto.assunto,
            TipoProcesso.tipo_processo.label("tipo_processo"),
        )
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
        .where(Assunto.ativo.is_(True), Assunto.excluido.is_(False))
    )
    stmt = tenant_filter(stmt, Assunto, tenant_id).order_by(Assunto.assunto)
    rows = (await db.execute(stmt)).all()
    return [
        {"id": r.id, "assunto": r.assunto, "tipo_processo": r.tipo_processo}
        for r in rows
    ]


@router.get("/processos", response_model=list[ProcessoCidadaoListItem])
async def meus_processos(
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[ProcessoCidadaoListItem]:
    return await listar_meus(db, cidadao, tenant_id=tenant_id)


@router.get("/processos/{processo_id}", response_model=ProcessoCidadaoDetail)
async def meu_processo_detail(
    processo_id: int,
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoCidadaoDetail:
    detail = await get_meu_detail(db, cidadao, processo_id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado ou não pertence a você",
        )
    return detail


@router.post(
    "/processos",
    response_model=ProcessoCidadaoDetail,
    status_code=status.HTTP_201_CREATED,
)
async def abrir_processo_endpoint(
    payload: AbrirProcessoCidadaoRequest,
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoCidadaoDetail:
    try:
        processo = await abrir_processo_cidadao(db, cidadao, payload, tenant_id=tenant_id)
    except CidadaoProcessoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    detail = await get_meu_detail(db, cidadao, processo.id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processo criado mas não localizado depois",
        )
    return detail


@router.post(
    "/servicos/{slug}/abrir",
    response_model=ProcessoCidadaoDetail,
    status_code=status.HTTP_201_CREATED,
)
async def abrir_por_servico_endpoint(
    slug: str,
    payload: AbrirPorServicoRequest,
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ProcessoCidadaoDetail:
    """Abre protocolo a partir de um serviço ativo do portal (PR 4b).

    Serviço resolvido por slug + tenant do Host. Defaults do serviço são
    aplicados server-side; o cidadão não escolhe classificação."""
    # 404 neutro (não achado/inativo/outro tenant) ou 409 controlado (mal config).
    servico = await obter_servico_solicitavel(db, tenant_id=tenant_id, slug=slug)
    try:
        processo = await abrir_processo_por_servico(
            db, cidadao, servico, payload, tenant_id=tenant_id
        )
    except CidadaoProcessoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    detail = await get_meu_detail(db, cidadao, processo.id, tenant_id=tenant_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processo criado mas não localizado depois",
        )
    return detail


async def _verificar_dono(
    db: AsyncSession,
    cidadao: UsuarioExterno,
    processo_id: int,
    tenant_id: int,
) -> None:
    if not cidadao.cpf_cnpj:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cadastro sem CPF/CNPJ")
    stmt = (
        select(Processo.id)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante)
        .where(
            Processo.id == processo_id,
            Processo.tenant_id == tenant_id,
            Manifestante.cpf_cnpj == cidadao.cpf_cnpj,
            Manifestante.tenant_id == tenant_id,
        )
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado ou não pertence a você",
        )


@router.post(
    "/processos/{processo_id}/anexos",
    response_model=AnexoCidadaoOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_anexo_cidadao_endpoint(
    processo_id: int,
    file: UploadFile = File(...),
    descricao: str | None = Form(None),
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    tenant_id: int = Depends(require_tenant_id),
    tenant_slug: str = Depends(require_tenant_slug),
    db: AsyncSession = Depends(get_db),
) -> AnexoCidadaoOut:
    """Cidadão anexa documento ao próprio processo. Sempre público."""
    await _verificar_dono(db, cidadao, processo_id, tenant_id)
    try:
        anexo = await upload_anexo(
            db,
            processo_id,
            file,
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            descricao=descricao,
            id_tipo_anexo=None,
            publico=True,
            usuario_id=None,
        )
    except AnexoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return AnexoCidadaoOut(
        id=anexo.id,
        descricao=anexo.descricao,
        e_doc=anexo.e_doc,
        qtd_paginas=anexo.qtd_paginas,
        publico=anexo.publico,
    )
