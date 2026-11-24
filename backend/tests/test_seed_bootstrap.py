import pytest
import pytest_asyncio
from sqlalchemy import text
from app.cli.seed_bootstrap import seed
from app.services.provisioning_tenant import UNIDADE_SIGLA
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


async def _lotacao_no_banco(usuario_id: int, tenant_id: int = 1) -> int | None:
    """Lê `utils.usuario.id_unidade_trabalho` DENTRO do contexto do tenant.

    `AdminSessionLocal` aponta para `aprimora_migrator` nos testes (ver o
    cabeçalho do conftest), que é NOBYPASSRLS. Sem `SET LOCAL app.tenant_id` a
    policy esconde a linha, o SELECT devolve 0 rows e `.scalar()` vira `None` —
    indistinguível de "existe e está nulo". A primeira versão destes testes
    reprovou uma correção que já funcionava exatamente por isso: o defeito
    estava na leitura, não no código sob teste.
    """
    async with SessionLocal() as db:
        await db.execute(text("SET LOCAL app.tenant_id = '%d'" % tenant_id))
        return (
            await db.execute(
                text(
                    "SELECT id_unidade_trabalho FROM utils.usuario "
                    "WHERE id = :uid"
                ),
                {"uid": usuario_id},
            )
        ).scalar()


@pytest.mark.asyncio
async def test_seed_bootstrap_lota_o_admin_na_unidade_padrao():
    """O admin do seed nasce LOTADO, e a unidade padrão existe.

    Antes desta guarda o seed criava tenant, admin e grupo mas nenhuma
    unidade, então `utils.usuario.id_unidade_trabalho` ficava nulo. O sintoma
    não era erro: `seed_demo caixas` emitia `[aviso] ... não tem unidade de
    lotação`, pulava os 8 processos das caixas de trabalho e saía com exit 0 —
    a demonstração subia com as caixas vazias e ninguém era avisado. Quem
    provisiona pelo painel/CLI nunca viu o defeito, porque `semear_tenant` já
    lotava o admin; só o caminho do seed ficava de fora.

    **O que este teste NÃO prova.** Medido por inversão em 2026-11-24: ele
    passa mesmo com a correção desfeita, porque o admin já existe no banco
    COM lotação e o ramo `usuario is None` (criação) só ocorre em banco
    virgem. Aqui ele vale como asserção de estado — admin lotado, na unidade
    de sigla `PG`. Quem reprova a regressão é
    `test_seed_bootstrap_repara_admin_que_ja_existe_sem_lotacao`, que inverte
    o estado antes de exigir o conserto.
    """
    async with SessionLocal() as db:
        res = await seed(db)
        await db.commit()

    assert res["unidade_lotacao_id"] is not None, (
        "o admin do seed precisa nascer lotado; sem isso as caixas de "
        "trabalho do seed_demo não montam"
    )
    assert await _lotacao_no_banco(res["usuario_id"], res["tenant_id"]) == (
        res["unidade_lotacao_id"]
    )

    # A unidade é a MESMA chave natural do provisionamento (sigla PG) — duas
    # unidades "padrão" diferentes por caminho de criação seria pior do que
    # nenhuma.
    async with SessionLocal() as db:
        await db.execute(
            text("SET LOCAL app.tenant_id = '%d'" % res["tenant_id"])
        )
        sigla = (
            await db.execute(
                text("SELECT sigla FROM utils.unidade_trabalho WHERE id = :uid"),
                {"uid": res["unidade_lotacao_id"]},
            )
        ).scalar()
    assert sigla == UNIDADE_SIGLA


@pytest.mark.asyncio
async def test_seed_bootstrap_repara_admin_que_ja_existe_sem_lotacao():
    """Rodar o seed conserta o admin que já está no banco sem lotação.

    Todo banco criado antes da correção tem um. O seed roda a cada deploy
    exatamente para suprir pré-requisito faltante; se ele só lotasse o admin
    NOVO, cada ambiente existente precisaria de um UPDATE à mão.

    A guarda é escrita por INVERSÃO — zera a lotação e exige que o seed a
    reponha. Sem zerar, ela passaria no banco já correto sem nunca exercitar o
    reparo.
    """
    async with SessionLocal() as db:
        res = await seed(db)
        await db.commit()
    usuario_id, tenant_id = res["usuario_id"], res["tenant_id"]

    async with SessionLocal() as db:
        await db.execute(text("SET LOCAL app.tenant_id = '%d'" % tenant_id))
        await db.execute(
            text(
                "UPDATE utils.usuario SET id_unidade_trabalho = NULL "
                "WHERE id = :uid"
            ),
            {"uid": usuario_id},
        )
        await db.commit()
    assert await _lotacao_no_banco(usuario_id, tenant_id) is None, (
        "a inversão não surtiu efeito — o teste não exercitaria o reparo"
    )

    async with SessionLocal() as db:
        res2 = await seed(db)
        await db.commit()

    assert res2["unidade_lotacao_id"] is not None
    assert await _lotacao_no_banco(usuario_id, tenant_id) is not None, (
        "o seed deve repor a lotação do admin que já existe"
    )


@pytest.mark.asyncio
async def test_seed_bootstrap_nao_sobrescreve_lotacao_escolhida():
    """Lotação definida por alguém não é sobrescrita pelo seed.

    O reparo preenche só quando o campo está NULO. Mover o admin para outra
    unidade é decisão operacional legítima (o `seed_itaitinga` reorganiza
    unidades), e um seed que a desfizesse a cada deploy seria pior do que o
    defeito que ele corrige.
    """
    async with SessionLocal() as db:
        res = await seed(db)
        await db.commit()
    usuario_id, tenant_id = res["usuario_id"], res["tenant_id"]
    lotacao_original = res["unidade_lotacao_id"]

    async with SessionLocal() as db:
        await db.execute(text("SET LOCAL app.tenant_id = '%d'" % tenant_id))
        outra = (
            await db.execute(
                text(
                    "INSERT INTO utils.unidade_trabalho "
                    "(unidade_trabalho, sigla, tenant_id, excluido) "
                    "VALUES ('Unidade Escolhida', 'UESC-TEST', :tid, false) "
                    "RETURNING id"
                ),
                {"tid": tenant_id},
            )
        ).scalar()
        await db.execute(
            text(
                "UPDATE utils.usuario SET id_unidade_trabalho = :un "
                "WHERE id = :uid"
            ),
            {"un": outra, "uid": usuario_id},
        )
        await db.commit()

    try:
        async with SessionLocal() as db:
            await seed(db)
            await db.commit()
        assert await _lotacao_no_banco(usuario_id, tenant_id) == outra, (
            "o seed não deve mover um admin já lotado"
        )
    finally:
        # Teardown no `finally`: a primeira versão deste teste deixou a
        # unidade e a lotação penduradas no banco de dev quando o assert
        # falhou, porque o cleanup estava depois dele.
        async with SessionLocal() as db:
            await db.execute(
                text("SET LOCAL app.tenant_id = '%d'" % tenant_id)
            )
            await db.execute(
                text(
                    "UPDATE utils.usuario SET id_unidade_trabalho = :un "
                    "WHERE id = :uid"
                ),
                {"un": lotacao_original, "uid": usuario_id},
            )
            await db.execute(
                text("DELETE FROM utils.unidade_trabalho WHERE id = :un"),
                {"un": outra},
            )
            await db.commit()
