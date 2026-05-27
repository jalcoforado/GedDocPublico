"""Matriz de permissões granulares — require_permission(codigo, action).

Testa a função de checagem da factory ``require_permission`` mockando
``load_permissions`` para gerar diferentes shapes de ``UserPermissions``.
Cobre todos os ramos:

| Usuário          | action     | trans tem? | flag?     | esperado |
|------------------|------------|------------|-----------|----------|
| super-user       | qualquer   | n/a        | n/a       | passa    |
| grupo c/ trans   | inserir    | sim        | True      | passa    |
| grupo c/ trans   | inserir    | sim        | False     | 403      |
| grupo s/ trans   | inserir    | não        | n/a       | 403      |
| grupo c/ trans   | None       | sim        | n/a       | passa    |
| sem grupo        | qualquer   | n/a        | n/a       | 403      |
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.auth.perms import require_permission
from app.models import Usuario
from app.services.permissoes import PermItem, UserPermissions


def _fake_user(uid: int = 42) -> Usuario:
    u = MagicMock(spec=Usuario)
    u.id = uid
    return u


def _patch_load(monkeypatch, perms: UserPermissions) -> None:
    """Sobrescreve load_permissions importado em ``app.auth.perms``."""

    async def fake_load(db, user_id, *, tenant_id):
        return perms

    monkeypatch.setattr("app.auth.perms.load_permissions", fake_load)


# -------- super-user bypass --------


async def test_super_user_passa_inserir(monkeypatch):
    _patch_load(
        monkeypatch,
        UserPermissions(is_super_usuario=True, nivel_valor=0, items=[]),
    )
    check = require_permission("usuario", "inserir")
    user = _fake_user()
    result = await check(user=user, tenant_id=1, db=MagicMock())
    assert result is user


async def test_super_user_passa_excluir(monkeypatch):
    _patch_load(
        monkeypatch,
        UserPermissions(is_super_usuario=True, nivel_valor=0, items=[]),
    )
    check = require_permission("processo", "excluir")
    user = _fake_user()
    assert await check(user=user, tenant_id=1, db=MagicMock()) is user


async def test_super_user_passa_action_none(monkeypatch):
    _patch_load(
        monkeypatch,
        UserPermissions(is_super_usuario=True, nivel_valor=0, items=[]),
    )
    check = require_permission("workflow")  # action=None
    user = _fake_user()
    assert await check(user=user, tenant_id=1, db=MagicMock()) is user


# -------- grupo com transação --------


async def test_grupo_com_flag_inserir_passa(monkeypatch):
    perms = UserPermissions(
        is_super_usuario=False,
        nivel_valor=5,
        items=[
            PermItem(
                codigo="manifestante",
                transacao="Manifestantes",
                inserir=True,
                atualizar=False,
                excluir=False,
            )
        ],
    )
    _patch_load(monkeypatch, perms)
    check = require_permission("manifestante", "inserir")
    user = _fake_user()
    assert await check(user=user, tenant_id=1, db=MagicMock()) is user


async def test_grupo_sem_flag_inserir_bloqueia(monkeypatch):
    """Tem a transação, mas inserir=False → 403."""
    perms = UserPermissions(
        is_super_usuario=False,
        nivel_valor=5,
        items=[
            PermItem(
                codigo="manifestante",
                transacao="Manifestantes",
                inserir=False,
                atualizar=True,
                excluir=False,
            )
        ],
    )
    _patch_load(monkeypatch, perms)
    check = require_permission("manifestante", "inserir")
    with pytest.raises(HTTPException) as exc:
        await check(user=_fake_user(), tenant_id=1, db=MagicMock())
    assert exc.value.status_code == 403
    assert "inserir" in exc.value.detail
    assert "manifestante" in exc.value.detail


async def test_grupo_com_atualizar_falha_em_excluir(monkeypatch):
    """Ações são independentes — ter atualizar não dá direito a excluir."""
    perms = UserPermissions(
        is_super_usuario=False,
        nivel_valor=5,
        items=[
            PermItem(
                codigo="processo",
                transacao="Processos",
                inserir=True,
                atualizar=True,
                excluir=False,
            )
        ],
    )
    _patch_load(monkeypatch, perms)
    check = require_permission("processo", "excluir")
    with pytest.raises(HTTPException) as exc:
        await check(user=_fake_user(), tenant_id=1, db=MagicMock())
    assert exc.value.status_code == 403
    assert "excluir" in exc.value.detail


# -------- grupo sem a transação --------


async def test_grupo_sem_a_transacao_bloqueia(monkeypatch):
    perms = UserPermissions(
        is_super_usuario=False,
        nivel_valor=5,
        items=[
            PermItem(
                codigo="manifestante",
                transacao="Manifestantes",
                inserir=True,
                atualizar=True,
                excluir=True,
            )
        ],
    )
    _patch_load(monkeypatch, perms)
    # Tenta usar transação 'workflow' que o usuário não tem
    check = require_permission("workflow", "inserir")
    with pytest.raises(HTTPException) as exc:
        await check(user=_fake_user(), tenant_id=1, db=MagicMock())
    assert exc.value.status_code == 403
    assert "workflow" in exc.value.detail


# -------- action=None (só presença da transação) --------


async def test_action_none_aceita_se_tem_transacao(monkeypatch):
    perms = UserPermissions(
        is_super_usuario=False,
        nivel_valor=5,
        items=[
            PermItem(
                codigo="auditoria",
                transacao="Auditoria",
                inserir=False,
                atualizar=False,
                excluir=False,
            )
        ],
    )
    _patch_load(monkeypatch, perms)
    # Mesmo com todas as flags False, action=None só checa presença
    check = require_permission("auditoria")
    user = _fake_user()
    assert await check(user=user, tenant_id=1, db=MagicMock()) is user


async def test_action_none_bloqueia_se_nao_tem_transacao(monkeypatch):
    perms = UserPermissions(
        is_super_usuario=False,
        nivel_valor=5,
        items=[],
    )
    _patch_load(monkeypatch, perms)
    check = require_permission("auditoria")
    with pytest.raises(HTTPException) as exc:
        await check(user=_fake_user(), tenant_id=1, db=MagicMock())
    assert exc.value.status_code == 403


# -------- usuário sem grupo --------


async def test_usuario_sem_grupo_bloqueia_tudo(monkeypatch):
    """nivel_valor=None significa usuário não está em grupo algum no app."""
    perms = UserPermissions(
        is_super_usuario=False, nivel_valor=None, items=[]
    )
    _patch_load(monkeypatch, perms)
    check = require_permission("processo", "inserir")
    with pytest.raises(HTTPException) as exc:
        await check(user=_fake_user(), tenant_id=1, db=MagicMock())
    assert exc.value.status_code == 403
