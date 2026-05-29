"""Catálogo de Serviços / Carta de Serviços (PR 4a).

- `router` (prefix `/servicos`): CRUD interno, autenticado + permissão `servico`.
- `portal_router` (prefix `/portal`): listagem pública (sem login), tenant pelo
  Host (padrão `branding.py`), só serviços ativos, projeção segura.

Abertura de protocolo por serviço é o PR 4b — aqui só catálogo (leitura pública).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.servico import (
    ServicoCreate,
    ServicoOut,
    ServicoPublicOut,
    ServicoUpdate,
)
from ..services import servico as servico_svc

router = APIRouter(prefix="/servicos", tags=["servicos"])


@router.get("", response_model=list[ServicoOut])
async def list_servicos(
    incluir_inativos: bool = Query(False),
    _: Usuario = Depends(require_permission("servico")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[ServicoOut]:
    rows = await servico_svc.listar_servicos(
        db, tenant_id=tenant_id, incluir_inativos=incluir_inativos
    )
    return [ServicoOut.model_validate(r) for r in rows]


@router.get("/{servico_id}", response_model=ServicoOut)
async def get_servico(
    servico_id: int,
    _: Usuario = Depends(require_permission("servico")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ServicoOut:
    servico = await servico_svc.obter_servico(db, tenant_id=tenant_id, servico_id=servico_id)
    return ServicoOut.model_validate(servico)


@router.post("", response_model=ServicoOut, status_code=status.HTTP_201_CREATED)
async def create_servico(
    payload: ServicoCreate,
    _: Usuario = Depends(require_permission("servico", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ServicoOut:
    servico = await servico_svc.criar_servico(db, tenant_id=tenant_id, payload=payload)
    return ServicoOut.model_validate(servico)


@router.put("/{servico_id}", response_model=ServicoOut)
async def update_servico(
    servico_id: int,
    payload: ServicoUpdate,
    _: Usuario = Depends(require_permission("servico", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ServicoOut:
    servico = await servico_svc.atualizar_servico(
        db, tenant_id=tenant_id, servico_id=servico_id, payload=payload
    )
    return ServicoOut.model_validate(servico)


@router.post("/{servico_id}/ativar", response_model=ServicoOut)
async def ativar_servico(
    servico_id: int,
    _: Usuario = Depends(require_permission("servico", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ServicoOut:
    servico = await servico_svc.set_ativo(
        db, tenant_id=tenant_id, servico_id=servico_id, ativo=True
    )
    return ServicoOut.model_validate(servico)


@router.post("/{servico_id}/desativar", response_model=ServicoOut)
async def desativar_servico(
    servico_id: int,
    _: Usuario = Depends(require_permission("servico", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> ServicoOut:
    servico = await servico_svc.set_ativo(
        db, tenant_id=tenant_id, servico_id=servico_id, ativo=False
    )
    return ServicoOut.model_validate(servico)


# --- Portal público (sem login; tenant pelo Host — padrão branding.py) -------
portal_router = APIRouter(prefix="/portal", tags=["portal"])


def _require_host_tenant(request: Request) -> int:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant não resolvido para este host",
        )
    return int(tid)


@portal_router.get("/servicos", response_model=list[ServicoPublicOut])
async def portal_list_servicos(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[ServicoPublicOut]:
    tenant_id = _require_host_tenant(request)
    return await servico_svc.listar_publico(db, tenant_id=tenant_id)


@portal_router.get("/servicos/{slug}", response_model=ServicoPublicOut)
async def portal_get_servico(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ServicoPublicOut:
    tenant_id = _require_host_tenant(request)
    return await servico_svc.obter_publico(db, tenant_id=tenant_id, slug=slug)
