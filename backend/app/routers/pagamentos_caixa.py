"""Rotas de caixa de Pagamentos (R1) — movimentações, extrato e saldo por conta."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import (
    BloqueioSaldoCreate, BloqueioSaldoOut, BloqueioSaldoUpdate,
    ContaSaldoPainel, MovimentacaoCreate, MovimentacaoOut, SaldoConta,
)
from fastapi import Response

from ..services import pagamentos_bloqueios as bloq
from ..services import pagamentos_caixa as svc
from ..services import pagamentos_export as export

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


# C1.3 — exportações. Declaradas ANTES da rota de painel por higiene de
# ordem (aqui não há colisão real: `painel.csv` e `painel` são segmentos
# distintos), mas a regra vale sempre neste repo — literal antes de
# paramétrica, senão a paramétrica engole e a requisição morre em 422.
@caixa_router.get("/caixa/painel.csv")
async def painel_csv(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    """Painel de caixa em CSV — os mesmos saldos que a tela mostra."""
    conteudo = await export.csv_painel_caixa(db, tenant_id=tenant_id)
    return Response(
        content=conteudo, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="painel-caixa.csv"'},
    )


@caixa_router.get("/caixa/painel.pdf")
async def painel_pdf(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                     tenant_id: int = Depends(require_tenant_id),
                     db: AsyncSession = Depends(get_db)):
    """Painel de caixa em PDF — é o que se imprime e arquiva."""
    conteudo = await export.pdf_painel_caixa(db, tenant_id=tenant_id)
    return Response(
        content=conteudo, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="painel-caixa.pdf"'},
    )


@caixa_router.get("/contas/{conta_id}/extrato.csv")
async def extrato_csv(conta_id: int,
                      _: Usuario = Depends(require_permission("pagamento_cadastro")),
                      tenant_id: int = Depends(require_tenant_id),
                      db: AsyncSession = Depends(get_db)):
    """Extrato INTERNO da conta (movimentações), não o extrato bancário."""
    conteudo = await export.csv_extrato_conta(db, tenant_id=tenant_id, conta_id=conta_id)
    return Response(
        content=conteudo, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="extrato-conta-{conta_id}.csv"'},
    )


@caixa_router.get("/caixa/painel", response_model=list[ContaSaldoPainel])
async def painel(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                 tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    return await svc.painel_caixa(db, tenant_id=tenant_id)


# ---------- bloqueios de saldo (v2.0) ----------
@caixa_router.get("/bloqueios", response_model=list[BloqueioSaldoOut])
async def listar_bloqueios(conta_id: int | None = None, apenas_ativos: bool = False,
                           _: Usuario = Depends(require_permission("pagamento_cadastro")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    return await bloq.listar_bloqueios(db, tenant_id=tenant_id, conta_id=conta_id,
                                       apenas_ativos=apenas_ativos)


@caixa_router.post("/bloqueios", response_model=BloqueioSaldoOut, status_code=status.HTTP_201_CREATED)
async def criar_bloqueio(payload: BloqueioSaldoCreate,
                         usuario: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                         tenant_id: int = Depends(require_tenant_id),
                         db: AsyncSession = Depends(get_db)):
    return await bloq.criar_bloqueio(db, tenant_id=tenant_id, usuario_id=usuario.id, payload=payload)


@caixa_router.put("/bloqueios/{bloqueio_id}", response_model=BloqueioSaldoOut)
async def atualizar_bloqueio(bloqueio_id: int, payload: BloqueioSaldoUpdate,
                             _: Usuario = Depends(require_permission("pagamento_cadastro", "atualizar")),
                             tenant_id: int = Depends(require_tenant_id),
                             db: AsyncSession = Depends(get_db)):
    return await bloq.atualizar_bloqueio(db, tenant_id=tenant_id, bloqueio_id=bloqueio_id, payload=payload)


@caixa_router.delete("/bloqueios/{bloqueio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_bloqueio(bloqueio_id: int,
                           _: Usuario = Depends(require_permission("pagamento_cadastro", "excluir")),
                           tenant_id: int = Depends(require_tenant_id),
                           db: AsyncSession = Depends(get_db)):
    await bloq.excluir_bloqueio(db, tenant_id=tenant_id, bloqueio_id=bloqueio_id)
