"""Frota (operacional) — vistoria/checklist interno de veículos.

Cobre o serviço de domínio (`services/frota.py`): CRUD tenant-scoped, validação
same-tenant do veículo, NÃO alteração da situação do veículo (mesmo 'reprovada'),
whitelist, filtros e soft-delete.
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
    VeiculoCreate,
    VeiculoVistoriaCreate,
    VeiculoVistoriaUpdate,
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
    slug = _slug("vist")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Vist", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _placa() -> str:
    return f"AAA{next(_placa_seq) % 10000:04d}"


async def _veiculo(engine, tenant_id: int, *, situacao="disponivel") -> int:
    async with _sm(engine)() as s:
        v = await frota_svc.criar_veiculo(
            s, tenant_id=tenant_id,
            payload=VeiculoCreate(placa=_placa(), situacao=situacao),
        )
        return v.id


async def _criar_vist(engine, tenant_id, id_veiculo, *, tipo="periodica",
                      resultado="aprovada", pneus=True):
    async with _sm(engine)() as s:
        return await frota_svc.criar_vistoria(
            s, tenant_id=tenant_id, id_veiculo=id_veiculo,
            payload=VeiculoVistoriaCreate(
                id_veiculo=id_veiculo, tipo=tipo, resultado=resultado, pneus_ok=pneus,
            ),
        )


async def _veiculo_situacao(engine, veiculo_id: int) -> str:
    async with _sm(engine)() as s:
        return (
            await s.execute(
                text("SELECT situacao FROM frota.veiculo WHERE id=:i"), {"i": veiculo_id}
            )
        ).scalar_one()


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM frota.veiculo_vistoria WHERE tenant_id=:t",
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


# ============================ Criação =======================================
async def test_criar_vistoria_mesmo_tenant(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        vist = await _criar_vist(admin_engine, t.id, v, tipo="saida", resultado="aprovada")
        assert vist.id is not None
        assert vist.tipo == "saida"
        assert vist.resultado == "aprovada"
        assert vist.pneus_ok is True
        assert vist.luzes_ok is False     # default
        assert vist.data_vistoria == HOJE  # default server-side
    finally:
        await _cleanup(admin_engine, t.id)


async def test_vistoria_reprovada_nao_altera_situacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id, situacao="disponivel")
        await _criar_vist(admin_engine, t.id, v, resultado="reprovada", pneus=False)
        assert await _veiculo_situacao(admin_engine, v) == "disponivel"  # intocado
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_vistoria_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        with pytest.raises(HTTPException) as exc:
            await _criar_vist(admin_engine, b.id, va)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


def test_tipo_e_resultado_obrigatorios():
    with pytest.raises(ValidationError):
        VeiculoVistoriaCreate(id_veiculo=1, resultado="aprovada")  # falta tipo
    with pytest.raises(ValidationError):
        VeiculoVistoriaCreate(id_veiculo=1, tipo="saida")  # falta resultado
    with pytest.raises(ValidationError):
        VeiculoVistoriaCreate(id_veiculo=1, tipo="invalido", resultado="aprovada")


# ============================ Listagem / filtros ============================
async def test_listar_filtra_veiculo_e_resultado(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v1 = await _veiculo(admin_engine, t.id)
        v2 = await _veiculo(admin_engine, t.id)
        await _criar_vist(admin_engine, t.id, v1, resultado="aprovada")
        await _criar_vist(admin_engine, t.id, v1, resultado="reprovada")
        await _criar_vist(admin_engine, t.id, v2, resultado="aprovada")
        async with _sm(admin_engine)() as s:
            do_v1 = await frota_svc.listar_vistorias(s, tenant_id=t.id, id_veiculo=v1)
            reprovadas = await frota_svc.listar_vistorias(s, tenant_id=t.id, resultado="reprovada")
        assert len(do_v1) == 2
        assert len(reprovadas) == 1
        assert all(x.resultado == "reprovada" for x in reprovadas)
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Update / whitelist ============================
async def test_update_campos_e_whitelist(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        vist = await _criar_vist(admin_engine, t.id, v, resultado="com_ressalvas")
        async with _sm(admin_engine)() as s:
            atualizada = await frota_svc.atualizar_vistoria(
                s, tenant_id=t.id, vistoria_id=vist.id,
                payload=VeiculoVistoriaUpdate(resultado="aprovada", luzes_ok=True),
            )
        assert atualizada.resultado == "aprovada"
        assert atualizada.luzes_ok is True
        assert atualizada.id_veiculo == v  # imutável
    finally:
        await _cleanup(admin_engine, t.id)


def test_update_schema_descarta_proibidos():
    m = VeiculoVistoriaUpdate.model_validate(
        {"luzes_ok": True, "id_veiculo": 7, "tenant_id": 1, "id": 9, "excluido": True}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"luzes_ok": True}
    for proibido in ("id_veiculo", "tenant_id", "id", "excluido"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ============================ Soft-delete / cross-tenant ====================
async def test_delete_soft_e_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        vist = await _criar_vist(admin_engine, a.id, va)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_vistoria(s, tenant_id=b.id, vistoria_id=vist.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            await frota_svc.excluir_vistoria(s, tenant_id=a.id, vistoria_id=vist.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_vistoria(s, tenant_id=a.id, vistoria_id=vist.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            excluido = (
                await s.execute(
                    text("SELECT excluido FROM frota.veiculo_vistoria WHERE id=:i"),
                    {"i": vist.id},
                )
            ).scalar_one()
        assert excluido is True
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)
