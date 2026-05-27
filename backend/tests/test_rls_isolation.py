"""Testes de isolamento Row-Level Security (multi-tenant).

Roda contra ``aprimora_app`` (NOBYPASSRLS) — sem isso, ``ged_user``
ignoraria policies e os testes passariam falsamente.

Tabela alvo: ``protocolos.tipo_anexo`` — RLS habilitado em 0006, schema
simples (só tenant_id NOT NULL), sem FKs obrigatórias.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession


async def _set_tenant(session: AsyncSession, tenant_id: int) -> None:
    """SET LOCAL dentro da transação atual (mesma semântica que o app)."""
    await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


async def _insert_tipo_anexo(
    session: AsyncSession, *, tenant_id: int, nome: str
) -> int:
    res = await session.execute(
        text(
            "INSERT INTO protocolos.tipo_anexo (tenant_id, tipo_anexo, excluido) "
            "VALUES (:tid, :nome, false) RETURNING id"
        ),
        {"tid": tenant_id, "nome": nome},
    )
    return int(res.scalar_one())


async def test_select_isolated_between_tenants(
    app_session: AsyncSession, two_tenants: tuple[int, int]
) -> None:
    """Com app.tenant_id=A só vê linhas de A; mesma session SELECT-only de B
    fora isso retorna vazio."""
    tid_a, tid_b = two_tenants

    # Insere 1 em A
    await _set_tenant(app_session, tid_a)
    id_a = await _insert_tipo_anexo(app_session, tenant_id=tid_a, nome="anexo-A")
    await app_session.commit()

    # Insere 1 em B
    await _set_tenant(app_session, tid_b)
    id_b = await _insert_tipo_anexo(app_session, tenant_id=tid_b, nome="anexo-B")
    await app_session.commit()

    # Com A: vê id_a, não vê id_b
    await _set_tenant(app_session, tid_a)
    visible_a = (
        await app_session.execute(
            text(
                "SELECT id FROM protocolos.tipo_anexo WHERE id IN (:a, :b)"
            ),
            {"a": id_a, "b": id_b},
        )
    ).scalars().all()
    assert id_a in visible_a, "tenant A deveria ver seu próprio registro"
    assert id_b not in visible_a, "tenant A NÃO deveria ver registro de B"

    # Com B: vê id_b, não vê id_a
    await app_session.rollback()
    await _set_tenant(app_session, tid_b)
    visible_b = (
        await app_session.execute(
            text(
                "SELECT id FROM protocolos.tipo_anexo WHERE id IN (:a, :b)"
            ),
            {"a": id_a, "b": id_b},
        )
    ).scalars().all()
    assert id_b in visible_b, "tenant B deveria ver seu próprio registro"
    assert id_a not in visible_b, "tenant B NÃO deveria ver registro de A"


async def test_insert_blocked_when_tenant_id_mismatches_setting(
    app_session: AsyncSession, two_tenants: tuple[int, int]
) -> None:
    """``WITH CHECK`` bloqueia INSERT com tenant_id que não bate com
    ``app.tenant_id``. Isso impede um servidor logado em A criar dado em B."""
    tid_a, tid_b = two_tenants

    await _set_tenant(app_session, tid_a)
    with pytest.raises(DBAPIError) as exc_info:
        await app_session.execute(
            text(
                "INSERT INTO protocolos.tipo_anexo (tenant_id, tipo_anexo, excluido) "
                "VALUES (:tid, 'cross-tenant', false)"
            ),
            {"tid": tid_b},
        )
        await app_session.commit()
    msg = str(exc_info.value).lower()
    assert "row-level security" in msg or "policy" in msg, (
        f"esperava erro de RLS policy, recebi: {msg}"
    )


async def test_select_without_tenant_setting_returns_empty(
    app_session: AsyncSession, two_tenants: tuple[int, int]
) -> None:
    """Sem ``SET LOCAL app.tenant_id``, a policy USING avalia
    ``NULL = NULL`` → false. Nenhuma linha visível, mesmo que exista."""
    tid_a, _ = two_tenants

    # Cria um registro com tid_a
    await _set_tenant(app_session, tid_a)
    id_a = await _insert_tipo_anexo(app_session, tenant_id=tid_a, nome="orphan")
    await app_session.commit()

    # Nova transação SEM SET LOCAL — registros de A não devem ser visíveis
    count = (
        await app_session.execute(
            text(
                "SELECT count(*) FROM protocolos.tipo_anexo WHERE id = :id"
            ),
            {"id": id_a},
        )
    ).scalar_one()
    assert count == 0, (
        f"sem app.tenant_id setado, RLS deveria esconder tudo; vi {count} linhas"
    )


async def test_update_only_affects_current_tenant(
    app_session: AsyncSession, two_tenants: tuple[int, int]
) -> None:
    """UPDATE feito com tenant_id=A não pode tocar em linhas de B mesmo
    se a query tentar — policy USING filtra antes do WHERE."""
    tid_a, tid_b = two_tenants

    await _set_tenant(app_session, tid_a)
    id_a = await _insert_tipo_anexo(app_session, tenant_id=tid_a, nome="original-A")
    await app_session.commit()

    await _set_tenant(app_session, tid_b)
    id_b = await _insert_tipo_anexo(app_session, tenant_id=tid_b, nome="original-B")
    await app_session.commit()

    # Logado em A, tento UPDATE em ambos
    await _set_tenant(app_session, tid_a)
    res = await app_session.execute(
        text(
            "UPDATE protocolos.tipo_anexo SET tipo_anexo = 'tampered' "
            "WHERE id IN (:a, :b)"
        ),
        {"a": id_a, "b": id_b},
    )
    await app_session.commit()
    # rowcount deve refletir SÓ a linha de A
    assert res.rowcount == 1, (
        f"UPDATE deveria afetar apenas 1 linha (tenant A); afetou {res.rowcount}"
    )

    # Confirma com admin: nome de A foi alterado, de B não.
    # (usa same session — após commit, próxima transação reabre, ainda como aprimora_app
    # com policies em vigor; vou conferir os nomes via SET tenant_id apropriado)
    await _set_tenant(app_session, tid_a)
    nome_a = (
        await app_session.execute(
            text("SELECT tipo_anexo FROM protocolos.tipo_anexo WHERE id = :id"),
            {"id": id_a},
        )
    ).scalar_one()
    assert nome_a == "tampered"

    await app_session.rollback()
    await _set_tenant(app_session, tid_b)
    nome_b = (
        await app_session.execute(
            text("SELECT tipo_anexo FROM protocolos.tipo_anexo WHERE id = :id"),
            {"id": id_b},
        )
    ).scalar_one()
    assert nome_b == "original-B", (
        "tenant B NÃO deveria ter sido tocado pelo UPDATE de A"
    )
