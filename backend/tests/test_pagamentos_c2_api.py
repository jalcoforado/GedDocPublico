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
from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.sistema_integrado import get_current_sistema_integrado, get_db_m2m
from app.config import get_settings
from app.main import app
from app.models import SistemaIntegrado
from app.schemas.pagamentos import SistemaIntegradoCreate
from app.services import modulos as modulos_svc
from app.services import pagamentos_sistemas as svc
from tests.conftest import APP_URL, arreio_tenant_http
from tests.test_pagamentos_autorizacao import _base, _payload_debito, _provisionar, _sm
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

        try:
            with caplog.at_level(logging.INFO, logger="aprimora.access"):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as c:
                    resp = await c.get("/api/v2/health", headers={"X-Api-Key": chave})
            assert resp.status_code == 200
        finally:
            # Sem isto, a conexão asyncpg do engine de `app.database` fica no
            # pool presa ao event loop DESTE teste; o próximo teste roda num
            # loop novo (pytest-asyncio é function-scoped) e o
            # `pool_pre_ping` estoura "attached to a different loop" ao tentar
            # reciclar essa conexão — flake descoberto na Task 7 (bastou um
            # teste HTTP novo logo depois deste para expor).
            from app.database import engine as app_engine
            await app_engine.dispose()

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


# ============================================================================
# Task 7 — C2.3: escrita idempotente + leitura por cursor (rotas M2M reais em
# `routers/pagamentos_integracao.py`) + as 3 correções herdadas do review da
# Task 6.
# ============================================================================


