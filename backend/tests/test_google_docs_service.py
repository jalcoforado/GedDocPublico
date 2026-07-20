"""Testes para Google Docs service (PR-F).

Cobre: token management, document creation, download, sync, export, archival.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.google_credencial import GoogleCredencial
from app.services.google_docs_service import (
    DocumentNotFoundError,
    GoogleDocsError,
    GoogleDocsService,
    PermissionDeniedError,
    TokenExpiredError,
)
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _provisionar(engine):
    """Cria tenant para testes. Retorna (tenant, admin_id)."""
    from app.models.usuario import Usuario
    from sqlalchemy import select

    unique_slug = f"gdocs-{str(uuid.uuid4())[:8]}"
    admin_email = f"admin-{uuid.uuid4().hex[:8]}@gdocs.local"

    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=unique_slug,
            nome="Tenant Google Docs Test",
            admin_email=admin_email,
            admin_nome="Admin",
            admin_cpf="11111111111",
            plano="basico",
        )

        # Obter o usuário admin que foi criado
        stmt = select(Usuario).where(Usuario.email == admin_email)
        result = await s.execute(stmt)
        admin = result.scalar_one_or_none()
        admin_id = admin.id if admin else None

    return tenant, admin_id


async def _criar_credencial(engine, tenant_id: int, usuario_id: int):
    """Cria credencial Google para teste."""
    from app.core.crypto import encrypt

    async with _sm(engine)() as s:
        cred = GoogleCredencial(
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            access_token_cifrado=encrypt("mock_access_token"),
            refresh_token_cifrado=encrypt("mock_refresh_token"),
            escopo="drive.file",
            expira_em=datetime.utcnow() + timedelta(hours=1),
            criado_em=datetime.utcnow(),
            revogado=False,
        )
        s.add(cred)
        await s.commit()
        await s.refresh(cred)
    return cred


@pytest.mark.asyncio
async def test_obter_credentials_usuario_found(admin_engine):
    """Obter credenciais do usuário."""
    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    async with _sm(admin_engine)() as db:
        result = await service.obter_credentials_usuario(
            db, tenant_id=tenant.id, usuario_id=admin_id
        )
        assert result.id == cred.id
        assert result.tenant_id == tenant.id
        assert result.id_usuario == admin_id
        assert result.revogado is False


@pytest.mark.asyncio
async def test_obter_credentials_usuario_not_found(admin_engine):
    """Credencial não encontrada retorna erro."""
    tenant, _ = await _provisionar(admin_engine)
    service = GoogleDocsService()

    async with _sm(admin_engine)() as db:
        with pytest.raises(PermissionDeniedError):
            await service.obter_credentials_usuario(
                db, tenant_id=tenant.id, usuario_id=9999
            )


@pytest.mark.asyncio
async def test_obter_credentials_usuario_revogado(admin_engine):
    """Credencial revogada retorna erro."""
    tenant, admin_id = await _provisionar(admin_engine)
    from app.core.crypto import encrypt

    async with _sm(admin_engine)() as s:
        cred = GoogleCredencial(
            tenant_id=tenant.id,
            id_usuario=admin_id,
            access_token_cifrado=encrypt("token"),
            refresh_token_cifrado=encrypt("refresh"),
            escopo="drive.file",
            expira_em=datetime.utcnow() + timedelta(hours=1),
            criado_em=datetime.utcnow(),
            revogado=True,  # Revoked!
        )
        s.add(cred)
        await s.commit()

    service = GoogleDocsService()

    async with _sm(admin_engine)() as db:
        with pytest.raises(PermissionDeniedError):
            await service.obter_credentials_usuario(
                db, tenant_id=tenant.id, usuario_id=admin_id
            )


@pytest.mark.asyncio
async def test_renovar_access_token_not_expired(admin_engine):
    """Token não expirado não é renovado."""
    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    async with _sm(admin_engine)() as db:
        # Chamar renovar_access_token com token válido
        result = await service.renovar_access_token(db, cred)

        # Deve retornar credencial sem alterações (token ainda válido)
        assert result.id == cred.id


@pytest.mark.asyncio
async def test_criar_google_doc_success(admin_engine):
    """Criar novo Google Doc."""
    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    # Mock Google Docs API
    with patch("app.services.google_docs_service.build") as mock_build:
        mock_docs_service = MagicMock()
        mock_build.return_value = mock_docs_service

        mock_create = MagicMock()
        mock_docs_service.documents.return_value.create.return_value = mock_create
        mock_create.execute.return_value = {"documentId": "google-doc-id-123"}

        async with _sm(admin_engine)() as db:
            result = await service.criar_google_doc(
                db,
                cred=cred,
                titulo="Test Document",
                corpo_html=None,
            )

            assert result["google_doc_id"] == "google-doc-id-123"
            assert (
                result["google_doc_url"]
                == "https://docs.google.com/document/d/google-doc-id-123/edit"
            )


@pytest.mark.asyncio
async def test_criar_google_doc_401_token_expired(admin_engine):
    """Criar Google Doc com token expirado."""
    from googleapiclient.errors import HttpError

    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    # Mock Google API error 401
    with patch("app.services.google_docs_service.build") as mock_build:
        mock_docs_service = MagicMock()
        mock_build.return_value = mock_docs_service

        mock_error = MagicMock()
        mock_error.resp.status = 401
        mock_docs_service.documents.return_value.create.return_value.execute.side_effect = (
            HttpError(mock_error, b"Unauthorized")
        )

        async with _sm(admin_engine)() as db:
            with pytest.raises(TokenExpiredError):
                await service.criar_google_doc(
                    db, cred=cred, titulo="Test", corpo_html=None
                )


@pytest.mark.asyncio
async def test_sincronizar_google_doc_success(admin_engine):
    """Sincronizar (baixar) Google Doc como DOCX."""
    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    mock_docx_bytes = b"PK\x03\x04..."  # Fake DOCX magic bytes

    with patch("app.services.google_docs_service.build") as mock_build:
        mock_drive_service = MagicMock()
        mock_build.return_value = mock_drive_service

        mock_export = MagicMock()
        mock_drive_service.files.return_value.export_media.return_value = mock_export
        mock_export.execute.return_value = mock_docx_bytes

        async with _sm(admin_engine)() as db:
            result = await service.sincronizar_google_doc(
                db, cred=cred, google_doc_id="doc-id-123"
            )

            assert result == mock_docx_bytes


@pytest.mark.asyncio
async def test_sincronizar_google_doc_404_not_found(admin_engine):
    """Sincronizar Google Doc não encontrado."""
    from googleapiclient.errors import HttpError

    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    with patch("app.services.google_docs_service.build") as mock_build:
        mock_drive_service = MagicMock()
        mock_build.return_value = mock_drive_service

        mock_error = MagicMock()
        mock_error.resp.status = 404
        mock_drive_service.files.return_value.export_media.return_value.execute.side_effect = (
            HttpError(mock_error, b"Not Found")
        )

        async with _sm(admin_engine)() as db:
            with pytest.raises(DocumentNotFoundError):
                await service.sincronizar_google_doc(
                    db, cred=cred, google_doc_id="nonexistent-id"
                )


@pytest.mark.asyncio
async def test_exportar_google_doc_como_pdf_success(admin_engine):
    """Exportar Google Doc como PDF."""
    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    mock_pdf_bytes = b"%PDF-1.4\n..."  # Fake PDF magic bytes

    with patch("app.services.google_docs_service.build") as mock_build:
        mock_drive_service = MagicMock()
        mock_build.return_value = mock_drive_service

        mock_export = MagicMock()
        mock_drive_service.files.return_value.export_media.return_value = mock_export
        mock_export.execute.return_value = mock_pdf_bytes

        async with _sm(admin_engine)() as db:
            result = await service.exportar_google_doc_como_pdf(
                db, cred=cred, google_doc_id="doc-id-123"
            )

            assert result == mock_pdf_bytes


@pytest.mark.asyncio
async def test_arquivar_google_doc_success(admin_engine):
    """Arquivar (mover para lixo) Google Doc."""
    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    with patch("app.services.google_docs_service.build") as mock_build:
        mock_drive_service = MagicMock()
        mock_build.return_value = mock_drive_service

        mock_update = MagicMock()
        mock_drive_service.files.return_value.update.return_value = mock_update
        mock_update.execute.return_value = {}

        async with _sm(admin_engine)() as db:
            await service.arquivar_google_doc(
                db, cred=cred, google_doc_id="doc-id-123"
            )

            # Verify update was called with trashed=True
            mock_drive_service.files.return_value.update.assert_called_once()
            call_kwargs = (
                mock_drive_service.files.return_value.update.call_args.kwargs
            )
            assert call_kwargs.get("body", {}).get("trashed") is True


@pytest.mark.asyncio
async def test_arquivar_google_doc_404_ignores_error(admin_engine):
    """Arquivar doc não encontrado não falha (idempotente)."""
    from googleapiclient.errors import HttpError

    tenant, admin_id = await _provisionar(admin_engine)
    cred = await _criar_credencial(admin_engine, tenant.id, usuario_id=admin_id)
    service = GoogleDocsService()

    with patch("app.services.google_docs_service.build") as mock_build:
        mock_drive_service = MagicMock()
        mock_build.return_value = mock_drive_service

        mock_error = MagicMock()
        mock_error.resp.status = 404
        mock_drive_service.files.return_value.update.return_value.execute.side_effect = (
            HttpError(mock_error, b"Not Found")
        )

        async with _sm(admin_engine)() as db:
            # Should not raise
            await service.arquivar_google_doc(
                db, cred=cred, google_doc_id="nonexistent-id"
            )
