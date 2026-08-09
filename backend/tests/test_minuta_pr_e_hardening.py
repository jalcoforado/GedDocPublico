"""Minuta PR-E — hardening: sanitização HTML + histórico (PR-E).

Testa:
- Sanitização via bleach em criar/atualizar/finalizar minuta
- Histórico de versões (GET /minutas/{id}/historico)
- Conteúdo malicioso é removido (XSS, scripts)
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Assunto, TipoProcesso, Usuario
from app.schemas.minuta import MinutaCreate, MinutaUpdate
from app.services import minutas as svc
from app.services.html_sanitizer import sanitizar_html
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    """Devolve (tenant, usuario_admin).

    Atenção: provisionar_tenant retorna (tenant, senha_temporária) — o 2º item
    é `str`, não o usuário. Os serviços de minuta esperam um `Usuario` (acessam
    `usuario.id`), então carregamos o admin do tenant aqui.
    """
    slug = _slug("minuta")
    async with _sm(engine)() as s:
        tenant, _senha_temp = await provisionar_tenant(
            s, slug=slug, nome="Pref Minuta", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    async with _sm(engine)() as s:
        user = (
            await s.execute(select(Usuario).where(Usuario.tenant_id == tenant.id).limit(1))
        ).scalar_one()
    return tenant, user


async def _criar_processo(engine, tenant_id: int) -> int:
    """Cria um processo mínimo válido e devolve seu id.

    Processo exige id_assunto, id_manifestante e id_unidade_proprietaria (todos
    FK NOT NULL) — montamos a cadeia inteira. Mesmo padrão de
    test_pr4d_complementacao.
    """
    async with _sm(engine)() as s:
        tp = TipoProcesso(
            tenant_id=tenant_id, tipo_processo="Geral",
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(tp)
        await s.flush()
        assunto = Assunto(
            tenant_id=tenant_id, assunto="Minuta", id_tipo_processo=tp.id,
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(assunto)
        await s.flush()

        unidade_id = int(
            (
                await s.execute(
                    text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )
        await s.execute(
            text(
                "INSERT INTO protocolos.manifestante "
                "(tenant_id, id_tipo_manifestante, nome, cpf_cnpj, ativo, excluido) "
                "SELECT :t, id, 'Manifestante Minuta', :cpf, true, false "
                "FROM protocolos.tipo_manifestante WHERE tenant_id=:t LIMIT 1"
            ),
            {"t": tenant_id, "cpf": uuid.uuid4().hex[:11]},
        )
        manifestante_id = int(
            (
                await s.execute(
                    text("SELECT id FROM protocolos.manifestante WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )
        processo_id = int(
            (
                await s.execute(
                    text(
                        "INSERT INTO protocolos.processo "
                        "(tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria, "
                        " virtual, data_hora_abertura, numero_processo, nivel_sigilo, "
                        " externo, migrado, ativo, excluido, canal_entrada) "
                        "VALUES (:t, :a, :m, :u, true, NOW(), :num, 'ostensivo', "
                        "        true, false, true, false, 'portal') RETURNING id"
                    ),
                    {
                        "t": tenant_id, "a": assunto.id, "m": manifestante_id,
                        "u": unidade_id, "num": f"P{uuid.uuid4().hex[:6].upper()}/2026",
                    },
                )
            ).scalar_one()
        )
        await s.commit()
    return processo_id


@pytest.mark.asyncio
async def test_sanitizar_html_remove_script(admin_engine):
    """Bleach remove <script> tags."""
    html = '<p>Texto <script>alert("xss")</script> aqui</p>'
    sanitizado = sanitizar_html(html)
    assert "<script>" not in sanitizado
    assert "Texto" in sanitizado


@pytest.mark.asyncio
async def test_sanitizar_html_remove_event_handlers(admin_engine):
    """Bleach remove onclick, onload, etc."""
    html = '<p onclick="alert(1)">Clique</p>'
    sanitizado = sanitizar_html(html)
    assert "onclick" not in sanitizado
    assert "Clique" in sanitizado


@pytest.mark.asyncio
async def test_sanitizar_html_preserva_tags_seguras(admin_engine):
    """Bleach preserva p, b, i, strong, etc."""
    html = '<p><b>negrito</b> e <i>itálico</i> e <u>sublinhado</u></p>'
    sanitizado = sanitizar_html(html)
    assert "<b>" in sanitizado
    assert "<i>" in sanitizado
    assert "<u>" in sanitizado
    assert "negrito" in sanitizado


@pytest.mark.asyncio
async def test_sanitizar_html_preserva_imagem_do_editor(admin_engine):
    """`img` só sobrevive com `src` apontando pro endpoint interno de imagens
    do editor — qualquer outra origem (externa) é removida (a `<img>` some
    inteira, sem `src`, o que a torna inofensiva)."""
    interna = '<img src="/api/v2/editor-imagens/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png" alt="logo">'
    assert sanitizar_html(interna) == interna

    externa = sanitizar_html('<img src="http://evil.com/x.png" onerror="alert(1)">')
    assert "src=" not in externa
    assert "evil.com" not in externa


@pytest.mark.asyncio
async def test_sanitizar_html_preserva_tabela(admin_engine):
    html = "<table><tr><th>H</th></tr><tr><td>D</td></tr></table>"
    sanitizado = sanitizar_html(html)
    assert "<table>" in sanitizado
    assert "<th>H</th>" in sanitizado
    assert "<td>D</td>" in sanitizado


@pytest.mark.asyncio
async def test_sanitizar_html_preserva_alinhamento_mas_nao_outro_css(admin_engine):
    """`style` só sobrevive com `text-align` — qualquer outra propriedade CSS
    (inclusive tentativa de `url(...)`) é zerada pelo CSSSanitizer do bleach."""
    alinhado = sanitizar_html('<p style="text-align: center;">centro</p>')
    assert 'style="text-align: center;"' in alinhado

    malicioso = sanitizar_html('<p style="background: url(javascript:alert(1))">x</p>')
    assert "url(" not in malicioso
    assert "javascript:" not in malicioso


@pytest.mark.asyncio
async def test_sanitizar_html_remove_style_tags(admin_engine):
    """Bleach remove <style> e propriedades perigosas."""
    html = '<p style="background: url(javascript:alert(1))">Texto</p>'
    sanitizado = sanitizar_html(html)
    assert "style=" not in sanitizado or "javascript:" not in sanitizado
    assert "Texto" in sanitizado


@pytest.mark.asyncio
async def test_criar_minuta_sanitiza_corpo_html(admin_engine):
    """criar_minuta aplica bleach ao corpo_html fornecido."""
    tenant, user = await _provisionar(admin_engine)

    processo_id = await _criar_processo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as db:

        # Minuta com HTML malicioso
        payload = MinutaCreate(
            titulo="Teste",
            origem="interno",
            corpo_html='<p><script>alert("xss")</script>Texto</p>',
        )
        m = await svc.criar_minuta(
            db, tenant_id=tenant.id, processo_id=processo_id,
            usuario=user, payload=payload
        )

        # Conteúdo deve estar sanitizado
        assert "<script>" not in m.corpo_html
        assert "Texto" in m.corpo_html


@pytest.mark.asyncio
async def test_atualizar_minuta_sanitiza_corpo_html(admin_engine):
    """atualizar_minuta aplica bleach ao corpo_html."""
    tenant, user = await _provisionar(admin_engine)
    processo_id = await _criar_processo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as db:

        payload_create = MinutaCreate(titulo="Teste", origem="interno", corpo_html="<p>Inicial</p>")
        m = await svc.criar_minuta(
            db, tenant_id=tenant.id, processo_id=processo_id,
            usuario=user, payload=payload_create
        )
        minuta_id = m.id

        # Atualizar com HTML malicioso
        payload_update = MinutaUpdate(
            corpo_html='<p><img src=x onerror="alert(1)">Atualizado</p>'
        )
        m_updated = await svc.atualizar_minuta(
            db, tenant_id=tenant.id, minuta_id=minuta_id,
            usuario=user, payload=payload_update
        )

        # Conteúdo deve estar sanitizado (onerror removido)
        assert "onerror=" not in m_updated.corpo_html
        assert "Atualizado" in m_updated.corpo_html


@pytest.mark.asyncio
async def test_historico_minuta_cria_versoes(admin_engine):
    """Cada atualização cria nova versão em minuta_historico."""
    tenant, user = await _provisionar(admin_engine)
    processo_id = await _criar_processo(admin_engine, tenant.id)

    async with _sm(admin_engine)() as db:

        # Criar minuta (versão 1)
        payload1 = MinutaCreate(titulo="Teste", origem="interno", corpo_html="<p>V1</p>")
        m = await svc.criar_minuta(
            db, tenant_id=tenant.id, processo_id=processo_id,
            usuario=user, payload=payload1
        )
        assert m.versao == 1

        # Atualizar (versão 2)
        payload2 = MinutaUpdate(corpo_html="<p>V2</p>")
        m = await svc.atualizar_minuta(
            db, tenant_id=tenant.id, minuta_id=m.id,
            usuario=user, payload=payload2
        )
        assert m.versao == 2

        # Atualizar novamente (versão 3)
        payload3 = MinutaUpdate(corpo_html="<p>V3</p>")
        m = await svc.atualizar_minuta(
            db, tenant_id=tenant.id, minuta_id=m.id,
            usuario=user, payload=payload3
        )
        assert m.versao == 3

        # Listar histórico
        historico = await svc.listar_historico_minuta(
            db, tenant_id=tenant.id, minuta_id=m.id
        )
        # Deve ter 3 versões em ordem DESC (3, 2, 1)
        assert len(historico) == 3
        assert historico[0].versao == 3
        assert historico[1].versao == 2
        assert historico[2].versao == 1
        assert "V3" in historico[0].corpo_html
        assert "V2" in historico[1].corpo_html
        assert "V1" in historico[2].corpo_html
