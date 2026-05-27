"""Geração concorrente de NUP — valida que UPSERT atômico previne race.

O endpoint de balcão pode receber N protocolos simultâneos. Sem
``INSERT ... ON CONFLICT DO UPDATE RETURNING`` haveria janela entre
SELECT e INSERT onde dois workers gerariam o mesmo sequencial.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Tenant
from app.services.nup import NupError, gerar_nup, validar_nup


CODIGO_ORGAO_TEST = "99999"


@pytest_asyncio.fixture
async def nup_tenant(admin_engine, two_tenants):
    """Tenant A com NUP federal habilitado e código de órgão de teste."""
    tid_a, _ = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        await s.execute(
            text(
                "UPDATE aprimora_py.tenant SET codigo_orgao_nup = :org, "
                "usar_nup_federal = true WHERE id = :id"
            ),
            {"org": CODIGO_ORGAO_TEST, "id": tid_a},
        )
        await s.commit()
    yield tid_a
    # cleanup de nup_sequencia já é feito pelo teardown de two_tenants


async def _generate_one(engine, tenant_id: int, ano: int) -> int:
    """Abre nova session, set tenant, gera 1 NUP, commita. Retorna o
    sequencial obtido."""
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        await s.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        tenant = (
            await s.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one()
        _nup_str, seq = await gerar_nup(s, tenant=tenant, ano=ano)
        await s.commit()
    return seq


async def test_gera_nup_basico(admin_engine, nup_tenant: int):
    """Tenant configurado gera primeiro NUP com sequencial=1 e DV válido."""
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        await s.execute(text(f"SET LOCAL app.tenant_id = '{nup_tenant}'"))
        tenant = (
            await s.execute(select(Tenant).where(Tenant.id == nup_tenant))
        ).scalar_one()
        nup_str, seq = await gerar_nup(s, tenant=tenant, ano=2026)
        await s.commit()

    assert seq == 1
    assert nup_str.startswith(f"{CODIGO_ORGAO_TEST}.000001/2026-")
    assert validar_nup(nup_str)


async def test_concorrencia_sem_duplicatas(admin_engine, nup_tenant: int):
    """N tasks paralelas geram NUP — todos sequenciais únicos e contíguos.

    UPSERT atômico (`INSERT ... ON CONFLICT DO UPDATE RETURNING`) garante
    que mesmo sob race a sequência avança sem buracos nem duplicatas.
    """
    N = 8
    tasks = [_generate_one(admin_engine, nup_tenant, 2026) for _ in range(N)]
    seqs = await asyncio.gather(*tasks)

    assert len(set(seqs)) == N, f"sequencial duplicado detectado: {seqs}"
    assert sorted(seqs) == list(range(1, N + 1)), (
        f"sequenciais não contíguos 1..{N}: {sorted(seqs)}"
    )


async def test_anos_separados_tem_sequencia_independente(
    admin_engine, nup_tenant: int
):
    """A PK é (tenant, órgão, ano) — virar o ano reinicia o sequencial."""
    seq_2026 = await _generate_one(admin_engine, nup_tenant, 2026)
    seq_2027 = await _generate_one(admin_engine, nup_tenant, 2027)
    assert seq_2026 == 1
    assert seq_2027 == 1


async def test_gerar_nup_falha_sem_codigo_orgao(admin_engine, two_tenants):
    """Tenant com flag ativa MAS sem código → NupError com mensagem útil."""
    tid_a, _ = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        await s.execute(
            text(
                "UPDATE aprimora_py.tenant SET usar_nup_federal = true, "
                "codigo_orgao_nup = NULL WHERE id = :id"
            ),
            {"id": tid_a},
        )
        await s.commit()

    async with Session() as s:
        await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
        tenant = (
            await s.execute(select(Tenant).where(Tenant.id == tid_a))
        ).scalar_one()
        import pytest

        with pytest.raises(NupError, match="codigo_orgao_nup"):
            await gerar_nup(s, tenant=tenant, ano=2026)


async def test_gerar_nup_falha_sem_flag(admin_engine, two_tenants):
    """Tenant sem flag ``usar_nup_federal`` → NupError mesmo com código."""
    tid_a, _ = two_tenants
    Session = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as s:
        await s.execute(
            text(
                "UPDATE aprimora_py.tenant SET usar_nup_federal = false, "
                "codigo_orgao_nup = :org WHERE id = :id"
            ),
            {"org": CODIGO_ORGAO_TEST, "id": tid_a},
        )
        await s.commit()

    async with Session() as s:
        await s.execute(text(f"SET LOCAL app.tenant_id = '{tid_a}'"))
        tenant = (
            await s.execute(select(Tenant).where(Tenant.id == tid_a))
        ).scalar_one()
        import pytest

        with pytest.raises(NupError, match="usar_nup_federal"):
            await gerar_nup(s, tenant=tenant, ano=2026)
