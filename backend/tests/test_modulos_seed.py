"""seed_bootstrap semeia o catálogo de módulos de forma idempotente."""
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.seed_bootstrap import garantir_contratacao_inicial, semear_modulos
from app.models import Modulo, TenantModulo


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


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def tenant_modulo_limpo(admin_engine, two_tenants):
    """`two_tenants`, mas limpando `aprimora_py.tenant_modulo` no teardown ANTES
    do teardown de `two_tenants` (fixtures desfazem na ordem inversa da
    montagem — como esta pede `two_tenants`, é desmontada primeiro). Sem
    isso, o `DELETE FROM aprimora_py.tenant` do teardown de `two_tenants`
    bate na FK `tenant_modulo_tenant_id_fkey` e o teste termina em erro
    mesmo passando (mesmo problema documentado em
    test_modulos_admin.py::two_tenants_com_audit_limpo)."""
    yield two_tenants
    tid_a, tid_b = two_tenants
    async with _sm(admin_engine)() as s:
        await s.execute(
            text("DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id IN (:a, :b)"),
            {"a": tid_a, "b": tid_b},
        )
        await s.commit()


@pytest.mark.asyncio
async def test_garantir_contratacao_inicial_contrata_tenant_sem_linha(
    admin_session, tenant_modulo_limpo
):
    """`two_tenants` cria o tenant via INSERT direto — nasce sem NENHUMA
    linha em tenant_modulo. `garantir_contratacao_inicial` tem que contratar
    todos os módulos contratáveis e ativos do catálogo."""
    tenant_id, _ = tenant_modulo_limpo

    esperados = set((await admin_session.execute(
        select(Modulo.slug).where(Modulo.contratavel.is_(True), Modulo.ativo.is_(True))
    )).scalars().all())

    contratados = await garantir_contratacao_inicial(admin_session, tenant_id)
    await admin_session.commit()

    assert set(contratados) == esperados

    vivos = set((await admin_session.execute(
        select(Modulo.slug)
        .join(TenantModulo, TenantModulo.id_modulo == Modulo.id)
        .where(TenantModulo.tenant_id == tenant_id, TenantModulo.excluido.is_(False))
    )).scalars().all())
    assert vivos == esperados


@pytest.mark.asyncio
async def test_garantir_contratacao_inicial_e_idempotente(
    admin_session, tenant_modulo_limpo
):
    """Segunda chamada não pode mexer: o tenant já tem linha (viva) depois
    da primeira."""
    tenant_id, _ = tenant_modulo_limpo

    primeira = await garantir_contratacao_inicial(admin_session, tenant_id)
    await admin_session.commit()
    assert primeira, "primeira chamada deveria contratar — tenant sem nenhuma linha"

    segunda = await garantir_contratacao_inicial(admin_session, tenant_id)
    await admin_session.commit()
    assert segunda == [], "tenant já tem linha — segunda chamada não deve contratar nada"

    total = (await admin_session.execute(
        select(TenantModulo.id).where(TenantModulo.tenant_id == tenant_id)
    )).scalars().all()
    assert len(total) == len(primeira), "segunda chamada duplicou vínculos"


@pytest.mark.asyncio
async def test_garantir_contratacao_inicial_nao_ressuscita_descontratacao(
    admin_session, tenant_modulo_limpo
):
    """A propriedade central do Critical do review de branch: uma
    descontratação DELIBERADA do platform admin (excluido=true/ativo=false)
    não pode ser revertida por uma chamada seguinte do seed. A condição de
    disparo é "nenhuma linha", não "nenhuma linha viva" — depois da primeira
    contratação o tenant já tem linha (mesmo que soft-deletada), e é isso
    que tem que barrar a segunda chamada de recontratar."""
    tenant_id, _ = tenant_modulo_limpo

    await garantir_contratacao_inicial(admin_session, tenant_id)
    await admin_session.commit()

    frota_id = (await admin_session.execute(
        select(Modulo.id).where(Modulo.slug == "frota")
    )).scalar_one()
    await admin_session.execute(
        text(
            "UPDATE aprimora_py.tenant_modulo SET excluido = true, ativo = false "
            "WHERE tenant_id = :t AND id_modulo = :m"
        ),
        {"t": tenant_id, "m": frota_id},
    )
    await admin_session.commit()

    resultado = await garantir_contratacao_inicial(admin_session, tenant_id)
    await admin_session.commit()
    assert resultado == [], "tenant já tinha linha — não deveria ter contratado nada"

    excluido, ativo = (await admin_session.execute(
        text(
            "SELECT excluido, ativo FROM aprimora_py.tenant_modulo "
            "WHERE tenant_id = :t AND id_modulo = :m"
        ),
        {"t": tenant_id, "m": frota_id},
    )).one()
    assert excluido is True and ativo is False, (
        "descontratação deliberada foi ressuscitada pelo seed — é exatamente "
        "isso que o Critical do review de branch pedia para nunca acontecer"
    )
