"""Manifestante — cadastro com tipo físico/jurídico e campos obrigatórios.

- O tipo de manifestante diz se é pessoa física ou jurídica (`natureza`,
  migration 0136); o documento tem de ter 11 dígitos (CPF) ou 14 (CNPJ)
  conforme o tipo escolhido.
- Nome, CPF/CNPJ, celular e e-mail são obrigatórios no cadastro. Na edição,
  campo ausente fica como está, mas obrigatório não pode ser esvaziado.
- Telefone é gravado só com dígitos (como o CPF); e-mail, aparado e em minúsculas.
- O tipo é FK "soft" quanto ao tenant: tipo de outra prefeitura dá 404.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import admin_id_do_tenant, as_user_dependency, provisionar_tenant_de_teste

URL = "/api/v2/manifestantes"


async def _cliente(admin_engine):
    t = await provisionar_tenant_de_teste(admin_engine, "manifcad")
    su = await admin_id_do_tenant(admin_engine, t.id)
    as_user_dependency(admin_engine, su, t.id, t.slug)()
    return t


async def _fechar():
    app.dependency_overrides.clear()
    from app.database import engine

    await engine.dispose()


async def _tipos(c: AsyncClient) -> dict[str, int]:
    return {t["natureza"]: t["id"] for t in (await c.get("/api/v2/tipos-manifestante")).json()}


def _payload(tipo: int, **campos) -> dict:
    return {
        "id_tipo_manifestante": tipo,
        "nome": "Maria Cadastro",
        "cpf_cnpj": "123.456.789-09",
        "telefone_celular": "(85) 99999-8888",
        "email": "maria@manifcad.test",
        **campos,
    }


@pytest.mark.asyncio
async def test_tenant_novo_nasce_com_tipo_fisico_e_juridico(admin_engine):
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tipos = (await c.get("/api/v2/tipos-manifestante")).json()
        assert {(t["tipo_manifestante"], t["natureza"]) for t in tipos} == {
            ("Pessoa Física", "F"),
            ("Pessoa Jurídica", "J"),
        }
    finally:
        await _fechar()


@pytest.mark.asyncio
@pytest.mark.parametrize("campo", ["nome", "cpf_cnpj", "telefone_celular"])
@pytest.mark.parametrize("valor", ["ausente", None, "", "   "])
async def test_obrigatorios_do_cadastro(admin_engine, campo, valor):
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            body = _payload((await _tipos(c))["F"])
            if valor == "ausente":
                del body[campo]
            else:
                body[campo] = valor
            r = await c.post(URL, json=body)
        assert r.status_code == 422, r.text
        assert any(e["loc"][-1] == campo for e in r.json()["detail"]), r.text
    finally:
        await _fechar()


@pytest.mark.asyncio
@pytest.mark.parametrize("natureza,doc,ok", [
    ("F", "123.456.789-09", True),
    ("F", "12.345.678/0001-90", False),
    ("F", "1234567890", False),
    ("J", "12.345.678/0001-90", True),
    ("J", "123.456.789-09", False),
    # CNPJ alfanumérico (IN RFB 2.229/2024): letra só nas 12 primeiras posições
    ("J", "12.ABC.345/01DE-35", True),
    ("J", "12.abc.345/01de-35", True),
    ("J", "12.ABC.345/01DE-3X", False),
    ("F", "123.ABC.789-09", False),
])
async def test_documento_segue_a_natureza_do_tipo(admin_engine, natureza, doc, ok):
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(URL, json=_payload((await _tipos(c))[natureza], cpf_cnpj=doc))
        if ok:
            assert r.status_code == 201, r.text
        else:
            assert r.status_code == 422, r.text
            assert ("CNPJ" if natureza == "J" else "CPF") in r.json()["detail"]
    finally:
        await _fechar()


@pytest.mark.asyncio
@pytest.mark.parametrize("valor", ["ausente", None, "", "   "])
async def test_email_e_opcional(admin_engine, valor):
    """E-mail opcional (decisão de 2026-11-04): ausente ou vazio grava `None`;
    na edição, dá para apagá-lo."""
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            body = _payload((await _tipos(c))["F"])
            if valor == "ausente":
                del body["email"]
            else:
                body["email"] = valor
            r = await c.post(URL, json=body)
            apaga = await c.put(f"{URL}/{r.json()['id']}", json={"email": ""})
        assert r.status_code == 201, r.text
        assert r.json()["email"] is None
        assert apaga.status_code == 200 and apaga.json()["email"] is None
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_telefone_gravado_so_com_digitos_e_email_normalizado(admin_engine):
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(URL, json=_payload(
                (await _tipos(c))["F"],
                telefone_celular="85999998888",
                telefone_residencial="8533334444",
                telefone_comercial="",
                email="  Maria@ManifCad.TEST ",
            ))
        assert r.status_code == 201, r.text
        m = r.json()
        assert m["telefone_celular"] == "85999998888"
        assert m["telefone_residencial"] == "8533334444"
        assert m["telefone_comercial"] is None
        assert m["email"] == "maria@manifcad.test"
    finally:
        await _fechar()


@pytest.mark.parametrize("gravado,exibido", [
    ("85999998888", "(85) 99999-8888"),
    ("8533334444", "(85) 3333-4444"),
    # cadastro anterior à regra, gravado como foi digitado: volta como está
    ("(85) 9999-8888 ramal 2", "(85) 9999-8888 ramal 2"),
    (None, ""),
])
def test_telefone_para_exibir(gravado, exibido):
    from app.schemas.manifestante import telefone_para_exibir

    assert telefone_para_exibir(gravado) == exibido


@pytest.mark.asyncio
@pytest.mark.parametrize("campo,valor", [
    ("telefone_celular", "9999-8888"),
    ("telefone_residencial", "123"),
    ("email", "maria@sem-ponto"),
    ("email", "maria.manifcad.test"),
])
async def test_formato_invalido_e_recusado(admin_engine, campo, valor):
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(URL, json=_payload((await _tipos(c))["F"], **{campo: valor}))
        assert r.status_code == 422, r.text
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_tipo_de_outra_prefeitura_da_404(admin_engine):
    outro = await provisionar_tenant_de_teste(admin_engine, "manifout")
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

            sm = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
            async with sm() as s:
                tipo_alheio = (await s.execute(text(
                    "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t AND natureza='F'"
                ), {"t": outro.id})).scalar_one()
            r = await c.post(URL, json=_payload(tipo_alheio))
        assert r.status_code == 404, r.text
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_edicao_parcial_nao_esvazia_obrigatorio(admin_engine):
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            m = (await c.post(URL, json=_payload((await _tipos(c))["F"]))).json()
            so_obs = await c.put(f"{URL}/{m['id']}", json={"observacao": "ok"})
            esvazia = await c.put(f"{URL}/{m['id']}", json={"telefone_celular": ""})
            limpa_opcional = await c.put(f"{URL}/{m['id']}", json={"telefone_comercial": ""})
        assert so_obs.status_code == 200, so_obs.text
        assert esvazia.status_code == 422, esvazia.text
        assert limpa_opcional.status_code == 200, limpa_opcional.text
        assert limpa_opcional.json()["telefone_celular"] == "85999998888"
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_trocar_tipo_confere_documento_ja_gravado(admin_engine):
    """Trocar para jurídica mantendo o CPF gravado é recusado; trocar tipo e
    documento juntos passa."""
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tipos = await _tipos(c)
            m = (await c.post(URL, json=_payload(tipos["F"]))).json()
            so_tipo = await c.put(f"{URL}/{m['id']}", json={"id_tipo_manifestante": tipos["J"]})
            os_dois = await c.put(f"{URL}/{m['id']}", json={
                "id_tipo_manifestante": tipos["J"], "cpf_cnpj": "12.345.678/0001-90"})
        assert so_tipo.status_code == 422, so_tipo.text
        assert os_dois.status_code == 200, os_dois.text
        assert os_dois.json()["cpf_cnpj"] == "12345678000190"
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_cadastro_antigo_sem_celular_continua_legivel(admin_engine):
    """A obrigatoriedade é do cadastro, não da leitura: linha antiga sem
    celular e sem e-mail continua listada."""
    t = await _cliente(admin_engine)
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        sm = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
        async with sm() as s:
            await s.execute(text(
                "INSERT INTO protocolos.manifestante (tenant_id, id_tipo_manifestante, nome, ativo, excluido) "
                "SELECT :t, id, 'Antigo Sem Celular', true, false FROM protocolos.tipo_manifestante "
                "WHERE tenant_id=:t AND natureza='F'"), {"t": t.id})
            await s.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(URL, params={"q": "Antigo Sem Celular"})
        assert r.status_code == 200, r.text
        assert [m["nome"] for m in r.json()["items"]] == ["Antigo Sem Celular"]
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_natureza_do_tipo_e_editavel(admin_engine):
    await _cliente(admin_engine)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            novo = await c.post("/api/v2/tipos-manifestante", json={
                "tipo_manifestante": "Empresa", "id_categoria": 1, "natureza": "J"})
            invalido = await c.post("/api/v2/tipos-manifestante", json={
                "tipo_manifestante": "X", "id_categoria": 1, "natureza": "Q"})
            muda = await c.put(f"/api/v2/tipos-manifestante/{novo.json()['id']}", json={"natureza": "F"})
        assert novo.status_code == 201 and novo.json()["natureza"] == "J", novo.text
        assert invalido.status_code == 422
        assert muda.status_code == 200 and muda.json()["natureza"] == "F"
    finally:
        await _fechar()
