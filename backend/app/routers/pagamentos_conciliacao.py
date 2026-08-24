"""Rotas de conciliação bancária (Onda B / Fase 3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_any_permission, require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import (
    ConciliacaoOut, ConciliarIn, ExtratoOut, ImportarExtratoIn, ImportarExtratoResultadoOut,
    LancamentoExtratoOut, SugestaoBaixaOut,
)
from fastapi import Response

from ..services import pagamentos_conciliacao as conc
from ..services import pagamentos_export as export

router = APIRouter(prefix="/pagamentos", tags=["pagamentos-conciliacao"])

_LEITURA = ("pagamento_pagar", "pagamento_autorizar", "pagamento_auditar", "pagamento_cadastro")


@router.post("/extratos", response_model=ImportarExtratoResultadoOut,
            status_code=status.HTTP_201_CREATED)
async def importar_extrato(payload: ImportarExtratoIn,
                           usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    res = await conc.importar_extrato(db, tenant_id=tenant_id, usuario_id=usuario.id, payload=payload)
    return ImportarExtratoResultadoOut(
        total_no_arquivo=res.total_no_arquivo, importados=res.importados,
        ignorados_por_id_externo=res.ignorados_por_id_externo,
        possiveis_duplicatas=res.possiveis_duplicatas,
        extrato=ExtratoOut.model_validate(res.extrato),
    )


@router.get("/extratos", response_model=list[ExtratoOut])
async def listar_extratos(id_conta: int | None = None,
                          _: Usuario = Depends(require_any_permission(*_LEITURA)),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    return [ExtratoOut.model_validate(e)
            for e in await conc.listar_extratos(db, tenant_id=tenant_id, id_conta=id_conta)]


@router.get("/extratos/{extrato_id}/lancamentos.csv")
async def lancamentos_csv(extrato_id: int,
                          _: Usuario = Depends(require_any_permission(*_LEITURA)),
                          tenant_id: int = Depends(require_tenant_id),
                          db: AsyncSession = Depends(get_db)):
    """Lançamentos do extrato em CSV — a matéria-prima da conciliação."""
    conteudo = await export.csv_lancamentos(db, tenant_id=tenant_id, id_extrato=extrato_id)
    return Response(
        content=conteudo, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="lancamentos-{extrato_id}.csv"'},
    )


@router.get("/extratos/{extrato_id}/lancamentos", response_model=list[LancamentoExtratoOut])
async def listar_lancamentos(extrato_id: int,
                             _: Usuario = Depends(require_any_permission(*_LEITURA)),
                             tenant_id: int = Depends(require_tenant_id),
                             db: AsyncSession = Depends(get_db)):
    return [LancamentoExtratoOut.model_validate(l)
            for l in await conc.listar_lancamentos(db, tenant_id=tenant_id, id_extrato=extrato_id)]


@router.get("/extratos/{extrato_id}/sugestoes", response_model=list[SugestaoBaixaOut])
async def sugestoes(extrato_id: int,
                    _: Usuario = Depends(require_any_permission(*_LEITURA)),
                    tenant_id: int = Depends(require_tenant_id),
                    db: AsyncSession = Depends(get_db)):
    return await conc.sugerir_baixas(db, tenant_id=tenant_id, id_extrato=extrato_id)


@router.post("/extratos/{extrato_id}/baixa-automatica")
async def baixa_automatica(extrato_id: int,
                           usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    n = await conc.baixa_automatica(db, tenant_id=tenant_id, id_extrato=extrato_id,
                                    usuario_id=usuario.id)
    return {"baixas": n}


@router.post("/conciliacoes", response_model=ConciliacaoOut, status_code=status.HTTP_201_CREATED)
async def conciliar(payload: ConciliarIn,
                    usuario: Usuario = Depends(require_permission("pagamento_pagar")),
                    tenant_id: int = Depends(require_tenant_id),
                    db: AsyncSession = Depends(get_db)):
    c = await conc.conciliar(db, tenant_id=tenant_id, id_lancamento=payload.id_lancamento,
                             id_movimentacao=payload.id_movimentacao, usuario_id=usuario.id)
    return ConciliacaoOut.model_validate(c)
