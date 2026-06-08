"""Frota PR-6 — documentos do veículo + alertas de vencimento.

Cobre o serviço de domínio (`services/frota.py`): CRUD tenant-scoped de
documentos do veículo, isolamento cross-tenant (404), soft-delete, whitelist de
edição e os alertas de vencido / a vencer. Mesmo padrão dos demais testes de
frota (provisionar_tenant + admin_engine).
"""
from __future__ import annotations

import itertools
import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.frota import (
    VeiculoCreate,
    VeiculoDocumentoCreate,
    VeiculoDocumentoUpdate,
)
from app.services import frota as frota_svc
from app.services.provisioning_tenant import provisionar_tenant

HOJE = date.today()


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("doc")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Doc", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


# Sequência monotônica garante placa única por tenant (formato ABC1234 válido)
# mesmo quando um teste cria mais de um veículo no mesmo tenant.
_placa_seq = itertools.count(1)


def _placa() -> str:
    return f"AAA{next(_placa_seq) % 10000:04d}"


async def _veiculo(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        v = await frota_svc.criar_veiculo(
            s, tenant_id=tenant_id, payload=VeiculoCreate(placa=_placa())
        )
        return v.id


async def _criar_doc(
    engine,
    tenant_id: int,
    id_veiculo: int,
    *,
    tipo="crlv",
    vencimento: date,
    emissao: date | None = None,
    status_doc: str = "ativo",
):
    async with _sm(engine)() as s:
        return await frota_svc.criar_documento(
            s, tenant_id=tenant_id, id_veiculo=id_veiculo,
            payload=VeiculoDocumentoCreate(
                tipo_documento=tipo, data_vencimento=vencimento,
                data_emissao=emissao, status=status_doc,
            ),
        )


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
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


# ============================ Criação (caminho feliz) =======================
async def test_criar_documento_mesmo_tenant(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        doc = await _criar_doc(
            admin_engine, t.id, v, vencimento=HOJE + timedelta(days=200),
            emissao=HOJE - timedelta(days=10),
        )
        assert doc.id is not None
        assert doc.id_veiculo == v
        assert doc.tenant_id == t.id
        assert doc.tipo_documento == "crlv"
        assert doc.status == "ativo"
        assert doc.excluido is False
        assert doc.criado_em is not None  # server-side
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Criação (bloqueios) ===========================
async def test_bloqueia_criar_documento_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        with pytest.raises(HTTPException) as exc:  # tenant B não enxerga veículo de A
            await _criar_doc(
                admin_engine, b.id, va, vencimento=HOJE + timedelta(days=30)
            )
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_bloqueia_criar_documento_veiculo_inexistente(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        with pytest.raises(HTTPException) as exc:
            await _criar_doc(
                admin_engine, t.id, 999_999, vencimento=HOJE + timedelta(days=30)
            )
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_criar_documento_veiculo_excluido(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            await frota_svc.excluir_veiculo(s, tenant_id=t.id, veiculo_id=v)
        with pytest.raises(HTTPException) as exc:
            await _criar_doc(
                admin_engine, t.id, v, vencimento=HOJE + timedelta(days=30)
            )
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, t.id)


def test_bloqueia_data_emissao_posterior_ao_vencimento():
    with pytest.raises(ValidationError):
        VeiculoDocumentoCreate(
            tipo_documento="seguro",
            data_emissao=date(2030, 6, 1),
            data_vencimento=date(2030, 1, 1),
        )


async def test_bloqueia_update_data_emissao_posterior_ao_vencimento(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        doc = await _criar_doc(
            admin_engine, t.id, v, vencimento=HOJE + timedelta(days=100)
        )
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.atualizar_documento(
                    s, tenant_id=t.id, documento_id=doc.id,
                    payload=VeiculoDocumentoUpdate(
                        data_emissao=HOJE + timedelta(days=200)
                    ),
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Listagem ======================================
async def test_listar_documentos_por_veiculo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        outro_v = await _veiculo(admin_engine, t.id)
        await _criar_doc(admin_engine, t.id, v, tipo="crlv",
                         vencimento=HOJE + timedelta(days=10))
        await _criar_doc(admin_engine, t.id, v, tipo="seguro",
                         vencimento=HOJE + timedelta(days=20))
        await _criar_doc(admin_engine, t.id, outro_v, tipo="vistoria",
                         vencimento=HOJE + timedelta(days=5))
        async with _sm(admin_engine)() as s:
            docs = await frota_svc.listar_documentos_veiculo(
                s, tenant_id=t.id, id_veiculo=v
            )
        assert len(docs) == 2  # só os do veículo v
        assert {d.tipo_documento for d in docs} == {"crlv", "seguro"}
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Detalhe cross-tenant ==========================
async def test_detalhe_documento_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        doc = await _criar_doc(
            admin_engine, a.id, va, vencimento=HOJE + timedelta(days=30)
        )
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_documento(
                    s, tenant_id=b.id, documento_id=doc.id
                )
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ Update: whitelist =============================
def test_update_schema_descarta_campos_proibidos():
    m = VeiculoDocumentoUpdate.model_validate(
        {"numero": "ABC", "tenant_id": 1, "id": 9, "id_veiculo": 7,
         "excluido": True, "criado_em": "2030-01-01T00:00:00",
         "atualizado_em": "2030-01-01T00:00:00"}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"numero": "ABC"}
    for proibido in ("tenant_id", "id", "id_veiculo", "excluido", "criado_em"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


async def test_update_atualiza_campos_permitidos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        doc = await _criar_doc(
            admin_engine, t.id, v, vencimento=HOJE + timedelta(days=100)
        )
        async with _sm(admin_engine)() as s:
            atualizado = await frota_svc.atualizar_documento(
                s, tenant_id=t.id, documento_id=doc.id,
                payload=VeiculoDocumentoUpdate(
                    numero="CRLV-2030", orgao_emissor="DETRAN", status="substituido"
                ),
            )
        assert atualizado.numero == "CRLV-2030"
        assert atualizado.orgao_emissor == "DETRAN"
        assert atualizado.status == "substituido"
        assert atualizado.id_veiculo == v  # imutável
        assert atualizado.atualizado_em is not None
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Delete = soft-delete ==========================
async def test_delete_faz_soft_delete(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        doc = await _criar_doc(
            admin_engine, t.id, v, vencimento=HOJE + timedelta(days=30)
        )
        async with _sm(admin_engine)() as s:
            await frota_svc.excluir_documento(s, tenant_id=t.id, documento_id=doc.id)
        # 404 via serviço (filtra excluído)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_documento(s, tenant_id=t.id, documento_id=doc.id)
            assert exc.value.status_code == 404
        # linha permanece com excluido=true
        async with _sm(admin_engine)() as s:
            excluido = (
                await s.execute(
                    text("SELECT excluido FROM frota.veiculo_documento WHERE id=:i"),
                    {"i": doc.id},
                )
            ).scalar_one()
        assert excluido is True
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Alertas =======================================
async def test_alertas_retornam_vencidos_e_a_vencer(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        d_vencido = await _criar_doc(
            admin_engine, t.id, v, tipo="crlv", vencimento=HOJE - timedelta(days=5)
        )
        d_a_vencer = await _criar_doc(
            admin_engine, t.id, v, tipo="seguro", vencimento=HOJE + timedelta(days=10)
        )
        # fora da janela de 30 dias — não deve aparecer
        await _criar_doc(
            admin_engine, t.id, v, tipo="vistoria",
            vencimento=HOJE + timedelta(days=200),
        )
        async with _sm(admin_engine)() as s:
            grupos = await frota_svc.listar_alertas_documentos(
                s, tenant_id=t.id, dias=30
            )
        ids_vencidos = {d.id for d in grupos["vencidos"]}
        ids_a_vencer = {d.id for d in grupos["a_vencer"]}
        assert d_vencido.id in ids_vencidos
        assert d_a_vencer.id in ids_a_vencer
        assert d_vencido.id not in ids_a_vencer
        assert len(grupos["a_vencer"]) == 1  # vistoria de 200 dias fica de fora
    finally:
        await _cleanup(admin_engine, t.id)


async def test_alertas_param_dias_amplia_janela(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        d = await _criar_doc(
            admin_engine, t.id, v, vencimento=HOJE + timedelta(days=100)
        )
        async with _sm(admin_engine)() as s:
            g30 = await frota_svc.listar_alertas_documentos(s, tenant_id=t.id, dias=30)
            g120 = await frota_svc.listar_alertas_documentos(s, tenant_id=t.id, dias=120)
        assert d.id not in {x.id for x in g30["a_vencer"]}
        assert d.id in {x.id for x in g120["a_vencer"]}
    finally:
        await _cleanup(admin_engine, t.id)


async def test_alertas_ignoram_status_retirado(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        # substituido/cancelado não disparam alerta mesmo vencidos
        await _criar_doc(admin_engine, t.id, v, tipo="crlv",
                         vencimento=HOJE - timedelta(days=5), status_doc="substituido")
        await _criar_doc(admin_engine, t.id, v, tipo="seguro",
                         vencimento=HOJE - timedelta(days=5), status_doc="cancelado")
        async with _sm(admin_engine)() as s:
            grupos = await frota_svc.listar_alertas_documentos(
                s, tenant_id=t.id, dias=30
            )
        assert grupos["vencidos"] == []
        assert grupos["a_vencer"] == []
    finally:
        await _cleanup(admin_engine, t.id)


async def test_alertas_respeitam_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        await _criar_doc(
            admin_engine, a.id, va, vencimento=HOJE - timedelta(days=5)
        )
        async with _sm(admin_engine)() as s:
            grupos_b = await frota_svc.listar_alertas_documentos(
                s, tenant_id=b.id, dias=30
            )
        assert grupos_b["vencidos"] == []  # tenant B não enxerga docs de A
        assert grupos_b["a_vencer"] == []
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)
