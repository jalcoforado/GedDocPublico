"""Favoritos e marcadores de processo (fatia F5, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.

Dois recursos independentes, ambos toggles sem trilha de auditoria (mesma
filosofia de `atribuir_responsavel`: só a DESIGNAÇÃO fica no histórico, não a
navegação):

- Favorito: acompanhamento pessoal, 1 linha por (usuário, processo).
- Marcador: catálogo de etiquetas por tenant; `definir_marcadores` substitui
  o conjunto INTEIRO vinculado ao processo, não marca/desmarca incrementalmente.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import (
    Assunto,
    Manifestante,
    Marcador,
    Processo,
    TipoProcesso,
    Usuario,
)
from app.services.marcadores import (
    MarcadorError,
    definir_marcadores,
    desfavoritar,
    favoritar,
)
from app.services.processos import list_processos
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _cria_usuario_comum(
    session, tenant_id: int, *, unidade_id: int, codigo_transacao: str = "processo",
    action_atualizar: bool = True,
) -> int:
    """Cópia do helper de `test_processo_destinos_permitidos.py` — mesma razão lá."""
    sistema_id = (
        await session.execute(
            text(
                "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
            ),
            {"app": APP},
        )
    ).scalar_one()
    nivel_id = (
        await session.execute(
            text("SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1")
        )
    ).scalar_one_or_none()
    if nivel_id is None:
        nivel_id = (
            await session.execute(
                text(
                    "INSERT INTO utils.nivel (nivel, valor, excluido) "
                    "VALUES ('Operacional', 1, false) RETURNING id"
                )
            )
        ).scalar_one()
    transacao_id = (
        await session.execute(
            text(
                "SELECT id FROM utils.transacao WHERE codigo = :c "
                "AND excluido = false LIMIT 1"
            ),
            {"c": codigo_transacao},
        )
    ).scalar_one()
    uid = (
        await session.execute(
            text(
                """
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo,
                                   id_unidade_trabalho)
        VALUES (:t, 'Operador', :email, '', :cpf, true, false, :app,
                'ultrassecreto', :u)
        RETURNING id
    """
            ),
            {
                "t": tenant_id,
                "email": f"op-{uuid.uuid4().hex[:8]}@f5.test",
                "cpf": uuid.uuid4().hex[:11],
                "app": APP,
                "u": unidade_id,
            },
        )
    ).scalar_one()
    gid = (
        await session.execute(
            text(
                """
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'Grupo F5', false) RETURNING id
    """
            ),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id},
        )
    ).scalar_one()
    await session.execute(
        text(
            """
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """
        ),
        {"t": tenant_id, "u": uid, "g": gid, "app": APP},
    )
    await session.execute(
        text(
            """
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, true, :atu, true, false)
    """
        ),
        {"t": tenant_id, "g": gid, "tr": transacao_id, "atu": action_atualizar},
    )
    return uid


@pytest_asyncio.fixture
async def cen(admin_engine):
    """Tenant com 1 unidade, 1 processo, 1 operador não-SU, 2 marcadores."""
    slug = _slug("f5-")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref F5",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )

    async with _sm(admin_engine)() as s:
        unidade_id = (
            await s.execute(
                text(
                    "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t "
                    "ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()
        id_tipo_manif = (
            await s.execute(
                text(
                    "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t "
                    "ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()

        tp = TipoProcesso(
            tenant_id=tenant.id, tipo_processo="Geral", exige_processo_pai=False,
            ativo=True, excluido=False,
        )
        manif = Manifestante(
            tenant_id=tenant.id, id_tipo_manifestante=id_tipo_manif, nome="Maria",
            ativo=True, excluido=False,
        )
        s.add_all([tp, manif])
        await s.flush()
        assunto = Assunto(
            tenant_id=tenant.id, assunto="Solicitação", id_tipo_processo=tp.id,
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(assunto)
        await s.flush()

        operador = await _cria_usuario_comum(s, tenant.id, unidade_id=unidade_id)

        p1 = Processo(
            tenant_id=tenant.id, id_assunto=assunto.id, virtual=True,
            data_hora_abertura=datetime.now(), numero_processo=f"{slug}-p1",
            id_unidade_proprietaria=unidade_id, id_manifestante=manif.id,
            id_local_atual=unidade_id, nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        p2 = Processo(
            tenant_id=tenant.id, id_assunto=assunto.id, virtual=True,
            data_hora_abertura=datetime.now(), numero_processo=f"{slug}-p2",
            id_unidade_proprietaria=unidade_id, id_manifestante=manif.id,
            id_local_atual=unidade_id, nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        s.add_all([p1, p2])
        await s.flush()

        m1 = Marcador(
            tenant_id=tenant.id, id_unidade_trabalho=None, nome="Urgente",
            cor="#FF0000", ativo=True, excluido=False,
        )
        m2 = Marcador(
            tenant_id=tenant.id, id_unidade_trabalho=None, nome="Revisar",
            cor="#00FF00", ativo=True, excluido=False,
        )
        s.add_all([m1, m2])
        await s.flush()
        await s.commit()

        dados = {
            "tenant": tenant,
            "unidade_id": unidade_id,
            "operador": operador,
            "processo1_id": p1.id,
            "processo2_id": p2.id,
            "marcador1_id": m1.id,
            "marcador2_id": m2.id,
        }

    yield dados

    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM aprimora_py.processo_marcador WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.marcador WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.processo_favorito WHERE tenant_id=:t",
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
            "  id_local_atual=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": dados["tenant"].id})
        await s.commit()


# ---------------------------------------------------------------------------
# Favorito — serviço
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_favoritar_e_idempotente(admin_engine, cen):
    t, p, u = cen["tenant"].id, cen["processo1_id"], cen["operador"]
    async with _sm(admin_engine)() as s:
        await favoritar(s, p, tenant_id=t, usuario_id=u)
    async with _sm(admin_engine)() as s:
        await favoritar(s, p, tenant_id=t, usuario_id=u)  # segunda vez não erra

    async with _sm(admin_engine)() as s:
        n = (
            await s.execute(
                text(
                    "SELECT count(*) FROM aprimora_py.processo_favorito "
                    "WHERE tenant_id=:t AND id_usuario=:u AND id_processo=:p"
                ),
                {"t": t, "u": u, "p": p},
            )
        ).scalar_one()
    assert n == 1


@pytest.mark.asyncio
async def test_desfavoritar_processo_nao_favoritado_nao_erra(admin_engine, cen):
    t, p, u = cen["tenant"].id, cen["processo1_id"], cen["operador"]
    async with _sm(admin_engine)() as s:
        await desfavoritar(s, p, tenant_id=t, usuario_id=u)  # nunca foi favorito


@pytest.mark.asyncio
async def test_favoritar_depois_desfavoritar_remove_a_linha(admin_engine, cen):
    t, p, u = cen["tenant"].id, cen["processo1_id"], cen["operador"]
    async with _sm(admin_engine)() as s:
        await favoritar(s, p, tenant_id=t, usuario_id=u)
    async with _sm(admin_engine)() as s:
        await desfavoritar(s, p, tenant_id=t, usuario_id=u)

    async with _sm(admin_engine)() as s:
        n = (
            await s.execute(
                text(
                    "SELECT count(*) FROM aprimora_py.processo_favorito "
                    "WHERE tenant_id=:t AND id_usuario=:u AND id_processo=:p"
                ),
                {"t": t, "u": u, "p": p},
            )
        ).scalar_one()
    assert n == 0


@pytest.mark.asyncio
async def test_list_processos_favoritos_sem_contexto_devolve_nada(admin_engine, cen):
    """Mesmo critério de `escopo`: contexto ausente é NADA, nunca "tudo"."""
    t, p, u = cen["tenant"].id, cen["processo1_id"], cen["operador"]
    async with _sm(admin_engine)() as s:
        await favoritar(s, p, tenant_id=t, usuario_id=u)

    async with _sm(admin_engine)() as s:
        items, total = await list_processos(
            s, tenant_id=t, page=1, page_size=20, favoritos=True,
            id_usuario_contexto=None,
        )
    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_list_processos_favoritos_filtra_so_os_favoritados(admin_engine, cen):
    t = cen["tenant"].id
    p1, p2, u = cen["processo1_id"], cen["processo2_id"], cen["operador"]
    async with _sm(admin_engine)() as s:
        await favoritar(s, p1, tenant_id=t, usuario_id=u)

    async with _sm(admin_engine)() as s:
        items, total = await list_processos(
            s, tenant_id=t, page=1, page_size=20, favoritos=True,
            id_usuario_contexto=u,
        )
    assert total == 1
    assert items[0].id == p1
    assert items[0].favorito is True

    async with _sm(admin_engine)() as s:
        items2, total2 = await list_processos(
            s, tenant_id=t, page=1, page_size=20, id_usuario_contexto=u,
        )
    assert total2 == 2  # sem o filtro, os dois aparecem
    por_id = {i.id: i.favorito for i in items2}
    assert por_id[p1] is True
    assert por_id[p2] is False


# ---------------------------------------------------------------------------
# Marcador — serviço
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_definir_marcadores_substitui_o_conjunto_inteiro(admin_engine, cen):
    t, p, u = cen["tenant"].id, cen["processo1_id"], cen["operador"]
    m1, m2 = cen["marcador1_id"], cen["marcador2_id"]

    async with _sm(admin_engine)() as s:
        await definir_marcadores(s, p, tenant_id=t, ids_marcador=[m1, m2], usuario_id=u)
    async with _sm(admin_engine)() as s:
        ids = (
            await s.execute(
                text(
                    "SELECT id_marcador FROM aprimora_py.processo_marcador "
                    "WHERE tenant_id=:t AND id_processo=:p ORDER BY id_marcador"
                ),
                {"t": t, "p": p},
            )
        ).scalars().all()
    assert sorted(ids) == sorted([m1, m2])

    # Segunda chamada com só m1: m2 sai.
    async with _sm(admin_engine)() as s:
        await definir_marcadores(s, p, tenant_id=t, ids_marcador=[m1], usuario_id=u)
    async with _sm(admin_engine)() as s:
        ids2 = (
            await s.execute(
                text(
                    "SELECT id_marcador FROM aprimora_py.processo_marcador "
                    "WHERE tenant_id=:t AND id_processo=:p"
                ),
                {"t": t, "p": p},
            )
        ).scalars().all()
    assert ids2 == [m1]


@pytest.mark.asyncio
async def test_definir_marcadores_e_idempotente(admin_engine, cen):
    t, p, u = cen["tenant"].id, cen["processo1_id"], cen["operador"]
    m1 = cen["marcador1_id"]
    async with _sm(admin_engine)() as s:
        await definir_marcadores(s, p, tenant_id=t, ids_marcador=[m1], usuario_id=u)
    async with _sm(admin_engine)() as s:
        await definir_marcadores(s, p, tenant_id=t, ids_marcador=[m1], usuario_id=u)

    async with _sm(admin_engine)() as s:
        n = (
            await s.execute(
                text(
                    "SELECT count(*) FROM aprimora_py.processo_marcador "
                    "WHERE tenant_id=:t AND id_processo=:p"
                ),
                {"t": t, "p": p},
            )
        ).scalar_one()
    assert n == 1


@pytest.mark.asyncio
async def test_definir_marcadores_vazio_remove_tudo(admin_engine, cen):
    t, p, u = cen["tenant"].id, cen["processo1_id"], cen["operador"]
    m1, m2 = cen["marcador1_id"], cen["marcador2_id"]
    async with _sm(admin_engine)() as s:
        await definir_marcadores(s, p, tenant_id=t, ids_marcador=[m1, m2], usuario_id=u)
    async with _sm(admin_engine)() as s:
        await definir_marcadores(s, p, tenant_id=t, ids_marcador=[], usuario_id=u)

    async with _sm(admin_engine)() as s:
        n = (
            await s.execute(
                text(
                    "SELECT count(*) FROM aprimora_py.processo_marcador "
                    "WHERE tenant_id=:t AND id_processo=:p"
                ),
                {"t": t, "p": p},
            )
        ).scalar_one()
    assert n == 0


@pytest.mark.asyncio
async def test_definir_marcadores_rejeita_id_fora_do_tenant(admin_engine, cen):
    t, p, u = cen["tenant"].id, cen["processo1_id"], cen["operador"]
    async with _sm(admin_engine)() as s:
        with pytest.raises(MarcadorError):
            await definir_marcadores(s, p, tenant_id=t, ids_marcador=[999999], usuario_id=u)


@pytest.mark.asyncio
async def test_definir_marcadores_processo_inexistente_e_sem_op(admin_engine, cen):
    """Sem-op silencioso, não erro: quem resolve "não existe" é o router
    (`get_processo_detail(...) is None -> 404`), não o service."""
    t, u = cen["tenant"].id, cen["operador"]
    m1 = cen["marcador1_id"]
    async with _sm(admin_engine)() as s:
        await definir_marcadores(s, 999999, tenant_id=t, ids_marcador=[m1], usuario_id=u)


@pytest.mark.asyncio
async def test_list_processos_id_marcador_filtra(admin_engine, cen):
    t = cen["tenant"].id
    p1, p2, u = cen["processo1_id"], cen["processo2_id"], cen["operador"]
    m1 = cen["marcador1_id"]
    async with _sm(admin_engine)() as s:
        await definir_marcadores(s, p1, tenant_id=t, ids_marcador=[m1], usuario_id=u)

    async with _sm(admin_engine)() as s:
        items, total = await list_processos(
            s, tenant_id=t, page=1, page_size=20, id_marcador=m1,
        )
    assert total == 1
    assert items[0].id == p1
    assert [mk.id for mk in items[0].marcadores] == [m1]

    async with _sm(admin_engine)() as s:
        items2, _ = await list_processos(s, tenant_id=t, page=1, page_size=20)
    por_id = {i.id: [mk.id for mk in i.marcadores] for i in items2}
    assert por_id[p1] == [m1]
    assert por_id[p2] == []


# ---------------------------------------------------------------------------
# HTTP, usuário comum
# ---------------------------------------------------------------------------


def _client_como(cen, admin_engine, *, user_id: int):
    t = cen["tenant"]

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (await s.execute(select(Usuario).where(Usuario.id == user_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(t.id, t.slug)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_http_usuario_comum_favorita_e_desfavorita(admin_engine, cen):
    """`require_permission("processo")` sem action: basta ter a transação —
    não precisa de `atualizar` — para favoritar."""
    async with _client_como(cen, admin_engine, user_id=cen["operador"]) as client:
        r = await client.put(f"/api/v2/processos/{cen['processo1_id']}/favorito")
        assert r.status_code == 200, r.text
        assert r.json()["favorito"] is True

        r2 = await client.put(f"/api/v2/processos/{cen['processo1_id']}/favorito")
        assert r2.status_code == 200, r2.text  # idempotente

        r3 = await client.delete(f"/api/v2/processos/{cen['processo1_id']}/favorito")
        assert r3.status_code == 200, r3.text
        assert r3.json()["favorito"] is False


@pytest.mark.asyncio
async def test_http_usuario_comum_sem_permissao_de_atualizar_nao_define_marcadores(
    admin_engine, cen,
):
    """`definir_marcadores` exige `require_permission("processo", "atualizar")`
    — diferente de favoritar, este É uma escrita no processo."""
    t = cen["tenant"]
    async with _sm(admin_engine)() as s:
        sem_atualizar = await _cria_usuario_comum(
            s, t.id, unidade_id=cen["unidade_id"], action_atualizar=False,
        )
        await s.commit()

    async with _client_como(cen, admin_engine, user_id=sem_atualizar) as client:
        r = await client.put(
            f"/api/v2/processos/{cen['processo1_id']}/marcadores",
            json={"ids_marcador": [cen["marcador1_id"]]},
        )
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_http_usuario_comum_com_permissao_define_marcadores(admin_engine, cen):
    async with _client_como(cen, admin_engine, user_id=cen["operador"]) as client:
        r = await client.put(
            f"/api/v2/processos/{cen['processo1_id']}/marcadores",
            json={"ids_marcador": [cen["marcador1_id"]]},
        )
        assert r.status_code == 200, r.text
        nomes = [mk["nome"] for mk in r.json()["marcadores"]]
        assert nomes == ["Urgente"]


@pytest.mark.asyncio
async def test_http_processo_inexistente_e_404_via_acesso_processo(admin_engine, cen):
    """`require_acesso_processo` roda antes do service — id que não existe
    (ou de outro tenant) não vaza pela rota de favorito, dá 404."""
    async with _client_como(cen, admin_engine, user_id=cen["operador"]) as client:
        r = await client.put("/api/v2/processos/999999999/favorito")
        assert r.status_code == 404, r.text
