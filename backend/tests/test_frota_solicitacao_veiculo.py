"""Frota PR-3 — Solicitação de Veículo.

Cobre o serviço de domínio (`services/frota.py`), o gate de permissão `frota`,
a máquina de estados (aprovar/rejeitar/cancelar com transições guardadas), as
validações de datas/passageiros, o solicitante server-side e o isolamento RLS.
Mesmo padrão de test_frota_motorista.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.perms import require_permission
from app.models import SolicitacaoVeiculo, Usuario
from app.schemas.frota import (
    SolicitacaoVeiculoCreate,
    SolicitacaoVeiculoRejeitar,
    SolicitacaoVeiculoUpdate,
)
from app.services import frota as frota_svc
from app.services.permissoes import UserPermissions
from app.services.provisioning_tenant import provisionar_tenant

SAIDA = datetime(2030, 1, 10, 8, 0, 0)
RETORNO = datetime(2030, 1, 10, 18, 0, 0)


def _sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(prefixo: str) -> str:
    return f"{prefixo}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("sol")
    async with _sessionmaker(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Prefeitura Sol", admin_email=f"{slug}@t.local",
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
            "DELETE FROM frota.solicitacao_veiculo WHERE tenant_id=:t",
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


def _payload(**over) -> SolicitacaoVeiculoCreate:
    base = dict(
        finalidade="Visita técnica", destino="Sede regional",
        data_saida_prevista=SAIDA, data_retorno_prevista=RETORNO,
        quantidade_passageiros=3,
    )
    base.update(over)
    return SolicitacaoVeiculoCreate(**base)


# ---------- CRUD básico + solicitante server-side ----------
async def test_criar_e_editar(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, tenant.id)
        async with _sessionmaker(admin_engine)() as s:
            criada = await frota_svc.criar_solicitacao(
                s, tenant_id=tenant.id, id_usuario_solicitante=uid, payload=_payload()
            )
            assert criada.id and criada.status == "solicitada"
            assert criada.id_usuario_solicitante == uid
            assert criada.necessita_motorista is False
        async with _sessionmaker(admin_engine)() as s:
            editada = await frota_svc.atualizar_solicitacao(
                s, tenant_id=tenant.id, solicitacao_id=criada.id,
                payload=SolicitacaoVeiculoUpdate(destino="Outro destino", quantidade_passageiros=5),
            )
            assert editada.destino == "Outro destino" and editada.quantidade_passageiros == 5
            assert editada.atualizado_em is not None
    finally:
        await _cleanup(admin_engine, tenant.id)


def test_create_schema_ignora_solicitante_e_status():
    m = SolicitacaoVeiculoCreate.model_validate({
        "finalidade": "X", "destino": "Y",
        "data_saida_prevista": SAIDA, "data_retorno_prevista": RETORNO,
        "quantidade_passageiros": 1,
        "id_usuario_solicitante": 999, "status": "aprovada", "tenant_id": 7,
    })
    dump = m.model_dump()
    for proibido in ("id_usuario_solicitante", "status", "tenant_id"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ---------- validações de schema ----------
def test_datas_invalidas_rejeitadas():
    with pytest.raises(ValidationError):
        _payload(data_saida_prevista=RETORNO, data_retorno_prevista=SAIDA)


def test_datas_iguais_ok():
    m = _payload(data_saida_prevista=SAIDA, data_retorno_prevista=SAIDA)
    assert m.data_saida_prevista == m.data_retorno_prevista


def test_passageiros_invalido_rejeitado():
    with pytest.raises(ValidationError):
        _payload(quantidade_passageiros=0)


def test_rejeitar_schema_exige_justificativa():
    with pytest.raises(ValidationError):
        SolicitacaoVeiculoRejeitar(justificativa_rejeicao="")


def test_update_schema_descarta_proibidos():
    m = SolicitacaoVeiculoUpdate.model_validate(
        {"destino": "Z", "status": "aprovada", "id_usuario_solicitante": 9,
         "tenant_id": 1, "id": 2, "excluido": True, "justificativa_rejeicao": "x"}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"destino": "Z"}
    for proibido in ("status", "id_usuario_solicitante", "tenant_id", "id", "excluido", "justificativa_rejeicao"):
        assert proibido not in dump


# ---------- máquina de estados ----------
async def _nova(engine, tenant_id, uid):
    async with _sessionmaker(engine)() as s:
        return await frota_svc.criar_solicitacao(
            s, tenant_id=tenant_id, id_usuario_solicitante=uid, payload=_payload()
        )


async def test_aprovar(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, tenant.id)
        sol = await _nova(admin_engine, tenant.id, uid)
        async with _sessionmaker(admin_engine)() as s:
            a = await frota_svc.aprovar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol.id)
            assert a.status == "aprovada"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_rejeitar_define_justificativa(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, tenant.id)
        sol = await _nova(admin_engine, tenant.id, uid)
        async with _sessionmaker(admin_engine)() as s:
            r = await frota_svc.rejeitar_solicitacao(
                s, tenant_id=tenant.id, solicitacao_id=sol.id, justificativa="Sem veículo disponível"
            )
            assert r.status == "rejeitada" and r.justificativa_rejeicao == "Sem veículo disponível"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_cancelar_de_solicitada(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, tenant.id)
        sol = await _nova(admin_engine, tenant.id, uid)
        async with _sessionmaker(admin_engine)() as s:
            c = await frota_svc.cancelar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol.id)
            assert c.status == "cancelada"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_cancelar_de_aprovada(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, tenant.id)
        sol = await _nova(admin_engine, tenant.id, uid)
        async with _sessionmaker(admin_engine)() as s:
            await frota_svc.aprovar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol.id)
        async with _sessionmaker(admin_engine)() as s:
            c = await frota_svc.cancelar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol.id)
            assert c.status == "cancelada"
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_transicoes_invalidas(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, tenant.id)

        # cancelada → aprovar / rejeitar = 409
        sol = await _nova(admin_engine, tenant.id, uid)
        async with _sessionmaker(admin_engine)() as s:
            await frota_svc.cancelar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol.id)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as e1:
                await frota_svc.aprovar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol.id)
            assert e1.value.status_code == 409
            with pytest.raises(HTTPException) as e2:
                await frota_svc.rejeitar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol.id, justificativa="x")
            assert e2.value.status_code == 409

        # rejeitada → cancelar / aprovar = 409
        sol2 = await _nova(admin_engine, tenant.id, uid)
        async with _sessionmaker(admin_engine)() as s:
            await frota_svc.rejeitar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol2.id, justificativa="x")
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as e3:
                await frota_svc.cancelar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol2.id)
            assert e3.value.status_code == 409
            with pytest.raises(HTTPException) as e4:
                await frota_svc.aprovar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol2.id)
            assert e4.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_editar_so_quando_solicitada(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, tenant.id)
        sol = await _nova(admin_engine, tenant.id, uid)
        async with _sessionmaker(admin_engine)() as s:
            await frota_svc.aprovar_solicitacao(s, tenant_id=tenant.id, solicitacao_id=sol.id)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.atualizar_solicitacao(
                    s, tenant_id=tenant.id, solicitacao_id=sol.id,
                    payload=SolicitacaoVeiculoUpdate(destino="tarde demais"),
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


async def test_update_datas_incoerentes_no_service(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, tenant.id)
        sol = await _nova(admin_engine, tenant.id, uid)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.atualizar_solicitacao(
                    s, tenant_id=tenant.id, solicitacao_id=sol.id,
                    payload=SolicitacaoVeiculoUpdate(data_retorno_prevista=SAIDA.replace(hour=6)),
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------- vínculos / cross-tenant ----------
async def test_unidade_de_outro_tenant_rejeitada(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ua = await _usuario_id(admin_engine, a.id)
        uni_b = await _unidade_id(admin_engine, b.id)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.criar_solicitacao(
                    s, tenant_id=a.id, id_usuario_solicitante=ua,
                    payload=_payload(id_unidade_solicitante=uni_b),
                )
            assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ua = await _usuario_id(admin_engine, a.id)
        sol = await _nova(admin_engine, a.id, ua)
        async with _sessionmaker(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_solicitacao(s, tenant_id=b.id, solicitacao_id=sol.id)
            assert exc.value.status_code == 404
            with pytest.raises(HTTPException) as exc2:
                await frota_svc.aprovar_solicitacao(s, tenant_id=b.id, solicitacao_id=sol.id)
            assert exc2.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


def test_create_payload_nao_altera_tenant_via_schema():
    # tenant_id no corpo é ignorado pelo schema; o serviço usa o do caller.
    m = _payload()
    assert not hasattr(m, "tenant_id")


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


async def _insert_solic(session: AsyncSession, *, tenant_id: int, id_user: int) -> int:
    res = await session.execute(
        text(
            "INSERT INTO frota.solicitacao_veiculo "
            "(tenant_id, id_usuario_solicitante, finalidade, destino, data_saida_prevista, "
            " data_retorno_prevista, quantidade_passageiros, necessita_motorista, status, "
            " criado_em, excluido) "
            "VALUES (:t, :u, 'F', 'D', :saida, :retorno, 2, false, 'solicitada', NOW(), false) "
            "RETURNING id"
        ),
        {"t": tenant_id, "u": id_user, "saida": SAIDA, "retorno": RETORNO},
    )
    return int(res.scalar_one())


async def test_rls_isolada_entre_tenants(admin_engine, app_session: AsyncSession):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ua = await _usuario_id(admin_engine, a.id)
        ub = await _usuario_id(admin_engine, b.id)

        await _set_tenant(app_session, a.id)
        id_a = await _insert_solic(app_session, tenant_id=a.id, id_user=ua)
        await app_session.commit()

        await _set_tenant(app_session, b.id)
        id_b = await _insert_solic(app_session, tenant_id=b.id, id_user=ub)
        await app_session.commit()

        await _set_tenant(app_session, a.id)
        visiveis = (
            await app_session.execute(
                text("SELECT id FROM frota.solicitacao_veiculo WHERE id IN (:a, :b)"),
                {"a": id_a, "b": id_b},
            )
        ).scalars().all()
        assert id_a in visiveis and id_b not in visiveis
        await app_session.rollback()

        await _set_tenant(app_session, a.id)
        with pytest.raises(DBAPIError) as exc:
            await _insert_solic(app_session, tenant_id=b.id, id_user=ub)
            await app_session.commit()
        assert "row-level security" in str(exc.value).lower() or "policy" in str(exc.value).lower()
        await app_session.rollback()
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)
