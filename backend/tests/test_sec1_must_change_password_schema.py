"""SEC-1 Commit 1 — schema + modelo da flag must_change_password.

Cobre exclusivamente migration 0030 + atributo no modelo `Usuario`. Não testa
guard, login, reset, frontend ou interceptor — esses entram em commits
posteriores do SEC-1.

Asserts:
- coluna `utils.usuario.must_change_password` existe;
- é BOOLEAN, NOT NULL, com DEFAULT false;
- todos os usuários existentes ficaram com `must_change_password = false`
  após o backfill (defesa em profundidade D-BACKFILL);
- INSERT sem valor explícito recebe false;
- modelo `Usuario` expõe o atributo com default Python = False;
- INSERT com valor true grava true (a coluna aceita os dois valores —
  garante que o tipo não é coercivo).
"""
from __future__ import annotations

import uuid

import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Usuario


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def sec1_user(admin_engine, two_tenants):
    """Cria um usuário descartável no tenant A e limpa no teardown."""
    tid, _ = two_tenants
    suf = uuid.uuid4().hex[:8]
    async with _sm(admin_engine)() as s:
        uid = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO utils.usuario "
                        "  (tenant_id, nome, email, senha, cpf, ativo, excluido) "
                        "VALUES (:t, :n, :e, :senha, :cpf, true, false) "
                        "RETURNING id"
                    ),
                    {
                        "t": tid,
                        "n": f"SEC1 {suf}",
                        "e": f"{suf}@sec1.local",
                        "senha": "x" * 32,  # MD5 dummy — não usado aqui
                        "cpf": uuid.uuid4().hex[:11],
                    },
                )
            ).scalar_one()
        )
        await s.commit()

    yield tid, uid

    async with _sm(admin_engine)() as s:
        await s.execute(text("DELETE FROM utils.usuario WHERE id = :u"), {"u": uid})
        await s.commit()


async def test_must_change_password_column_exists_and_shape(admin_engine):
    """Coluna existe, é BOOLEAN, NOT NULL, com DEFAULT false."""
    async with _sm(admin_engine)() as s:
        row = (
            await s.execute(
                text(
                    """
                    SELECT data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'utils'
                      AND table_name = 'usuario'
                      AND column_name = 'must_change_password'
                    """
                )
            )
        ).one_or_none()

    assert row is not None, "coluna utils.usuario.must_change_password não existe"
    data_type, is_nullable, column_default = row
    assert data_type == "boolean"
    assert is_nullable == "NO"
    assert column_default is not None
    assert "false" in column_default.lower()


async def test_backfill_existing_users_are_false(admin_engine):
    """Migration 0030 fez backfill: o usuário-âncora `admin@local.test`,
    presente no provisionamento inicial do tenant default (tenant_id=1) e
    portanto pré-migração, tem `must_change_password=false`. Sanity check
    direto de D-BACKFILL.

    Reescrita (TECH-2): a versão anterior contava globalmente todos os
    usuários ativos com flag=true, o que ficava sensível a leftovers
    legítimos criados por E2E, reset administrativo ou provisionamento.
    A semântica correta da migration é: *usuários existentes no momento
    da migration receberam false*. Verificamos isso por âncora — não por
    contagem global.
    """
    async with _sm(admin_engine)() as s:
        row = (
            await s.execute(
                text(
                    "SELECT must_change_password FROM utils.usuario "
                    "WHERE email = 'admin@local.test' "
                    "  AND tenant_id = 1 "
                    "  AND ativo = true "
                    "  AND excluido = false"
                )
            )
        ).scalar_one_or_none()

    assert row is not None, (
        "Usuário-âncora `admin@local.test` ausente no tenant default — "
        "esperado pelo provisionamento inicial. Sem âncora, não dá pra "
        "validar D-BACKFILL deterministicamente."
    )
    assert row is False, (
        "D-BACKFILL violado: usuário-âncora `admin@local.test` (pré-migration) "
        "deveria ter `must_change_password=false`. Se algum reset/edição "
        "administrativa foi feita nesse usuário em DEV, restaurar com "
        "`UPDATE utils.usuario SET must_change_password=false WHERE "
        "email='admin@local.test' AND tenant_id=1`."
    )


async def test_insert_sem_valor_explicito_recebe_false(admin_engine, sec1_user):
    """INSERT que não especifica a coluna deve receber DEFAULT false."""
    _, uid = sec1_user
    async with _sm(admin_engine)() as s:
        result = (
            await s.execute(
                text(
                    "SELECT must_change_password FROM utils.usuario WHERE id = :u"
                ),
                {"u": uid},
            )
        ).scalar_one()
    assert result is False


async def test_modelo_usuario_default_python_e_false(admin_engine, sec1_user):
    """Carrega o usuário via ORM e confirma que o atributo está acessível
    com valor False (default Python coerente com server_default SQL)."""
    _, uid = sec1_user
    async with _sm(admin_engine)() as s:
        u = (
            await s.execute(select(Usuario).where(Usuario.id == uid))
        ).scalar_one()
    assert hasattr(u, "must_change_password")
    assert u.must_change_password is False


async def test_coluna_aceita_true(admin_engine, sec1_user):
    """Sanity: a coluna aceita o valor true (garante que não é uma constraint
    fixa em false). Não testa fluxo funcional — só o tipo da coluna."""
    _, uid = sec1_user
    async with _sm(admin_engine)() as s:
        await s.execute(
            text(
                "UPDATE utils.usuario SET must_change_password = true WHERE id = :u"
            ),
            {"u": uid},
        )
        await s.commit()
        val = (
            await s.execute(
                text(
                    "SELECT must_change_password FROM utils.usuario WHERE id = :u"
                ),
                {"u": uid},
            )
        ).scalar_one()
    assert val is True
