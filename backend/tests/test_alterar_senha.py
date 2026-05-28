"""Troca self-service de senha (PR2c).

Cobre: sucesso (grava bcrypt), senha atual incorreta, e usuário legado MD5 que
após a troca passa a ter bcrypt — ou seja, deixa de cair no bloqueio de
assinatura (needs_rehash=False).
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.password import hash_md5, hash_password, verify_password
from app.models import Usuario
from app.services.conta import ContaError, alterar_senha


def _session(admin_engine):
    return async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)()


async def _criar_usuario(admin_engine, tenant_id, *, bcrypt: bool, senha: str) -> int:
    suf = uuid.uuid4().hex[:8]
    async with _session(admin_engine) as s:
        uid = int(
            (await s.execute(
                text(
                    "INSERT INTO utils.usuario (tenant_id, nome, email, senha, senha_bcrypt, cpf, ativo, excluido) "
                    "VALUES (:t,:n,:e,:senha,:bc,:cpf,true,false) RETURNING id"
                ),
                {
                    "t": tenant_id, "n": f"Conta {suf}", "e": f"{suf}@conta.local",
                    "senha": hash_md5(senha),
                    "bc": hash_password(senha) if bcrypt else None,
                    "cpf": uuid.uuid4().hex[:11],
                },
            )).scalar_one()
        )
        await s.commit()
    return uid


@pytest_asyncio.fixture
async def conta_tenant(two_tenants):
    tid, _ = two_tenants
    yield tid
    # usuários limpos pelo teardown de two_tenants? Não — limpamos aqui.


async def _load(admin_engine, uid) -> Usuario:
    async with _session(admin_engine) as s:
        return (await s.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()


async def test_alterar_senha_sucesso(admin_engine, conta_tenant):
    uid = await _criar_usuario(admin_engine, conta_tenant, bcrypt=True, senha="velha123")
    async with _session(admin_engine) as s:
        user = (await s.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()
        await alterar_senha(s, usuario=user, senha_atual="velha123", nova_senha="nova-senha-1")
    user = await _load(admin_engine, uid)
    ok, needs = verify_password("nova-senha-1", bcrypt_hash=user.senha_bcrypt, md5_hash=user.senha)
    assert ok is True and needs is False
    # senha antiga não vale mais via bcrypt
    ok_velha, _ = verify_password("velha123", bcrypt_hash=user.senha_bcrypt, md5_hash=None)
    assert ok_velha is False
    async with _session(admin_engine) as s:
        await s.execute(text("DELETE FROM aprimora_py.audit_log WHERE id_usuario = :u"), {"u": uid})
        await s.execute(text("DELETE FROM utils.usuario WHERE id = :u"), {"u": uid})
        await s.commit()


async def test_alterar_senha_atual_incorreta(admin_engine, conta_tenant):
    uid = await _criar_usuario(admin_engine, conta_tenant, bcrypt=True, senha="velha123")
    async with _session(admin_engine) as s:
        user = (await s.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()
        with pytest.raises(ContaError, match="incorreta"):
            await alterar_senha(s, usuario=user, senha_atual="errada", nova_senha="nova-senha-1")
    async with _session(admin_engine) as s:
        await s.execute(text("DELETE FROM utils.usuario WHERE id = :u"), {"u": uid})
        await s.commit()


async def test_usuario_md5_legado_desbloqueia_assinatura(admin_engine, conta_tenant):
    # Sem bcrypt — só MD5. Antes da troca, verify_password sinaliza needs_rehash.
    uid = await _criar_usuario(admin_engine, conta_tenant, bcrypt=False, senha="legada123")
    user0 = await _load(admin_engine, uid)
    ok0, needs0 = verify_password("legada123", bcrypt_hash=user0.senha_bcrypt, md5_hash=user0.senha)
    assert ok0 is True and needs0 is True  # cairia no 409 ao assinar

    async with _session(admin_engine) as s:
        user = (await s.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()
        await alterar_senha(s, usuario=user, senha_atual="legada123", nova_senha="moderna-1")

    user = await _load(admin_engine, uid)
    ok, needs = verify_password("moderna-1", bcrypt_hash=user.senha_bcrypt, md5_hash=user.senha)
    # needs_rehash=False → assinatura NÃO bloqueia mais
    assert ok is True and needs is False
    assert user.senha_bcrypt is not None
    async with _session(admin_engine) as s:
        await s.execute(text("DELETE FROM aprimora_py.audit_log WHERE id_usuario = :u"), {"u": uid})
        await s.execute(text("DELETE FROM utils.usuario WHERE id = :u"), {"u": uid})
        await s.commit()
