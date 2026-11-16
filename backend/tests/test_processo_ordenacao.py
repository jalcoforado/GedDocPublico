"""SI-19 — a listagem de processos ordena pela coluna escolhida na tela.

A lista é paginada no servidor, então a ordenação também tem de ser: ordenar
só os 20 da página na tela daria uma ordem que muda ao trocar de página.
`ordenar` é uma lista fechada porque vira ORDER BY.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models import Assunto, Manifestante, TipoProcesso
from tests.conftest import admin_id_do_tenant, as_user_dependency, provisionar_tenant_de_teste

URL = "/api/v2/processos"


async def _cenario(admin_engine) -> dict:
    t = await provisionar_tenant_de_teste(admin_engine, "ordena")
    sm = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with sm() as s:
        unidade = (await s.execute(text(
            "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
        tipo_manif = (await s.execute(text(
            "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t ORDER BY id LIMIT 1"),
            {"t": t.id})).scalar_one()
        tp = TipoProcesso(tenant_id=t.id, tipo_processo="Geral", exige_processo_pai=False,
                          ativo=True, excluido=False)
        s.add(tp)
        await s.flush()
        assunto = Assunto(tenant_id=t.id, assunto="Pedido", id_tipo_processo=tp.id,
                          exige_processo_pai=False, ativo=True, excluido=False)
        manifs = [
            Manifestante(tenant_id=t.id, id_tipo_manifestante=tipo_manif, nome=nome,
                         ativo=True, excluido=False)
            for nome in ("Carlos", "Ana", "Bruno")
        ]
        s.add_all([assunto, *manifs])
        await s.commit()
    as_user_dependency(admin_engine, await admin_id_do_tenant(admin_engine, t.id), t.id, t.slug)()
    return {"unidade": unidade, "assunto": assunto.id, "manifs": [m.id for m in manifs]}


async def _fechar():
    app.dependency_overrides.clear()
    from app.database import engine

    await engine.dispose()


@pytest.mark.asyncio
async def test_ordena_por_coluna_nos_dois_sentidos(admin_engine):
    cen = await _cenario(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            for id_manif in cen["manifs"]:
                r = await c.post(URL, json={
                    "id_assunto": cen["assunto"], "id_manifestante": id_manif,
                    "id_unidade_proprietaria": cen["unidade"],
                })
                assert r.status_code == 201, r.text
            asc = await c.get(URL, params={"ordenar": "manifestante", "direcao": "asc"})
            desc = await c.get(URL, params={"ordenar": "manifestante", "direcao": "desc"})
            invalido = await c.get(URL, params={"ordenar": "senha; drop table"})
        assert [p["manifestante"] for p in asc.json()["items"]] == ["Ana", "Bruno", "Carlos"]
        assert [p["manifestante"] for p in desc.json()["items"]] == ["Carlos", "Bruno", "Ana"]
        # Fora da lista fechada não chega ao SQL.
        assert invalido.status_code == 422
    finally:
        await _fechar()
