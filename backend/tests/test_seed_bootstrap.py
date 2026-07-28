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
async def test_seed_bootstrap_cria_acoes_de_protocolo():
    """Sem estas ações o módulo de protocolo é inutilizável.

    `protocolos.acao` é catálogo GLOBAL. Faltando ABERTURA, abrir processo
    morre com "Ação 'ABERTURA' não cadastrada"; faltando ENCAMINHAMENTO/
    RECEBIMENTO, não se tramita. Foi o estado da VPS até 2026-07-27, porque
    quem semeava era `ci/seed-e2e.sql` — que só roda no CI.
    """
    async with SessionLocal() as db:
        await seed(db)
        await db.commit()
    async with SessionLocal() as db:
        flags = set(
            (
                await db.execute(
                    text(
                        "SELECT flag FROM protocolos.acao "
                        "WHERE ativo = true AND excluido = false"
                    )
                )
            ).scalars()
        )
    assert {"ABERTURA", "ENCAMINHAMENTO", "RECEBIMENTO"} <= flags


@pytest.mark.asyncio
async def test_seed_bootstrap_nao_duplica_acoes():
    """Compara antes/depois em vez de fixar a contagem em 1.

    A suíte compartilha o banco e outros testes inserem em `protocolos.acao`
    (ver test_pr5b_prazos), então contagem global absoluta daria falso negativo.
    """
    conta = text(
        "SELECT count(*) FROM protocolos.acao "
        "WHERE flag = 'ABERTURA' AND excluido = false"
    )
    async with SessionLocal() as db:
        await seed(db); await db.commit()
    async with SessionLocal() as db:
        antes = (await db.execute(conta)).scalar_one()
    async with SessionLocal() as db:
        await seed(db); await db.commit()  # 2a vez não duplica
    async with SessionLocal() as db:
        depois = (await db.execute(conta)).scalar_one()
    assert depois == antes


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
