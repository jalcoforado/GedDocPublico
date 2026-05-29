"""Admin SaaS / Gestão de Tenants (PR3a).

Cobre o serviço único de provisionamento (incl. **sob a role RLS de produção**
`aprimora_app`), a allowlist de admin de plataforma (403), atomicidade, slug
imutável/validação, limites/plano armazenados, módulos derivados do plano e
bloqueio por desativação.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import require_platform_admin
from app.config import get_settings, modulos_do_plano
from app.schemas.admin_tenant import AdminTenantOut, AdminTenantUpdate
from app.services.provisioning_tenant import (
    ProvisioningError,
    SlugIndisponivelError,
    provisionar_tenant,
    validar_slug,
)


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _cleanup(admin_engine, tenant_id: int) -> None:
    """Remove tudo que o provisionamento cria, em ordem FK-safe (via ged_user)."""
    Session = _sessionmaker(admin_engine)
    async with Session() as s:
        for stmt in (
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


def _novo_slug(prefixo: str) -> str:
    return f"{prefixo}{uuid.uuid4().hex[:8]}"


async def _provisionar(session_factory, slug, **kw):
    async with session_factory() as s:
        return await provisionar_tenant(
            s,
            slug=slug,
            nome=kw.get("nome", "Prefeitura Teste"),
            admin_email=kw.get("admin_email", f"{slug}@teste.local"),
            admin_nome=kw.get("admin_nome", "Administrador"),
            admin_cpf=kw.get("admin_cpf", uuid.uuid4().hex[:11]),
            plano=kw.get("plano", "basico"),
            limite_usuarios=kw.get("limite_usuarios"),
            limite_armazenamento_mb=kw.get("limite_armazenamento_mb"),
            ator_usuario_id=kw.get("ator_usuario_id"),
        )


# ---- serviço: provisionamento completo (admin_engine / ged_user) ----
async def test_provisiona_tenant_completo(admin_engine):
    slug = _novo_slug("prov")
    Session = _sessionmaker(admin_engine)
    tenant, senha = await _provisionar(
        Session, slug, plano="profissional", limite_usuarios=10, limite_armazenamento_mb=2048
    )
    try:
        assert senha and len(senha) >= 8
        async with Session() as s:
            t = (await s.execute(text("SELECT plano, limite_usuarios, limite_armazenamento_mb, ativo FROM aprimora_py.tenant WHERE id=:t"), {"t": tenant.id})).first()
            assert t.plano == "profissional" and t.limite_usuarios == 10 and t.limite_armazenamento_mb == 2048 and t.ativo is True
            # admin bcrypt-only (sem MD5)
            u = (await s.execute(text("SELECT senha, senha_bcrypt FROM utils.usuario WHERE tenant_id=:t"), {"t": tenant.id})).first()
            assert u.senha == "" and u.senha_bcrypt and u.senha_bcrypt.startswith("$2")
            for tbl in ("utils.grupo", "utils.usuario_grupo", "utils.unidade_trabalho", "protocolos.tipo_manifestante"):
                n = (await s.execute(text(f"SELECT count(*) FROM {tbl} WHERE tenant_id=:t"), {"t": tenant.id})).scalar_one()
                assert n == 1, f"{tbl} deveria ter 1 linha"
            audit = (await s.execute(text("SELECT count(*) FROM aprimora_py.audit_log WHERE tenant_id=:t AND acao='tenant.provisionado'"), {"t": tenant.id})).scalar_one()
            assert audit == 1
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---- CRÍTICO: provisionamento sob a role RLS de produção (aprimora_app) ----
async def test_provisiona_sob_rls_producao(admin_engine, app_session):
    """Roda o provisionamento como aprimora_app (NOBYPASSRLS). Se o
    SET LOCAL app.tenant_id não fosse aplicado, os inserts tenant-scoped
    falhariam na policy WITH CHECK. Sucesso = contexto setado corretamente."""
    slug = _novo_slug("rls")
    tenant, senha = await provisionar_tenant(
        app_session, slug=slug, nome="RLS Prod", admin_email=f"{slug}@t.local",
        admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
    )
    try:
        assert tenant.id and senha
        # confirma via ged_user (bypass) que o bootstrap tenant-scoped foi gravado
        async with _sessionmaker(admin_engine)() as s:
            n = (await s.execute(text("SELECT count(*) FROM utils.usuario WHERE tenant_id=:t"), {"t": tenant.id})).scalar_one()
            assert n == 1
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---- slug duplicado / inválido / reservado ----
async def test_slug_duplicado_409(admin_engine):
    slug = _novo_slug("dup")
    Session = _sessionmaker(admin_engine)
    tenant, _ = await _provisionar(Session, slug)
    try:
        with pytest.raises(SlugIndisponivelError):
            await _provisionar(Session, slug, admin_cpf=uuid.uuid4().hex[:11])
    finally:
        await _cleanup(admin_engine, tenant.id)


def test_slug_validacao():
    assert validar_slug("Sobral-2") == "sobral-2"
    for ruim in ("ab", "-bad", "bad-", "admin", "www", "com espaco", "a"):
        with pytest.raises(ProvisioningError):
            validar_slug(ruim)


# ---- atomicidade: falha no meio → rollback (sem tenant parcial) ----
async def test_bootstrap_transacional_rollback(admin_engine, monkeypatch):
    slug = _novo_slug("rollbk")
    import app.services.provisioning_tenant as ps

    def _boom(_):
        raise RuntimeError("falha simulada após criar o tenant")

    monkeypatch.setattr(ps, "hash_password", _boom)
    Session = _sessionmaker(admin_engine)
    async with Session() as s:
        with pytest.raises(RuntimeError):
            await provisionar_tenant(
                s, slug=slug, nome="X", admin_email="x@x.local",
                admin_nome="X", admin_cpf=uuid.uuid4().hex[:11],
            )
    async with Session() as s:
        existe = (await s.execute(text("SELECT id FROM aprimora_py.tenant WHERE slug=:s"), {"s": slug})).scalar_one_or_none()
    assert existe is None  # rollback total — sem tenant órfão


# ---- allowlist de admin de plataforma (403) ----
async def test_require_platform_admin_allowlist(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("PLATFORM_ADMIN_EMAILS", "ops@aprimora.app, boss@x.com")
    try:
        allow = SimpleNamespace(email="OPS@aprimora.app")  # case-insensitive
        assert (await require_platform_admin(current=allow)) is allow
        # super-usuário de tenant comum NÃO é admin de plataforma
        with pytest.raises(HTTPException) as ei:
            await require_platform_admin(current=SimpleNamespace(email="su@prefeitura.gov.br"))
        assert ei.value.status_code == 403
        with pytest.raises(HTTPException):
            await require_platform_admin(current=SimpleNamespace(email=""))
    finally:
        get_settings.cache_clear()


# ---- desativação bloqueia resolução por subdomínio ----
async def test_desativado_bloqueia_resolucao(admin_engine):
    slug = _novo_slug("deact")
    Session = _sessionmaker(admin_engine)
    tenant, _ = await _provisionar(Session, slug)
    try:
        async with Session() as s:
            await s.execute(text("UPDATE aprimora_py.tenant SET ativo=false WHERE id=:t"), {"t": tenant.id})
            await s.commit()
        # mesma query do TenantMiddleware: slug + ativo=true → não resolve
        async with Session() as s:
            achado = (await s.execute(text("SELECT id FROM aprimora_py.tenant WHERE slug=:s AND ativo=true"), {"s": slug})).scalar_one_or_none()
        assert achado is None
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---- contratos: slug imutável, módulos por plano, listagem sem dados internos ----
def test_update_schema_nao_tem_slug():
    assert "slug" not in AdminTenantUpdate.model_fields


def test_modulos_derivam_do_plano():
    assert "protocolo" in modulos_do_plano("basico")
    assert len(modulos_do_plano("enterprise")) > len(modulos_do_plano("basico"))
    assert modulos_do_plano("inexistente") == modulos_do_plano("basico")


def test_admin_out_so_registro_de_tenant():
    campos = set(AdminTenantOut.model_fields)
    # nunca expõe dados tenant-scoped (conteúdo interno do tenant)
    assert {"usuarios", "processos", "anexos", "manifestantes"}.isdisjoint(campos)


def test_cli_usa_mesmo_servico():
    from app.cli import tenant as cli
    assert cli.provisionar_tenant is provisionar_tenant