async def _http_m2m(engine, tenant_id, slug, api_key, metodo, caminho, **kw):
    """Como `_http` (test_pagamentos_c2_contabil), mas autentica por
    `X-Api-Key` em vez de sobrescrever `get_current_user` — a rota M2M não usa
    `get_current_user` nenhum. `arreio_tenant_http` ainda é necessário para o
    `Host` de teste resolver o MESMO tenant do dono da chave (senão
    `get_current_sistema_integrado` vê `request.state.tenant_id` de um tenant
    default divergente e recusa com 401 — ver teste `test_d` acima)."""
    headers = {**kw.pop("headers", {}), "X-Api-Key": api_key}
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.request(metodo, caminho, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


async def _cenario_debito(engine, tenant_id):
    """Sistema com os dois escopos + fornecedor/natureza/fonte/conta/unidade
    prontos para montar um `DebitoCreate`."""
    forn, nat, fonte, conta, unidade_id = await _base(engine, tenant_id)
    return forn, nat, fonte, conta, unidade_id


def _payload_json(forn, nat, fonte, conta, unidade_id, **kw) -> dict:
    return _payload_debito(forn, nat, fonte, conta, unidade_id=unidade_id, **kw).model_dump(mode="json")


async def _contar_debitos(engine, tenant_id) -> int:
    async with _sm(engine)() as s:
        return int((await s.execute(text(
            "SELECT count(*) FROM pagamentos.debito WHERE tenant_id=:t"), {"t": tenant_id}
        )).scalar_one())


ROTA_DEBITOS = "/api/v2/integracao/pagamentos/debitos"


@pytest.mark.asyncio
async def test_t7_a_post_debito_com_chave_replay_nao_cria_segundo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)
        payload = _payload_json(forn, nat, fonte, conta, unidade_id, valor="100.00")

        antes = await _contar_debitos(admin_engine, t.id)
        r1 = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                             json=payload, headers={"Idempotency-Key": "chave-x"})
        assert r1.status_code == 201, r1.text[:300]
        body1 = r1.json()

        r2 = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                             json=payload, headers={"Idempotency-Key": "chave-x"})
        assert r2.status_code == 201, r2.text[:300]
        assert r2.json() == body1, "replay deveria devolver a MESMA resposta gravada"

        depois = await _contar_debitos(admin_engine, t.id)
        assert depois == antes + 1, "replay não pode criar um segundo débito"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_t7_b_mesma_chave_payload_diferente_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)
        p1 = _payload_json(forn, nat, fonte, conta, unidade_id, valor="100.00")
        p2 = _payload_json(forn, nat, fonte, conta, unidade_id, valor="200.00")

        r1 = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                             json=p1, headers={"Idempotency-Key": "chave-y"})
        assert r1.status_code == 201, r1.text[:300]

        r2 = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                             json=p2, headers={"Idempotency-Key": "chave-y"})
        assert r2.status_code == 409, r2.text[:300]
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_t7_c_sem_idempotency_key_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)
        payload = _payload_json(forn, nat, fonte, conta, unidade_id, valor="100.00")

        r = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS, json=payload)
        assert r.status_code == 422, r.text[:300]
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_t7_c2_idempotency_key_maior_que_64_chars_422(admin_engine):
    """FIX WAVE (Important 2): `pagamentos.idempotencia.chave` é `String(64)`
    — antes desta guarda, uma chave de 65+ chars passava pela validação do
    router e só estourava no INSERT como 500 (StringDataRightTruncation),
    em vez de um 422 claro para o integrador."""
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)
        payload = _payload_json(forn, nat, fonte, conta, unidade_id, valor="100.00")
        chave_longa = "x" * 65

        r = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                            json=payload, headers={"Idempotency-Key": chave_longa})
        assert r.status_code == 422, r.text[:300]
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_t7_d_escopo_leitura_tentando_escrever_403(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=False)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)
        payload = _payload_json(forn, nat, fonte, conta, unidade_id, valor="100.00")

        r = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                            json=payload, headers={"Idempotency-Key": "chave-d"})
        assert r.status_code == 403, r.text[:300]
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_t7_e_get_debitos_paginado_por_cursor_cobre_tudo_sem_repetir(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)

        criados_ids = []
        for i in range(5):
            payload = _payload_json(forn, nat, fonte, conta, unidade_id, valor=f"{100 + i}.00")
            r = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                                json=payload, headers={"Idempotency-Key": f"chave-lote-{i}"})
            assert r.status_code == 201, r.text[:300]
            criados_ids.append(r.json()["id"])

        vistos = []
        cursor = None
        paginas = 0
        while True:
            caminho = ROTA_DEBITOS + (f"?cursor={cursor}&limite=2" if cursor else "?limite=2")
            r = await _http_m2m(admin_engine, t.id, t.slug, chave, "GET", caminho)
            assert r.status_code == 200, r.text[:300]
            body = r.json()
            ids_pagina = [item["id"] for item in body["items"]]
            assert all(i in criados_ids for i in ids_pagina)
            vistos.extend(ids_pagina)
            paginas += 1
            assert paginas <= 10, "loop de paginação não convergiu"
            cursor = body["proximo_cursor"]
            if cursor is None:
                break

        assert sorted(vistos) == sorted(set(vistos)), "cursor repetiu algum id"
        assert set(criados_ids) <= set(vistos), "cursor pulou algum débito criado"
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_t7_f_alterado_desde_filtra(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)
        payload = _payload_json(forn, nat, fonte, conta, unidade_id, valor="100.00")
        r = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                            json=payload, headers={"Idempotency-Key": "chave-f"})
        assert r.status_code == 201, r.text[:300]
        did = r.json()["id"]

        futuro = (datetime.utcnow() + timedelta(days=1)).isoformat()
        r_futuro = await _http_m2m(admin_engine, t.id, t.slug, chave, "GET",
                                   ROTA_DEBITOS + f"?alterado_desde={futuro}")
        assert r_futuro.status_code == 200
        assert did not in [i["id"] for i in r_futuro.json()["items"]]

        passado = (datetime.utcnow() - timedelta(days=1)).isoformat()
        r_passado = await _http_m2m(admin_engine, t.id, t.slug, chave, "GET",
                                    ROTA_DEBITOS + f"?alterado_desde={passado}")
        assert r_passado.status_code == 200
        assert did in [i["id"] for i in r_passado.json()["items"]]
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_t7_g_liquidar_sem_empenho_paridade_com_realm_admin(admin_engine):
    """Paridade deliberada: a rota M2M `liquidar` espelha
    `confirmar_liquidacao` EXATAMENTE, mesma regra da rota admin
    `POST /pagamentos/debitos/{id}/confirmar-liquidacao` — nenhuma das duas
    exige número de empenho. RN-01 (empenho obrigatório) é regra de
    AUTORIZAÇÃO (`pagamentos_autorizacao.autorizar_lote`), que o M2M não
    expõe nesta fatia; inventar um check de RN-01 dentro de `liquidar` seria
    a porta M2M aplicando uma regra que a porta admin não aplica no mesmo
    ato — divergência, não paridade. Este teste prova a paridade nos DOIS
    sentidos: (1) liquidar sem empenho pela porta M2M dá 200 (não 422); (2)
    o MESMO ato, no MESMO débito tipo, pela porta admin, também dá 200 —
    então "funciona" não é um acidente da M2M, é o comportamento real que
    ela está espelhando."""
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(
            admin_engine, t.id, ["pagamento_cadastro", "pagamento_validar", "pagamento_solicitar"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)

        # (1) Porta M2M: cria sem empenho, liquida — tem que dar 200.
        payload = _payload_debito(forn, nat, fonte, conta, unidade_id=unidade_id, valor="100.00")
        payload_dict = payload.model_dump(mode="json")
        payload_dict["numero_ne"] = None  # sem empenho
        r = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                            json=payload_dict, headers={"Idempotency-Key": "chave-g-criar"})
        assert r.status_code == 201, r.text[:300]
        did = r.json()["id"]
        assert r.json()["numero_ne"] is None

        r_liq = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST",
                                f"{ROTA_DEBITOS}/{did}/liquidar",
                                headers={"Idempotency-Key": "chave-g-liquidar"})
        assert r_liq.status_code == 200, r_liq.text[:300]
        assert r_liq.json()["liquidacao_confirmada"] is True
        assert r_liq.json()["numero_ne"] is None  # continua sem empenho — ninguém exigiu

        # (2) Porta admin: MESMO cenário (débito sem empenho), mesmo ato
        # (`confirmar-liquidacao`) — tem que dar 200 também, provando que o
        # (1) acima não é um caminho paralelo mais frouxo, é o MESMO caminho.
        r_admin_criar = await _http(admin_engine, t.id, t.slug, uid, "POST",
                                    "/api/v2/pagamentos/debitos", json=payload_dict)
        assert r_admin_criar.status_code == 201, r_admin_criar.text[:300]
        did_admin = r_admin_criar.json()["id"]

        r_admin_liq = await _http(admin_engine, t.id, t.slug, uid, "POST",
                                  f"/api/v2/pagamentos/debitos/{did_admin}/confirmar-liquidacao",
                                  json={})
        assert r_admin_liq.status_code == 200, r_admin_liq.text[:300]
        assert r_admin_liq.json()["liquidacao_confirmada"] is True
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_t7_h_cross_tenant_404(admin_engine, two_tenants):
    t = await _provisionar(admin_engine)
    t2 = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)
        forn, nat, fonte, conta, unidade_id = await _cenario_debito(admin_engine, t.id)
        payload = _payload_json(forn, nat, fonte, conta, unidade_id, valor="100.00")
        r = await _http_m2m(admin_engine, t.id, t.slug, chave, "POST", ROTA_DEBITOS,
                            json=payload, headers={"Idempotency-Key": "chave-h"})
        assert r.status_code == 201, r.text[:300]
        did = r.json()["id"]

        uid2 = await _usuario_com(admin_engine, t2.id, ["pagamento_cadastro"])
        sistema2, chave2 = await _criar_sistema_direto(
            admin_engine, t2.id, usuario_id=uid2, escopo_leitura=True, escopo_escrita=True)

        r_liq = await _http_m2m(admin_engine, t2.id, t2.slug, chave2, "POST",
                                f"{ROTA_DEBITOS}/{did}/liquidar",
                                headers={"Idempotency-Key": "chave-h-liquidar"})
        assert r_liq.status_code == 404, r_liq.text[:300]
    finally:
        await _cleanup(admin_engine, t.id)
        await _cleanup(admin_engine, t2.id)


