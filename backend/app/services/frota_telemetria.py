from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.frota import VeiculoPosicao, VeiculoAbastecimento
from ..schemas.frota_telemetria import PosicaoSchema

async def registrar_posicoes_gps(
    db: AsyncSession,
    id_veiculo: int,
    posicoes: list[PosicaoSchema],
    tenant_id: int
) -> int:
    """Insere um batch de posições GPS para telemetria."""
    if not posicoes:
        return 0

    novas_posicoes = [
        VeiculoPosicao(
            tenant_id=tenant_id,
            id_veiculo=id_veiculo,
            timestamp=p.timestamp,
            latitude=p.latitude,
            longitude=p.longitude,
            velocidade=p.velocidade,
            ignicao_ligada=p.ignicao_ligada,
            criado_em=datetime.utcnow()
        )
        for p in posicoes
    ]
    
    db.add_all(novas_posicoes)
    await db.commit()
    return len(novas_posicoes)

async def obter_trajeto(
    db: AsyncSession,
    id_veiculo: int,
    data_inicial: datetime,
    data_final: datetime,
    tenant_id: int
) -> list[VeiculoPosicao]:
    """Retorna o trajeto percorrido no período informado."""
    result = await db.execute(
        select(VeiculoPosicao)
        .where(
            VeiculoPosicao.tenant_id == tenant_id,
            VeiculoPosicao.id_veiculo == id_veiculo,
            VeiculoPosicao.timestamp >= data_inicial,
            VeiculoPosicao.timestamp <= data_final
        )
        .order_by(VeiculoPosicao.timestamp.asc())
    )
    return list(result.scalars().all())

async def calcular_consumo_combustivel(
    db: AsyncSession,
    id_veiculo: int,
    tenant_id: int
):
    """Calcula eficiência km/l baseada no histórico de abastecimentos."""
    result = await db.execute(
        select(VeiculoAbastecimento)
        .where(
            VeiculoAbastecimento.tenant_id == tenant_id,
            VeiculoAbastecimento.id_veiculo == id_veiculo,
            VeiculoAbastecimento.excluido.is_(False)
        )
        .order_by(VeiculoAbastecimento.data_abastecimento.asc(), VeiculoAbastecimento.km_atual.asc())
    )
    abastecimentos = result.scalars().all()

    if len(abastecimentos) < 2:
        return {
            "id_veiculo": id_veiculo,
            "eficiencia_media_km_l": Decimal("0.0"),
            "km_total_percorrido": 0,
            "litros_total": Decimal("0.0"),
            "detalhes": []
        }

    detalhes = []
    km_total = 0
    litros_totais_para_media = Decimal("0.0")

    for i in range(1, len(abastecimentos)):
        anterior = abastecimentos[i-1]
        atual = abastecimentos[i]

        delta_km = atual.km_atual - anterior.km_atual
        if delta_km < 0:
            continue # Inconsistência de hodômetro

        # Calcula km/l considerando os litros deste abastecimento (para completar o tanque do percurso)
        eficiencia = Decimal(delta_km) / atual.litros if atual.litros > 0 else Decimal(0)
        
        km_total += delta_km
        litros_totais_para_media += atual.litros

        detalhes.append({
            "id_abastecimento": atual.id,
            "data_abastecimento": atual.data_abastecimento,
            "litros": atual.litros,
            "km_percorrido": delta_km,
            "eficiencia_km_l": round(eficiencia, 2)
        })

    eficiencia_media = (Decimal(km_total) / litros_totais_para_media) if litros_totais_para_media > 0 else Decimal(0)

    return {
        "id_veiculo": id_veiculo,
        "eficiencia_media_km_l": round(eficiencia_media, 2),
        "km_total_percorrido": km_total,
        "litros_total": round(litros_totais_para_media, 2),
        "detalhes": detalhes
    }
