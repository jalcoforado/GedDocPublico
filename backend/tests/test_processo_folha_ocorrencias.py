"""Folha de ocorrências (fatia F7, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.

O PDF é uma saída impressa da MESMA timeline que a aba "Movimentações" já
mostra (`_load_movimentacoes`) — não uma segunda fonte reconstruída do
`audit_log` cru. Por isso o teste prova duas coisas: que os textos das
colunas aparecem no PDF, e que a ORDEM é cronológica ascendente (a tela
mostra mais recente primeiro; a folha impressa lê-se do mais antigo pro mais
recente, como qualquer trilha de auditoria).
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import (
    Assunto,
    Despacho,
    Manifestante,
    Movimentacao,
    Processo,
    TipoProcesso,
    Usuario,
)
from app.services.pdf_folha_ocorrencias import gerar_folha_ocorrencias_pdf
from app.services.processos import get_processo_detail
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _cria_usuario_comum(session, tenant_id: int, *, unidade_id: int) -> int:
    """Cópia do helper de `test_processo_destinos_permitidos.py` — mesma razão lá."""
    sistema_id = (
        await session.execute(
            text("SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"),
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
            text("SELECT id FROM utils.transacao WHERE codigo = 'processo' AND excluido = false LIMIT 1")
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
                "email": f"op-{uuid.uuid4().hex[:8]}@f7.test",
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
        VALUES (:t, :n, :s, 'Grupo F7', false) RETURNING id
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
        VALUES (:t, :g, :tr, true, true, true, false)
    """
        ),
        {"t": tenant_id, "g": gid, "tr": transacao_id},
    )
    return uid


@pytest_asyncio.fixture
async def cen(admin_engine):
    slug = _slug("f7-")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref F7",
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
        id_admin = (
            await s.execute(
                text("SELECT id FROM utils.usuario WHERE tenant_id=:t ORDER BY id LIMIT 1"),
                {"t": tenant.id},
            )
        ).scalar_one()
        id_acao_abertura = (
            await s.execute(
                text("SELECT id FROM protocolos.acao WHERE flag='ABERTURA' AND excluido=false LIMIT 1")
            )
        ).scalar_one()
        id_acao_recebimento = (
            await s.execute(
                text("SELECT id FROM protocolos.acao WHERE flag='RECEBIMENTO' AND excluido=false LIMIT 1")
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

        abertura = datetime.now() - timedelta(days=2)
        recebimento = datetime.now() - timedelta(days=1)

        processo = Processo(
            tenant_id=tenant.id,
            id_assunto=assunto.id,
            virtual=True,
            data_hora_abertura=abertura,
            numero_processo=f"{slug}-p1",
            id_unidade_proprietaria=unidade_id,
            id_manifestante=manif.id,
            id_local_atual=unidade_id,
            nivel_sigilo="ostensivo",
            ativo=True,
            excluido=False,
        )
        s.add(processo)
        await s.flush()

        mov_abertura = Movimentacao(
            tenant_id=tenant.id, id_processo=processo.id,
            id_unidade_responsavel=unidade_id, id_acao=id_acao_abertura,
            data_hora_movimentacao=abertura, ativo=True, excluido=False,
        )
        mov_recebimento = Movimentacao(
            tenant_id=tenant.id, id_processo=processo.id,
            id_unidade_responsavel=unidade_id, id_acao=id_acao_recebimento,
            id_usuario=id_admin,
            data_hora_movimentacao=recebimento, ativo=True, excluido=False,
        )
        s.add_all([mov_abertura, mov_recebimento])
        await s.flush()

        despacho = Despacho(
            tenant_id=tenant.id, id_processo=processo.id,
            despacho="Observação de teste F7", id_usuario=id_admin,
            id_movimentacao=mov_recebimento.id, ativo=True, excluido=False,
        )
        s.add(despacho)
        await s.flush()
        await s.commit()

        dados = {"tenant": tenant, "processo_id": processo.id, "operador": operador}

    yield dados

    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.despacho WHERE tenant_id=:t",
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


def _texto(pdf_bytes: bytes) -> str:
    return " ".join(
        "".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages).split()
    )


@pytest.mark.asyncio
async def test_folha_traz_processo_ocorrencias_e_observacao(admin_engine, cen):
    async with _sm(admin_engine)() as s:
        detail = await get_processo_detail(s, cen["processo_id"], tenant_id=cen["tenant"].id)
    assert detail is not None

    pdf_bytes = gerar_folha_ocorrencias_pdf(detail)
    assert pdf_bytes[:4] == b"%PDF"

    texto = _texto(pdf_bytes)
    assert detail.numero_processo in texto
    assert "Abertura" in texto
    assert "Recebimento" in texto
    assert "Observação de teste F7" in texto


@pytest.mark.asyncio
async def test_folha_ordena_do_mais_antigo_para_o_mais_recente(admin_engine, cen):
    """`_load_movimentacoes` devolve mais recente primeiro (pra timeline na
    tela); a folha IMPRESSA inverte — testa a inversão, não só a presença."""
    async with _sm(admin_engine)() as s:
        detail = await get_processo_detail(s, cen["processo_id"], tenant_id=cen["tenant"].id)
    assert detail is not None
    # Confere a premissa: a API devolve mais recente primeiro.
    assert detail.movimentacoes[0].acao == "Recebimento"
    assert detail.movimentacoes[-1].acao == "Abertura"

    texto = _texto(gerar_folha_ocorrencias_pdf(detail))
    assert texto.index("Abertura") < texto.index("Recebimento")


@pytest.mark.asyncio
async def test_folha_sem_movimentacoes_nao_quebra(admin_engine, cen):
    """Processo sem timeline (caso improvável em fluxo normal, mas existe em
    base migrada) gera PDF válido com aviso, não uma exceção."""
    async with _sm(admin_engine)() as s:
        await s.execute(
            text("DELETE FROM protocolos.despacho WHERE tenant_id=:t"),
            {"t": cen["tenant"].id},
        )
        await s.execute(
            text(
                "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL "
                "WHERE tenant_id=:t"
            ),
            {"t": cen["tenant"].id},
        )
        await s.execute(
            text("DELETE FROM protocolos.movimentacao WHERE tenant_id=:t"),
            {"t": cen["tenant"].id},
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        detail = await get_processo_detail(s, cen["processo_id"], tenant_id=cen["tenant"].id)
    assert detail is not None
    assert detail.movimentacoes == []

    pdf_bytes = gerar_folha_ocorrencias_pdf(detail)
    assert pdf_bytes[:4] == b"%PDF"
    assert "Sem ocorrências registradas" in _texto(pdf_bytes)


@pytest.mark.asyncio
async def test_http_usuario_comum_baixa_a_folha(admin_engine, cen):
    t = cen["tenant"]

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(select(Usuario).where(Usuario.id == cen["operador"]))
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"/api/v2/processos/{cen['processo_id']}/folha-ocorrencias.pdf")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"