async def _slugs_contratados_e_contratavel(s, tenant_id: int) -> tuple[set[str], set[str]]:
    """`(slugs_contratados_hoje, slugs_do_catalogo_contratavel)`.

    `slugs_contratados` inclui os módulos NÃO-contratáveis (hoje só 'comum');
    `modulos_svc.contratar` só aceita slugs do catálogo `contratavel=True` —
    devolver 'comum' de volta pra `contratar` faria explodir com "módulo
    inexistente ou não contratável" (`services/modulos.py`). Este helper
    isola a interseção segura para (des)contratar sem afetar 'comum'."""
    from app.models import Modulo

    atuais = await modulos_svc.slugs_contratados(s, tenant_id)
    catalogo = {
        m.slug for m in (await s.execute(
            select(Modulo).where(Modulo.contratavel.is_(True))
        )).scalars().all()
    }
    return atuais, catalogo


@pytest.mark.asyncio
async def test_t7_i_modulo_descontratado_403_via_gate_m2m(admin_engine):
    """`_exigir_modulo_pagamentos` (routers/pagamentos_integracao.py) é o gate
    de CONTRATAÇÃO do realm M2M — chave válida, escopo certo, mas tenant sem
    o módulo `pagamentos` contratado tem que levar 403. Molde de
    `tests/test_leitura_por_modulo.py`/`test_permissoes_modulo.py`:
    `services.modulos.contratar` reconcilia a lista de slugs contratados —
    chamar com uma lista SEM 'pagamentos' descontrata (soft, `excluido=True`
    em `tenant_modulo`, nunca DELETE).

    RED real (não apenas "rodei e vi 403"): comentando mentalmente o gate — ou
    seja, provando que ele é a ÚNICA barreira aqui — a mesma chamada com o
    módulo contratado dá 200 (primeira metade do teste) e SÓ descontratando
    ele vira 403 (segunda metade); a inversão A/B na mesma chave/mesmo tenant
    é a prova de que o 403 vem do gate de módulo, não de escopo ou 404."""
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_com(admin_engine, t.id, ["pagamento_cadastro"])
        sistema, chave = await _criar_sistema_direto(
            admin_engine, t.id, usuario_id=uid, escopo_leitura=True, escopo_escrita=True)

        # (A) módulo contratado (estado padrão do provisionamento) -> 200.
        r_com_modulo = await _http_m2m(admin_engine, t.id, t.slug, chave, "GET", ROTA_DEBITOS)
        assert r_com_modulo.status_code == 200, r_com_modulo.text[:300]

        # Descontrata só 'pagamentos', preservando os demais módulos do tenant.
        async with _sm(admin_engine)() as s:
            atuais, catalogo = await _slugs_contratados_e_contratavel(s, t.id)
            await modulos_svc.contratar(s, t.id, sorted((atuais & catalogo) - {"pagamentos"}))
            await s.commit()

        # (B) MESMA chave, MESMO tenant, módulo descontratado -> 403 pelo gate.
        r_sem_modulo = await _http_m2m(admin_engine, t.id, t.slug, chave, "GET", ROTA_DEBITOS)
        assert r_sem_modulo.status_code == 403, r_sem_modulo.text[:300]
        assert "pagamentos" in r_sem_modulo.json()["detail"]
        assert "não contratado" in r_sem_modulo.json()["detail"]
    finally:
        # Recontrata antes do teardown: `_cleanup` apaga o tenant inteiro, mas
        # deixar o vínculo descontratado por trás de um teste que falhou no
        # meio não deveria depender disso — recontratar é barato e explícito.
        async with _sm(admin_engine)() as s:
            atuais, catalogo = await _slugs_contratados_e_contratavel(s, t.id)
            await modulos_svc.contratar(s, t.id, sorted((atuais & catalogo) | {"pagamentos"}))
            await s.commit()
        await _cleanup(admin_engine, t.id)


