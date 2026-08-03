"""SEC-RLS-00B — usuário comum (não-SU) por HTTP nos módulos que faltavam.

O brief exige **pelo menos um teste HTTP com usuário comum por módulo
contratado**, e a razão está escrita no CLAUDE.md: em `auth/perms.py` o bypass
de super-usuário **retorna antes** do `getattr(item, action)`. Uma suíte que só
exercita SU nunca percorre o ramo comum — foi assim que 10 rotas do transporte
com um `action` inexistente ficaram devolvendo HTTP 500 para qualquer operador
não-SU, com todos os testes verdes.

Cobertura que já existia quando este arquivo foi escrito:

| módulo         | teste                                                              |
|----------------|--------------------------------------------------------------------|
| `protocolo`    | `test_leitura_por_modulo::test_usuario_sem_permissao_continua_lendo` |
| `administracao`| `test_leitura_por_modulo` (rotas de administração)                   |
| `transporte`   | `test_transporte_p4_relatorio::test_http_usuario_comum_acessa_relatorio_kpis` |

Faltavam **`pagamentos`** e **`frota`** — os dois só tinham teste HTTP com SU
(`test_permissoes_modulo::test_http_su_sem_modulo_recebe_403`). Este arquivo
fecha a tabela.

Cada módulo tem o par completo, e o par é o ponto: só o 200 provaria que a
rota responde, e só o 403 passaria verde numa rota que nega todo mundo. Junto,
o par prova que a permissão **discrimina**.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.services.modulos import contratar
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

# NÃO fixar "sistemas" aqui: `load_permissions` filtra grupos por
# `Sistema.app == app_name`, e o `.env` local vale `aprimora`. Hardcodar o
# default faria o usuário comum nascer num sistema que a consulta de permissões
# não enxerga, e o teste falharia com 403 — parecendo defeito de gate quando é
# defeito de fixture.
APP = get_settings().app_name

# (slug do módulo, código da transação, rota GET)
CENARIOS = [
    ("pagamentos", "pagamento_autorizar", "/api/v2/pagamentos/autorizacao/fila"),
    ("frota", "frota", "/api/v2/frota/veiculos"),
]


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _cria_usuario_comum(session, tenant_id: int, *, codigo_transacao: str) -> int:
    """Usuário de nível != 0 cujo grupo concede `codigo_transacao`.

    Cópia deliberada de `test_permissoes_modulo::_cria_usuario_comum` — os
    arquivos de teste deste repositório são autônomos por convenção. O
    `get-or-create` do nível não é zelo: o bootstrap garante só o nível 0
    (super-usuário), e em banco limpo um `scalar_one()` aqui estoura com
    `NoResultFound` — foi assim que um teste ficou verde local e vermelho no CI.
    """
    sistema_id = (await session.execute(text(
        "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
    ), {"app": APP})).scalar_one()
    nivel_id = (await session.execute(text(
        "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
    ))).scalar_one_or_none()
    if nivel_id is None:
        nivel_id = (await session.execute(text(
            "INSERT INTO utils.nivel (nivel, valor, excluido) "
            "VALUES ('Operacional', 1, false) RETURNING id"
        ))).scalar_one()
    transacao_id = (await session.execute(text(
        "SELECT id FROM utils.transacao WHERE codigo = :c AND excluido = false LIMIT 1"
    ), {"c": codigo_transacao})).scalar_one()
    uid = (await session.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo)
        VALUES (:t, 'Usuario Comum', :email, '', :cpf, true, false,
                :app, 'interno')
        RETURNING id
    """), {
        "t": tenant_id,
        "email": f"comum-{uuid.uuid4().hex[:8]}@rls00b.test",
        "cpf": uuid.uuid4().hex[:11],
        "app": APP,
    })).scalar_one()
    gid = (await session.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'Grupo Comum RLS', false) RETURNING id
    """), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await session.execute(text("""
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
    await session.execute(text("""
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, false, false, false, false)
    """), {"t": tenant_id, "g": gid, "tr": transacao_id})
    return int(uid)


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


def _as_user(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    async def _get_user():
        async with _sm(engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == usuario_id))
            ).scalar_one()

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        arreio_tenant_http(tenant_id, tenant_slug)

    return _setup


@pytest_asyncio.fixture
async def cliente():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    from app.database import engine as app_engine
    await app_engine.dispose()


@pytest.mark.parametrize("modulo,transacao,rota", CENARIOS)
async def test_usuario_comum_com_permissao_e_modulo_contratado_acessa(
    admin_engine, cliente, modulo: str, transacao: str, rota: str
) -> None:
    """200 pelo caminho real: usuário comum, permissão via `grupo_transacao`.

    O SU não serve aqui: o bypass de `auth/perms.py` retorna antes de olhar o
    `action` do item, então uma rota gateada com um `action` que não existe
    responde 200 para SU e 500 para todo o resto. Este teste é o que percorre
    o ramo comum.
    """
    slug = f"rls00b{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome=f"Pref {modulo}", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, [modulo])
            uid = await _cria_usuario_comum(s, tenant.id, codigo_transacao=transacao)
            await s.commit()

        _as_user(admin_engine, uid, tenant.id, tenant.slug)()
        r = await cliente.get(rota)
        # `== 200` e não `!= 403`: a asserção fraca deixaria passar o 500 do
        # `action` inexistente, que é exatamente o defeito que este teste
        # existe para pegar.
        assert r.status_code == 200, (
            f"[{modulo}] usuário comum COM permissão e COM módulo contratado "
            f"não passou em {rota}: {r.status_code} {r.text}"
        )
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.parametrize("modulo,transacao,rota", CENARIOS)
async def test_usuario_comum_sem_o_modulo_contratado_recebe_403(
    admin_engine, cliente, modulo: str, transacao: str, rota: str
) -> None:
    """O outro lado do par: mesma permissão, tenant SEM o módulo → 403.

    Sem este, o teste acima passaria verde numa configuração em que a
    contratação não filtra nada. Com ele, o par prova que a permissão e a
    contratação discriminam — e não que a rota simplesmente responde.
    """
    slug = f"rls00bn{uuid.uuid4().hex[:8]}"
    outro = "frota" if modulo != "frota" else "pagamentos"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome=f"Pref sem {modulo}", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    try:
        async with _sm(admin_engine)() as s:
            # Contrata OUTRO módulo, não nenhum: prova que o gate é específico
            # do slug, e não um "tenant pelado" genérico.
            await contratar(s, tenant.id, [outro])
            uid = await _cria_usuario_comum(s, tenant.id, codigo_transacao=transacao)
            await s.commit()

        _as_user(admin_engine, uid, tenant.id, tenant.slug)()
        r = await cliente.get(rota)
        assert r.status_code == 403, (
            f"[{modulo}] tenant SEM o módulo deveria dar 403 em {rota}: "
            f"{r.status_code} {r.text}"
        )
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)
