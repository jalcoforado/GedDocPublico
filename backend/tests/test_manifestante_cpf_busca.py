"""Manifestante — CPF/CNPJ só com dígitos e busca que aceita máscara.

Dois defeitos vistos em homologação (2026-09-28):
- cadastrar manifestante com CNPJ digitado com máscara (`12.345.678/0001-90`,
  18 caracteres) dava 422 contra `max_length=14`; CPF com máscara passava por
  caber em 14, mas era gravado com pontos e traço;
- gravado com máscara, o manifestante nunca era ligado ao cidadão no portal,
  que compara `Manifestante.cpf_cnpj == cidadao.cpf_cnpj` e guarda o CPF do
  cidadão só com dígitos.

Agora a entrada é normalizada no schema e a busca digitada com máscara
procura pelos dígitos.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.main import app
from tests.conftest import admin_id_do_tenant, as_user_dependency, provisionar_tenant_de_teste


async def _cliente(admin_engine):
    t = await provisionar_tenant_de_teste(admin_engine, "manif")
    su = await admin_id_do_tenant(admin_engine, t.id)
    as_user_dependency(admin_engine, su, t.id, t.slug)()
    return t


async def _fechar():
    app.dependency_overrides.clear()
    from app.database import engine

    await engine.dispose()


async def _tipo(c: AsyncClient) -> int:
    return (await c.get("/api/v2/tipos-manifestante")).json()[0]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("digitado,gravado", [
    ("12.345.678/0001-90", "12345678000190"),
    ("123.456.789-09", "12345678909"),
    (" 123 456 789 09 ", "12345678909"),
    ("12345678909", "12345678909"),
    ("", None),
    (None, None),
])
async def test_cadastro_grava_cpf_cnpj_so_com_digitos(admin_engine, digitado, gravado):
    t = await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v2/manifestantes", json={
                "id_tipo_manifestante": await _tipo(c), "nome": "Fulano", "cpf_cnpj": digitado})
        assert r.status_code == 201, r.text
        assert r.json()["cpf_cnpj"] == gravado
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_cpf_cnpj_com_mais_de_14_digitos_e_recusado(admin_engine):
    t = await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/api/v2/manifestantes", json={
                "id_tipo_manifestante": await _tipo(c), "nome": "X", "cpf_cnpj": "1" * 15})
        assert r.status_code == 422
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_edicao_tambem_normaliza(admin_engine):
    t = await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            m = (await c.post("/api/v2/manifestantes", json={
                "id_tipo_manifestante": await _tipo(c), "nome": "Y"})).json()
            r = await c.put(f"/api/v2/manifestantes/{m['id']}", json={"cpf_cnpj": "12.345.678/0001-90"})
        assert r.status_code == 200, r.text
        assert r.json()["cpf_cnpj"] == "12345678000190"
    finally:
        await _fechar()


@pytest.mark.asyncio
@pytest.mark.parametrize("busca", ["123.456.789-09", "123.456", "12345678909", "789-09"])
async def test_busca_com_mascara_encontra_cadastro_so_com_digitos(admin_engine, busca):
    t = await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v2/manifestantes", json={
                "id_tipo_manifestante": await _tipo(c), "nome": "Maria Busca", "cpf_cnpj": "12345678909"})
            r = await c.get("/api/v2/manifestantes", params={"q": busca, "page_size": 20})
        assert r.status_code == 200, r.text
        assert [m["nome"] for m in r.json()["items"]] == ["Maria Busca"]
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_busca_por_nome_continua_funcionando(admin_engine):
    t = await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v2/manifestantes", json={
                "id_tipo_manifestante": await _tipo(c), "nome": "Joana Nome Unico"})
            r = await c.get("/api/v2/manifestantes", params={"q": "nome unico"})
        assert [m["nome"] for m in r.json()["items"]] == ["Joana Nome Unico"]
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_migration_0125_tira_mascara_do_que_ja_estava_gravado(admin_engine):
    """Dados gravados antes da correção: a 0125 normaliza. O teste reaplica o
    SQL dela sobre linhas no formato antigo (a migration já rodou neste banco)."""
    t = await provisionar_tenant_de_teste(admin_engine, "manifmig")
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    sm = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
    async with sm() as s:
        tipo = (await s.execute(text(
            "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"), {"t": t.id})).scalar_one()
        for doc in ("123.456.789-09", "987.654.321-00", "", "11122233344"):
            await s.execute(text(
                "INSERT INTO protocolos.manifestante (tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                "VALUES (:t, :tp, :n, :d, true, false)"), {"t": t.id, "tp": tipo, "n": f"M {uuid.uuid4().hex[:4]}", "d": doc})
        await s.commit()
    async with sm() as s:
        await s.execute(text(SQL_0125))
        await s.commit()
        docs = sorted((await s.execute(text(
            "SELECT coalesce(cpf_cnpj, 'NULL') FROM protocolos.manifestante WHERE tenant_id=:t"), {"t": t.id})).scalars())
    assert docs == sorted(["12345678909", "98765432100", "NULL", "11122233344"])


def _sql_da_migration() -> str:
    """Importa a constante da própria migration — o teste exercita o SQL real."""
    import importlib.util
    import pathlib

    arq = next(pathlib.Path(__file__).resolve().parents[1].glob("alembic/versions/0125_*.py"))
    spec = importlib.util.spec_from_file_location("migration_0125", arq)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SQL_NORMALIZA


try:
    SQL_0125 = _sql_da_migration()
except StopIteration:  # migration ainda não existe: o teste da 0125 reprova
    SQL_0125 = "SELECT 1"


@pytest.mark.asyncio
async def test_busca_global_acha_manifestante_por_cpf_com_mascara(admin_engine):
    """Ctrl+K (`/busca`): o CPF digitado com máscara encontra o cadastro gravado
    só com dígitos."""
    t = await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v2/manifestantes", json={
                "id_tipo_manifestante": await _tipo(c), "nome": "Global Busca", "cpf_cnpj": "12345678909"})
            r = await c.get("/api/v2/busca", params={"q": "123.456.789-09"})
        assert r.status_code == 200, r.text
        assert [m["nome"] for m in r.json()["manifestantes"]] == ["Global Busca"]
    finally:
        await _fechar()
