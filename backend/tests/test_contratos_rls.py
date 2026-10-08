"""Contratos G1 — RLS de `pagamentos.contrato_aditivo` e `contrato_apostila`.

Roda como `aprimora_app` (NOBYPASSRLS). Os testes de service usam `ged_user`,
que ignora policy: provam o filtro aplicacional, não a camada do banco. Aqui o
SELECT não tem `WHERE tenant_id` de propósito — quem filtra é a policy.

`test_rls_papeis_minimos.py::test_toda_tabela_com_rls_responde_sob_aprimora_app`
já varre as duas tabelas (grant e GUC). Este arquivo acrescenta o que a
varredura não afirma: que a policy de fato SEPARA.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.contratos import ApostilaCreate
from app.services import contratos as svc
from tests.contratos_util import aditivo_vigente, contrato_vigente, provisionar, sm

USUARIO = SimpleNamespace(id=None, nivel_acesso_sigilo="interno")


async def _set_tenant(session: AsyncSession, tenant_id: int) -> None:
    await session.execute(text(f"SET LOCAL app.tenant_id = '{int(tenant_id)}'"))


async def _cenario(engine):
    """Dois tenants, cada um com um contrato, um aditivo e uma apostila."""
    saida = []
    for _ in range(2):
        tenant = await provisionar(engine, "ctrls")
        c = await contrato_vigente(engine, tenant.id, USUARIO)
        a = await aditivo_vigente(engine, tenant.id, c.id, None, tipo="AA", valor="1000")
        async with sm(engine)() as s:
            p = await svc.criar_apostila(
                s, tenant_id=tenant.id, contrato_id=c.id, usuario_id=None,
                payload=ApostilaCreate(tipo="OUTRO", data=date(2026, 6, 1), descricao="RLS"))
        saida.append((tenant.id, c.id, a.id, p.id))
    return saida


@pytest.mark.parametrize("tabela, indice", [
    ("pagamentos.contrato_aditivo", 2),
    ("pagamentos.contrato_apostila", 3),
])
async def test_cada_tenant_so_enxerga_os_proprios_atos(
        admin_engine, app_session: AsyncSession, tabela, indice):
    a, b = await _cenario(admin_engine)
    ids = {"a": a[indice], "b": b[indice]}

    await _set_tenant(app_session, a[0])
    vistos_a = (await app_session.execute(
        text(f"SELECT id FROM {tabela} WHERE id IN (:a, :b)"), ids)).scalars().all()
    await app_session.rollback()

    await _set_tenant(app_session, b[0])
    vistos_b = (await app_session.execute(
        text(f"SELECT id FROM {tabela} WHERE id IN (:a, :b)"), ids)).scalars().all()
    await app_session.rollback()

    assert vistos_a == [ids["a"]]
    assert vistos_b == [ids["b"]]


async def test_sem_tenant_na_sessao_nada_e_visivel(admin_engine, app_session: AsyncSession):
    """Controle: prova que o teste acima passa por causa da policy, e não
    porque a consulta devolveria uma linha de qualquer jeito."""
    a, _b = await _cenario(admin_engine)
    vistos = (await app_session.execute(
        text("SELECT id FROM pagamentos.contrato_aditivo WHERE id = :i"),
        {"i": a[2]})).scalars().all()
    await app_session.rollback()
    assert vistos == []


async def test_tenant_nao_grava_aditivo_em_contrato_alheio(
        admin_engine, app_session: AsyncSession):
    """WITH CHECK: com a sessão no tenant B, uma linha com `tenant_id` de A é
    recusada pelo banco — mesmo com o contrato de A existindo."""
    a, b = await _cenario(admin_engine)
    await _set_tenant(app_session, b[0])
    with pytest.raises(DBAPIError) as exc:
        await app_session.execute(text("""
            INSERT INTO pagamentos.contrato_aditivo
                (tenant_id, id_contrato, sequencial, numero, exercicio, tipo,
                 data_assinatura, valor, situacao, criado_em, excluido)
            VALUES (:t, :c, 99, 'INVASOR', 2026, 'AA', :d, :v, 'RASCUNHO', NOW(), false)
        """), {"t": a[0], "c": a[1], "d": date(2026, 6, 1), "v": Decimal("1")})
    await app_session.rollback()
    assert "row-level security" in str(exc.value).lower()
