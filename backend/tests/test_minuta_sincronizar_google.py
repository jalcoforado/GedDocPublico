"""Minuta — sincronização de volta do Google Doc (BACKLOG 2.4).

`POST /minutas/{id}/sincronizar-google` baixa o DOCX do Drive, converte os
parágrafos em HTML, sanitiza e — se o conteúdo mudou — versiona a minuta.

Nenhuma credencial Google é necessária: o DOCX é fabricado aqui com python-docx e
injetado no lugar do `GoogleDocsService` (patch no módulo do service, que é onde o
nome é resolvido).
"""
from __future__ import annotations

import io
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from docx import Document
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Minuta, MinutaHistorico, Usuario
from app.schemas.minuta import MinutaCreate
from app.services import minutas as svc
from app.services.google_docs_service import GoogleDocsError
from tests.conftest import arreio_tenant_http
from tests.test_minuta_pr_e_hardening import _criar_processo, _provisionar, _sm

APP = get_settings().app_name


def _docx(*paragrafos: str) -> bytes:
    d = Document()
    for p in paragrafos:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@contextmanager
def _google(docx_bytes: bytes | None = None, erro: Exception | None = None):
    """Substitui o `GoogleDocsService`: devolve `docx_bytes` ou levanta `erro`."""
    with patch("app.services.minutas.GoogleDocsService") as cls:
        inst = cls.return_value
        inst.obter_credentials_usuario = AsyncMock(return_value=object())
        inst.sincronizar_google_doc = AsyncMock(return_value=docx_bytes, side_effect=erro)
        yield inst


async def _cenario(engine, *, com_google_doc: bool = True):
    """Tenant + admin + processo + minuta rascunho de origem Google.

    É o estado que `criar_minuta` produz para `origem="google"`: sem corpo local
    (`corpo_html=None`), versão 1 e nenhuma linha de histórico — o CHECK
    `ck_minuta_google_doc_id_coerente` só admite `google_doc_id` nessa origem.

    Devolve (tenant, usuario, minuta_id).
    """
    tenant, user = await _provisionar(engine)
    processo_id = await _criar_processo(engine, tenant.id)
    async with _sm(engine)() as db:
        m = await svc.criar_minuta(
            db, tenant_id=tenant.id, processo_id=processo_id, usuario=user,
            payload=MinutaCreate(titulo="Sync", origem="google"),
        )
        if com_google_doc:
            m.google_doc_id = f"doc-{uuid.uuid4().hex[:8]}"
            m.google_doc_url = f"https://docs.google.com/document/d/{m.google_doc_id}/edit"
            await db.commit()
        minuta_id = m.id
    return tenant, user, minuta_id


async def _historico(engine, minuta_id: int) -> list[MinutaHistorico]:
    async with _sm(engine)() as s:
        return list((await s.execute(
            select(MinutaHistorico)
            .where(MinutaHistorico.id_minuta == minuta_id)
            .order_by(MinutaHistorico.versao)
        )).scalars().all())


async def _minuta(engine, minuta_id: int) -> Minuta:
    async with _sm(engine)() as s:
        return (await s.execute(select(Minuta).where(Minuta.id == minuta_id))).scalar_one()


async def _sincronizar(engine, tenant, user, minuta_id):
    async with _sm(engine)() as db:
        return await svc.sincronizar_google_doc_para_minuta(
            db, tenant_id=tenant.id, minuta_id=minuta_id, usuario_id=user.id
        )


@pytest.mark.asyncio
async def test_sincronizar_traz_conteudo_versiona_e_grava_historico(admin_engine):
    tenant, user, minuta_id = await _cenario(admin_engine)

    # parágrafo vazio e só-espaço não viram <p></p>
    with _google(_docx("Primeira linha", "", "   ", "Segunda linha")):
        m = await _sincronizar(admin_engine, tenant, user, minuta_id)

    assert m.corpo_html == "<p>Primeira linha</p><p>Segunda linha</p>"
    assert m.versao == 2

    # origem google nasce sem histórico: a 1ª sincronização grava a v2 e é a única linha
    historico = await _historico(admin_engine, minuta_id)
    assert [h.versao for h in historico] == [2]
    assert historico[0].corpo_html == "<p>Primeira linha</p><p>Segunda linha</p>"
    assert historico[0].id_usuario == user.id

    async with _sm(admin_engine)() as s:
        n = (await s.execute(text(
            "SELECT count(*) FROM aprimora_py.audit_log "
            "WHERE tenant_id=:t AND acao='minuta.google_doc_sincronizado' AND id_entidade=:m"
        ), {"t": tenant.id, "m": minuta_id})).scalar_one()
    assert n == 1


@pytest.mark.asyncio
async def test_sincronizar_so_versiona_quando_o_conteudo_muda(admin_engine):
    tenant, user, minuta_id = await _cenario(admin_engine)

    with _google(_docx("Mesmo texto")):
        await _sincronizar(admin_engine, tenant, user, minuta_id)
        m = await _sincronizar(admin_engine, tenant, user, minuta_id)
    assert m.versao == 2  # a 2ª chamada, com o mesmo conteúdo, não subiu para 3
    assert [h.versao for h in await _historico(admin_engine, minuta_id)] == [2]

    with _google(_docx("Texto editado no Google")):
        m = await _sincronizar(admin_engine, tenant, user, minuta_id)
    assert m.versao == 3
    assert m.corpo_html == "<p>Texto editado no Google</p>"
    assert [h.versao for h in await _historico(admin_engine, minuta_id)] == [2, 3]


