"""Assunto hierárquico — id_assunto_pai/nivel/codigo (E2, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md` §5 E2.

Escopo desta fatia é só a hierarquia LOCAL (autoreferente, por tenant) —
decidido em 2026-09-18 depois que a "herança por referência" da resposta a
Q2 se mostrou exigir uma tabela de catálogo global que ninguém escopou ainda
(quem administra, qual conteúdo inicial). Ver docstring da migration 0118.

`nivel` nunca é digitada — sempre calculada a partir do pai (raiz = 1). Um
assunto não pode virar pai de si mesmo nem de um dos seus próprios
descendentes (ciclo).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.main import app
from app.models import TipoProcesso, Usuario
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine) -> tuple[int, str, int, int]:
    """Devolve (tenant_id, tenant_slug, su_id, id_tipo_processo)."""
    slug = _slug("e2-")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref E2", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    async with _sm(engine)() as s:
        su_id = (await s.execute(
            text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant.id},
        )).scalar_one()
        tp = TipoProcesso(
            tenant_id=tenant.id, tipo_processo="Geral E2",
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(tp)
        await s.commit()
        await s.refresh(tp)
    return tenant.id, tenant.slug, su_id, tp.id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
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

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, tenant_slug)


@pytest.mark.asyncio
async def test_criar_raiz_e_filhos_calcula_nivel(admin_engine):
    tenant_id, slug, su_id, tp_id = await _provisionar(admin_engine)
    try:
        _as_user(admin_engine, su_id, tenant_id, slug)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            host = {"Host": f"{slug}.aprimora.local"}
            r_raiz = await client.post(
                "/api/v2/assuntos",
                json={"assunto": "Aquisição", "id_tipo_processo": tp_id},
                headers=host,
            )
            assert r_raiz.status_code == 201, r_raiz.text
            raiz = r_raiz.json()
            assert raiz["nivel"] == 1
            assert raiz["id_assunto_pai"] is None

            r_filho = await client.post(
                "/api/v2/assuntos",
                json={
                    "assunto": "Equipamentos e material permanente",
                    "id_tipo_processo": tp_id,
                    "id_assunto_pai": raiz["id"],
                },
                headers=host,
            )
            assert r_filho.status_code == 201, r_filho.text
            filho = r_filho.json()
            assert filho["nivel"] == 2

            r_neto = await client.post(
                "/api/v2/assuntos",
                json={
                    "assunto": "Aeronaves",
                    "id_tipo_processo": tp_id,
                    "id_assunto_pai": filho["id"],
                    "codigo": "01.01.01",
                },
                headers=host,
            )
            assert r_neto.status_code == 201, r_neto.text
            neto = r_neto.json()
            assert neto["nivel"] == 3
            assert neto["codigo"] == "01.01.01"
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant_id)


@pytest.mark.asyncio
async def test_pai_de_outro_tenant_e_404(admin_engine):
    tenant_a, slug_a, su_a, tp_a = await _provisionar(admin_engine)
    tenant_b, slug_b, su_b, tp_b = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            from app.models import Assunto
            alheio = Assunto(
                tenant_id=tenant_b, assunto="Do outro tenant", id_tipo_processo=tp_b,
                exige_processo_pai=False, ativo=True, excluido=False, nivel=1,
            )
            s.add(alheio)
            await s.commit()
            await s.refresh(alheio)

        _as_user(admin_engine, su_a, tenant_a, slug_a)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v2/assuntos",
                json={
                    "assunto": "Tentativa cross-tenant", "id_tipo_processo": tp_a,
                    "id_assunto_pai": alheio.id,
                },
                headers={"Host": f"{slug_a}.aprimora.local"},
            )
        assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant_a)
        await _cleanup(admin_engine, tenant_b)


@pytest.mark.asyncio
async def test_atualizar_pai_recalcula_nivel_e_recusa_ciclo(admin_engine):
    tenant_id, slug, su_id, tp_id = await _provisionar(admin_engine)
    try:
        _as_user(admin_engine, su_id, tenant_id, slug)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            host = {"Host": f"{slug}.aprimora.local"}
            raiz = (await client.post(
                "/api/v2/assuntos",
                json={"assunto": "Raiz", "id_tipo_processo": tp_id},
                headers=host,
            )).json()
            filho = (await client.post(
                "/api/v2/assuntos",
                json={
                    "assunto": "Filho", "id_tipo_processo": tp_id,
                    "id_assunto_pai": raiz["id"],
                },
                headers=host,
            )).json()
            outra_raiz = (await client.post(
                "/api/v2/assuntos",
                json={"assunto": "Outra raiz", "id_tipo_processo": tp_id},
                headers=host,
            )).json()

            # Move "Filho" para debaixo de "Outra raiz" — nivel recalcula.
            r_move = await client.put(
                f"/api/v2/assuntos/{filho['id']}",
                json={"id_assunto_pai": outra_raiz["id"]},
                headers=host,
            )
            assert r_move.status_code == 200, r_move.text
            assert r_move.json()["nivel"] == 2

            # "Raiz" virar pai de "Filho" agora seria ciclo: Filho é pai de
            # Raiz? Não — tentamos o inverso real: Raiz vira filho de Filho,
            # e depois tentar Filho como pai de Raiz outra vez fecharia o
            # laço. Testamos o caso direto: um nó não pode ser pai de si.
            r_self = await client.put(
                f"/api/v2/assuntos/{filho['id']}",
                json={"id_assunto_pai": filho["id"]},
                headers=host,
            )
            assert r_self.status_code == 400, r_self.text

            # Ciclo de verdade: Raiz vira filho de Filho, então Filho não
            # pode voltar a ser filho de Raiz.
            r_raiz_sob_filho = await client.put(
                f"/api/v2/assuntos/{raiz['id']}",
                json={"id_assunto_pai": filho["id"]},
                headers=host,
            )
            assert r_raiz_sob_filho.status_code == 200, r_raiz_sob_filho.text

            r_ciclo = await client.put(
                f"/api/v2/assuntos/{filho['id']}",
                json={"id_assunto_pai": raiz["id"]},
                headers=host,
            )
            assert r_ciclo.status_code == 400, r_ciclo.text
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant_id)


@pytest.mark.asyncio
async def test_listar_filtra_por_ramo_e_por_raiz(admin_engine):
    tenant_id, slug, su_id, tp_id = await _provisionar(admin_engine)
    try:
        _as_user(admin_engine, su_id, tenant_id, slug)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            host = {"Host": f"{slug}.aprimora.local"}
            raiz_a = (await client.post(
                "/api/v2/assuntos",
                json={"assunto": "Ramo A", "id_tipo_processo": tp_id},
                headers=host,
            )).json()
            raiz_b = (await client.post(
                "/api/v2/assuntos",
                json={"assunto": "Ramo B", "id_tipo_processo": tp_id},
                headers=host,
            )).json()
            await client.post(
                "/api/v2/assuntos",
                json={
                    "assunto": "Filho de A", "id_tipo_processo": tp_id,
                    "id_assunto_pai": raiz_a["id"],
                },
                headers=host,
            )

            r_raizes = await client.get(
                "/api/v2/assuntos", params={"apenas_raiz": True}, headers=host,
            )
            nomes_raiz = {i["assunto"] for i in r_raizes.json()["items"]}
            assert nomes_raiz == {"Ramo A", "Ramo B"}

            r_filhos_a = await client.get(
                "/api/v2/assuntos", params={"id_assunto_pai": raiz_a["id"]}, headers=host,
            )
            nomes_filhos = {i["assunto"] for i in r_filhos_a.json()["items"]}
            assert nomes_filhos == {"Filho de A"}
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()
        await _cleanup(admin_engine, tenant_id)
