"""Frota — telemetria: ingestão e consulta de posições GPS por veículo.

Mesmas regras do resto de `services/frota.py`:
- `tenant_id` vem sempre do caller, nunca do payload.
- `id_veiculo` é validado **same-tenant** antes de qualquer gravação ou
  leitura (`frota.obter_veiculo`): a FK `frota.veiculo(id)` garante que o
  veículo existe, mas não que é do tenant — sem essa checagem, um tenant
  gravaria posição no veículo de outro. Veículo de outro tenant (ou excluído)
  é **404**, igual a inexistente.

Ingestão idempotente: o índice único `(tenant_id, id_veiculo, data_hora)`
com `ON CONFLICT DO NOTHING` faz o reenvio de um lote (retry do rastreador
após timeout) não duplicar pontos. A resposta diz quantos foram ignorados.

Fora desta fatia (backlog §2.3): km/l, trajeto/rotas derivados, retenção da
série e o canal de ingestão definitivo (provider externo × hardware próprio).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import tenant_filter
from ..models import VeiculoPosicao
from ..schemas.frota_telemetria import MAX_POSICOES_POR_CONSULTA, PosicoesLoteCreate
from .frota import obter_veiculo


def _utc_sem_fuso(valor: datetime) -> datetime:
    """A coluna é `TIMESTAMP WITHOUT TIME ZONE` em UTC. Instante com fuso é
    convertido; instante sem fuso é tomado como UTC (convenção do schema)."""
    if valor.tzinfo is None:
        return valor
    return valor.astimezone(timezone.utc).replace(tzinfo=None)


async def registrar_posicoes(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int,
    payload: PosicoesLoteCreate,
) -> dict[str, int]:
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=id_veiculo)

    agora = datetime.utcnow()
    # Dedup dentro do próprio lote, explícito: duas leituras com o mesmo
    # instante no mesmo payload valem como uma (fica a primeira) e contam como
    # `ignoradas`, sem depender de como o ON CONFLICT trata duplicata interna.
    linhas: dict[datetime, dict] = {}
    for p in payload.posicoes:
        data_hora = _utc_sem_fuso(p.data_hora)
        if data_hora in linhas:
            continue
        linhas[data_hora] = {
            "tenant_id": tenant_id,
            "id_veiculo": id_veiculo,
            "data_hora": data_hora,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "velocidade": p.velocidade,
            "ignicao_ligada": p.ignicao_ligada,
            "criado_em": agora,
        }

    stmt = (
        pg_insert(VeiculoPosicao)
        .values(list(linhas.values()))
        .on_conflict_do_nothing(
            index_elements=["tenant_id", "id_veiculo", "data_hora"]
        )
        .returning(VeiculoPosicao.id)
    )
    inseridas = len((await db.execute(stmt)).scalars().all())
    await db.commit()

    recebidas = len(payload.posicoes)
    return {
        "recebidas": recebidas,
        "registradas": inseridas,
        "ignoradas": recebidas - inseridas,
    }


async def listar_posicoes(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_veiculo: int,
    inicio: datetime,
    fim: datetime,
) -> list[VeiculoPosicao]:
    """Posições do veículo em `[inicio, fim]`, em ordem cronológica.

    Período com mais de `MAX_POSICOES_POR_CONSULTA` pontos é **422**, não
    truncado: um trajeto cortado em silêncio desenharia no mapa um percurso que
    o veículo não fez."""
    inicio = _utc_sem_fuso(inicio)
    fim = _utc_sem_fuso(fim)
    if fim < inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O fim do período não pode ser anterior ao início.",
        )
    await obter_veiculo(db, tenant_id=tenant_id, veiculo_id=id_veiculo)

    stmt = tenant_filter(select(VeiculoPosicao), VeiculoPosicao, tenant_id)
    stmt = (
        stmt.where(
            VeiculoPosicao.id_veiculo == id_veiculo,
            VeiculoPosicao.data_hora >= inicio,
            VeiculoPosicao.data_hora <= fim,
        )
        .order_by(VeiculoPosicao.data_hora.asc())
        .limit(MAX_POSICOES_POR_CONSULTA + 1)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    if len(rows) > MAX_POSICOES_POR_CONSULTA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"O período tem mais de {MAX_POSICOES_POR_CONSULTA} posições; "
                "reduza o intervalo."
            ),
        )
    return rows
