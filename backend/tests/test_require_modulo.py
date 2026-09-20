"""`require_modulo` barra por CONTRATAÇÃO do tenant, não por permissão do usuário.

A propriedade central desta fatia está no último teste: usuário sem permissão
nenhuma continua lendo, desde que o tenant tenha o módulo. Se algum dia alguém
"melhorar" a dependência para também exigir permissão, esse teste reprova — e é
o único aviso de que a fatia mudou de natureza.
"""
import pytest
from fastapi import HTTPException

from app.auth.modulos import require_modulo, require_modulo_qualquer
from app.services.modulos import contratar


@pytest.mark.asyncio
async def test_barra_tenant_sem_o_modulo(two_tenants, admin_session):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()

    check = require_modulo("pagamentos")
    with pytest.raises(HTTPException) as e:
        await check(tenant_id=tid, db=admin_session)
    assert e.value.status_code == 403
    assert "pagamentos" in str(e.value.detail)
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_passa_com_o_modulo_contratado(two_tenants, admin_session):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()

    check = require_modulo("frota")
    assert await check(tenant_id=tid, db=admin_session) is None
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_modulo_nao_contratavel_nunca_barra(two_tenants, admin_session):
    """`comum` está sempre disponível — nem contratando zero módulos ele cai."""
    tid, _ = two_tenants
    await contratar(admin_session, tid, [])
    await admin_session.flush()

    check = require_modulo("comum")
    assert await check(tenant_id=tid, db=admin_session) is None
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_nao_consulta_permissao_do_usuario(two_tenants, admin_session):
    """A PROPRIEDADE DA FATIA: a dependência não recebe usuário e não o consulta.

    Se a assinatura passar a exigir `user`, este teste quebra na chamada — de
    propósito. A decisão registrada no escopo é que esta fatia fecha SÓ a
    contratação; exigir permissão de leitura é outra decisão, do dono do produto.
    """
    import inspect

    params = set(inspect.signature(require_modulo("frota")).parameters)
    assert params == {"tenant_id", "db"}, (
        "require_modulo passou a depender de algo além de tenant/db — se for o "
        "usuário, a fatia virou mudança de política de acesso"
    )


# ---------------------------------------------------------------------------
# require_modulo_qualquer — item 2.2 do backlog (Transporte Regulado): rotas
# genéricas de routers/workflow.py, usadas por protocolo (processo) e
# transporte (ocorrência/alvará/convocação) por igual.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qualquer_passa_com_qualquer_um_dos_modulos_contratado(
    two_tenants, admin_session
):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["transporte"])
    await admin_session.flush()

    check = require_modulo_qualquer("protocolo", "transporte")
    assert await check(tenant_id=tid, db=admin_session) is None
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_qualquer_barra_sem_nenhum_dos_modulos(two_tenants, admin_session):
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()

    check = require_modulo_qualquer("protocolo", "transporte")
    with pytest.raises(HTTPException) as e:
        await check(tenant_id=tid, db=admin_session)
    assert e.value.status_code == 403
    assert "protocolo" in str(e.value.detail)
    assert "transporte" in str(e.value.detail)
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_qualquer_nao_e_qualquer_modulo_generico(two_tenants, admin_session):
    """Não é "algum módulo contratado" — é só os slugs listados. `pagamentos`
    sozinho não satisfaz um gate de ("protocolo", "transporte")."""
    tid, _ = two_tenants
    await contratar(admin_session, tid, ["pagamentos"])
    await admin_session.flush()

    check = require_modulo_qualquer("protocolo", "transporte")
    with pytest.raises(HTTPException):
        await check(tenant_id=tid, db=admin_session)
    await admin_session.rollback()
