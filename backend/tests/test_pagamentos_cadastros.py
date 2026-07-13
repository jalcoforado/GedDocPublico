"""Pagamentos PAG-1 — cadastro de Credor.

Cobre o serviço de domínio (`services/pagamentos_cadastros.py`): CRUD
tenant-scoped, cifragem Fernet dos dados bancários em repouso, unicidade de
CNPJ/CPF por tenant, isolamento cross-tenant (404) e reveal decifrado. Mesmo
padrão dos testes de transporte regulado (provisionar_tenant + admin_engine).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import CredorCreate, DadosBancarios
from app.services import pagamentos_cadastros as svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pagcred")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _criar(engine, tenant_id, *, cnpj_cpf=None, dados_bancarios=None):
    async with _sm(engine)() as s:
        return await svc.criar_credor(
            s, tenant_id=tenant_id,
            payload=CredorCreate(
                tipo_pessoa="JURIDICA", cnpj_cpf=cnpj_cpf or _doc(), nome="Medlar LTDA",
                dados_bancarios=dados_bancarios,
            ),
        )


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.credor WHERE tenant_id=:t",
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


# ============================ Criação + cifragem =============================
async def test_criar_credor_com_dados_bancarios(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        dados = DadosBancarios(banco="001", agencia="1234", conta="5678-9", chave_pix="pix@medlar")
        c = await _criar(admin_engine, t.id, dados_bancarios=dados)
        saida = svc.credor_out(c)
        assert saida["tem_dados_bancarios"] is True
        assert c.tenant_id == t.id
    finally:
        await _cleanup(admin_engine, t.id)


async def test_dados_bancarios_credor_decifra_corretamente(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        dados = DadosBancarios(banco="001", agencia="1234", conta="5678-9", chave_pix="pix@medlar")
        c = await _criar(admin_engine, t.id, dados_bancarios=dados)
        async with _sm(admin_engine)() as s:
            revelado = await svc.dados_bancarios_credor(s, tenant_id=t.id, credor_id=c.id)
        assert revelado.chave_pix == "pix@medlar"
        assert revelado.banco == "001"
        assert revelado.agencia == "1234"
        assert revelado.conta == "5678-9"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_dados_bancarios_cifrados_em_repouso(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        dados = DadosBancarios(conta="SEGREDO123")
        c = await _criar(admin_engine, t.id, dados_bancarios=dados)
        async with _sm(admin_engine)() as s:
            row = (
                await s.execute(
                    text("SELECT conta_cif FROM pagamentos.credor WHERE id=:i"), {"i": c.id}
                )
            ).fetchone()
        assert row[0] is not None
        assert "SEGREDO123" not in row[0]
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Unicidade de documento ==========================
async def test_cnpj_cpf_duplicado_mesmo_tenant_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        doc = _doc()
        await _criar(admin_engine, t.id, cnpj_cpf=doc)
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, t.id, cnpj_cpf=doc)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Cross-tenant 404 =================================
async def test_obter_credor_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ca = await _criar(admin_engine, a.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await svc.obter_credor(s, tenant_id=b.id, credor_id=ca.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)
