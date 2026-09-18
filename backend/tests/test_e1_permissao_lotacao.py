"""Permissão por lotação e lotação ativa da sessão (E1, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md` §5 E1, §6
Q1 ("pelos dois eixos", Jorge, 2026-09-16).

`UsuarioGrupo.id_unidade_trabalho` já existia no schema legado — migration
0117 só acrescenta FK + índice (ver a docstring dela: 0 de 104 linhas
preenchidas antes desta fatia, a coluna estava dormente). Nulo = vínculo
global (comportamento de sempre); preenchido = só vale quando a lotação
ATIVA da sessão bater. Os dois eixos se somam por UNIÃO, nunca interseção.

Cobertura:
- `load_permissions`: sem contexto (byte a byte igual a antes), com
  contexto errado (grant de lotação alheia não vaza), com contexto certo
  (grant de lotação aparece), união com um grant global simultâneo.
- `listar_lotacoes`: principal + secundária, sem duplicar, usuário sem
  lotação nenhuma.
- HTTP fim-a-fim, sem nenhum dependency_override — token real, decodificado
  pelo caminho de produção: login emite a claim com a lotação principal;
  `POST /auth/lotacao-ativa` troca para uma lotação do próprio usuário e
  RECUSA lotação alheia (403); a troca muda o que `/permissoes/me` mostra
  na mesma sessão (cookie novo, sem segunda chamada a /auth/me).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.jwt import build_payload, encode_token, get_jwt_secret
from app.config import get_settings
from app.main import app
from app.services.permissoes import listar_lotacoes, load_permissions
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    """Tenant com admin SU (lotação principal) + uma segunda unidade
    ("secundária") — `provisionar_tenant` só cria a primeira."""
    slug = _slug("e1-")
    async with _sm(engine)() as s:
        tenant, senha = await provisionar_tenant(
            s, slug=slug, nome="Pref E1", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    async with _sm(engine)() as s:
        admin_id = (await s.execute(
            text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant.id},
        )).scalar_one()
        principal_id = (await s.execute(
            text("SELECT id_unidade_trabalho FROM utils.usuario WHERE id=:u"),
            {"u": admin_id},
        )).scalar_one()
        tipo_id = (await s.execute(
            text(
                "SELECT id FROM utils.tipo_unidade_trabalho "
                "WHERE tenant_id=:t LIMIT 1"
            ),
            {"t": tenant.id},
        )).scalar_one()
        secundaria_id = (await s.execute(
            text(
                "INSERT INTO utils.unidade_trabalho "
                "(tenant_id, unidade_trabalho, id_tipo_unidade_trabalho, excluido) "
                "VALUES (:t, 'Setor Secundário E1', :ti, false) RETURNING id"
            ),
            {"t": tenant.id, "ti": tipo_id},
        )).scalar_one()
        await s.commit()
    return tenant, admin_id, principal_id, secundaria_id, senha


async def _cria_usuario_comum(
    session, tenant_id: int, *, principal_id: int, secundaria_id: int
) -> tuple[int, int, int]:
    """Usuário comum lotado em `principal_id`, com `secundaria_id` como
    lotação extra (`utils.usuario_unidade_trabalho`) — o par principal +
    secundárias da captura 38 do SUiTE. Devolve (usuario_id, sistema_id,
    nivel_id) para quem for conceder grupos."""
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
    uid = (await session.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo,
                                   id_unidade_trabalho, must_change_password)
        VALUES (:t, 'Usuario Comum E1', :email, '', :cpf, true, false,
                :app, 'interno', :u, false)
        RETURNING id
    """), {
        "t": tenant_id, "email": f"comum-e1-{uuid.uuid4().hex[:8]}@t.local",
        "cpf": uuid.uuid4().hex[:11], "app": APP, "u": principal_id,
    })).scalar_one()
    await session.execute(text("""
        INSERT INTO utils.usuario_unidade_trabalho
            (tenant_id, id_usuario, id_unidade_trabalho, excluido)
        VALUES (:t, :u, :s, false)
    """), {"t": tenant_id, "u": uid, "s": secundaria_id})
    return uid, sistema_id, nivel_id