@pytest.mark.asyncio
async def test_sincronizar_trata_texto_do_doc_como_texto_nao_marcacao(admin_engine):
    """O Google Doc é texto puro. `<nome>` digitado ali é um placeholder, não uma tag:
    sem escapar antes do sanitizador, o bleach o descartaria e o texto sumiria em
    silêncio. `<script>` digitado vira texto inerte, não some nem executa."""
    tenant, user, minuta_id = await _cenario(admin_engine)

    with _google(_docx(
        "Prazo < 5 dias e valor > R$ 10 & mais",
        "Prezado <nome>,",
        "<script>alert(1)</script>",
    )):
        m = await _sincronizar(admin_engine, tenant, user, minuta_id)

    assert "Prezado &lt;nome&gt;," in m.corpo_html
    assert "Prazo &lt; 5 dias e valor &gt; R$ 10 &amp; mais" in m.corpo_html
    assert "<script" not in m.corpo_html
    assert "&lt;script&gt;" in m.corpo_html


@pytest.mark.asyncio
async def test_sincronizar_recusa_minuta_que_nao_e_rascunho(admin_engine):
    tenant, user, minuta_id = await _cenario(admin_engine)
    # 'cancelada', não 'finalizada': esta exige `id_anexo_final` (CHECK)
    async with _sm(admin_engine)() as s:
        await s.execute(text("UPDATE protocolos.minuta SET status='cancelada' WHERE id=:i"),
                        {"i": minuta_id})
        await s.commit()

    with _google(_docx("Texto novo")) as google:
        with pytest.raises(HTTPException) as exc:
            await _sincronizar(admin_engine, tenant, user, minuta_id)

    assert exc.value.status_code == 409
    google.sincronizar_google_doc.assert_not_awaited()
    assert (await _minuta(admin_engine, minuta_id)).corpo_html is None


@pytest.mark.asyncio
async def test_sincronizar_sem_google_doc_associado_e_400(admin_engine):
    tenant, user, minuta_id = await _cenario(admin_engine, com_google_doc=False)

    with _google(_docx("Texto novo")) as google:
        with pytest.raises(HTTPException) as exc:
            await _sincronizar(admin_engine, tenant, user, minuta_id)

    assert exc.value.status_code == 400
    google.sincronizar_google_doc.assert_not_awaited()


@pytest.mark.asyncio
async def test_sincronizar_erro_do_google_vira_400_e_nao_altera_a_minuta(admin_engine):
    tenant, user, minuta_id = await _cenario(admin_engine)

    with _google(erro=GoogleDocsError("boom")):
        with pytest.raises(HTTPException) as exc:
            await _sincronizar(admin_engine, tenant, user, minuta_id)

    assert exc.value.status_code == 400
    assert "Erro ao sincronizar do Google Docs" in exc.value.detail
    m = await _minuta(admin_engine, minuta_id)
    assert (m.corpo_html, m.versao) == (None, 1)
    assert await _historico(admin_engine, minuta_id) == []


async def _usuario_comum(engine, tenant_id: int, *, atualiza_processo: bool) -> int:
    """Usuário nível != 0 (não é super-usuário → não passa pelo bypass de `perms.py`)."""
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
            VALUES (:t, 'Comum Sync', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id"""), {"t": tenant_id, "e": f"sync-{uuid.uuid4().hex[:8]}@minuta.test",
                               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one())
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, :g, false) RETURNING id"""),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id,
             "g": f"Sync {uuid.uuid4().hex[:6]}"})).scalar_one())
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :a)"""),
            {"t": tenant_id, "u": uid, "g": gid, "a": APP})
        tr = (await s.execute(text(
            "SELECT id FROM utils.transacao WHERE codigo='processo' AND excluido=false LIMIT 1"
        ))).scalar_one()
        await s.execute(text("""
            INSERT INTO utils.grupo_transacao
                (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
            VALUES (:t, :g, :tr, false, :at, false, false)"""),
            {"t": tenant_id, "g": gid, "tr": int(tr), "at": atualiza_processo})
        await s.commit()
    return uid


async def _post_sincronizar(engine, tenant, usuario_id: int, minuta_id: int):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant.id, tenant.slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(f"/api/v2/minutas/{minuta_id}/sincronizar-google")
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


@pytest.mark.asyncio
async def test_http_usuario_comum_sincroniza_e_sem_permissao_leva_403(admin_engine):
    """A suíte inteira roda como super-usuário e o bypass de `perms.py` retorna antes
    do `getattr(item, action)`: só o ramo comum prova que a rota está bem gateada e
    que o `usuario.id` chega ao service."""
    tenant, _user, minuta_id = await _cenario(admin_engine)
    pode = await _usuario_comum(admin_engine, tenant.id, atualiza_processo=True)
    nao_pode = await _usuario_comum(admin_engine, tenant.id, atualiza_processo=False)

    with _google(_docx("Vindo do Google")) as google:
        negado = await _post_sincronizar(admin_engine, tenant, nao_pode, minuta_id)
        assert negado.status_code == 403, negado.text[:300]
        google.sincronizar_google_doc.assert_not_awaited()

        ok = await _post_sincronizar(admin_engine, tenant, pode, minuta_id)

    assert ok.status_code == 200, ok.text[:300]
    corpo = ok.json()
    assert corpo["corpo_html"] == "<p>Vindo do Google</p>"
    assert corpo["versao"] == 2
    assert (await _historico(admin_engine, minuta_id))[-1].id_usuario == pode
