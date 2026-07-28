"""Migration 0073 — catálogo de módulos: estrutura e backfill."""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_catalogo_tem_seis_modulos(admin_session):
    linhas = (await admin_session.execute(
        text("SELECT slug, contratavel FROM aprimora_py.modulo ORDER BY ordem")
    )).all()
    slugs = [r[0] for r in linhas]
    assert slugs == ["protocolo", "pagamentos", "frota", "transporte",
                     "administracao", "comum"]
    contratavel = {r[0]: r[1] for r in linhas}
    assert contratavel["comum"] is False
    assert all(contratavel[s] for s in slugs if s != "comum")


@pytest.mark.asyncio
async def test_backfill_contratou_cinco_no_tenant_default(admin_session):
    # O backfill roda na migration, então só alcança tenants que já existiam.
    # O tenant default é o único garantido nessa condição.
    total = (await admin_session.execute(text("""
        SELECT COUNT(*) FROM aprimora_py.tenant_modulo tm
          JOIN aprimora_py.tenant t ON t.id = tm.tenant_id
         WHERE t.slug = 'sobral' AND tm.excluido = false
    """))).scalar_one()
    assert total == 5


@pytest.mark.asyncio
async def test_unicidade_parcial_ignora_excluido(admin_session):
    tid = (await admin_session.execute(
        text("SELECT id FROM aprimora_py.tenant WHERE slug = 'sobral'")
    )).scalar_one()
    mid = (await admin_session.execute(
        text("SELECT id FROM aprimora_py.modulo WHERE slug = 'frota'")
    )).scalar_one()
    # Marca o vínculo vivo como excluído e insere outro: o índice parcial
    # (WHERE excluido = false) tem que permitir a convivência.
    await admin_session.execute(text(
        "UPDATE aprimora_py.tenant_modulo SET excluido = true "
        "WHERE tenant_id = :t AND id_modulo = :m"), {"t": tid, "m": mid})
    await admin_session.execute(text(
        "INSERT INTO aprimora_py.tenant_modulo (tenant_id, id_modulo) "
        "VALUES (:t, :m)"), {"t": tid, "m": mid})
    await admin_session.flush()

    vivos = (await admin_session.execute(text(
        "SELECT COUNT(*) FROM aprimora_py.tenant_modulo "
        "WHERE tenant_id = :t AND id_modulo = :m AND excluido = false"
    ), {"t": tid, "m": mid})).scalar_one()
    total = (await admin_session.execute(text(
        "SELECT COUNT(*) FROM aprimora_py.tenant_modulo "
        "WHERE tenant_id = :t AND id_modulo = :m"
    ), {"t": tid, "m": mid})).scalar_one()
    assert vivos == 1, "deveria haver exatamente um vínculo vivo"
    assert total == 2, "o vínculo soft-deletado deveria continuar na tabela"
    await admin_session.rollback()
