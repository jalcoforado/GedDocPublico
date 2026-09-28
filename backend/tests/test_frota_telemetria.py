"""Testes para o módulo de Telemetria de Frota (Item 2.3).

Cobre o registro de posições GPS, extração de trajeto e cálculo de
consumo de combustível com isolamento RLS multi-tenant.
"""
from __future__ import annotations

import itertools
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.frota import (
    VeiculoCreate,
    VeiculoAbastecimentoCreate,
)
from app.schemas.frota_telemetria import PosicaoSchema
from app.services import frota as frota_svc
from app.services import frota_telemetria as telemetria_svc
from app.services.provisioning_tenant import provisionar_tenant


_placa_seq = itertools.count(1)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("telem")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Prefeitura Telemetria", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _placa() -> str:
    return f"BBA{next(_placa_seq) % 10000:04d}"


async def _veiculo(engine, tenant_id: int, *, km=0, situacao="disponivel") -> int:
    async with _sm(engine)() as s:
        v = await frota_svc.criar_veiculo(
            s, tenant_id=tenant_id,
            payload=VeiculoCreate(placa=_placa(), quilometragem_atual=km, situacao=situacao),
        )
        return v.id


async def _criar_abast(engine, tenant_id, id_veiculo, *, km, litros=40.0, data_abast: date | None = None):
    async with _sm(engine)() as s:
        return await frota_svc.criar_abastecimento(
            s, tenant_id=tenant_id, id_veiculo=id_veiculo,
            payload=VeiculoAbastecimentoCreate(
                id_veiculo=id_veiculo, km_atual=km, litros=litros, valor_total=litros * 5.0,
                data_abastecimento=data_abast or date.today()
            ),
        )


@pytest.mark.asyncio
async def test_registrar_e_obter_trajeto(admin_engine):
    """Garante que a telemetria registra e retorna pontos GPS no intervalo."""
    t1 = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    v1 = await _veiculo(admin_engine, t1.id)
    v2 = await _veiculo(admin_engine, t2.id)

    agora = datetime.utcnow()
    pos_t1 = [
        PosicaoSchema(
            timestamp=agora - timedelta(minutes=10), latitude=Decimal("-23.5"), longitude=Decimal("-46.6"), velocidade=Decimal("40.5")
        ),
        PosicaoSchema(
            timestamp=agora - timedelta(minutes=5), latitude=Decimal("-23.6"), longitude=Decimal("-46.7"), velocidade=Decimal("50.0")
        ),
    ]

    async with _sm(admin_engine)() as s:
        qtd = await telemetria_svc.registrar_posicoes_gps(s, id_veiculo=v1, posicoes=pos_t1, tenant_id=t1.id)
    assert qtd == 2

    # Vazamento tenant-cruzado
    async with _sm(admin_engine)() as s:
        v2_trajeto = await telemetria_svc.obter_trajeto(s, v2, agora - timedelta(hours=1), agora, t2.id)
        assert len(v2_trajeto) == 0

    # Filtro de data
    async with _sm(admin_engine)() as s:
        trajeto_ok = await telemetria_svc.obter_trajeto(s, v1, agora - timedelta(hours=1), agora, t1.id)
        assert len(trajeto_ok) == 2
        assert trajeto_ok[0].velocidade == Decimal("40.5")
        assert trajeto_ok[1].velocidade == Decimal("50.0")

        # Range anterior
        trajeto_fora = await telemetria_svc.obter_trajeto(s, v1, agora - timedelta(hours=2), agora - timedelta(hours=1), t1.id)
        assert len(trajeto_fora) == 0


@pytest.mark.asyncio
async def test_calcular_consumo_combustivel(admin_engine):
    """Garante que o consumo km/l é calculado baseando-se na distância entre abastecimentos."""
    t = await _provisionar(admin_engine)
    v = await _veiculo(admin_engine, t.id, km=1000)

    # Menos de 2 abastecimentos: consumo indisponível (0.0)
    async with _sm(admin_engine)() as s:
        await _criar_abast(admin_engine, t.id, v, km=1000, litros=50.0, data_abast=date(2026, 1, 1))
        
        consumo_incompleto = await telemetria_svc.calcular_consumo_combustivel(s, v, t.id)
        assert consumo_incompleto["eficiencia_media_km_l"] == Decimal("0.0")
        assert consumo_incompleto["km_total_percorrido"] == 0

    # Adiciona abastecimentos subsequentes
    # 2o abastecimento (km 1500), 50 litros no percurso (1500-1000) => 500 / 50 = 10 km/l
    await _criar_abast(admin_engine, t.id, v, km=1500, litros=50.0, data_abast=date(2026, 1, 5))
    
    # 3o abastecimento (km 1800), 60 litros no percurso (1800-1500) => 300 / 60 = 5 km/l
    await _criar_abast(admin_engine, t.id, v, km=1800, litros=60.0, data_abast=date(2026, 1, 10))

    async with _sm(admin_engine)() as s:
        consumo = await telemetria_svc.calcular_consumo_combustivel(s, v, t.id)
        
        # Média = (500 + 300) / (50 + 60) = 800 / 110 = 7.27
        assert consumo["km_total_percorrido"] == 800
        assert consumo["litros_total"] == Decimal("110.0")
        
        # O Decimal pode ter mais casas
        assert round(consumo["eficiencia_media_km_l"], 2) == Decimal("7.27")
        
        # Detalhes: o detalhe #1 vai referenciar o percurso até o abastecimento #2
        # Detalhes: o detalhe #2 vai referenciar o percurso até o abastecimento #3
        assert len(consumo["detalhes"]) == 2
        
        assert consumo["detalhes"][0]["km_percorrido"] == 500
        assert consumo["detalhes"][0]["eficiencia_km_l"] == Decimal("10.0")
        
        assert consumo["detalhes"][1]["km_percorrido"] == 300
        assert consumo["detalhes"][1]["eficiencia_km_l"] == Decimal("5.0")
