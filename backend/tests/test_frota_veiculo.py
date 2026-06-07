"""Fundação do módulo de Frota — cadastro de Veículos.

Cobre o serviço de domínio (`services/frota.py`), o gate de permissão `frota`,
a unicidade de placa, a guarda de quilometragem e o isolamento RLS multi-tenant.
Padrão: `admin_engine` (ged_user/BYPASSRLS) + `provisionar_tenant` para setup
(igual test_pr4a_servicos); RLS validado via `app_session` + `two_tenants`.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.perms import require_permission
from app.models import Usuario, Veiculo
from app.schemas.frota import VeiculoCreate, VeiculoUpdate
from app.services import frota as frota_svc
from app.services.permissoes import UserPermissions
from app.services.provisioning_tenant import provisionar_tenant


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(prefixo: str) -> str:
    return f"{prefixo}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("frota")
    async with _sessionmaker(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Prefeitura Frota", admin_email=f"{slug}@t.local",
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


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sessionmaker(engine)() as s:
        for stmt in (
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


# ---------- CRUD básico ----------
async def test_criar_e_editar_veiculo(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            criado = await frota_svc.criar_veiculo(
                s, tenant_id=tenant.id,
                payload=VeiculoCreate(placa="ABC1234", marca="Fiat", modelo="Uno"),
            )
            assert criado.id and criado.situacao == "disponivel"
            assert criado.forma_posse == "proprio" and criado.quilometragem_atual == 0
            assert criado.placa == "ABC1234"

        async with _sessionmaker(admin_engine)() as s:
            editado = await frota_svc.atualizar_veiculo(
                s, tenant_id=tenant.id, veiculo_id=criado.id,
                payload=VeiculoUpdate(situacao="manutencao", quilometragem_atual=15000),
            )
            assert editado.situacao == "manutencao"
            assert editado.quilometragem_atual == 15000
            assert editado.atualizado_em is not None
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_placa_normalizada(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            v = await frota_svc.criar_veiculo(
                s, tenant_id=tenant.id, payload=VeiculoCreate(placa=" abc-1d23 ")
            )
            assert v.placa == "ABC1D23"
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- placa única ----------
async def test_placa_unica_por_tenant(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            await frota_svc.criar_veiculo(
                s, tenant_id=tenant.id, payload=VeiculoCreate(placa="DUP1234")
            )
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.criar_veiculo(
                    s, tenant_id=tenant.id, payload=VeiculoCreate(placa="DUP1234")
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_mesma_placa_em_tenants_diferentes_ok(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            va = await frota_svc.criar_veiculo(
                s, tenant_id=a.id, payload=VeiculoCreate(placa="SAM1234")
            )
        async with _sessionmaker(admin_engine)() as s:
            vb = await frota_svc.criar_veiculo(
                s, tenant_id=b.id, payload=VeiculoCreate(placa="SAM1234")
            )
        assert va.placa == vb.placa and va.tenant_id != vb.tenant_id
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_placa_reutilizavel_apos_soft_delete(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            v = await frota_svc.criar_veiculo(
                s, tenant_id=tenant.id, payload=VeiculoCreate(placa="REC1234")
            )
        async with _sessionmaker(admin_engine)() as s:
            await frota_svc.excluir_veiculo(s, tenant_id=tenant.id, veiculo_id=v.id)
        # obter agora dá 404 (soft-deletado)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_veiculo(s, tenant_id=tenant.id, veiculo_id=v.id)
            assert exc.value.status_code == 404
        # mesma placa pode ser recriada
        async with _sessionmaker(admin_engine)() as s:
            novo = await frota_svc.criar_veiculo(
                s, tenant_id=tenant.id, payload=VeiculoCreate(placa="REC1234")
            )
            assert novo.id != v.id
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- cross-tenant + tenant_id imutável ----------
async def test_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        async with _sessionmaker(admin_engine)() as s:
            v = await frota_svc.criar_veiculo(
                s, tenant_id=a.id, payload=VeiculoCreate(placa="CRS1234")
            )
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_veiculo(s, tenant_id=b.id, veiculo_id=v.id)
            assert exc.value.status_code == 404
            with pytest.raises(HTTPException) as exc2:
                await frota_svc.atualizar_veiculo(
                    s, tenant_id=b.id, veiculo_id=v.id,
                    payload=VeiculoUpdate(marca="hack"),
                )
            assert exc2.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


def test_update_schema_descarta_tenant_id():
    m = VeiculoUpdate.model_validate(
        {"marca": "X", "tenant_id": 999, "id": 7, "excluido": True}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"marca": "X"}
    for proibido in ("tenant_id", "id", "excluido"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ---------- unidade same-tenant ----------
async def test_unidade_do_tenant_aceita(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _unidade_id(admin_engine, tenant.id)
        async with _sessionmaker(admin_engine)() as s:
            v = await frota_svc.criar_veiculo(
                s, tenant_id=tenant.id,
                payload=VeiculoCreate(placa="UNI1234", id_unidade_responsavel=uid),
            )
            assert v.id_unidade_responsavel == uid
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_unidade_de_outro_tenant_rejeitada(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        uid_b = await _unidade_id(admin_engine, b.id)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.criar_veiculo(
                    s, tenant_id=a.id,
                    payload=VeiculoCreate(placa="UNI9876", id_unidade_responsavel=uid_b),
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- validações de schema (422) ----------
def test_quilometragem_negativa_rejeitada():
    with pytest.raises(ValidationError):
        VeiculoCreate(placa="ABC1234", quilometragem_atual=-1)


def test_placa_invalida_rejeitada():
    with pytest.raises(ValidationError):
        VeiculoCreate(placa="123ABCD")
    with pytest.raises(ValidationError):
        VeiculoCreate(placa="ABC12")  # curta demais


def test_situacao_invalida_rejeitada():
    with pytest.raises(ValidationError):
        VeiculoCreate(placa="ABC1234", situacao="voando")


def test_forma_posse_invalida_rejeitada():
    with pytest.raises(ValidationError):
        VeiculoCreate(placa="ABC1234", forma_posse="emprestado")


# ---------- gate de permissão `frota` (monkeypatch) ----------
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
    assert "frota" in exc.value.detail


# ---------- RLS multi-tenant (aprimora_app / NOBYPASSRLS) ----------
async def _set_tenant(session: AsyncSession, tenant_id: int) -> None:
    await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


async def _insert_veiculo(session: AsyncSession, *, tenant_id: int, placa: str) -> int:
    res = await session.execute(
        text(
            "INSERT INTO frota.veiculo (tenant_id, placa, situacao, quilometragem_atual, "
            "forma_posse, criado_em, excluido) "
            "VALUES (:t, :p, 'disponivel', 0, 'proprio', NOW(), false) RETURNING id"
        ),
        {"t": tenant_id, "p": placa},
    )
    return int(res.scalar_one())


async def test_rls_isolada_entre_tenants(
    app_session: AsyncSession, two_tenants: tuple[int, int]
) -> None:
    tid_a, tid_b = two_tenants
    try:
        await _set_tenant(app_session, tid_a)
        id_a = await _insert_veiculo(app_session, tenant_id=tid_a, placa="RLSA123")
        await app_session.commit()

        await _set_tenant(app_session, tid_b)
        id_b = await _insert_veiculo(app_session, tenant_id=tid_b, placa="RLSB123")
        await app_session.commit()

        # Com A: vê o seu, não vê o de B.
        await _set_tenant(app_session, tid_a)
        visiveis = (
            await app_session.execute(
                text("SELECT id FROM frota.veiculo WHERE id IN (:a, :b)"),
                {"a": id_a, "b": id_b},
            )
        ).scalars().all()
        assert id_a in visiveis and id_b not in visiveis
        await app_session.rollback()

        # WITH CHECK bloqueia inserir no tenant errado.
        await _set_tenant(app_session, tid_a)
        with pytest.raises(DBAPIError) as exc:
            await _insert_veiculo(app_session, tenant_id=tid_b, placa="HACK123")
            await app_session.commit()
        assert "row-level security" in str(exc.value).lower() or "policy" in str(exc.value).lower()
        await app_session.rollback()
    finally:
        # Limpa os veículos para o teardown do fixture poder remover os tenants.
        for tid in (tid_a, tid_b):
            await _set_tenant(app_session, tid)
            await app_session.execute(
                text("DELETE FROM frota.veiculo WHERE tenant_id = :t"), {"t": tid}
            )
            await app_session.commit()
