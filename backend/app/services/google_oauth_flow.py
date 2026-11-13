"""Google OAuth flow orchestration service (PR-F Phases 4-5; SI-32).

Handles state generation, authorization code exchange, and credential storage.
Tokens are encrypted at rest using Fernet cipher.

SI-32 — o que mudou:

- **PKCE ligado, com o verifier guardado.** O Google recomenda PKCE também
  para app web. Ligado explicitamente aqui: a URL leva o `code_challenge` e o
  `code_verifier` viaja no contexto do `state` (Redis, 5 min, uso único) até o
  `Flow` do callback. Antes, cada ponta montava um `Flow` novo e nada passava
  de uma para a outra — na 1.2.0 (fixada) o PKCE vem desligado e isso passava;
  numa versão que o ligue por padrão, toda conexão quebraria com
  "invalid_grant: Missing code verifier".
- **Sem arquivo temporário.** O client secret era gravado num `.json` em /tmp
  a cada requisição e nunca apagado. O `Flow` agora nasce de
  `from_client_config`, em memória.
- **Quem começou é quem termina.** O callback recebe o usuário da sessão e
  recusa um `state` de outro usuário/tenant ANTES de trocar o código — senão a
  credencial de quem autorizou no Google ficaria gravada para quem gerou o
  link.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta

from google_auth_oauthlib.flow import Flow
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..core.crypto import encrypt
from ..models.google_credencial import GoogleCredencial

logger = logging.getLogger("google_oauth")

STATE_TTL_SECONDS = 300  # 5 minutes


class OutroUsuarioError(ValueError):
    """O `state` foi gerado por outro usuário/tenant que não o da sessão."""


class GoogleOAuthFlow:
    """Orchestrates Google OAuth flow: URL generation and callback handling."""

    def __init__(self, redis_client: Redis):
        """Initialize with Redis client for state storage."""
        self.redis = redis_client
        settings = get_settings()
        self.client_id = settings.google_oauth_client_id
        self.client_secret = settings.google_oauth_client_secret
        self.redirect_uri = settings.google_oauth_redirect_uri
        self._tem_chave_cifra = bool(settings.dados_sensiveis_encryption_key)
        self.scopes = ["https://www.googleapis.com/auth/drive.file"]

    @property
    def configurado(self) -> bool:
        """Client ID e secret presentes — sem eles não há como falar com o Google.

        O valor de exemplo do `.env.example` ("YOUR_CLIENT_ID...") conta como
        ausente: copiado sem trocar, levava ao "invalid_client" do Google em
        vez de à mensagem de "não configurado".

        Sem a chave de cifra (`DADOS_SENSIVEIS_ENCRYPTION_KEY`) também não: o
        usuário autorizaria no Google e o token não teria como ser gravado.
        """
        def real(v: str) -> bool:
            return bool(v) and not v.upper().startswith("YOUR_")

        return real(self.client_id) and real(self.client_secret) and self._tem_chave_cifra

    def _flow(self, *, state: str | None = None, code_verifier: str | None = None) -> Flow:
        """`Flow` montado em memória (client "web" — é o tipo da credencial)."""
        config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri],
            }
        }
        kwargs: dict = {"scopes": self.scopes, "redirect_uri": self.redirect_uri}
        if state is not None:
            kwargs["state"] = state
        if code_verifier is not None:
            kwargs["code_verifier"] = code_verifier
        else:
            # Ida: a biblioteca gera o verifier (from_client_config não o faz
            # por padrão na 1.2.0).
            kwargs["autogenerate_code_verifier"] = True
        return Flow.from_client_config(config, **kwargs)

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
        if not self.configurado:
            raise ValueError("Google OAuth não está configurado")

        state = str(uuid.uuid4())
        flow = self._flow()
        # offline + consent: garante refresh token (o documento é editado dias
        # depois de criado). A biblioteca gera o code_verifier do PKCE aqui.
        auth_url, _ = flow.authorization_url(
            state=state, access_type="offline", prompt="consent"
        )

        # O verifier tem de chegar ao callback — sem ele o Google recusa a
        # troca do código. Fica no Redis com o resto do contexto (5 min, uso
        # único), nunca na URL.
        context = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "minuta_id": minuta_id,
            "processo_id": processo_id,
            "code_verifier": flow.code_verifier,
        }
        await self.redis.setex(
            f"oauth_state:{state}",
            STATE_TTL_SECONDS,
            json.dumps(context),
        )

        return auth_url

    async def ler_contexto(self, state: str) -> dict | None:
        """Contexto do `state` sem consumi-lo (para o callback saber o processo
        de volta mesmo quando o Google devolve erro)."""
        bruto = await self.redis.get(f"oauth_state:{state}")
        if not bruto:
            return None
        try:
            ctx = json.loads(bruto)
        except (json.JSONDecodeError, TypeError):
            return None
        ctx.pop("code_verifier", None)
        return ctx

    async def descartar_state(self, state: str) -> None:
        await self.redis.delete(f"oauth_state:{state}")

    async def handle_callback(
        self,
        code: str,
        state: str,
        db: AsyncSession | None = None,
        *,
        usuario_id: int | None = None,
        tenant_id: int | None = None,
    ) -> dict:
        """Exchange authorization code for tokens and save credentials.

        Args:
            code: Authorization code from Google
            state: State parameter to validate
            db: Database session for storing credentials (optional for tests)
            usuario_id / tenant_id: quem está na sessão do navegador que voltou
                do Google. Informados, têm de ser os mesmos que geraram o state.

        Returns:
            Dictionary with keys: user_id, tenant_id, minuta_id, processo_id

        Raises:
            OutroUsuarioError: state de outro usuário/tenant (nada é gravado)
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

        code_verifier = context.pop("code_verifier", None)

        # Quem começou é quem termina — conferido ANTES de trocar o código.
        if (usuario_id is not None and context.get("user_id") != usuario_id) or (
            tenant_id is not None and context.get("tenant_id") != tenant_id
        ):
            await self.redis.delete(state_key)
            logger.warning(
                "OAuth state de outro usuário: state de %s/%s, sessão de %s/%s",
                context.get("user_id"), context.get("tenant_id"), usuario_id, tenant_id,
            )
            raise OutroUsuarioError("Sessão de outro usuário")

        # Exchange code for tokens
        try:
            flow = self._flow(state=state, code_verifier=code_verifier)
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