async def _concede(
    session, tenant_id, sistema_id, nivel_id, usuario_id, codigo_transacao,
    *, id_unidade_trabalho: int | None = None, nome_grupo: str = "Grupo E1",
) -> int:
    """Cria grupo + grupo_transacao + usuario_grupo concedendo
    `codigo_transacao`, com o escopo de lotação pedido."""
    transacao_id = (await session.execute(text(
        "SELECT id FROM utils.transacao WHERE codigo = :c AND excluido = false LIMIT 1"
    ), {"c": codigo_transacao})).scalar_one()
    gid = (await session.execute(text("""
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, :g, false) RETURNING id
    """), {
        "t": tenant_id, "n": nivel_id, "s": sistema_id,
        "g": f"{nome_grupo}-{uuid.uuid4().hex[:6]}",
    })).scalar_one()
    await session.execute(text("""
        INSERT INTO utils.usuario_grupo
            (tenant_id, id_usuario, id_grupo, ativo, excluido, app, id_unidade_trabalho)
        VALUES (:t, :u, :g, true, false, :app, :ut)
    """), {
        "t": tenant_id, "u": usuario_id, "g": gid, "app": APP,
        "ut": id_unidade_trabalho,
    })
    await session.execute(text("""
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, true, true, true, false)
    """), {"t": tenant_id, "g": gid, "tr": transacao_id})
    return gid


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


# --------------------------------------------------------------------------
# load_permissions — o filtro por lotação
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_de_lotacao_nao_conta_sem_contexto_ativo(admin_engine):
    """Comportamento de sempre: sem `id_unidade_contexto`, só o global conta —
    byte a byte igual a antes desta fatia."""
    tenant, _, principal_id, secundaria_id, _ = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            uid, sis, niv = await _cria_usuario_comum(
                db, tenant.id, principal_id=principal_id, secundaria_id=secundaria_id,
            )
            await _concede(
                db, tenant.id, sis, niv, uid, "manifestante",
                id_unidade_trabalho=secundaria_id,
            )
            await db.commit()

        async with _sm(admin_engine)() as db:
            perms = await load_permissions(db, uid, tenant_id=tenant.id)
        assert "manifestante" not in {p.codigo for p in perms.items}
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_grant_de_lotacao_nao_vaza_para_lotacao_errada(admin_engine):
    tenant, _, principal_id, secundaria_id, _ = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            uid, sis, niv = await _cria_usuario_comum(
                db, tenant.id, principal_id=principal_id, secundaria_id=secundaria_id,
            )
            await _concede(
                db, tenant.id, sis, niv, uid, "manifestante",
                id_unidade_trabalho=secundaria_id,
            )
            await db.commit()

        async with _sm(admin_engine)() as db:
            perms = await load_permissions(
                db, uid, tenant_id=tenant.id, id_unidade_contexto=principal_id,
            )
        assert "manifestante" not in {p.codigo for p in perms.items}
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_grant_de_lotacao_conta_com_contexto_certo(admin_engine):
    tenant, _, principal_id, secundaria_id, _ = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            uid, sis, niv = await _cria_usuario_comum(
                db, tenant.id, principal_id=principal_id, secundaria_id=secundaria_id,
            )
            await _concede(
                db, tenant.id, sis, niv, uid, "manifestante",
                id_unidade_trabalho=secundaria_id,
            )
            await db.commit()

        async with _sm(admin_engine)() as db:
            perms = await load_permissions(
                db, uid, tenant_id=tenant.id, id_unidade_contexto=secundaria_id,
            )
        assert "manifestante" in {p.codigo for p in perms.items}
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_uniao_global_e_lotacao_nao_interseccao(admin_engine):
    """Q1: os dois eixos se SOMAM. Um grant global ('frota') sobrevive
    trocando de lotação; o de lotação ('manifestante') só aparece na sua."""
    tenant, _, principal_id, secundaria_id, _ = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            uid, sis, niv = await _cria_usuario_comum(
                db, tenant.id, principal_id=principal_id, secundaria_id=secundaria_id,
            )
            await _concede(db, tenant.id, sis, niv, uid, "frota")  # global
            await _concede(
                db, tenant.id, sis, niv, uid, "manifestante",
                id_unidade_trabalho=secundaria_id,
            )
            await db.commit()

        async with _sm(admin_engine)() as db:
            no_principal = await load_permissions(
                db, uid, tenant_id=tenant.id, id_unidade_contexto=principal_id,
            )
        codigos_principal = {p.codigo for p in no_principal.items}
        assert "frota" in codigos_principal
        assert "manifestante" not in codigos_principal

        async with _sm(admin_engine)() as db:
            na_secundaria = await load_permissions(
                db, uid, tenant_id=tenant.id, id_unidade_contexto=secundaria_id,
            )
        codigos_secundaria = {p.codigo for p in na_secundaria.items}
        assert "frota" in codigos_secundaria, "vínculo global sumiu ao trocar de lotação"
        assert "manifestante" in codigos_secundaria
    finally:
        await _cleanup(admin_engine, tenant.id)


