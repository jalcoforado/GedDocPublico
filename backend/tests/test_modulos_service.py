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


@pytest.mark.asyncio
async def test_codigos_bloqueados_falha_alto_quando_catalogo_corrompido(admin_session, two_tenants):
    tid, _ = two_tenants
    # Simula catálogo corrompido: 'comum' (não-contratável, sempre
    # disponível) fica inativo. slugs_contratados passaria a devolver
    # set() e `Modulo.slug.not_in(set())` compila pra sempre-verdadeiro —
    # bloquearia TODOS os códigos de TODOS os módulos, em silêncio.
    # codigos_bloqueados tem que falhar alto em vez disso.
    await admin_session.execute(text(
        "UPDATE aprimora_py.modulo SET ativo = false WHERE slug = 'comum'"
    ))
    await admin_session.flush()
    with pytest.raises(RuntimeError):
        await codigos_bloqueados(admin_session, tid)
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_modulos_do_tenant_lista_modulo_inativo_mas_contratado(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["transporte"])
    await admin_session.flush()
    # Módulo é desativado na plataforma DEPOIS de contratado: o vínculo
    # continua vivo em tenant_modulo. O admin precisa ver isso pra poder
    # descontratar — não pra o módulo simplesmente sumir da tela.
    await admin_session.execute(text(
        "UPDATE aprimora_py.modulo SET ativo = false WHERE slug = 'transporte'"
    ))
    await admin_session.flush()
    itens = await modulos_do_tenant(admin_session, tid)
    por_slug = {m["slug"]: m for m in itens}
    assert "transporte" in por_slug, "módulo inativo sumiu da listagem do admin"
    assert por_slug["transporte"]["ativo"] is False
    assert por_slug["transporte"]["contratado"] is True, (
        "contrato existente não pode desaparecer só porque o módulo foi desativado"
    )
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_contratar_recusa_modulo_inativo(admin_session, two_tenants):
    tid, _ = two_tenants
    await admin_session.execute(text(
        "UPDATE aprimora_py.modulo SET ativo = false WHERE slug = 'administracao'"
    ))
    await admin_session.flush()
    with pytest.raises(ValueError):
        await contratar(admin_session, tid, ["administracao"])
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_contratar_recusa_vinculo_novo_de_modulo_inativo(admin_session, two_tenants):
    """`inativos_novos`: contratar do zero um módulo que NUNCA foi contratado
    e está inativo continua recusado — só o "já tenho, mexi em outra coisa"
    passa a ser permitido."""
    tid, _ = two_tenants
    await admin_session.execute(text(
        "UPDATE aprimora_py.modulo SET ativo = false WHERE slug = 'administracao'"
    ))
    await admin_session.flush()
    with pytest.raises(ValueError):
        await contratar(admin_session, tid, ["administracao"])
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_contratar_mantem_modulo_ja_contratado_e_inativo(admin_session, two_tenants):
    """Achado do review final F2: a aba de módulos reenvia TODOS os slugs
    marcados, incluindo os já contratados que estão inativos (checkbox
    desabilitado, mas continua marcado para permitir descontratar). Isso não
    pode virar 400 só porque o admin também mudou outro módulo no mesmo
    payload."""
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["transporte"])
    await admin_session.flush()
    await admin_session.execute(text(
        "UPDATE aprimora_py.modulo SET ativo = false WHERE slug = 'transporte'"
    ))
    await admin_session.flush()

    # Reenvia 'transporte' (já contratado, agora inativo) JUNTO com uma
    # contratação nova de 'frota' — não pode levantar ValueError.
    await contratar(admin_session, tid, ["transporte", "frota"])
    await admin_session.flush()

    itens = await modulos_do_tenant(admin_session, tid)
    por_slug = {m["slug"]: m for m in itens}
    assert por_slug["transporte"]["contratado"] is True, (
        "módulo já contratado e inativo não pode ser descontratado só por "
        "estar na mesma reconciliação de outro módulo"
    )
    assert por_slug["frota"]["contratado"] is True, "contratação nova junto no mesmo payload falhou"
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_contratar_permite_descontratar_modulo_inativo(admin_session, two_tenants):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["transporte"])
    await admin_session.flush()
    await admin_session.execute(text(
        "UPDATE aprimora_py.modulo SET ativo = false WHERE slug = 'transporte'"
    ))
    await admin_session.flush()
    # Descontratar (tirar da lista alvo) tem que funcionar mesmo com o
    # módulo inativo — só CONTRATAR um inativo é que é recusado.
    await contratar(admin_session, tid, [])
    await admin_session.flush()
    excluido = (await admin_session.execute(text(
        "SELECT tm.excluido FROM aprimora_py.tenant_modulo tm "
        "JOIN aprimora_py.modulo m ON m.id = tm.id_modulo "
        "WHERE tm.tenant_id = :t AND m.slug = 'transporte'"
    ), {"t": tid})).scalar_one()
    assert excluido is True, "descontratar não marcou excluido no vínculo do módulo inativo"
    await admin_session.rollback()
