"""Frota (operacional) — abastecimentos de veículos.

Cobre o serviço de domínio (`services/frota.py`): CRUD tenant-scoped, validação
same-tenant de veículo/motorista, atualização condicional da quilometragem do
veículo (sem mexer na situação), resumo agregado, whitelist e soft-delete.
"""
from __future__ import annotations

import itertools
import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.frota import (
    MotoristaCreate,
    VeiculoAbastecimentoCreate,
    VeiculoAbastecimentoUpdate,
    VeiculoCreate,
)
from app.services import frota as frota_svc
from app.services.provisioning_tenant import provisionar_tenant

HOJE = date.today()
_placa_seq = itertools.count(1)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("abast")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Abast", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _placa() -> str:
    return f"AAA{next(_placa_seq) % 10000:04d}"


async def _veiculo(engine, tenant_id: int, *, km=0, situacao="disponivel") -> int:
    async with _sm(engine)() as s:
        v = await frota_svc.criar_veiculo(
            s, tenant_id=tenant_id,
            payload=VeiculoCreate(placa=_placa(), quilometragem_atual=km, situacao=situacao),
        )
        return v.id


async def _motorista(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        m = await frota_svc.criar_motorista(
            s, tenant_id=tenant_id,
            payload=MotoristaCreate(
                nome="Cond", cpf=str(uuid.uuid4().int)[:11], cnh_numero=str(uuid.uuid4().int)[:11],
                cnh_categoria="B", cnh_validade=date(2031, 1, 1),
            ),
        )
        return m.id


async def _criar_abast(engine, tenant_id, id_veiculo, *, km, litros=40.0, valor=300.0,
                       id_motorista=None):
    async with _sm(engine)() as s:
        return await frota_svc.criar_abastecimento(
            s, tenant_id=tenant_id, id_veiculo=id_veiculo,
            payload=VeiculoAbastecimentoCreate(
                id_veiculo=id_veiculo, km_atual=km, litros=litros, valor_total=valor,
                id_motorista=id_motorista,
            ),
        )


async def _veiculo_estado(engine, veiculo_id: int):
    async with _sm(engine)() as s:
        return (
            await s.execute(
                text("SELECT situacao, quilometragem_atual FROM frota.veiculo WHERE id=:i"),
                {"i": veiculo_id},
            )
        ).one()


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM frota.veiculo_abastecimento WHERE tenant_id=:t",
            "DELETE FROM frota.veiculo_manutencao WHERE tenant_id=:t",
            "DELETE FROM frota.veiculo_documento WHERE tenant_id=:t",
            "DELETE FROM frota.solicitacao_veiculo WHERE tenant_id=:t",
            "DELETE FROM frota.motorista WHERE tenant_id=:t",
            "DELETE FROM frota.veiculo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


# ============================ Criação + km do veículo =======================
async def test_criar_abastecimento_atualiza_km_se_maior(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id, km=1000)
        a = await _criar_abast(admin_engine, t.id, v, km=1500)
        assert a.id is not None
        assert float(a.litros) == 40.0
        sit, km = await _veiculo_estado(admin_engine, v)
        assert km == 1500                 # hodômetro avançou
        assert sit == "disponivel"        # situação NÃO muda
    finally:
        await _cleanup(admin_engine, t.id)


async def test_criar_abastecimento_nao_reduz_km(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id, km=5000)
        await _criar_abast(admin_engine, t.id, v, km=4000)  # km menor, registro retroativo
        _, km = await _veiculo_estado(admin_engine, v)
        assert km == 5000                 # não regride
    finally:
        await _cleanup(admin_engine, t.id)


async def test_abastecimento_com_motorista_same_tenant(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        m = await _motorista(admin_engine, t.id)
        a = await _criar_abast(admin_engine, t.id, v, km=10, id_motorista=m)
        assert a.id_motorista == m
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Bloqueios =====================================
async def test_bloqueia_abastecimento_veiculo_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        with pytest.raises(HTTPException) as exc:
            await _criar_abast(admin_engine, b.id, va, km=10)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_bloqueia_motorista_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        vb = await _veiculo(admin_engine, b.id)
        ma = await _motorista(admin_engine, a.id)
        with pytest.raises(HTTPException) as exc:  # motorista de A em abastecimento de B
            await _criar_abast(admin_engine, b.id, vb, km=10, id_motorista=ma)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


def test_bloqueia_litros_nao_positivo():
    with pytest.raises(ValidationError):
        VeiculoAbastecimentoCreate(id_veiculo=1, km_atual=10, litros=0, valor_total=100)


def test_bloqueia_valor_negativo():
    with pytest.raises(ValidationError):
        VeiculoAbastecimentoCreate(id_veiculo=1, km_atual=10, litros=10, valor_total=-1)


# ============================ Listagem / resumo =============================
async def test_listar_e_resumo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id, km=0)
        await _criar_abast(admin_engine, t.id, v, km=100, litros=40, valor=300)
        await _criar_abast(admin_engine, t.id, v, km=500, litros=60, valor=480)
        async with _sm(admin_engine)() as s:
            lista = await frota_svc.listar_abastecimentos(s, tenant_id=t.id, id_veiculo=v)
            resumo = await frota_svc.resumo_abastecimentos(s, tenant_id=t.id)
        assert len(lista) == 2
        assert resumo["total_abastecimentos"] == 2
        assert resumo["total_litros"] == 100.0
        assert resumo["total_valor"] == 780.0
        assert resumo["media_valor_litro"] == round(780.0 / 100.0, 4)
        assert resumo["ultimo_abastecimento"] == HOJE
    finally:
        await _cleanup(admin_engine, t.id)


async def test_resumo_vazio(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            resumo = await frota_svc.resumo_abastecimentos(s, tenant_id=t.id)
        assert resumo["total_abastecimentos"] == 0
        assert resumo["total_litros"] == 0
        assert resumo["media_valor_litro"] is None
        assert resumo["ultimo_abastecimento"] is None
    finally:
        await _cleanup(admin_engine, t.id)


async def test_resumo_respeita_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        await _criar_abast(admin_engine, a.id, va, km=10)
        async with _sm(admin_engine)() as s:
            resumo_b = await frota_svc.resumo_abastecimentos(s, tenant_id=b.id)
        assert resumo_b["total_abastecimentos"] == 0
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ Update / whitelist ============================
def test_update_schema_descarta_proibidos():
    m = VeiculoAbastecimentoUpdate.model_validate(
        {"posto": "Posto X", "id_veiculo": 7, "tenant_id": 1, "id": 9, "excluido": True}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"posto": "Posto X"}
    for proibido in ("id_veiculo", "tenant_id", "id", "excluido"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


async def test_update_e_soft_delete_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        ab = await _criar_abast(admin_engine, a.id, va, km=10)
        async with _sm(admin_engine)() as s:
            atualizado = await frota_svc.atualizar_abastecimento(
                s, tenant_id=a.id, abastecimento_id=ab.id,
                payload=VeiculoAbastecimentoUpdate(posto="Posto Central", valor_total=350),
            )
        assert atualizado.posto == "Posto Central"
        assert float(atualizado.valor_total) == 350
        # cross-tenant detalhe -> 404
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_abastecimento(s, tenant_id=b.id, abastecimento_id=ab.id)
            assert exc.value.status_code == 404
        # soft delete
        async with _sm(admin_engine)() as s:
            await frota_svc.excluir_abastecimento(s, tenant_id=a.id, abastecimento_id=ab.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_abastecimento(s, tenant_id=a.id, abastecimento_id=ab.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)
