"""Testes para GoogleOAuthFlow service (PR-F Phases 4-5).

Cobre: state generation, OAuth URL creation, authorization code exchange,
token encryption, credential storage, and error handling.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
from redis.asyncio import Redis


@pytest.mark.asyncio
async def test_generate_oauth_url_success(redis_client: Redis):
    """Generate OAuth URL + save state to Redis."""
    from app.services.google_oauth_flow import GoogleOAuthFlow

    service = GoogleOAuthFlow(redis_client)

    url = await service.generate_oauth_url(
        user_id=123,
        tenant_id=1,
        minuta_id=456,
        processo_id=789,
    )

    assert "https://accounts.google.com/o/oauth2/v2/auth" in url
    assert "drive.file" in url
    # Verify state is in Redis
    keys = await redis_client.keys("oauth_state:*")
    assert len(keys) == 1

    # Regressão: processo_id era recebido pela rota mas nunca chegava a ser
    # gravado no contexto do state — o callback não tinha como saber pra
    # onde voltar quando minuta_id vier 0 (usuário só conectando a conta).
    context = json.loads(await redis_client.get(keys[0]))
    assert context["processo_id"] == 789
    assert context["minuta_id"] == 456


@pytest.mark.asyncio
async def test_handle_callback_state_expired(redis_client: Redis):
    """State not in Redis → ValueError."""
    from app.services.google_oauth_flow import GoogleOAuthFlow

    service = GoogleOAuthFlow(redis_client)

    with pytest.raises(ValueError, match="Sessão expirou"):
        await service.handle_callback("auth_code", "invalid-state")


@pytest.mark.asyncio
async def test_handle_callback_invalid_code(redis_client: Redis):
    """Google API rejects code → ValueError."""
    from app.services.google_oauth_flow import GoogleOAuthFlow

    service = GoogleOAuthFlow(redis_client)

    # Setup state in Redis
    state = str(uuid.uuid4())
    context = {"user_id": 123, "tenant_id": 1, "minuta_id": 456}
    await redis_client.setex(
        f"oauth_state:{state}",
        300,
        json.dumps(context),
    )

    # Mock Flow to reject code
    with patch("app.services.google_oauth_flow.Flow") as mock_flow:
        mock_flow.from_client_secrets_file.return_value.fetch_token.side_effect = Exception(
            "invalid_grant"
        )

        with pytest.raises(ValueError, match="Google negou"):
            await service.handle_callback("bad_code", state)
