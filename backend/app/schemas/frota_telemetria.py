from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

class PosicaoSchema(BaseModel):
    timestamp: datetime
    latitude: Decimal = Field(..., max_digits=10, decimal_places=8)
    longitude: Decimal = Field(..., max_digits=11, decimal_places=8)
    velocidade: Decimal | None = None
    ignicao_ligada: bool | None = None

class PosicaoResponse(PosicaoSchema):
    id: int
    id_veiculo: int
    criado_em: datetime

class ConsumoDetalheSchema(BaseModel):
    id_abastecimento: int
    data_abastecimento: datetime
    litros: Decimal
    km_percorrido: int
    eficiencia_km_l: Decimal

class ConsumoResponse(BaseModel):
    id_veiculo: int
    eficiencia_media_km_l: Decimal
    km_total_percorrido: int
    litros_total: Decimal
    detalhes: list[ConsumoDetalheSchema]
