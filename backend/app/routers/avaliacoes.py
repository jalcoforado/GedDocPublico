"""Pedido de avaliação e decisão por documento (SI-73, RF-04 V2).

Só HTTP; as regras estão em `services/avaliacoes.py`. Permissões:

- pedir e reenviar: `processo`/`atualizar` (é quem tramita o processo);
- decidir: `documento_avaliar` E ser o avaliador designado (no service);
- ler: qualquer uma das duas.

O sigilo vem antes de resolver qualquer recurso: nas rotas com `processo_id`,
aqui; nas rotas por id de pedido, no service (`_pedido_autorizado`), que
devolve o mesmo 404 para "não existe" e "não pode ver".
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_any_permission, require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.avaliacao import AvaliacaoDecisoes, AvaliacaoPedidoCreate, AvaliacaoPedidoOut
from ..schemas.common import Paginated
from ..services import avaliacoes as svc
from ..services.sigilo import SigiloAcessoError, assert_acesso_processo

router = APIRouter(tags=["avaliacoes"])

_LEITURA = require_any_permission("processo", svc.TRANSACAO)


def _http(e: svc.AvaliacaoError) -> HTTPException:
    codigo = status.HTTP_400_BAD_REQUEST
    if isinstance(e, svc.AvaliacaoNaoEncontrada):
        codigo = status.HTTP_404_NOT_FOUND
    elif isinstance(e, svc.AvaliacaoConflito):
        codigo = status.HTTP_409_CONFLICT
    elif isinstance(e, svc.AvaliacaoInvalida):
        codigo = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(e, svc.AvaliacaoProibida):
        codigo = status.HTTP_403_FORBIDDEN
    return HTTPException(status_code=codigo, detail=str(e))


async def _exigir_acesso(db: AsyncSession, processo_id: int, tenant_id: int, usuario) -> None:
    try:
        await assert_acesso_processo(
            db, tenant_id=tenant_id, processo_id=processo_id, usuario=usuario
        )
    except SigiloAcessoError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado")


@router.post(
    "/processos/{processo_id}/avaliacoes",
    response_model=AvaliacaoPedidoOut,
    status_code=status.HTTP_201_CREATED,
)
async def pedir_avaliacao(
    processo_id: int,
    body: AvaliacaoPedidoCreate,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AvaliacaoPedidoOut:
    await _exigir_acesso(db, processo_id, tenant_id, current)
    try:
        return await svc.criar_pedido(db, processo_id, body, tenant_id=tenant_id, usuario=current)
    except svc.AvaliacaoError as e:
        raise _http(e)


@router.get("/processos/{processo_id}/avaliacoes", response_model=list[AvaliacaoPedidoOut])
async def avaliacoes_do_processo(
    processo_id: int,
    current: Usuario = Depends(_LEITURA),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[AvaliacaoPedidoOut]:
    await _exigir_acesso(db, processo_id, tenant_id, current)
    return await svc.listar_do_processo(db, processo_id, tenant_id=tenant_id)


@router.get("/avaliacoes", response_model=Paginated[AvaliacaoPedidoOut])
async def minhas_avaliacoes(
    papel: Literal["avaliador", "solicitante"] = Query(...),
    situacao: Literal["pendente", "concluida"] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current: Usuario = Depends(_LEITURA),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Paginated[AvaliacaoPedidoOut]:
    """Caixas "Para avaliar" (`papel=avaliador`) e "Avaliações solicitadas"
    (`papel=solicitante`): só os pedidos do próprio usuário."""
    return await svc.listar_meus(
        db, tenant_id=tenant_id, usuario=current, papel=papel, situacao=situacao,
        page=page, page_size=page_size,
    )


@router.get("/avaliacoes/{pedido_id}", response_model=AvaliacaoPedidoOut)
async def obter_avaliacao(
    pedido_id: int,
    current: Usuario = Depends(_LEITURA),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AvaliacaoPedidoOut:
    try:
        return await svc.obter_pedido(db, pedido_id, tenant_id=tenant_id, usuario=current)
    except svc.AvaliacaoError as e:
        raise _http(e)


@router.post("/avaliacoes/{pedido_id}/decisoes", response_model=AvaliacaoPedidoOut)
async def decidir_avaliacao(
    pedido_id: int,
    body: AvaliacaoDecisoes,
    current: Usuario = Depends(require_permission(svc.TRANSACAO)),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AvaliacaoPedidoOut:
    try:
        return await svc.decidir(db, pedido_id, body, tenant_id=tenant_id, usuario=current)
    except svc.AvaliacaoError as e:
        raise _http(e)


@router.post(
    "/avaliacoes/{pedido_id}/itens/{item_id}/reenviar", response_model=AvaliacaoPedidoOut
)
async def reenviar_avaliacao(
    pedido_id: int,
    item_id: int,
    current: Usuario = Depends(require_permission("processo", "atualizar")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AvaliacaoPedidoOut:
    try:
        return await svc.reenviar(db, pedido_id, item_id, tenant_id=tenant_id, usuario=current)
    except svc.AvaliacaoError as e:
        raise _http(e)
