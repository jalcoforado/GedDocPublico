"""Rotas de export contábil de Pagamentos (C2.1) — lotes imutáveis de eventos
neutros para sistema contábil externo. Mesmo gate dos endpoints de export/
caixa vizinhos (`pagamento_cadastro`)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.pagamentos import ExportContabilGerarIn, ExportContabilLoteOut
from ..services import pagamentos_contabil as svc
from sqlalchemy.ext.asyncio import AsyncSession

contabil_router = APIRouter(prefix="/pagamentos/contabil", tags=["pagamentos-contabil"])


@contabil_router.post("/lotes", response_model=ExportContabilLoteOut, status_code=201)
async def gerar_lote(payload: ExportContabilGerarIn,
                     usuario: Usuario = Depends(require_permission("pagamento_cadastro", "inserir")),
                     tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    lote = await svc.gerar_lote(db, tenant_id=tenant_id, ate=payload.ate, usuario_id=usuario.id)
    return ExportContabilLoteOut.model_validate(lote)


@contabil_router.get("/lotes", response_model=list[ExportContabilLoteOut])
async def listar_lotes(_: Usuario = Depends(require_permission("pagamento_cadastro")),
                       tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    lotes = await svc.listar_lotes(db, tenant_id=tenant_id)
    return [ExportContabilLoteOut.model_validate(l) for l in lotes]


# Literal (`/{lote_id}/arquivo`) é sub-rota de um segmento paramétrico já
# declarado acima (`/lotes` sem id) — sem colisão com outra rota do mesmo
# prefixo, mas mantém o hábito do módulo: literal antes de paramétrica-irmã.
@contabil_router.get("/lotes/{lote_id}/arquivo")
async def baixar_arquivo(lote_id: int,
                         _: Usuario = Depends(require_permission("pagamento_cadastro")),
                         tenant_id: int = Depends(require_tenant_id), db: AsyncSession = Depends(get_db)):
    lote = await svc.obter_lote(db, tenant_id=tenant_id, lote_id=lote_id)
    conteudo = await svc.reconstruir_csv(db, tenant_id=tenant_id, lote_id=lote_id)
    nome = f"export-contabil-{lote.numero}.csv"
    return Response(
        content=conteudo, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