# --------------------------------------------------------------------------
# listar_lotacoes
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listar_lotacoes_principal_e_secundaria_sem_duplicar(admin_engine):
    tenant, admin_id, principal_id, secundaria_id, _ = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            uid, _, _ = await _cria_usuario_comum(
                db, tenant.id, principal_id=principal_id, secundaria_id=secundaria_id,
            )
            # segunda linha "acidental" apontando pra própria principal — não
            # pode duplicar na resposta.
            await db.execute(text("""
                INSERT INTO utils.usuario_unidade_trabalho
                    (tenant_id, id_usuario, id_unidade_trabalho, excluido)
                VALUES (:t, :u, :p, false)
            """), {"t": tenant.id, "u": uid, "p": principal_id})
            await db.commit()

        async with _sm(admin_engine)() as db:
            from app.models import Usuario
            from sqlalchemy import select
            usuario = (await db.execute(
                select(Usuario).where(Usuario.id == uid)
            )).scalar_one()
            lotacoes = await listar_lotacoes(db, tenant_id=tenant.id, usuario=usuario)

        assert {l.id for l in lotacoes} == {principal_id, secundaria_id}
        principal = next(l for l in lotacoes if l.id == principal_id)
        secundaria = next(l for l in lotacoes if l.id == secundaria_id)
        assert principal.principal is True
        assert secundaria.principal is False
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_listar_lotacoes_usuario_sem_lotacao_devolve_vazio(admin_engine):
    tenant, admin_id, principal_id, secundaria_id, _ = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            uid = (await db.execute(text("""
                INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf,
                    ativo, excluido, app, nivel_acesso_sigilo, id_unidade_trabalho,
                    must_change_password)
                VALUES (:t, 'Sem Lotacao', :email, '', :cpf, true, false, :app,
                        'interno', NULL, false)
                RETURNING id
            """), {
                "t": tenant.id, "email": f"semlotacao-{uuid.uuid4().hex[:8]}@t.local",
                "cpf": uuid.uuid4().hex[:11], "app": APP,
            })).scalar_one()
            await db.commit()

        async with _sm(admin_engine)() as db:
            from app.models import Usuario
            from sqlalchemy import select
            usuario = (await db.execute(
                select(Usuario).where(Usuario.id == uid)
            )).scalar_one()
            lotacoes = await listar_lotacoes(db, tenant_id=tenant.id, usuario=usuario)
        assert lotacoes == []
    finally:
        await _cleanup(admin_engine, tenant.id)


