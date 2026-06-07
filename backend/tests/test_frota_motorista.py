"""Frota PR-2 — cadastro de Motoristas/Condutores.

Cobre o serviço de domínio (`services/frota.py`), o gate de permissão `frota`,
a unicidade de CPF, as validações de CNH/CPF/e-mail, o vínculo same-tenant
(unidade/usuário), a inativação e o isolamento RLS multi-tenant. Mesmo padrão
de test_frota_veiculo.
"""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.perms import require_permission
from app.models import Motorista, Usuario
from app.schemas.frota import MotoristaCreate, MotoristaUpdate
from app.services import frota as frota_svc
from app.services.permissoes import UserPermissions
from app.services.provisioning_tenant import provisionar_tenant

VALIDADE = date(2030, 12, 31)


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(prefixo: str) -> str:
    return f"{prefixo}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("mot")
    async with _sessionmaker(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Prefeitura Mot", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


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


async def _usuario_id(engine, tenant_id: int) -> int:
    async with _sessionmaker(engine)() as s:
        return int(
            (
                await s.execute(
                    text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sessionmaker(engine)() as s:
        for stmt in (
            "DELETE FROM frota.motorista WHERE tenant_id=:t",
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


def _payload(**over) -> MotoristaCreate:
    base = dict(
        nome="João Motorista", cpf="12345678901", cnh_numero="98765432100",
        cnh_categoria="D", cnh_validade=VALIDADE,
    )
    base.update(over)
    return MotoristaCreate(**base)


# ---------- CRUD básico ----------
async def test_criar_e_editar_motorista(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            criado = await frota_svc.criar_motorista(
                s, tenant_id=tenant.id, payload=_payload()
            )
            assert criado.id and criado.situacao == "ativo"
            assert criado.cnh_categoria == "D" and criado.cpf == "12345678901"

        async with _sessionmaker(admin_engine)() as s:
            editado = await frota_svc.atualizar_motorista(
                s, tenant_id=tenant.id, motorista_id=criado.id,
                payload=MotoristaUpdate(telefone="85999990000", cnh_categoria="E"),
            )
            assert editado.telefone == "85999990000"
            assert editado.cnh_categoria == "E"
            assert editado.atualizado_em is not None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_cpf_e_cnh_normalizados(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            m = await frota_svc.criar_motorista(
                s, tenant_id=tenant.id,
                payload=_payload(cpf="123.456.789-01", cnh_numero="987.654.321-00"),
            )
            assert m.cpf == "12345678901" and m.cnh_numero == "98765432100"
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- inativar / reativar ----------
async def test_inativar_e_reativar(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            m = await frota_svc.criar_motorista(s, tenant_id=tenant.id, payload=_payload())
        async with _sessionmaker(admin_engine)() as s:
            d = await frota_svc.set_situacao_motorista(
                s, tenant_id=tenant.id, motorista_id=m.id, situacao="inativo"
            )
            assert d.situacao == "inativo"
        async with _sessionmaker(admin_engine)() as s:
            a = await frota_svc.set_situacao_motorista(
                s, tenant_id=tenant.id, motorista_id=m.id, situacao="ativo"
            )
            assert a.situacao == "ativo"
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- CPF único ----------
async def test_cpf_unico_por_tenant(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            await frota_svc.criar_motorista(
                s, tenant_id=tenant.id, payload=_payload(cpf="11122233344")
            )
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.criar_motorista(
                    s, tenant_id=tenant.id, payload=_payload(cpf="11122233344")
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_mesmo_cpf_em_tenants_diferentes_ok(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            ma = await frota_svc.criar_motorista(
                s, tenant_id=a.id, payload=_payload(cpf="55566677788")
            )
        async with _sessionmaker(admin_engine)() as s:
            mb = await frota_svc.criar_motorista(
                s, tenant_id=b.id, payload=_payload(cpf="55566677788")
            )
        assert ma.cpf == mb.cpf and ma.tenant_id != mb.tenant_id
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_cpf_reutilizavel_apos_soft_delete(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            m = await frota_svc.criar_motorista(
                s, tenant_id=tenant.id, payload=_payload(cpf="99988877766")
            )
        async with _sessionmaker(admin_engine)() as s:
            await frota_svc.excluir_motorista(s, tenant_id=tenant.id, motorista_id=m.id)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_motorista(s, tenant_id=tenant.id, motorista_id=m.id)
            assert exc.value.status_code == 404
        async with _sessionmaker(admin_engine)() as s:
            novo = await frota_svc.criar_motorista(
                s, tenant_id=tenant.id, payload=_payload(cpf="99988877766")
            )
            assert novo.id != m.id
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- cross-tenant ----------
async def test_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            m = await frota_svc.criar_motorista(
                s, tenant_id=a.id, payload=_payload(cpf="10101010101")
            )
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_motorista(s, tenant_id=b.id, motorista_id=m.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


def test_update_schema_descarta_tenant_id():
    m = MotoristaUpdate.model_validate(
        {"nome": "X", "tenant_id": 999, "id": 7, "excluido": True}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"nome": "X"}
    for proibido in ("tenant_id", "id", "excluido"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ---------- vínculos same-tenant ----------
async def test_unidade_e_usuario_do_tenant_aceitos(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        usr = await _usuario_id(admin_engine, tenant.id)
        async with _sessionmaker(admin_engine)() as s:
            m = await frota_svc.criar_motorista(
                s, tenant_id=tenant.id,
                payload=_payload(cpf="20202020202", id_unidade=uid, id_usuario=usr),
            )
            assert m.id_unidade == uid and m.id_usuario == usr
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_usuario_de_outro_tenant_rejeitado(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        usr_b = await _usuario_id(admin_engine, b.id)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.criar_motorista(
                    s, tenant_id=a.id,
                    payload=_payload(cpf="30303030303", id_usuario=usr_b),
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- validações de schema (422) ----------
def test_cpf_invalido_rejeitado():
    with pytest.raises(ValidationError):
        _payload(cpf="123")


def test_cnh_invalida_rejeitada():
    with pytest.raises(ValidationError):
        _payload(cnh_numero="123")


def test_cnh_categoria_invalida_rejeitada():
    with pytest.raises(ValidationError):
        _payload(cnh_categoria="Z")


def test_email_invalido_rejeitado():
    with pytest.raises(ValidationError):
        _payload(email="nao-eh-email")


def test_email_valido_ok():
    m = _payload(email="motorista@prefeitura.gov.br")
    assert m.email == "motorista@prefeitura.gov.br"


# ---------- gate de permissão `frota` ----------
def _fake_user(uid: int = 9) -> Usuario:
    u = MagicMock(spec=Usuario)
    u.id = uid
    return u


def _patch_load(monkeypatch, perms: UserPermissions) -> None:
    async def fake_load(db, user_id, *, tenant_id):
        return perms

    monkeypatch.setattr("app.auth.perms.load_permissions", fake_load)


async def test_gate_frota_su_bypassa(monkeypatch):
    _patch_load(monkeypatch, UserPermissions(is_super_usuario=True, nivel_valor=0, items=[]))
    check = require_permission("frota", "inserir")
    user = _fake_user()
    assert await check(user=user, tenant_id=1, db=MagicMock()) is user


async def test_gate_frota_nao_su_403(monkeypatch):
    _patch_load(monkeypatch, UserPermissions(is_super_usuario=False, nivel_valor=5, items=[]))
    check = require_permission("frota", "inserir")
    with pytest.raises(HTTPException) as exc:
        await check(user=_fake_user(), tenant_id=1, db=MagicMock())
    assert exc.value.status_code == 403


# ---------- RLS multi-tenant ----------
async def _set_tenant(session: AsyncSession, tenant_id: int) -> None:
    await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


async def _insert_motorista(session: AsyncSession, *, tenant_id: int, cpf: str) -> int:
    res = await session.execute(
        text(
            "INSERT INTO frota.motorista (tenant_id, nome, cpf, cnh_numero, cnh_categoria, "
            "cnh_validade, situacao, criado_em, excluido) "
            "VALUES (:t, 'M', :c, '98765432100', 'B', '2030-12-31', 'ativo', NOW(), false) "
            "RETURNING id"
        ),
        {"t": tenant_id, "c": cpf},
    )
    return int(res.scalar_one())


async def test_rls_isolada_entre_tenants(
    app_session: AsyncSession, two_tenants: tuple[int, int]
) -> None:
    tid_a, tid_b = two_tenants
    try:
        await _set_tenant(app_session, tid_a)
        id_a = await _insert_motorista(app_session, tenant_id=tid_a, cpf="40404040401")
        await app_session.commit()

        await _set_tenant(app_session, tid_b)
        id_b = await _insert_motorista(app_session, tenant_id=tid_b, cpf="40404040402")
        await app_session.commit()

        await _set_tenant(app_session, tid_a)
        visiveis = (
            await app_session.execute(
                text("SELECT id FROM frota.motorista WHERE id IN (:a, :b)"),
                {"a": id_a, "b": id_b},
            )
        ).scalars().all()
        assert id_a in visiveis and id_b not in visiveis
        await app_session.rollback()

        await _set_tenant(app_session, tid_a)
        with pytest.raises(DBAPIError) as exc:
            await _insert_motorista(app_session, tenant_id=tid_b, cpf="40404040403")
            await app_session.commit()
        assert "row-level security" in str(exc.value).lower() or "policy" in str(exc.value).lower()
        await app_session.rollback()
    finally:
        for tid in (tid_a, tid_b):
            await _set_tenant(app_session, tid)
            await app_session.execute(
                text("DELETE FROM frota.motorista WHERE tenant_id = :t"), {"t": tid}
            )
            await app_session.commit()
