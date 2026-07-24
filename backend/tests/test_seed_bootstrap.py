import pytest
import pytest_asyncio
from sqlalchemy import text
from app.cli.seed_bootstrap import seed
from app.database import SessionLocal
from app.services.permissoes import load_permissions
import app.database as _db_module


@pytest_asyncio.fixture(autouse=True)
async def dispose_engine():
    """Descarta conexões do pool antes de cada teste.

    O engine global em app.database usa asyncpg, que vincula conexões ao
    event loop do momento da criação. Como pytest-asyncio cria um loop novo
    por função, sem dispose o segundo teste recebe conexões do loop anterior
    e morre com "Future attached to a different loop".
    """
    await _db_module.engine.dispose()
    yield
    await _db_module.engine.dispose()


@pytest.mark.asyncio
async def test_seed_bootstrap_cria_super_usuario():
    async with SessionLocal() as db:
        res = await seed(db)
        await db.commit()
    assert res["tenant_id"] == 1
    assert res["usuario_id"] > 0
    # A verificação real: load_permissions vê o admin como super-usuário.
    async with SessionLocal() as db:
        perms = await load_permissions(db, res["usuario_id"], tenant_id=1)
    assert perms.is_super_usuario is True


@pytest.mark.asyncio
async def test_seed_bootstrap_idempotente():
    async with SessionLocal() as db:
        await seed(db); await db.commit()
    async with SessionLocal() as db:
        res2 = await seed(db); await db.commit()  # 2a vez não duplica
    async with SessionLocal() as db:
        n = (await db.execute(text(
            "SELECT count(*) FROM utils.usuario WHERE email='admin@local.test'"
        ))).scalar_one()
    assert n == 1
