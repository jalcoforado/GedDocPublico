"""load_permissions respeita a contratação de módulos — inclusive para SU."""
import pytest
from sqlalchemy import text

from app.config import get_settings
from app.services.modulos import contratar
from app.services.permissoes import load_permissions

# O brief original hardcodeava app='sistemas' — esse valor não corresponde a
# nenhum utils.sistema ligado às 23 transações da Task 3B nesta base (o
# container roda APP_NAME=aprimora; 'sistemas' é uma linha de catálogo
# distinta, sem sistema_transacao vinculada). Com o literal errado, a query
# `Sistema.app == app` em load_permissions nunca casa, `rows` vem vazio e a
# função devolve is_super_usuario=False para QUALQUER teste aqui — inclusive
# depois do fix do Step 3. Troquei pelo padrão já usado em
# app/cli/seed_bootstrap.py e tests/test_transacoes_rbac.py:
# get_settings().app_name. Mesmo bug de fundo do já conhecido
# test_pr5a_dashboard_servicos.py / test_jwt_compat.py, mas ali é tolerado
# como falha pré-existente fora de escopo; aqui é o teste central da fatia
# — se ficar quebrado por esse motivo, "SU não bypassa contratação" nunca é
# realmente exercitado.
APP = get_settings().app_name


async def _cria_su(session, tenant_id: int) -> int:
    """Cria usuário + grupo nível 0 no sistema do app. Devolve o id do usuário."""
    sistema_id = (await session.execute(text(
        "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
    ), {"app": APP})).scalar_one()
    nivel_id = (await session.execute(text(
        "SELECT id FROM utils.nivel WHERE valor = 0 LIMIT 1"
    ))).scalar_one()
    uid = (await session.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo)
        VALUES (:t, 'SU Modulo', :email, '', '00000000000', true, false,
                :app, 'interno')
        RETURNING id
    """), {"t": tenant_id, "email": f"su-mod-{tenant_id}@modulo.test", "app": APP})).scalar_one()
    gid = (await session.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'SU Modulo', false) RETURNING id
    """), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await session.execute(text("""
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
    await session.flush()
    return uid


@pytest.mark.asyncio
async def test_su_nao_bypassa_contratacao(admin_session, two_tenants):
    """A decisão de segurança central: SU vê tudo do que foi contratado, e só."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid, ["frota"])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    codigos = {p.codigo for p in perms.items}

    assert perms.is_super_usuario is True
    assert "frota" in codigos, "módulo contratado sumiu para o SU"
    assert not {c for c in codigos if c.startswith("pagamento_")}, (
        "SU enxergou transações de módulo NÃO contratado"
    )
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_transacao_de_modulo_comum_sobrevive(admin_session, two_tenants):
    """'comum' não é contratável e nunca pode ser filtrado."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid, [])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    assert "dashboard" in {p.codigo for p in perms.items}
    await admin_session.rollback()


@pytest.mark.asyncio
async def test_contratar_tudo_nao_muda_nada(admin_session, two_tenants):
    """Regressão: com os 5 contratados, o resultado é o de antes da mudança."""
    tid, _ = two_tenants
    uid = await _cria_su(admin_session, tid)
    await contratar(admin_session, tid,
                    ["protocolo", "pagamentos", "frota", "transporte", "administracao"])
    await admin_session.flush()

    perms = await load_permissions(admin_session, uid, tenant_id=tid)
    codigos = {p.codigo for p in perms.items}
    assert "frota" in codigos
    assert "processo" in codigos
    assert "pagamento_autorizar" in codigos
    await admin_session.rollback()
