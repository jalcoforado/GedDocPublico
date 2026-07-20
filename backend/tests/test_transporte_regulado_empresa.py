"""Transporte Regulado PR-2 — cadastro de Empresas reguladas.

Cobre o serviço de domínio (`services/transporte_regulado.py`): CRUD tenant-scoped,
normalização/unicidade de CNPJ, isolamento cross-tenant (404), whitelist de edição,
vínculo de representante permissionário (mesmo tenant), ações de situação
(inativar/reativar/suspender) e soft-delete. Mesmo padrão dos testes de Permissionário.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import (
    EmpresaCreate,
    EmpresaUpdate,
    PermissionarioCreate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("emp")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Emp", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _cnpj() -> str:
    return str(uuid.uuid4().int)[:14]


def _cpf() -> str:
    return str(uuid.uuid4().int)[:11]


async def _criar(engine, tenant_id, *, cnpj=None, tipo="taxi", situacao="pendente",
                 representante=None):
    async with _sm(engine)() as s:
        return await tr_svc.criar_empresa(
            s, tenant_id=tenant_id,
            payload=EmpresaCreate(
                razao_social="Transportes Acme LTDA", cnpj=cnpj or _cnpj(),
                tipo_servico=tipo, situacao=situacao,
                id_representante_permissionario=representante,
            ),
        )


async def _criar_permissionario(engine, tenant_id):
    async with _sm(engine)() as s:
        return await tr_svc.criar_permissionario(
            s, tenant_id=tenant_id,
            payload=PermissionarioCreate(nome="Rep", cpf=_cpf(), tipo_servico="taxi"),
        )


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM transporte_regulado.empresa WHERE tenant_id=:t",
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
async def test_criar_empresa(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        e = await _criar(admin_engine, t.id, tipo="transporte_escolar")
        assert e.id is not None
        assert e.tenant_id == t.id
        assert e.tipo_servico == "transporte_escolar"
        assert e.situacao == "pendente"      # default
        assert e.excluido is False
        assert e.criado_em is not None       # server-side
    finally:
        await _cleanup(admin_engine, t.id)


def test_cnpj_normaliza():
    e = EmpresaCreate(razao_social="X", cnpj="12.345.678/0001-90", tipo_servico="taxi")
    assert e.cnpj == "12345678000190"


def test_cnpj_invalido_rejeitado():
    with pytest.raises(ValidationError):
        EmpresaCreate(razao_social="X", cnpj="123", tipo_servico="taxi")


def test_razao_social_obrigatoria():
    with pytest.raises(ValidationError):
        EmpresaCreate(razao_social="", cnpj="12345678000190", tipo_servico="taxi")


def test_tipo_servico_obrigatorio():
    with pytest.raises(ValidationError):
        EmpresaCreate(razao_social="X", cnpj="12345678000190")  # falta tipo_servico


def test_uf_normaliza_e_valida():
    e = EmpresaCreate(razao_social="X", cnpj="12345678000190", tipo_servico="taxi", uf="ce")
    assert e.uf == "CE"
    with pytest.raises(ValidationError):
        EmpresaCreate(razao_social="X", cnpj="12345678000190", tipo_servico="taxi", uf="ABC")


# ============================ Unicidade de CNPJ =============================
async def test_cnpj_duplicado_mesmo_tenant_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        cnpj = _cnpj()
        await _criar(admin_engine, t.id, cnpj=cnpj)
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, t.id, cnpj=cnpj)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_cnpj_igual_em_outro_tenant_permitido(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        cnpj = _cnpj()
        ea = await _criar(admin_engine, a.id, cnpj=cnpj)
        eb = await _criar(admin_engine, b.id, cnpj=cnpj)  # mesmo CNPJ, outro tenant: OK
        assert ea.id != eb.id
        assert ea.cnpj == eb.cnpj == cnpj
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_cnpj_reutilizavel_apos_soft_delete(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        cnpj = _cnpj()
        e1 = await _criar(admin_engine, t.id, cnpj=cnpj)
        async with _sm(admin_engine)() as s:
            await tr_svc.excluir_empresa(s, tenant_id=t.id, empresa_id=e1.id)
        e2 = await _criar(admin_engine, t.id, cnpj=cnpj)  # CNPJ liberado após soft-delete
        assert e2.id != e1.id
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Cross-tenant 404 ==============================
async def test_detalhe_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ea = await _criar(admin_engine, a.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await tr_svc.obter_empresa(s, tenant_id=b.id, empresa_id=ea.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ Update / whitelist ============================
async def test_update_atualiza_campos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        e = await _criar(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            up = await tr_svc.atualizar_empresa(
                s, tenant_id=t.id, empresa_id=e.id,
                payload=EmpresaUpdate(nome_fantasia="Acme", numero_autorizacao="AUT-001"),
            )
        assert up.nome_fantasia == "Acme"
        assert up.numero_autorizacao == "AUT-001"
    finally:
        await _cleanup(admin_engine, t.id)


def test_update_schema_descarta_proibidos():
    m = EmpresaUpdate.model_validate(
        {"nome_fantasia": "Acme", "tenant_id": 1, "id": 9, "excluido": True,
         "criado_em": "2030-01-01T00:00:00", "atualizado_em": "2030-01-01T00:00:00"}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"nome_fantasia": "Acme"}
    for proibido in ("tenant_id", "id", "excluido", "criado_em", "atualizado_em"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ============================ Ações de situação =============================
async def test_inativar_reativar_suspender(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        e = await _criar(admin_engine, t.id, situacao="ativa")
        async with _sm(admin_engine)() as s:
            inativa = await tr_svc.set_situacao_empresa(
                s, tenant_id=t.id, empresa_id=e.id, situacao="inativa")
        assert inativa.situacao == "inativa"
        async with _sm(admin_engine)() as s:
            ativa = await tr_svc.set_situacao_empresa(
                s, tenant_id=t.id, empresa_id=e.id, situacao="ativa")
        assert ativa.situacao == "ativa"
        async with _sm(admin_engine)() as s:
            suspensa = await tr_svc.set_situacao_empresa(
                s, tenant_id=t.id, empresa_id=e.id, situacao="suspensa")
        assert suspensa.situacao == "suspensa"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Listagem / filtros ============================
async def test_listar_filtra_situacao_e_tipo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        await _criar(admin_engine, t.id, tipo="taxi", situacao="ativa")
        await _criar(admin_engine, t.id, tipo="mototaxi", situacao="pendente")
        async with _sm(admin_engine)() as s:
            ativas, _ = await tr_svc.listar_empresas(s, tenant_id=t.id, situacao="ativa")
            mototaxi, _ = await tr_svc.listar_empresas(s, tenant_id=t.id, tipo_servico="mototaxi")
        assert len(ativas) == 1 and ativas[0].situacao == "ativa"
        assert len(mototaxi) == 1 and mototaxi[0].tipo_servico == "mototaxi"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Representante permissionário ==================
async def test_representante_deve_ser_mesmo_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        rep_a = await _criar_permissionario(admin_engine, a.id)
        # representante do tenant A é aceito na empresa do tenant A
        ea = await _criar(admin_engine, a.id, representante=rep_a.id)
        assert ea.id_representante_permissionario == rep_a.id
        # representante do tenant A é rejeitado (404) numa empresa do tenant B
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, b.id, representante=rep_a.id)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ Soft-delete ===================================
async def test_delete_faz_soft_delete(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        e = await _criar(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            await tr_svc.excluir_empresa(s, tenant_id=t.id, empresa_id=e.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await tr_svc.obter_empresa(s, tenant_id=t.id, empresa_id=e.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            excluido = (
                await s.execute(
                    text("SELECT excluido FROM transporte_regulado.empresa WHERE id=:i"),
                    {"i": e.id},
                )
            ).scalar_one()
        assert excluido is True
    finally:
        await _cleanup(admin_engine, t.id)
