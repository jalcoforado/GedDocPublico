"""Transporte Regulado PR-1 — cadastro de Permissionários.

Cobre o serviço de domínio (`services/transporte_regulado.py`): CRUD tenant-scoped,
normalização/unicidade de CPF, isolamento cross-tenant (404), whitelist de edição,
ações de situação (inativar/reativar/suspender) e soft-delete. Mesmo padrão dos
testes de frota (provisionar_tenant + admin_engine).
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import (
    PermissionarioCreate,
    PermissionarioUpdate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("perm")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Perm", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _cpf() -> str:
    return str(uuid.uuid4().int)[:11]


async def _criar(engine, tenant_id, *, cpf=None, tipo="taxi", situacao="pendente"):
    async with _sm(engine)() as s:
        return await tr_svc.criar_permissionario(
            s, tenant_id=tenant_id,
            payload=PermissionarioCreate(
                nome="Fulano de Tal", cpf=cpf or _cpf(), tipo_servico=tipo, situacao=situacao
            ),
        )


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM transporte_regulado.permissionario WHERE tenant_id=:t",
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
async def test_criar_permissionario(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _criar(admin_engine, t.id, tipo="mototaxi")
        assert p.id is not None
        assert p.tenant_id == t.id
        assert p.tipo_servico == "mototaxi"
        assert p.situacao == "pendente"      # default
        assert p.excluido is False
        assert p.criado_em is not None       # server-side
    finally:
        await _cleanup(admin_engine, t.id)


def test_cpf_normaliza():
    p = PermissionarioCreate(nome="X", cpf="123.456.789-01", tipo_servico="taxi")
    assert p.cpf == "12345678901"


def test_cpf_invalido_rejeitado():
    with pytest.raises(ValidationError):
        PermissionarioCreate(nome="X", cpf="123", tipo_servico="taxi")


def test_cnh_validade_obrigatoria_se_cnh_informada():
    with pytest.raises(ValidationError):
        PermissionarioCreate(nome="X", cpf="12345678901", tipo_servico="taxi",
                             cnh_numero="10000000001")  # falta cnh_validade


def test_tipo_servico_obrigatorio():
    with pytest.raises(ValidationError):
        PermissionarioCreate(nome="X", cpf="12345678901")  # falta tipo_servico


# ============================ Unicidade de CPF ==============================
async def test_cpf_duplicado_mesmo_tenant_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        cpf = _cpf()
        await _criar(admin_engine, t.id, cpf=cpf)
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, t.id, cpf=cpf)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_cpf_igual_em_outro_tenant_permitido(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        cpf = _cpf()
        pa = await _criar(admin_engine, a.id, cpf=cpf)
        pb = await _criar(admin_engine, b.id, cpf=cpf)  # mesmo CPF, outro tenant: OK
        assert pa.id != pb.id
        assert pa.cpf == pb.cpf == cpf
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_cpf_reutilizavel_apos_soft_delete(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        cpf = _cpf()
        p1 = await _criar(admin_engine, t.id, cpf=cpf)
        async with _sm(admin_engine)() as s:
            await tr_svc.excluir_permissionario(s, tenant_id=t.id, permissionario_id=p1.id)
        p2 = await _criar(admin_engine, t.id, cpf=cpf)  # CPF liberado após soft-delete
        assert p2.id != p1.id
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Cross-tenant 404 ==============================
async def test_detalhe_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        pa = await _criar(admin_engine, a.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await tr_svc.obter_permissionario(s, tenant_id=b.id, permissionario_id=pa.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ Update / whitelist ============================
async def test_update_atualiza_campos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _criar(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            up = await tr_svc.atualizar_permissionario(
                s, tenant_id=t.id, permissionario_id=p.id,
                payload=PermissionarioUpdate(telefone="88999990000", numero_permissao="PERM-001"),
            )
        assert up.telefone == "88999990000"
        assert up.numero_permissao == "PERM-001"
    finally:
        await _cleanup(admin_engine, t.id)


def test_update_schema_descarta_proibidos():
    m = PermissionarioUpdate.model_validate(
        {"telefone": "88999990000", "tenant_id": 1, "id": 9, "excluido": True,
         "criado_em": "2030-01-01T00:00:00", "atualizado_em": "2030-01-01T00:00:00"}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"telefone": "88999990000"}
    for proibido in ("tenant_id", "id", "excluido", "criado_em", "atualizado_em"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ============================ Ações de situação =============================
async def test_inativar_reativar_suspender(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _criar(admin_engine, t.id, situacao="ativo")
        async with _sm(admin_engine)() as s:
            inativo = await tr_svc.set_situacao_permissionario(
                s, tenant_id=t.id, permissionario_id=p.id, situacao="inativo")
        assert inativo.situacao == "inativo"
        async with _sm(admin_engine)() as s:
            ativo = await tr_svc.set_situacao_permissionario(
                s, tenant_id=t.id, permissionario_id=p.id, situacao="ativo")
        assert ativo.situacao == "ativo"
        async with _sm(admin_engine)() as s:
            suspenso = await tr_svc.set_situacao_permissionario(
                s, tenant_id=t.id, permissionario_id=p.id, situacao="suspenso")
        assert suspenso.situacao == "suspenso"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Listagem / filtros ============================
async def test_listar_filtra_situacao_e_tipo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        await _criar(admin_engine, t.id, tipo="taxi", situacao="ativo")
        await _criar(admin_engine, t.id, tipo="mototaxi", situacao="pendente")
        async with _sm(admin_engine)() as s:
            ativos = await tr_svc.listar_permissionarios(s, tenant_id=t.id, situacao="ativo")
            mototaxi = await tr_svc.listar_permissionarios(s, tenant_id=t.id, tipo_servico="mototaxi")
        assert len(ativos) == 1 and ativos[0].situacao == "ativo"
        assert len(mototaxi) == 1 and mototaxi[0].tipo_servico == "mototaxi"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Soft-delete ===================================
async def test_delete_faz_soft_delete(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _criar(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            await tr_svc.excluir_permissionario(s, tenant_id=t.id, permissionario_id=p.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await tr_svc.obter_permissionario(s, tenant_id=t.id, permissionario_id=p.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            excluido = (
                await s.execute(
                    text("SELECT excluido FROM transporte_regulado.permissionario WHERE id=:i"),
                    {"i": p.id},
                )
            ).scalar_one()
        assert excluido is True
    finally:
        await _cleanup(admin_engine, t.id)
