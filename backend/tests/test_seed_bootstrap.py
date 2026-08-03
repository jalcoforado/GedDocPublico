import pytest
import pytest_asyncio
from sqlalchemy import text
from app.cli.seed_bootstrap import seed
# O seed é operação ADMINISTRATIVA: escreve em `aprimora_py.modulo` e
# `modulo_transacao`, onde o papel da API só tem SELECT (inventário §8.6). O
# teste abre a mesma conexão que o CLI abre — usar `app.database.SessionLocal`
# aqui testaria um caminho que produção não percorre.
from app.database_admin import AdminSessionLocal as SessionLocal
from app.database_admin import descartar_engine_admin
from app.services.permissoes import load_permissions
import app.database as _db_module


@pytest_asyncio.fixture(autouse=True)
async def dispose_engine():
    """Descarta conexões do pool antes de cada teste.

    O engine global em app.database usa asyncpg, que vincula conexões ao
    event loop do momento da criação. Como pytest-asyncio cria um loop novo
    por função, sem dispose o segundo teste recebe conexões do loop anterior
    e morre com "Future attached to a different loop". O engine administrativo
    é memoizado em `database_admin` e tem o mesmo problema.
    """
    await _db_module.engine.dispose()
    await descartar_engine_admin()
    yield
    await _db_module.engine.dispose()
    await descartar_engine_admin()


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
        res1 = await seed(db); await db.commit()
    async with SessionLocal() as db:
        res2 = await seed(db); await db.commit()  # 2a vez não duplica
    assert res2["tenant_id"] == res1["tenant_id"]
    # A contagem PRECISA rodar numa sessão com `app.tenant_id` instalado:
    # `utils.usuario` tem RLS, e uma `SessionLocal()` crua avalia a policy com
    # `tenant_id = NULL` → zero linhas, **sem erro**. Sob BYPASSRLS isso passava
    # despercebido; sob papel sujeito a RLS, o `assert 0 == 1` acusaria uma
    # duplicação que não existe. É o defeito de arreio do inventário §9.5.
    async with SessionLocal(tenant_id=res2["tenant_id"]) as db:
        n = (await db.execute(text(
            "SELECT count(*) FROM utils.usuario "
            "WHERE tenant_id = :t AND email='admin@local.test'"
        ), {"t": res2["tenant_id"]})).scalar_one()
    assert n == 1
