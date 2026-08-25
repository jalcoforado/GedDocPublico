"""Pagamentos Onda C2 — fatia C2.3: realm M2M (sistema integrado + API key).

Cobre `auth/sistema_integrado.py` (autenticação por `X-Api-Key`) e as rotas de
gestão em `routers/pagamentos_cadastros.py` (`sistemas_integrados_router`).

Reaproveita `_provisionar`/`_novo_usuario`/`_sm` de `test_pagamentos_autorizacao`
e `_usuario_com`/`_http` de `test_pagamentos_c2_contabil` pelo mesmo motivo dos
dois: montar esse harness do zero é ~150 linhas que já existem, e uma segunda
cópia divergiria do rito real.

O que cada teste procura, e por que não é o óbvio:

- **(a)** o segredo só existe UMA vez, no corpo do POST — a listagem não pode
  carregar `chave`/`hash_chave` nem por acidente (schema errado no endpoint
  de listagem vazaria bcrypt hash, que é "só" mais difícil de quebrar, não
  impossível).
- **(b)** chave válida resolve o objeto certo — chama a dependência
  DIRETAMENTE (sem passar por um router de negócio M2M, que esta fatia não
  cria) para provar tenant/escopos, sem acoplar o teste a uma rota que ainda
  não existe.
- **(c)** três formas de "inválida" — prefixo desconhecido, segredo errado
  pro prefixo certo, e chave revogada — são caminhos de código DIFERENTES
  (`scalar_one_or_none() is None`, `_verify_bcrypt` falso, `revogado_em is
  not None`) e uma prova só não cobre as outras duas.
- **(d)** a chave de um tenant não autentica em nome de outro só porque o
  host resolveu esse outro tenant — é o guard explícito da dependência, não
  a RLS (que hoje é inerte por F-12; ver docstring da migration 0102).
- **(e)** a mensagem de acesso (`RequestLoggingMiddleware`) não loga headers
  nenhum, então prova por inspeção de TODOS os campos do record — não é
  redação seletiva, é ausência total, e o teste precisa provar isso em vez
  de supor.
"""
from __future__ import annotations

import logging
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from sqlalchemy import text

from app.auth.sistema_integrado import get_current_sistema_integrado
from app.config import get_settings
from app.main import app
from app.schemas.pagamentos import SistemaIntegradoCreate
from app.services import pagamentos_sistemas as svc
from tests.test_pagamentos_autorizacao import _provisionar, _sm
from tests.test_pagamentos_c2_contabil import _http, _usuario_com

APP = get_settings().app_name


async def _usuario_gestor(engine, tenant_id: int) -> int:
    """Como `_usuario_com`, mas concede `atualizar` além de `inserir` — a
    revogação de chave usa `require_permission("pagamento_cadastro",
    "atualizar")`, e `_usuario_com` (importado de `test_pagamentos_c2_contabil`)
    só concede `inserir`, porque C2.1 nunca precisou de atualizar."""
    async with _sm(engine)() as s:
        sistema_id = int((await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app=:a AND excluido=false LIMIT 1"
        ), {"a": APP})).scalar_one())
        nivel_id = (await s.execute(text(
            "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
        ))).scalar_one_or_none()
        if nivel_id is None:
            nivel_id = (await s.execute(text(
                "INSERT INTO utils.nivel (nivel, valor, excluido) "
                "VALUES ('Operacional', 1, false) RETURNING id"))).scalar_one()
        uid = int((await s.execute(text("""
            INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                       excluido, app, nivel_acesso_sigilo)
            VALUES (:t, 'Gestor C2.3', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id"""), {"t": tenant_id, "e": f"c23-{uuid.uuid4().hex[:8]}@exp.test",
                               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one())
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, :g, false) RETURNING id"""),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id,
             "g": f"Gestor Sistemas {uuid.uuid4().hex[:6]}"})).scalar_one())
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :a)"""),
            {"t": tenant_id, "u": uid, "g": gid, "a": APP})
        tr = (await s.execute(text(
            "SELECT id FROM utils.transacao WHERE codigo=:c AND excluido=false LIMIT 1"
        ), {"c": "pagamento_cadastro"})).scalar_one()
        await s.execute(text("""
            INSERT INTO utils.grupo_transacao
                (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
            VALUES (:t, :g, :tr, true, true, false, false)"""),
            {"t": tenant_id, "g": gid, "tr": int(tr)})
        await s.commit()
    return uid


