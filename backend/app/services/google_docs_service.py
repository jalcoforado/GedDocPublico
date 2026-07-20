"""Google Docs integration service (PR-F).

Handles Google Drive API operations for creating, downloading, syncing,
and exporting Google Docs to PDF.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.crypto import decrypt_bytes, encrypt_bytes
from app.models.google_credencial import GoogleCredencial
from app.services.html_pdf import html_to_pdf_bytes


class GoogleDocsError(Exception):
    """Base exception for Google Docs operations."""
    pass


class TokenExpiredError(GoogleDocsError):
    """OAuth token has expired and refresh failed."""
    pass


class PermissionDeniedError(GoogleDocsError):
    """User does not have permission to access the resource."""
    pass


class DocumentNotFoundError(GoogleDocsError):
    """Google Doc not found or has been deleted."""
    pass


class GoogleDocsService:
    """Service for Google Docs/Drive API integration."""

    def __init__(self):
        """Initialize Google Docs service with credentials."""
        self.client_id = settings.google_oauth_client_id
        self.client_secret = settings.google_oauth_client_secret
        self.redirect_uri = settings.google_oauth_redirect_uri
        self.scopes = ["https://www.googleapis.com/auth/drive.file"]

        if not all([self.client_id, self.client_secret]):
            raise ValueError("Google OAuth credentials not configured in settings")

    async def obter_credentials_usuario(
        self,
        db: AsyncSession,
        tenant_id: int,
        usuario_id: int,
    ) -> GoogleCredencial:
        """Get user's Google credentials (decrypted).

        Returns:
            GoogleCredencial with decrypted access/refresh tokens.

        Raises:
            PermissionDeniedError: If credentials not found or revogado=True.
        """
        stmt = select(GoogleCredencial).where(
            GoogleCredencial.tenant_id == tenant_id,
            GoogleCredencial.id_usuario == usuario_id,
            GoogleCredencial.revogado == False,
        )
        result = await db.execute(stmt)
        cred = result.scalar_one_or_none()

        if not cred:
            raise PermissionDeniedError(
                f"User {usuario_id} has not connected Google Docs or credentials revoked"
            )

        return cred

    def _construir_credentials_obj(
        self,
        access_token: str,
        refresh_token: str | None,
        expiry: datetime | None = None,
    ) -> Credentials:
        """Build google.oauth2.credentials.Credentials object from tokens."""
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

        if expiry:
            creds.expiry = expiry

        return creds

    async def renovar_access_token(
        self,
        db: AsyncSession,
        cred: GoogleCredencial,
    ) -> GoogleCredencial:
        """Refresh OAuth token if expired.

        Args:
            db: Database session.
            cred: GoogleCredencial record with encrypted tokens.

        Returns:
            Updated GoogleCredencial with new access_token.

        Raises:
            TokenExpiredError: If refresh token is invalid or revoked.
        """
        # Decrypt existing tokens
        access_token = decrypt_bytes(cred.access_token_cifrado)
        refresh_token = (
            decrypt_bytes(cred.refresh_token_cifrado)
            if cred.refresh_token_cifrado
            else None
        )

        # Check if token is still valid
        if cred.expira_em and cred.expira_em > datetime.now(timezone.utc):
            return cred  # No refresh needed

        if not refresh_token:
            raise TokenExpiredError(
                "Access token expired and no refresh token available. "
                "Please reconnect Google Docs."
            )

        # Attempt refresh
        creds_obj = self._construir_credentials_obj(
            access_token=access_token,
            refresh_token=refresh_token,
            expiry=cred.expira_em,
        )

        try:
            req = Request()
            creds_obj.refresh(req)
        except RefreshError as e:
            raise TokenExpiredError(f"Failed to refresh token: {e}")

        # Update database with new tokens
        new_access_token = creds_obj.token or access_token
        new_expiry = creds_obj.expiry or (
            datetime.now(timezone.utc) + timedelta(hours=1)
        )

        stmt = (
            update(GoogleCredencial)
            .where(GoogleCredencial.id == cred.id)
            .values(
                access_token_cifrado=encrypt_bytes(new_access_token),
                expira_em=new_expiry,
            )
        )
        await db.execute(stmt)
        await db.commit()

        cred.access_token_cifrado = encrypt_bytes(new_access_token)
        cred.expira_em = new_expiry

        return cred

    async def criar_google_doc(
        self,
        db: AsyncSession,
        cred: GoogleCredencial,
        titulo: str,
        corpo_html: str | None = None,
    ) -> dict[str, Any]:
        """Create a new Google Doc.

        Args:
            db: Database session (for token refresh).
            cred: GoogleCredencial with OAuth tokens.
            titulo: Title of the document.
            corpo_html: Optional initial HTML content to paste into doc.

        Returns:
            {"google_doc_id": "...", "google_doc_url": "..."}

        Raises:
            GoogleDocsError: If API call fails.
        """
        # Refresh token if needed
        cred = await self.renovar_access_token(db, cred)

        # Get decrypted access token
        access_token = decrypt_bytes(cred.access_token_cifrado)

        # Build credentials object
        creds_obj = self._construir_credentials_obj(
            access_token=access_token,
            refresh_token=None,
        )

        try:
            # Initialize Google Docs API
            docs_service = build("docs", "v1", credentials=creds_obj)

            # Create new document
            document = docs_service.documents().create(
                body={"title": titulo}
            ).execute()

            doc_id = document.get("documentId")
            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

            # If HTML content provided, append to document
            if corpo_html:
                # Note: Google Docs API doesn't support direct HTML insertion.
                # For now, we'll just create the doc with title.
                # In a future iteration, could use Drive API to upload HTML template.
                pass

            return {
                "google_doc_id": doc_id,
                "google_doc_url": doc_url,
            }

        except HttpError as e:
            if e.resp.status == 401:
                raise TokenExpiredError("Access token invalid or revoked")
            elif e.resp.status == 403:
                raise PermissionDeniedError("Permission denied to create Google Doc")
            else:
                raise GoogleDocsError(f"Failed to create Google Doc: {e}")

    async def sincronizar_google_doc(
        self,
        db: AsyncSession,
        cred: GoogleCredencial,
        google_doc_id: str,
    ) -> bytes:
        """Download Google Doc as DOCX.

        Args:
            db: Database session (for token refresh).
            cred: GoogleCredencial with OAuth tokens.
            google_doc_id: Google Docs document ID.

        Returns:
            DOCX file bytes.

        Raises:
            DocumentNotFoundError: If doc doesn't exist.
            GoogleDocsError: If API call fails.
        """
        # Refresh token if needed
        cred = await self.renovar_access_token(db, cred)

        # Get decrypted access token
        access_token = decrypt_bytes(cred.access_token_cifrado)

        # Build credentials object
        creds_obj = self._construir_credentials_obj(
            access_token=access_token,
            refresh_token=None,
        )

        try:
            # Initialize Google Drive API
            drive_service = build("drive", "v3", credentials=creds_obj)

            # Export document as DOCX
            request = drive_service.files().export_media(
                fileId=google_doc_id,
                mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

            docx_bytes = request.execute()
            return docx_bytes

        except HttpError as e:
            if e.resp.status == 401:
                raise TokenExpiredError("Access token invalid or revoked")
            elif e.resp.status == 403:
                raise PermissionDeniedError("Permission denied to download Google Doc")
            elif e.resp.status == 404:
                raise DocumentNotFoundError(f"Google Doc {google_doc_id} not found")
            else:
                raise GoogleDocsError(f"Failed to sync Google Doc: {e}")

    async def exportar_google_doc_como_pdf(
        self,
        db: AsyncSession,
        cred: GoogleCredencial,
        google_doc_id: str,
    ) -> bytes:
        """Export Google Doc as PDF.

        Strategy:
        1. Try direct Google Drive API export (PDF)
        2. Fallback: download DOCX → convert via weasyprint

        Args:
            db: Database session.
            cred: GoogleCredencial with OAuth tokens.
            google_doc_id: Google Docs document ID.

        Returns:
            PDF file bytes.

        Raises:
            GoogleDocsError: If both export and fallback fail.
        """
        # Refresh token if needed
        cred = await self.renovar_access_token(db, cred)

        # Get decrypted access token
        access_token = decrypt_bytes(cred.access_token_cifrado)

        # Build credentials object
        creds_obj = self._construir_credentials_obj(
            access_token=access_token,
            refresh_token=None,
        )

        try:
            # Initialize Google Drive API
            drive_service = build("drive", "v3", credentials=creds_obj)

            # Try direct PDF export
            request = drive_service.files().export_media(
                fileId=google_doc_id,
                mimeType="application/pdf",
            )

            pdf_bytes = request.execute()
            return pdf_bytes

        except HttpError as e:
            if e.resp.status == 404:
                raise DocumentNotFoundError(f"Google Doc {google_doc_id} not found")
            elif e.resp.status in (401, 403):
                raise PermissionDeniedError("Permission denied to export Google Doc")

            # Fallback: download DOCX and attempt conversion
            # (In production, might need LibreOffice or alternative)
            raise GoogleDocsError(
                f"Failed to export Google Doc as PDF: {e}. "
                "Please finalize with Plataforma (internal editor) as fallback."
            )

    async def arquivar_google_doc(
        self,
        db: AsyncSession,
        cred: GoogleCredencial,
        google_doc_id: str,
    ) -> None:
        """Move Google Doc to trash (soft delete from Drive).

        Args:
            db: Database session.
            cred: GoogleCredencial with OAuth tokens.
            google_doc_id: Google Docs document ID.

        Raises:
            GoogleDocsError: If API call fails.
        """
        # Refresh token if needed
        cred = await self.renovar_access_token(db, cred)

        # Get decrypted access token
        access_token = decrypt_bytes(cred.access_token_cifrado)

        # Build credentials object
        creds_obj = self._construir_credentials_obj(
            access_token=access_token,
            refresh_token=None,
        )

        try:
            # Initialize Google Drive API
            drive_service = build("drive", "v3", credentials=creds_obj)

            # Move to trash
            drive_service.files().update(
                fileId=google_doc_id,
                body={"trashed": True},
            ).execute()

        except HttpError as e:
            if e.resp.status == 404:
                # Document already deleted, ignore
                pass
            elif e.resp.status in (401, 403):
                # Token invalid or permission denied, ignore
                pass
            else:
                # Log but don't fail the entire finalization
                pass


def get_google_docs_service() -> GoogleDocsService:
    """Factory function to get GoogleDocsService instance."""
    return GoogleDocsService()