# --------------------------------------------------------------------------
# HTTP fim-a-fim — SEM dependency_overrides, token real (produção de verdade)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_emite_contexto_com_lotacao_principal(admin_engine):
    tenant, admin_id, principal_id, _, senha = await _provisionar(admin_engine)
    try:
        arreio_tenant_http(tenant.id, tenant.slug)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            host = {"Host": f"{tenant.slug}.aprimora.local"}
            r = await client.post(
                "/api/v2/auth/login",
                json={"email": _admin_email(tenant.slug), "senha": senha},
                headers=host,
            )
            assert r.status_code == 200, r.text
            r_me = await client.get("/api/v2/auth/me", headers=host)
        assert r_me.status_code == 200, r_me.text
        body = r_me.json()
        assert body["unidade_contexto_id"] == principal_id
        assert any(l["id"] == principal_id and l["principal"] for l in body["lotacoes"])
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)


def _admin_email(slug: str) -> str:
    return f"{slug}@t.local"


@pytest.mark.asyncio
async def test_trocar_lotacao_ativa_muda_o_que_permissoes_me_mostra(admin_engine):
    """Fim-a-fim sem overrides: token direto no cookie (mesmo formato do
    login), troca de lotação, e a MESMA sessão HTTP reflete o novo contexto
    sem precisar reconsultar /auth/me."""
    tenant, admin_id, principal_id, secundaria_id, _ = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as db:
            uid, sis, niv = await _cria_usuario_comum(
                db, tenant.id, principal_id=principal_id, secundaria_id=secundaria_id,
            )
            await _concede(
                db, tenant.id, sis, niv, uid, "manifestante",
                id_unidade_trabalho=secundaria_id,
            )
            await db.commit()

        async with _sm(admin_engine)() as db:
            secret = await get_jwt_secret(db)
            payload = build_payload(
                uid, "comum-e1@t.local", tenant_id=tenant.id,
                unidade_contexto_id=principal_id,
            )
            token = encode_token(payload, secret)

        arreio_tenant_http(tenant.id, tenant.slug)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            host = {"Host": f"{tenant.slug}.aprimora.local"}
            client.cookies.set("aprimora_token", token)

            r1 = await client.get("/api/v2/permissoes/me", headers=host)
            assert r1.status_code == 200, r1.text
            assert "manifestante" not in {
                p["codigo"] for p in r1.json()["permissoes"]
            }

            r_troca = await client.post(
                "/api/v2/auth/lotacao-ativa",
                json={"id_unidade_trabalho": secundaria_id},
                headers=host,
            )
            assert r_troca.status_code == 200, r_troca.text
            assert r_troca.json()["unidade_contexto_id"] == secundaria_id

            # Mesmo client, sem tocar no cookie: o Set-Cookie da troca já
            # vale para a próxima chamada.
            r2 = await client.get("/api/v2/permissoes/me", headers=host)
        assert r2.status_code == 200, r2.text
        assert "manifestante" in {p["codigo"] for p in r2.json()["permissoes"]}
    finally:
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_trocar_para_lotacao_alheia_recebe_403(admin_engine):
    tenant, admin_id, principal_id, secundaria_id, _ = await _provisionar(admin_engine)
    outro_tenant = None
    try:
        # Uma unidade de OUTRO tenant — não pode virar contexto ativo daqui.
        outro_tenant, _, _, alheia_id, _ = await _provisionar(admin_engine)

        async with _sm(admin_engine)() as db:
            uid, _, _ = await _cria_usuario_comum(
                db, tenant.id, principal_id=principal_id, secundaria_id=secundaria_id,
            )
            await db.commit()
            secret = await get_jwt_secret(db)
            payload = build_payload(
                uid, "comum-e1@t.local", tenant_id=tenant.id,
                unidade_contexto_id=principal_id,
            )
            token = encode_token(payload, secret)

        arreio_tenant_http(tenant.id, tenant.slug)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            host = {"Host": f"{tenant.slug}.aprimora.local"}
            client.cookies.set("aprimora_token", token)
            r = await client.post(
                "/api/v2/auth/lotacao-ativa",
                json={"id_unidade_trabalho": alheia_id},
                headers=host,
            )
        assert r.status_code == 403, r.text
    finally:
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant.id)
        if outro_tenant is not None:
            await _cleanup(admin_engine, outro_tenant.id)
