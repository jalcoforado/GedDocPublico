"""Tenant provisionado nasce com módulos contratados."""
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.modulos import contratar_modulos_iniciais, slugs_contratados
from app.services.provisioning_tenant import provisionar_tenant

CONTRATAVEIS = {"protocolo", "pagamentos", "frota", "transporte", "administracao"}


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _cleanup_tenant(engine, tenant_id: int) -> None:
    """Não apaga tenant_modulo de propósito: o CASCADE da 0075 tem de levá-lo.

    Se o DELETE do tenant falhar com violação de FK, é sinal de que a 0075 não
    foi aplicada — e é assim que este teste também vigia a migration.
    """
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest.mark.asyncio
async def test_default_contrata_todos_os_contrataveis(admin_session, two_tenants):
    """Default é 'tudo'. Mudá-lo em silêncio quebraria quem já provisiona."""
    tid, _ = two_tenants
    await contratar_modulos_iniciais(admin_session, tid, None)
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == CONTRATAVEIS | {"comum"}
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_lista_explicita_limita(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar_modulos_iniciais(admin_session, tid, ["frota", "transporte"])
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {"frota", "transporte", "comum"}
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_provisionamento_real_contrata(admin_engine):
    """O caminho que importa de verdade: `provisionar_tenant` contrata sozinho.

    Sem este teste a task passaria com a função certa e o wiring errado — que
    foi exatamente o defeito da versão anterior deste plano, onde a contratação
    ficava na CLI e nenhum dos chamadores reais passava por lá.
    """
    slug = f"mod9-{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Módulos",
            admin_email=f"{slug}@modulos.test",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
        )
    try:
        async with _sm(admin_engine)() as s:
            assert await slugs_contratados(s, tenant.id) == CONTRATAVEIS | {"comum"}
    finally:
        await _cleanup_tenant(admin_engine, tenant.id)
