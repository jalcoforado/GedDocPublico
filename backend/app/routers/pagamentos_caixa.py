"""Rotas de caixa de Pagamentos (R1) — movimentações, extrato e saldo por conta."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import ContaSaldoPainel, MovimentacaoCreate, MovimentacaoOut, SaldoConta
from ..services import pagamentos_caixa as svc

caixa_router = APIRouter(prefix="/pagamentos", tags=["pagamentos-caixa"])


@caixa_router.post("/movimentacoes", response_model=MovimentacaoOut, status_code=status.HTTP_201_CREATED)
async def lancar(payload: MovimentacaoCreate,
                 usuario: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                 tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    m = await svc.lancar_movimentacao(db, tenant_id=tenant_id, usuario_id=usuario.id, payload=payload)
    return MovimentacaoOut.model_validate(m)


@caixa_router.get("/contas/{conta_id}/extrato", response_model=list[MovimentacaoOut])
async def extrato(conta_id: int, _: Usuario = Depends(require_permission("pagamento_cadastro")),
                  tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return [MovimentacaoOut.model_validate(m) for m in await svc.listar_extrato(db, tenant_id=tenant_id, conta_id=conta_id)]


@caixa_router.get("/contas/{conta_id}/saldo", response_model=SaldoConta)
async def saldo(conta_id: int, _: Usuario = Depends(require_permission("pagamento_cadastro")),
                tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return await svc.saldo_conta(db, tenant_id=tenant_id, conta_id=conta_id)


@caixa_router.get("/caixa/painel", response_model=list[ContaSaldoPainel])
async def painel(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                 tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return await svc.painel_caixa(db, tenant_id=tenant_id)
