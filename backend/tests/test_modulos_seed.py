"""seed_bootstrap semeia o catálogo de módulos de forma idempotente."""
import pytest
from sqlalchemy import text

from app.cli.seed_bootstrap import semear_modulos


@pytest.mark.asyncio
async def test_semear_modulos_e_idempotente(admin_session):
    antes = (await admin_session.execute(
        text("SELECT COUNT(*) FROM aprimora_py.modulo_transacao")
    )).scalar_one()

    await semear_modulos(admin_session)
    await admin_session.flush()
    depois_1 = (await admin_session.execute(
        text("SELECT COUNT(*) FROM aprimora_py.modulo_transacao")
    )).scalar_one()

    await semear_modulos(admin_session)
    await admin_session.flush()
    depois_2 = (await admin_session.execute(
        text("SELECT COUNT(*) FROM aprimora_py.modulo_transacao")
    )).scalar_one()

    assert depois_1 >= antes
    assert depois_2 == depois_1, "segunda chamada duplicou vínculos"
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_transacao_inexistente_e_ignorada(admin_session):
    """Código que não existe em utils.transacao não pode explodir o seed."""
    await semear_modulos(admin_session)
    await admin_session.flush()
    orfas = (await admin_session.execute(text("""
        SELECT COUNT(*) FROM aprimora_py.modulo_transacao mt
         WHERE NOT EXISTS (SELECT 1 FROM utils.transacao t WHERE t.id = mt.id_transacao)
    """))).scalar_one()
    assert orfas == 0
    await admin_session.rollback()