# --------------------------------------------- correções herdadas da Task 6

class _SistemaFake:
    """Só o que `get_db_m2m` toca: `tenant_id`."""
    def __init__(self, tenant_id: int) -> None:
        self.tenant_id = tenant_id


@pytest.mark.asyncio
async def test_corr1_get_db_m2m_usa_tenant_do_sistema_nunca_request_state():
    """Correção 1 do review da Task 6: `get_db_m2m` não lê `request.state` —
    só `sistema.tenant_id`, que já veio resolvido de `get_current_sistema_integrado`
    como dependência DA PRÓPRIA FUNÇÃO (não irmã). Prova por inversão: chamamos
    `get_db_m2m` passando um `sistema` fake, SEM nenhum `Request` no caminho —
    se a função dependesse de `request.state` ela nem teria como rodar."""
    fake = _SistemaFake(tenant_id=999999)
    agen = get_db_m2m(sistema=fake)  # type: ignore[arg-type]
    session = await agen.__anext__()
    try:
        assert session.info.get("tenant_id") == 999999
    finally:
        await agen.aclose()


@pytest.mark.asyncio
async def test_corr3_prefixo_sob_aprimora_app_enxerga_tenant_da_chave(admin_engine):
    """Correção 3: sob o papel `aprimora_app` (RLS de verdade, NOBYPASSRLS —
    molde de `test_rls_papeis_minimos.py`), o fluxo completo — autenticar por
    PREFIXO (GUC NULL, busca global — migration 0103) + query de negócio
    escopada (GUC = tenant da chave) — enxerga exatamente o tenant da chave, e
    só ele.

    Usa `pagamentos.sistema_integrado` como "a tabela de negócio": é a própria
    tabela que a migration 0103 mudou a policy de SELECT, então provar a
    isolação NELA é o teste mais direto do que a correção garante — sem
    precisar montar fornecedor/natureza/fonte/unidade só para uma segunda
    tabela dizer a mesma coisa.
    """
    t_a = await _provisionar(admin_engine)
    t_b = await _provisionar(admin_engine)
    try:
        uid_a = await _usuario_com(admin_engine, t_a.id, ["pagamento_cadastro"])
        uid_b = await _usuario_com(admin_engine, t_b.id, ["pagamento_cadastro"])
        sistema_a, _ = await _criar_sistema_direto(admin_engine, t_a.id, usuario_id=uid_a)
        sistema_b, _ = await _criar_sistema_direto(admin_engine, t_b.id, usuario_id=uid_b)

        engine = create_async_engine(APP_URL)
        Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        try:
            # 1) Busca por PREFIXO com GUC NULL (pré-autenticação, como
            #    `get_current_sistema_integrado` faz numa chamada M2M cujo Host
            #    não resolveu tenant nenhum) — precisa achar a linha de
            #    QUALQUER tenant, senão a autenticação M2M quebra sob RLS.
            async with Session() as s:
                achou_a = (await s.execute(
                    select(SistemaIntegrado).where(SistemaIntegrado.prefixo == sistema_a.prefixo)
                )).scalar_one_or_none()
                assert achou_a is not None, (
                    "com GUC NULL a policy nova devia achar QUALQUER tenant — "
                    "sem isso a autenticação M2M fica cega sob aprimora_app")
                assert achou_a.tenant_id == t_a.id
                await s.rollback()

            # 2) Com a GUC fixada no tenant ERRADO (não o dono do prefixo),
            #    a mesma busca não pode achar a linha — a policy não virou
            #    "sempre visível", só "visível quando não há tenant fixado".
            async with Session() as s:
                await s.execute(text(f"SET LOCAL app.tenant_id = '{t_b.id}'"))
                nao_achou = (await s.execute(
                    select(SistemaIntegrado).where(SistemaIntegrado.prefixo == sistema_a.prefixo)
                )).scalar_one_or_none()
                assert nao_achou is None
                await s.rollback()

            # 3) Query de negócio ESCOPADA (GUC = tenant da chave, como
            #    `get_db_m2m` monta a sessão depois de autenticar): enxerga o
            #    PRÓPRIO sistema e não o do outro tenant — "enxerga o tenant
            #    da chave", nada mais.
            async with Session() as s:
                await s.execute(text(f"SET LOCAL app.tenant_id = '{t_a.id}'"))
                vistos = (await s.execute(
                    select(SistemaIntegrado.id).where(SistemaIntegrado.tenant_id == t_a.id)
                )).scalars().all()
                assert sistema_a.id in vistos
                cross = (await s.execute(
                    select(SistemaIntegrado).where(SistemaIntegrado.id == sistema_b.id)
                )).scalar_one_or_none()
                assert cross is None, "cross-tenant deveria ser invisível, não só filtrado"
                await s.rollback()
        finally:
            await engine.dispose()
    finally:
        await _cleanup(admin_engine, t_a.id)
        await _cleanup(admin_engine, t_b.id)
