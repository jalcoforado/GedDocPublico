from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..auth.deps import require_tenant_id
from ..auth.modulos import require_modulo
from ..auth.perms import require_permission
from ..database import get_db
from ..models.frota import Veiculo
from ..schemas.frota_telemetria import PosicaoSchema, PosicaoResponse, ConsumoResponse
from ..services.frota_telemetria import registrar_posicoes_gps, obter_trajeto, calcular_consumo_combustivel

router = APIRouter(tags=["frota-telemetria"])

async def _validar_veiculo(db: AsyncSession, id_veiculo: int, tenant_id: int) -> Veiculo:
    result = await db.execute(
        select(Veiculo).where(
            Veiculo.id == id_veiculo,
            Veiculo.tenant_id == tenant_id,
            Veiculo.excluido.is_(False)
        )
    )
    veiculo = result.scalars().first()
    if not veiculo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Veículo não encontrado")
    return veiculo


@router.post(
    "/frota/veiculos/{id_veiculo}/telemetria/posicoes",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_modulo("frota")), Depends(require_permission("frota", "operar"))]
)
async def post_posicoes(
    id_veiculo: int,
    posicoes: list[PosicaoSchema],
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    await _validar_veiculo(db, id_veiculo, tenant_id)
    qtd = await registrar_posicoes_gps(db, id_veiculo, posicoes, tenant_id)
    return {"message": f"{qtd} posições registradas com sucesso."}


@router.get(
    "/frota/veiculos/{id_veiculo}/telemetria/trajeto",
    response_model=list[PosicaoResponse],
    dependencies=[Depends(require_modulo("frota")), Depends(require_permission("frota", "visualizar"))]
)
async def get_trajeto(
    id_veiculo: int,
    data_inicial: datetime = Query(...),
    data_final: datetime = Query(...),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    await _validar_veiculo(db, id_veiculo, tenant_id)
    trajeto = await obter_trajeto(db, id_veiculo, data_inicial, data_final, tenant_id)
    return trajeto


@router.get(
    "/frota/veiculos/{id_veiculo}/telemetria/consumo",
    response_model=ConsumoResponse,
    dependencies=[Depends(require_modulo("frota")), Depends(require_permission("frota", "visualizar"))]
)
async def get_consumo(
    id_veiculo: int,
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db)
):
    await _validar_veiculo(db, id_veiculo, tenant_id)
    consumo = await calcular_consumo_combustivel(db, id_veiculo, tenant_id)
    return consumo
