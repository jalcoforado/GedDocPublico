"""Google OAuth flow orchestration service (PR-F Phases 4-5).

Handles state generation, authorization code exchange, and credential storage.
Tokens are encrypted at rest using Fernet cipher.
"""
from __future__ import annotations

import json
import logging
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from google_auth_oauthlib.flow import Flow
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..core.crypto import encrypt
from ..models.google_credencial import GoogleCredencial

logger = logging.getLogger("google_oauth")

STATE_TTL_SECONDS = 300  # 5 minutes


class GoogleOAuthFlow:
    """Orchestrates Google OAuth flow: URL generation and callback handling."""

    def __init__(self, redis_client: Redis):
        """Initialize with Redis client for state storage."""
        self.redis = redis_client
        settings = get_settings()
        self.client_id = settings.google_oauth_client_id
        self.client_secret = settings.google_oauth_client_secret
        self.redirect_uri = settings.google_oauth_redirect_uri
        self.scopes = ["https://www.googleapis.com/auth/drive.file"]
        self._secrets_file = None

    def _get_secrets_file(self) -> str:
        """Get or create temporary secrets file with OAuth credentials."""
        if self._secrets_file is None:
            secrets_dict = {
                "installed": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": [self.redirect_uri],
                }
            }
            # Create temporary file for secrets
            fd, path = tempfile.mkstemp(suffix=".json", text=True)
            try:
                with open(fd, "w") as f:
                    json.dump(secrets_dict, f)
                self._secrets_file = path
            except Exception as e:
                logger.error(f"Failed to create secrets file: {e}")
                raise
        return self._secrets_file

    async def generate_oauth_url(
        self, user_id: int, tenant_id: int, minuta_id: int, processo_id: int
    ) -> str:
        """Generate OAuth URL and save state to Redis.

        Args:
            user_id: ID of the user initiating OAuth flow
            tenant_id: ID of the tenant
            minuta_id: ID da minuta sendo editada — 0 quando o usuário está só
                conectando a conta Google, ainda sem nenhuma minuta criada.
            processo_id: ID do processo associado — usado pelo callback para
                saber pra onde voltar quando minuta_id vier 0.

        Returns:
            Full OAuth authorization URL

        Raises:
            ValueError: If OAuth is not configured
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Google OAuth não está configurado")

        # Generate unique state
        state = str(uuid.uuid4())

        # Store context in Redis with 5-minute TTL
        context = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "minuta_id": minuta_id,
            "processo_id": processo_id,
        }
        await self.redis.setex(
            f"oauth_state:{state}",
            STATE_TTL_SECONDS,
            json.dumps(context),
        )

        # Build OAuth flow using secrets file
        secrets_file = self._get_secrets_file()
        flow = Flow.from_client_secrets_file(
            secrets_file,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri,
        )

        # Generate authorization URL with offline access and consent prompt
        auth_url, _ = flow.authorization_url(
            state=state, access_type="offline", prompt="consent"
        )

        return auth_url

    async def handle_callback(
        self, code: str, state: str, db: AsyncSession | None = None
    ) -> dict:
        """Exchange authorization code for tokens and save credentials.

        Args:
            code: Authorization code from Google
            state: State parameter to validate
            db: Database session for storing credentials (optional for tests)

        Returns:
            Dictionary with keys: user_id, tenant_id, minuta_id, processo_id

        Raises:
            ValueError: If state is expired, code is invalid, or exchange fails
        """
        # Validate state exists in Redis
        state_key = f"oauth_state:{state}"
        context_json = await self.redis.get(state_key)

        if not context_json:
            raise ValueError("Sessão expirou")

        # Parse context
        try:
            context = json.loads(context_json)
        except (json.JSONDecodeError, TypeError):
            await self.redis.delete(state_key)
            raise ValueError("Sessão inválida")

        # Exchange code for tokens
        try:
            secrets_file = self._get_secrets_file()
            flow = Flow.from_client_secrets_file(
                secrets_file,
                scopes=self.scopes,
                redirect_uri=self.redirect_uri,
                state=state,
            )
            flow.fetch_token(code=code)
        except Exception as e:
            logger.error(f"OAuth token exchange failed: {e}")
            await self.redis.delete(state_key)
            raise ValueError(f"Google negou a autorização: {str(e)[:100]}")

        # Save credentials to database if session provided
        if db:
            try:
                user_id = context["user_id"]
                tenant_id = context["tenant_id"]

                # Get encrypted tokens
                access_token = flow.credentials.token
                refresh_token = flow.credentials.refresh_token

                if not access_token:
                    raise ValueError("Acesso não autorizado pelo Google")

                # Encrypt tokens
                access_token_cifrado = encrypt(access_token)
                refresh_token_cifrado = (
                    encrypt(refresh_token) if refresh_token else encrypt("")
                )

                # Calculate expiration
                if flow.credentials.expiry:
                    expira_em = flow.credentials.expiry
                else:
                    expira_em = datetime.utcnow() + timedelta(hours=1)

                # Revoke old credentials
                stmt = (
                    update(GoogleCredencial)
                    .where(
                        GoogleCredencial.tenant_id == tenant_id,
                        GoogleCredencial.id_usuario == user_id,
                        GoogleCredencial.revogado == False,
                    )
                    .values(revogado=True)
                )
                await db.execute(stmt)

                # Create new credential record
                new_cred = GoogleCredencial(
                    tenant_id=tenant_id,
                    id_usuario=user_id,
                    access_token_cifrado=access_token_cifrado,
                    refresh_token_cifrado=refresh_token_cifrado,
                    escopo="drive.file",
                    expira_em=expira_em,
                    criado_em=datetime.utcnow(),
                    revogado=False,
                )
                db.add(new_cred)
                await db.commit()

                logger.info(
                    f"OAuth credentials stored for user {user_id} tenant {tenant_id}"
                )
            except ValueError:
                raise
            except Exception as e:
                logger.error(f"Failed to store OAuth credentials: {e}")
                raise ValueError(f"Falha ao salvar credenciais: {str(e)[:100]}")

        # Clean up state from Redis
        await self.redis.delete(state_key)

        return context