async def _cleanup(engine, tenant_id: int) -> None:
    from sqlalchemy import text

    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.idempotencia WHERE tenant_id=:t",
            "DELETE FROM pagamentos.sistema_integrado WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()
    from tests.test_pagamentos_autorizacao import _cleanup as _cleanup_aut

    await _cleanup_aut(engine, tenant_id)


def _fake_request(*, api_key: str | None, tenant_id: int | None) -> Request:
    headers = []
    if api_key is not None:
        headers.append((b"x-api-key", api_key.encode()))
    scope = {
        "type": "http",
        "headers": headers,
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 0),
    }
    request = Request(scope)
    request.state.tenant_id = tenant_id
    return request


async def _resolver(engine, *, api_key: str | None, tenant_id: int | None = None):
    """Chama a dependência diretamente, com uma sessão do `admin_engine` de
    teste — de propósito NÃO usa `app.database.SessionLocal`/engine da app:
    aquele engine é compartilhado com `_http` (que o `dispose()` a cada
    chamada, ver `test_pagamentos_c2_contabil.py::_http`), e misturar os dois
    dentro do mesmo teste — cada um com seu próprio event loop por função do
    pytest-asyncio — produz `RuntimeError: ... attached to a different loop`.
    `admin_engine` é a mesma conexão que todo o resto desta suíte usa para
    chamar serviço diretamente (sem HTTP), e não é tocado por `_http`."""
    request = _fake_request(api_key=api_key, tenant_id=tenant_id)
    async with _sm(engine)() as db:
        return await get_current_sistema_integrado(request, db)


async def _criar_sistema_direto(engine, tenant_id: int, *, usuario_id: int, **kw) -> tuple[object, str]:
    async with _sm(engine)() as s:
        return await svc.criar_sistema(
            s, tenant_id=tenant_id, payload=SistemaIntegradoCreate(nome="Sistema Externo", **kw),
            usuario_id=usuario_id)


# ---------------------------------------------------------------- (a) HTTP

@pytest.mark.asyncio
async def test_a_criar_devolve_chave_uma_vez_lista_nao_expoe_segredo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])

        r = await _http(admin_engine, t.id, t.slug, uid, "POST",
                        "/api/v2/pagamentos/sistemas-integrados",
                        json={"nome": "ERP Financeiro"})
        assert r.status_code == 201, r.text[:300]
        body = r.json()
        assert body["chave"].startswith("apy_")
        prefixo, _, segredo = body["chave"].partition(".")
        assert prefixo == body["prefixo"]
        assert segredo  # segredo não-vazio

        r2 = await _http(admin_engine, t.id, t.slug, uid, "GET",
                         "/api/v2/pagamentos/sistemas-integrados")
        assert r2.status_code == 200
        itens = r2.json()
        assert any(i["id"] == body["id"] for i in itens)
        for item in itens:
            assert "chave" not in item
            assert "hash_chave" not in item
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (b)

@pytest.mark.asyncio
async def test_b_chave_valida_resolve_tenant_e_escopos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)

        resolvido = await _resolver(admin_engine, api_key=chave)
        assert resolvido.id == sistema.id
        assert resolvido.tenant_id == t.id
        assert resolvido.escopo_leitura is True
        assert resolvido.escopo_escrita is True
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (c)

