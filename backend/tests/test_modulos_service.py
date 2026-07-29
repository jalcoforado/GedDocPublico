"""Service de módulos — contratação e derivação de códigos bloqueados."""
import pytest
from sqlalchemy import text

from app.services.modulos import (
    codigos_bloqueados,
    contratar,
    modulos_do_tenant,
    slugs_contratados,
)


async def _contrata_tudo(session, tenant_id: int) -> None:
    await session.execute(text("""
        INSERT INTO aprimora_py.tenant_modulo (tenant_id, id_modulo)
        SELECT :t, id FROM aprimora_py.modulo WHERE contratavel = true
    """), {"t": tenant_id})
    await session.flush()


@pytest.mark.asyncio
async def test_comum_sempre_conta_como_contratado(admin_session, two_tenants):
    tid, _ = two_tenants
    # Tenant novo, nada contratado: 'comum' ainda assim aparece.
    assert await slugs_contratados(admin_session, tid) == {"comum"}


@pytest.mark.asyncio
async def test_contratar_e_descontratar_reconcilia(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota", "pagamentos"])
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {"frota", "pagamentos", "comum"}

    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {"frota", "comum"}

    # Descontratar é soft-delete: a linha continua lá.
    total = (await admin_session.execute(text(
        "SELECT COUNT(*) FROM aprimora_py.tenant_modulo WHERE tenant_id = :t"
    ), {"t": tid})).scalar_one()
    assert total == 2, "descontratar apagou a linha em vez de marcar excluido"
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_recontratar_reaproveita_a_linha(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    await contratar(admin_session, tid, [])
    await admin_session.flush()
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    assert await slugs_contratados(admin_session, tid) == {"frota", "comum"}
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_codigos_bloqueados_lista_modulo_nao_contratado(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    bloqueados = await codigos_bloqueados(admin_session, tid)
    assert "frota" not in bloqueados, "módulo contratado não pode ser bloqueado"
    assert "dashboard" not in bloqueados, "transação de 'comum' nunca é bloqueada"
    assert "processo" in bloqueados, "protocolo não foi contratado, deveria bloquear"
    assert any(c.startswith("pagamento_") for c in bloqueados), (
        "pagamentos não foi contratado, suas transações deveriam estar bloqueadas"
    )
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_modulos_do_tenant_marca_contratacao(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()
    itens = await modulos_do_tenant(admin_session, tid)
    por_slug = {m["slug"]: m["contratado"] for m in itens}
    assert por_slug["frota"] is True
    assert por_slug["pagamentos"] is False
    assert "comum" not in por_slug, "módulo não-contratável não entra na tela de contratação"
    await admin_session.rollback()
