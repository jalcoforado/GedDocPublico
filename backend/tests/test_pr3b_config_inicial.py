"""PR 3b — Bootstrap configurável / configuração inicial do tenant.

Cobre:
- `atualizar_config_institucional`: whitelist (ignora campos de plataforma),
  escopo por tenant_id (sem cross-tenant), validação de `id_unidade_padrao`
  (existe, do tenant, ativa).
- `resetar_senha_usuario`: gera temporária, persiste só hash moderno, zera MD5,
  audita (marca SU), 404 cross-tenant.
- `calcular_onboarding`: reflete o estado real (vazio → false; preenchido → true).
- Gate `configuracao:atualizar`: SU bypassa; não-SU sem a transação → 403.
- Schema `TenantInstitucionalUpdate` descarta extras (id/slug/plano/…).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.password import verify_password
from app.auth.perms import require_permission
from app.models import Tenant, Usuario
from app.schemas.tenant import TenantInstitucionalUpdate
from app.services.permissoes import UserPermissions
from app.services.provisioning_tenant import provisionar_tenant
from app.services.tenant_config import (
    atualizar_config_institucional,
    calcular_onboarding,
)
from app.services.usuario_senha import resetar_senha_usuario


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(prefixo: str) -> str:
    return f"{prefixo}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine, **kw) -> Tenant:
    slug = _slug(kw.get("prefixo", "pr3b"))
    async with _sessionmaker(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome=kw.get("nome", "Prefeitura Teste"),
            admin_email=f"{slug}@teste.local",
            admin_nome="Administrador",
            admin_cpf=uuid.uuid4().hex[:11],
            plano=kw.get("plano", "basico"),
        )
    return tenant


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sessionmaker(engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.especie_documental WHERE tenant_id=:t",
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


async def _unidade_id(engine, tenant_id: int) -> int:
    async with _sessionmaker(engine)() as s:
        return int(
            (
                await s.execute(
                    text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )


# ---------- whitelist + escopo ----------
async def test_atualiza_so_institucional_ignora_plataforma(admin_engine):
    tenant = await _provisionar(admin_engine, plano="basico")
    try:
        # Corpo com campos PROIBIDOS junto dos permitidos: o schema descarta os extras.
        payload = TenantInstitucionalUpdate.model_validate(
            {
                "nome": "Prefeitura Nova",
                "sigla": "PMN",
                "email_institucional": "contato@pmn.gov.br",
                # proibidos — devem ser ignorados:
                "id": 999999,
                "slug": "hackeado",
                "plano": "enterprise",
                "ativo": False,
                "limite_usuarios": 1,
                "cnpj": "00000000000000",
            }
        )
        async with _sessionmaker(admin_engine)() as s:
            await atualizar_config_institucional(s, tenant_id=tenant.id, payload=payload)

        async with _sessionmaker(admin_engine)() as s:
            t = (await s.execute(select(Tenant).where(Tenant.id == tenant.id))).scalar_one()
            assert t.nome == "Prefeitura Nova"
            assert t.sigla == "PMN"
            assert t.email_institucional == "contato@pmn.gov.br"
            # plataforma intacta
            assert t.slug == tenant.slug
            assert t.plano == "basico"
            assert t.ativo is True
            assert t.limite_usuarios is None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_escopo_por_tenant_id_sem_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine, nome="Tenant A")
    b = await _provisionar(admin_engine, nome="Tenant B")
    try:
        async with _sessionmaker(admin_engine)() as s:
            await atualizar_config_institucional(
                s, tenant_id=a.id, payload=TenantInstitucionalUpdate(nome="Só o A muda")
            )
        async with _sessionmaker(admin_engine)() as s:
            ta = (await s.execute(select(Tenant).where(Tenant.id == a.id))).scalar_one()
            tb = (await s.execute(select(Tenant).where(Tenant.id == b.id))).scalar_one()
            assert ta.nome == "Só o A muda"
            assert tb.nome == "Tenant B"  # intacto
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- id_unidade_padrao ----------
async def test_unidade_padrao_do_tenant_aceita(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        async with _sessionmaker(admin_engine)() as s:
            t = await atualizar_config_institucional(
                s, tenant_id=tenant.id, payload=TenantInstitucionalUpdate(id_unidade_padrao=uid)
            )
            assert t.id_unidade_padrao == uid
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_unidade_padrao_de_outro_tenant_rejeitada(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        uid_b = await _unidade_id(admin_engine, b.id)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await atualizar_config_institucional(
                    s, tenant_id=a.id, payload=TenantInstitucionalUpdate(id_unidade_padrao=uid_b)
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_unidade_padrao_inativa_rejeitada(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        async with _sessionmaker(admin_engine)() as s:
            await s.execute(
                text("UPDATE utils.unidade_trabalho SET excluido=true WHERE id=:i"), {"i": uid}
            )
            await s.commit()
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await atualizar_config_institucional(
                    s, tenant_id=tenant.id, payload=TenantInstitucionalUpdate(id_unidade_padrao=uid)
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- reset de senha temporária ----------
async def test_reset_gera_persiste_hash_e_audita(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            admin = (
                await s.execute(select(Usuario).where(Usuario.tenant_id == tenant.id))
            ).scalar_one()
            user, senha_temp = await resetar_senha_usuario(
                s, usuario_id=admin.id, tenant_id=tenant.id, ator_usuario_id=admin.id
            )
        assert senha_temp and len(senha_temp) >= 8

        async with _sessionmaker(admin_engine)() as s:
            row = (
                await s.execute(
                    text("SELECT senha, senha_bcrypt FROM utils.usuario WHERE id=:i"),
                    {"i": user.id},
                )
            ).first()
            assert row.senha == ""  # MD5 legado zerado
            assert row.senha_bcrypt and row.senha_bcrypt.startswith("$2")
            # login com a nova funciona; a senha não fica em claro
            ok, _ = verify_password(senha_temp, bcrypt_hash=row.senha_bcrypt, md5_hash=row.senha)
            assert ok is True

            audit = (
                await s.execute(
                    text(
                        "SELECT payload::text AS p FROM aprimora_py.audit_log "
                        "WHERE tenant_id=:t AND acao='usuario.senha_resetada'"
                    ),
                    {"t": tenant.id},
                )
            ).first()
            assert audit is not None
            assert senha_temp not in audit.p  # senha NUNCA no audit
            assert '"afetado_super_usuario": true' in audit.p  # admin provisionado é SU
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_reset_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            admin_b = (
                await s.execute(select(Usuario).where(Usuario.tenant_id == b.id))
            ).scalar_one()
            # tenta resetar o admin de B usando o tenant de A → 404
            with pytest.raises(HTTPException) as exc:
                await resetar_senha_usuario(
                    s, usuario_id=admin_b.id, tenant_id=a.id, ator_usuario_id=1
                )
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- onboarding ----------
async def test_onboarding_reflete_estado_real(admin_engine):
    # tenant "cru" (sem bootstrap) → tudo pendente nos itens calculados por contagem
    slug = _slug("onb")
    async with _sessionmaker(admin_engine)() as s:
        tid = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO aprimora_py.tenant (slug, nome, ativo, plano, criado_em) "
                        "VALUES (:s, 'Onb', true, 'basico', :n) RETURNING id"
                    ),
                    {"s": slug, "n": datetime.now()},
                )
            ).scalar_one()
        )
        await s.commit()
    try:
        async with _sessionmaker(admin_engine)() as s:
            tenant = (await s.execute(select(Tenant).where(Tenant.id == tid))).scalar_one()
            onb = await calcular_onboarding(s, tenant_id=tid, tenant=tenant)
        por_chave = {i.chave: i.concluido for i in onb.itens}
        assert por_chave["dados_institucionais"] is False
        assert por_chave["unidade_padrao"] is False
        assert por_chave["unidades"] is False
        assert por_chave["assuntos"] is False
        # módulo de assinatura está no plano básico → habilitado (placeholder honesto)
        assert por_chave["assinatura"] is True

        # preenche dados institucionais + cria uma unidade → itens viram true
        async with _sessionmaker(admin_engine)() as s:
            await atualizar_config_institucional(
                s,
                tenant_id=tid,
                payload=TenantInstitucionalUpdate(
                    email_institucional="x@x.gov.br",
                    telefone_institucional="(00) 0000-0000",
                    texto_boas_vindas_portal="Bem-vindo!",
                ),
            )
            await s.execute(
                text(
                    "INSERT INTO utils.unidade_trabalho (tenant_id, unidade_trabalho, excluido) "
                    "VALUES (:t, 'Protocolo', false)"
                ),
                {"t": tid},
            )
            await s.commit()

        async with _sessionmaker(admin_engine)() as s:
            tenant = (await s.execute(select(Tenant).where(Tenant.id == tid))).scalar_one()
            onb2 = await calcular_onboarding(s, tenant_id=tid, tenant=tenant)
        por_chave2 = {i.chave: i.concluido for i in onb2.itens}
        assert por_chave2["dados_institucionais"] is True
        assert por_chave2["unidades"] is True
        assert por_chave2["portal_cidadao"] is True
        assert onb2.concluidos > onb.concluidos
    finally:
        await _cleanup(admin_engine, tid)


# ---------- gate configuracao:atualizar (sem DB; monkeypatch) ----------
def _fake_user(uid: int = 7) -> Usuario:
    u = MagicMock(spec=Usuario)
    u.id = uid
    return u


def _patch_load(monkeypatch, perms: UserPermissions) -> None:
    async def fake_load(db, user_id, *, tenant_id):
        return perms

    monkeypatch.setattr("app.auth.perms.load_permissions", fake_load)


async def test_gate_configuracao_su_bypassa(monkeypatch):
    _patch_load(monkeypatch, UserPermissions(is_super_usuario=True, nivel_valor=0, items=[]))
    check = require_permission("configuracao", "atualizar")
    user = _fake_user()
    assert await check(user=user, tenant_id=1, db=MagicMock()) is user


async def test_gate_configuracao_nao_su_sem_transacao_403(monkeypatch):
    _patch_load(monkeypatch, UserPermissions(is_super_usuario=False, nivel_valor=5, items=[]))
    check = require_permission("configuracao", "atualizar")
    with pytest.raises(HTTPException) as exc:
        await check(user=_fake_user(), tenant_id=1, db=MagicMock())
    assert exc.value.status_code == 403
    assert "configuracao" in exc.value.detail


# ---------- schema: descarta extras ----------
def test_institucional_update_descarta_extras():
    m = TenantInstitucionalUpdate.model_validate(
        {"nome": "X", "plano": "enterprise", "slug": "y", "id": 1, "ativo": False}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"nome": "X"}
    for proibido in ("plano", "slug", "id", "ativo"):
        assert proibido not in dump
        assert not hasattr(m, proibido)