@pytest.mark.asyncio
async def test_c_prefixo_desconhecido_401(admin_engine):
    with pytest.raises(Exception) as exc:
        await _resolver(admin_engine, api_key=f"apy_{uuid.uuid4().hex[:8]}.segredo-qualquer")
    assert getattr(exc.value, "status_code", None) == 401


@pytest.mark.asyncio
async def test_c_segredo_errado_401(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(admin_engine, t.id, usuario_id=uid)
        prefixo = chave.split(".", 1)[0]

        with pytest.raises(Exception) as exc:
            await _resolver(admin_engine, api_key=f"{prefixo}.segredo-errado")
        assert getattr(exc.value, "status_code", None) == 401
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_c_chave_revogada_401(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_gestor(admin_engine, t.id)
        sistema, chave = await _criar_sistema_direto(admin_engine, t.id, usuario_id=uid)

        # A chave funciona antes da revogação.
        assert (await _resolver(admin_engine, api_key=chave)).id == sistema.id

        r = await _http(admin_engine, t.id, t.slug, uid, "POST",
                        f"/api/v2/pagamentos/sistemas-integrados/{sistema.id}/revogar")
        assert r.status_code == 200
        assert r.json()["revogado_em"] is not None
        assert r.json()["ativo"] is False

        with pytest.raises(Exception) as exc:
            await _resolver(admin_engine, api_key=chave)
        assert getattr(exc.value, "status_code", None) == 401
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_c_sem_header_ou_mal_formado_401(admin_engine):
    for chave_ruim in (None, "sem-ponto", "apy_abc.", ".segredo"):
        with pytest.raises(Exception) as exc:
            await _resolver(admin_engine, api_key=chave_ruim)
        assert getattr(exc.value, "status_code", None) == 401, chave_ruim


# ---------------------------------------------------------------- (d)

@pytest.mark.asyncio
async def test_d_chave_do_tenant_a_nao_autentica_como_tenant_b(admin_engine, two_tenants):
    tid_a, tid_b = two_tenants
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(admin_engine, t.id, usuario_id=uid)

        # Host resolveu um tenant DIFERENTE do dono da chave -> 401, não 200
        # "autenticado como o tenant errado".
        with pytest.raises(Exception) as exc:
            await _resolver(admin_engine, api_key=chave, tenant_id=tid_a if tid_a != t.id else tid_b)
        assert getattr(exc.value, "status_code", None) == 401

        # Sem tenant resolvido pelo host, a chave manda -- e é o tenant certo.
        resolvido = await _resolver(admin_engine, api_key=chave, tenant_id=None)
        assert resolvido.tenant_id == t.id

        # Host resolvendo o MESMO tenant da chave funciona normalmente.
        resolvido2 = await _resolver(admin_engine, api_key=chave, tenant_id=t.id)
        assert resolvido2.tenant_id == t.id
    finally:
        await _cleanup(admin_engine, t.id)


# ---------------------------------------------------------------- (e)

@pytest.mark.asyncio
async def test_e_log_de_acesso_nao_expoe_segredo_da_api_key(admin_engine, caplog):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(admin_engine, t.id, usuario_id=uid)
        segredo = chave.split(".", 1)[1]

        with caplog.at_level(logging.INFO, logger="aprimora.access"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/api/v2/health", headers={"X-Api-Key": chave})
        assert resp.status_code == 200

        registros_access = [r for r in caplog.records if r.name == "aprimora.access"]
        assert registros_access, "esperava ao menos 1 linha de log de acesso"
        for record in registros_access:
            partes = [record.getMessage()]
            for k, v in record.__dict__.items():
                if k not in ("msg", "args"):
                    partes.append(str(v))
            texto = " ".join(partes)
            assert segredo not in texto, f"segredo vazou no log: {texto!r}"
            assert chave not in texto, f"chave completa vazou no log: {texto!r}"
    finally:
        await _cleanup(admin_engine, t.id)
