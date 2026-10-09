"""Migration 0073 — catálogo de módulos: estrutura e backfill."""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_catalogo_tem_sete_modulos(admin_session):
    # Seis contratáveis + `comum`. O sexto, `contratos`, entrou pela migration
    # 0132 (Contratos G1) com ordem 6 — depois de `administracao`, antes de
    # `comum` (99).
    linhas = (await admin_session.execute(
        text("SELECT slug, contratavel FROM aprimora_py.modulo ORDER BY ordem")
    )).all()
    slugs = [r[0] for r in linhas]
    assert slugs == ["protocolo", "pagamentos", "frota", "transporte",
                     "administracao", "contratos", "comum"]
    contratavel = {r[0]: r[1] for r in linhas}
    assert contratavel["comum"] is False
    assert all(contratavel[s] for s in slugs if s != "comum")


@pytest.mark.asyncio
async def test_tenant_default_tem_todos_os_contrataveis(admin_session):
    # Era `test_backfill_contratou_cinco_no_tenant_default`. O backfill da 0073
    # só alcança tenants que JÁ EXISTIAM quando ela rodou; em banco limpo (CI,
    # scripts/bootstrap-db.sh) o `upgrade head` roda antes de qualquer tenant
    # existir, e quem contrata é o seed (`ci/seed-e2e.sql` e
    # `seed_bootstrap.garantir_contratacao_inicial`), depois das migrations.
    # Este teste verifica só o resultado, não a origem.
    #
    # O número acompanha o catálogo em vez de ser um literal: a migration 0132
    # (`contratos`) NÃO contrata ninguém, de propósito — em banco limpo o
    # tenant default recebe o sexto módulo pelo seed, que contrata tudo o que
    # é contratável. Num banco de desenvolvimento antigo, em que `sobral` já
    # existia quando a 0132 chegou, este teste reprova até alguém rodar
    # `seed_demo_contratos apply` — e é o comportamento certo: avisa que o
    # módulo novo não foi contratado.
    contrataveis = (await admin_session.execute(text(
        "SELECT COUNT(*) FROM aprimora_py.modulo WHERE contratavel AND ativo"
    ))).scalar_one()
    assert contrataveis == 6
    total = (await admin_session.execute(text("""
        SELECT COUNT(*) FROM aprimora_py.tenant_modulo tm
          JOIN aprimora_py.tenant t ON t.id = tm.tenant_id
         WHERE t.slug = 'sobral' AND tm.excluido = false
    """))).scalar_one()
    assert total == contrataveis


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
