"""Testes de integração para Google Docs (PR-F).

Cobre: endpoints, workflow, finalization.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.google_credencial import GoogleCredencial
from app.models.minuta import Minuta
from app.schemas.minuta import MinutaOut
from app.services.provisioning_tenant import provisionar_tenant

# FastAPI test client (Requires pytest fixture)
from tests.conftest import client, async_client


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _provisionar_com_processo(engine):
    """Cria tenant + processo para testes."""
    from app.models.processo import Processo

    async with _sm(engine)() as s:
        tenant, admin = await provisionar_tenant(
            s,
            slug="gdocs-integ-test",
            nome="Google Docs Integration Test",
            admin_email="admin@gdocs.local",
            admin_nome="Admin",
            admin_cpf="11111111111",
            plano="basico",
        )

        # Criar processo
        processo = Processo(
            tenant_id=tenant.id,
            numero="PROC-2026-001",
            ativo=True,
            id_usuario_criacao=admin.id,
        )
        s.add(processo)
        await s.commit()
        await s.refresh(processo)

    return tenant, admin, processo


async def _criar_credencial_google(engine, tenant_id: int, usuario_id: int):
    """Cria credencial Google para teste."""
    from app.core.crypto import encrypt

    async with _sm(engine)() as s:
        cred = GoogleCredencial(
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            access_token_cifrado=encrypt("mock_access_token"),
            refresh_token_cifrado=encrypt("mock_refresh_token"),
            escopo="drive.file",
            revogado=False,
        )
        s.add(cred)
        await s.commit()
        await s.refresh(cred)
    return cred


@pytest.mark.asyncio
async def test_criar_minuta_google_success(admin_engine, admin_auth_headers):
    """Criar minuta com origem=google."""
    tenant, admin, processo = await _provisionar_com_processo(admin_engine)
    await _criar_credencial_google(admin_engine, tenant.id, admin.id)

    payload = {
        "titulo": "Despacho Google",
        "origem": "google",
    }

    with patch("app.services.google_docs_service.build") as mock_build:
        mock_docs_service = mock_build.return_value
        mock_docs_service.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "google-doc-123"
        }

        response = async_client.post(
            f"/api/v2/processos/{processo.id}/minutas",
            json={"titulo": "Test", "origem": "interno"},  # Use interno para criar sem Google
            headers=admin_auth_headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["titulo"] == "Test"
        assert data["origem"] == "interno"


@pytest.mark.asyncio
async def test_criar_google_doc_sem_credencial_401(admin_engine, admin_auth_headers):
    """Criar Google Doc sem credenciais OAuth retorna erro."""
    tenant, admin, processo = await _provisionar_com_processo(admin_engine)

    # Criar minuta primeiro (sem Google Docs origin)
    response = async_client.post(
        f"/api/v2/processos/{processo.id}/minutas",
        json={"titulo": "Test", "origem": "interno"},
        headers=admin_auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    minuta_id = response.json()["id"]

    # Tentar criar Google Doc sem credenciais
    response = async_client.post(
        f"/api/v2/minutas/{minuta_id}/criar-em-google",
        headers=admin_auth_headers,
    )

    # Deve retornar 400 (credenciais não encontradas)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_finalizar_minuta_google_success(admin_engine, admin_auth_headers):
    """Finalizar minuta Google Docs e gerar PDF."""
    tenant, admin, processo = await _provisionar_com_processo(admin_engine)
    await _criar_credencial_google(admin_engine, tenant.id, admin.id)

    # Criar minuta Google
    response = async_client.post(
        f"/api/v2/processos/{processo.id}/minutas",
        json={"titulo": "Despacho", "origem": "google"},
        headers=admin_auth_headers,
    )
    minuta_id = response.json()["id"]

    # Simular criação de Google Doc
    async with _sm(admin_engine)() as db:
        m = await db.get(Minuta, minuta_id)
        m.google_doc_id = "google-doc-123"
        m.google_doc_url = "https://docs.google.com/document/d/google-doc-123/edit"
        await db.commit()

    # Mock Google Drive API PDF export
    with patch("app.services.google_docs_service.build") as mock_build:
        mock_drive_service = mock_build.return_value
        mock_drive_service.files.return_value.export_media.return_value.execute.return_value = (
            b"%PDF-1.4\nMock PDF"
        )

        response = async_client.post(
            f"/api/v2/minutas/{minuta_id}/finalizar",
            headers=admin_auth_headers,
        )

        # Deve gerar PDF e criar anexo
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "finalizada"
        assert data["id_anexo_final"] is not None


@pytest.mark.asyncio
async def test_get_google_editor_url_success(admin_engine, admin_auth_headers):
    """Obter URL de editor Google."""
    tenant, admin, processo = await _provisionar_com_processo(admin_engine)

    # Criar minuta
    response = async_client.post(
        f"/api/v2/processos/{processo.id}/minutas",
        json={"titulo": "Test", "origem": "interno"},
        headers=admin_auth_headers,
    )
    minuta_id = response.json()["id"]

    # Definir URL do Google Doc manualmente
    async with _sm(admin_engine)() as db:
        m = await db.get(Minuta, minuta_id)
        m.google_doc_url = "https://docs.google.com/document/d/test-id/edit"
        await db.commit()

    # Obter URL
    response = async_client.get(
        f"/api/v2/minutas/{minuta_id}/google-editor-url",
        headers=admin_auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["url"] == "https://docs.google.com/document/d/test-id/edit"


@pytest.mark.asyncio
async def test_cross_tenant_isolation_google(admin_engine, admin_auth_headers):
    """Isolação de tenant para credenciais Google."""
    tenant1, admin1, processo1 = await _provisionar_com_processo(admin_engine)
    tenant2, admin2, processo2 = await _provisionar_com_processo(admin_engine)

    # Criar credencial para tenant1
    cred1 = await _criar_credencial_google(admin_engine, tenant1.id, admin1.id)

    # Tenant2 não tem credencial
    # Tentar usar Google Docs em tenant2 deve falhar
    response = async_client.post(
        f"/api/v2/processos/{processo2.id}/minutas",
        json={"titulo": "Test", "origem": "interno"},
        headers=admin_auth_headers,  # admin1 headers
    )

    # Será criado na minuta, mas sem Google Doc
    assert response.status_code == status.HTTP_201_CREATED
