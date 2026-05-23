"""Endpoints públicos do cidadão (usuário externo).

- /cidadao/cadastrar — público (não exige token)
- /cidadao/login — público
- /cidadao/me — requer token de cidadão
- /cidadao/processos — listar meus processos
- /cidadao/processos/{id} — detalhe (só do próprio)
- /cidadao/processos — POST: abrir novo
- /cidadao/assuntos — catálogo público de assuntos (pra preencher select)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_cidadao
from ..auth.jwt import build_cidadao_payload, encode_token, get_jwt_secret
from ..config import get_settings
from ..database import get_db
from ..models import Assunto, TipoProcesso, UsuarioExterno
from ..schemas.cidadao import (
    AbrirProcessoCidadaoRequest,
    CadastroCidadaoRequest,
    CidadaoMeResponse,
    LoginCidadaoRequest,
    LoginCidadaoResponse,
    ProcessoCidadaoDetail,
    ProcessoCidadaoListItem,
)
from ..services.cidadao_auth import (
    CidadaoAuthError,
    cadastrar,
    login,
)
from ..services.cidadao_processos import (
    CidadaoProcessoError,
    abrir_processo_cidadao,
    get_meu_detail,
    listar_meus,
)

settings = get_settings()
router = APIRouter(prefix="/cidadao", tags=["cidadao"])


@router.post(
    "/cadastrar",
    response_model=CidadaoMeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def cadastrar_endpoint(
    payload: CadastroCidadaoRequest,
    db: AsyncSession = Depends(get_db),
) -> CidadaoMeResponse:
    try:
        cidadao = await cadastrar(db, payload, app=settings.app_name)
    except CidadaoAuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return CidadaoMeResponse.model_validate(cidadao)


@router.post("/login", response_model=LoginCidadaoResponse)
async def login_endpoint(
    payload: LoginCidadaoRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginCidadaoResponse:
    try:
        cidadao = await login(db, cpf_cnpj=payload.cpf_cnpj, senha=payload.senha)
    except CidadaoAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    secret = await get_jwt_secret(db)
    token_payload = build_cidadao_payload(cidadao.id, cidadao.cpf_cnpj or "")
    token = encode_token(token_payload, secret)

    # Cookie HttpOnly (Fase 9.4.3 #8) — JS não lê, enviado same-origin automaticamente.
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


@router.get("/assuntos")
async def assuntos_publico(
    db: AsyncSession = Depends(get_db),
):
    """Catálogo público de assuntos para o cidadão escolher na abertura."""
    rows = (
        await db.execute(
            select(
                Assunto.id,
                Assunto.assunto,
                TipoProcesso.tipo_processo.label("tipo_processo"),
            )
            .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
            .where(Assunto.ativo.is_(True), Assunto.excluido.is_(False))
            .order_by(Assunto.assunto)
        )
    ).all()
    return [
        {"id": r.id, "assunto": r.assunto, "tipo_processo": r.tipo_processo}
        for r in rows
    ]


@router.get("/processos", response_model=list[ProcessoCidadaoListItem])
async def meus_processos(
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    db: AsyncSession = Depends(get_db),
) -> list[ProcessoCidadaoListItem]:
    return await listar_meus(db, cidadao)


@router.get("/processos/{processo_id}", response_model=ProcessoCidadaoDetail)
async def meu_processo_detail(
    processo_id: int,
    cidadao: UsuarioExterno = Depends(get_current_cidadao),
    db: AsyncSession = Depends(get_db),
) -> ProcessoCidadaoDetail:
    detail = await get_meu_detail(db, cidadao, processo_id)
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
    db: AsyncSession = Depends(get_db),
) -> ProcessoCidadaoDetail:
    try:
        processo = await abrir_processo_cidadao(db, cidadao, payload)
    except CidadaoProcessoError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    detail = await get_meu_detail(db, cidadao, processo.id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processo criado mas não localizado depois",
        )
    return detail
