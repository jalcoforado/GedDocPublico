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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.minuta import MinutaCreate, MinutaUpdate
from app.services import minutas as svc
from app.services.html_sanitizer import sanitizar_html
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("minuta")
    async with _sm(engine)() as s:
        tenant, user = await provisionar_tenant(
            s, slug=slug, nome="Pref Minuta", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant, user


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

    async with _sm(admin_engine)() as db:
        # Criar processo dummy
        from app.models import Processo
        proc = Processo(
            tenant_id=tenant.id,
            numero="2024.00001",
            tipo="protocolo",
            status_externo="aberto",
            status_interno="triagem",
            descricao="Teste",
        )
        db.add(proc)
        await db.flush()
        processo_id = proc.id

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

    async with _sm(admin_engine)() as db:
        # Setup processo + minuta
        from app.models import Processo
        proc = Processo(
            tenant_id=tenant.id,
            numero="2024.00002",
            tipo="protocolo",
            status_externo="aberto",
            status_interno="triagem",
            descricao="Teste",
        )
        db.add(proc)
        await db.flush()

        payload_create = MinutaCreate(titulo="Teste", origem="interno", corpo_html="<p>Inicial</p>")
        m = await svc.criar_minuta(
            db, tenant_id=tenant.id, processo_id=proc.id,
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

    async with _sm(admin_engine)() as db:
        from app.models import Processo
        proc = Processo(
            tenant_id=tenant.id,
            numero="2024.00003",
            tipo="protocolo",
            status_externo="aberto",
            status_interno="triagem",
            descricao="Teste",
        )
        db.add(proc)
        await db.flush()

        # Criar minuta (versão 1)
        payload1 = MinutaCreate(titulo="Teste", origem="interno", corpo_html="<p>V1</p>")
        m = await svc.criar_minuta(
            db, tenant_id=tenant.id, processo_id=proc.id,
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
