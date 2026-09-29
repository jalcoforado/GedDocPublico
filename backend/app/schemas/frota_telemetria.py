"""Frota — telemetria (posições GPS). Schemas de entrada e saída.

`id_veiculo` vem do path e `tenant_id` do caller: nenhum dos dois entra no
schema de entrada. `data_hora` com fuso é convertida para UTC sem fuso no
serviço (a coluna é `TIMESTAMP WITHOUT TIME ZONE`, como o resto do schema).
"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# Teto de pontos por requisição. Um rastreador típico manda 1 ponto a cada
# 10–30 s; 1.000 cobrem horas de buffer offline sem abrir porta para um POST
# de milhões de linhas numa transação só.
MAX_POSICOES_POR_LOTE = 1000

# Teto de pontos devolvidos numa consulta de período.
MAX_POSICOES_POR_CONSULTA = 5000


class PosicaoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_hora: datetime
    latitude: Decimal = Field(..., ge=-90, le=90, max_digits=10, decimal_places=8)
    longitude: Decimal = Field(..., ge=-180, le=180, max_digits=11, decimal_places=8)
    velocidade: Decimal | None = Field(None, ge=0, max_digits=5, decimal_places=2)
    ignicao_ligada: bool | None = None


class PosicoesLoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    posicoes: list[PosicaoCreate] = Field(
        ..., min_length=1, max_length=MAX_POSICOES_POR_LOTE
    )


class PosicoesLoteOut(BaseModel):
    """Resultado da ingestão. `ignoradas` = pontos já gravados antes (mesmo
    veículo e mesma `data_hora`) — reenvio de lote é idempotente."""

    recebidas: int
    registradas: int
    ignoradas: int


class PosicaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_veiculo: int
    data_hora: datetime
    latitude: Decimal
    longitude: Decimal
    velocidade: Decimal | None
    ignicao_ligada: bool | None
    criado_em: datetime
