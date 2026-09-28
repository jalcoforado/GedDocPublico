"""Frota — telemetria: posições GPS por veículo.

Sob `/frota/veiculos/{veiculo_id}/telemetria/...`, com a transação `frota`
(a mesma do cadastro de veículos, módulo `frota` em `MODULO_TRANSACOES`):
ingestão exige `inserir`; consulta é leitura, **sem action**. O gate de
contratação vem de `require_permission` — transação de módulo não contratado
é negada lá, antes do bypass de super-usuário.

Nenhuma rota literal aqui disputa segmento com rota paramétrica irmã: o
`{veiculo_id}` é seguido de `/telemetria/...`, e `/frota/veiculos/{veiculo_id}`
do router de frota não casa com barra.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Usuario
from ..schemas.frota_telemetria import PosicaoOut, PosicoesLoteCreate, PosicoesLoteOut
from ..services import frota_telemetria as telemetria_svc

router = APIRouter(prefix="/frota/veiculos", tags=["frota-telemetria"])


@router.post(
    "/{veiculo_id}/telemetria/posicoes",
    response_model=PosicoesLoteOut,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_posicoes(
    veiculo_id: int,
    payload: PosicoesLoteCreate,
    _: Usuario = Depends(require_permission("frota", "inserir")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PosicoesLoteOut:
    resultado = await telemetria_svc.registrar_posicoes(
        db, tenant_id=tenant_id, id_veiculo=veiculo_id, payload=payload
    )
    return PosicoesLoteOut(**resultado)


@router.get(
    "/{veiculo_id}/telemetria/posicoes",
    response_model=list[PosicaoOut],
)
async def listar_posicoes(
    veiculo_id: int,
    inicio: datetime = Query(...),
    fim: datetime = Query(...),
    _: Usuario = Depends(require_permission("frota")),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[PosicaoOut]:
    rows = await telemetria_svc.listar_posicoes(
        db, tenant_id=tenant_id, id_veiculo=veiculo_id, inicio=inicio, fim=fim
    )
    return [PosicaoOut.model_validate(r) for r in rows]
