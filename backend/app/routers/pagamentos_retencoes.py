"""Rotas de retenções tributárias sobre débito (F4, spec §4.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_any_permission, require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import (
    RetencaoCreate, RetencaoOut, RetencaoRecolherIn, RetencaoUpdate, RetencoesDebitoOut,
)
from ..services import pagamentos_retencoes as ret

router = APIRouter(prefix="/pagamentos", tags=["pagamentos-retencoes"])

_LEITURA = ("pagamento_pagar", "pagamento_autorizar", "pagamento_auditar",
            "pagamento_validar", "pagamento_cadastro")


@router.get("/debitos/{debito_id}/retencoes", response_model=RetencoesDebitoOut)
async def listar_retencoes(debito_id: int,
                           _: Usuario = Depends(require_any_permission(*_LEITURA)),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    bruto, liquido, retencoes = await ret.resumo_retencoes(
        db, tenant_id=tenant_id, debito_id=debito_id)
    return RetencoesDebitoOut(
        valor_bruto=bruto, valor_liquido=liquido,
        retencoes=[RetencaoOut.model_validate(r) for r in retencoes],
    )


@router.post("/debitos/{debito_id}/retencoes", response_model=RetencaoOut,
            status_code=status.HTTP_201_CREATED)
async def criar_retencao(debito_id: int, payload: RetencaoCreate,
                         _: Usuario = Depends(require_permission("pagamento_pagar")),
                         tenant_id: int = Depends(require_tenant_id),
                         db: AsyncSession = Depends(get_db)):
    return await ret.criar_retencao(db, tenant_id=tenant_id, debito_id=debito_id, payload=payload)


@router.get("/retencoes/pendentes", response_model=list[RetencaoOut])
async def listar_pendentes(tipo: str | None = None,
                           _: Usuario = Depends(require_permission("pagamento_pagar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    return await ret.listar_pendentes_recolhimento(db, tenant_id=tenant_id, tipo=tipo)


@router.put("/retencoes/{retencao_id}", response_model=RetencaoOut)
async def atualizar_retencao(retencao_id: int, payload: RetencaoUpdate,
                             _: Usuario = Depends(require_permission("pagamento_pagar")),
                             tenant_id: int = Depends(require_tenant_id),
                             db: AsyncSession = Depends(get_db)):
    return await ret.atualizar_retencao(db, tenant_id=tenant_id, retencao_id=retencao_id,
                                        payload=payload)


@router.delete("/retencoes/{retencao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_retencao(retencao_id: int,
                           _: Usuario = Depends(require_permission("pagamento_pagar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    await ret.excluir_retencao(db, tenant_id=tenant_id, retencao_id=retencao_id)


@router.post("/retencoes/{retencao_id}/recolher", response_model=RetencaoOut)
async def recolher_retencao(retencao_id: int, payload: RetencaoRecolherIn,
                            _: Usuario = Depends(require_permission("pagamento_pagar")),
                            tenant_id: int = Depends(require_tenant_id),
                            db: AsyncSession = Depends(get_db)):
    return await ret.recolher_retencao(
        db, tenant_id=tenant_id, retencao_id=retencao_id,
        data_recolhimento=payload.data_recolhimento,
        documento_recolhimento=payload.documento_recolhimento,
    )
