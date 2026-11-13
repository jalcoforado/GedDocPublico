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
        mock_flow.from_client_config.return_value.fetch_token.side_effect = Exception(
            "invalid_grant"
        )

        with pytest.raises(ValueError, match="Google negou"):
            await service.handle_callback("bad_code", state)


# ---------------------------------------------------------------- SI-32
# PKCE ligado: a URL leva o code_challenge e o code_verifier tem de chegar ao
# Flow do callback — sem ele o Google recusa a troca ("Missing code verifier").


@pytest.mark.asyncio
async def test_si32_url_leva_code_challenge_e_verifier_fica_no_state(redis_client: Redis):
    from app.services.google_oauth_flow import GoogleOAuthFlow

    url = await GoogleOAuthFlow(redis_client).generate_oauth_url(
        user_id=1, tenant_id=1, minuta_id=0, processo_id=7
    )
    assert "code_challenge=" in url and "code_challenge_method=S256" in url
    (chave,) = await redis_client.keys("oauth_state:*")
    ctx = json.loads(await redis_client.get(chave))
    assert len(ctx["code_verifier"]) >= 43  # RFC 7636
    # O verifier é segredo: nunca na URL que vai para o navegador.
    assert ctx["code_verifier"] not in url


@pytest.mark.asyncio
async def test_si32_callback_devolve_o_verifier_ao_flow(redis_client: Redis):
    from app.services import google_oauth_flow as mod

    servico = mod.GoogleOAuthFlow(redis_client)
    await servico.generate_oauth_url(user_id=5, tenant_id=2, minuta_id=0, processo_id=9)
    (chave,) = await redis_client.keys("oauth_state:*")
    state = chave.decode().split(":", 1)[1] if isinstance(chave, bytes) else chave.split(":", 1)[1]
    verifier = json.loads(await redis_client.get(chave))["code_verifier"]

    vistos: list[dict] = []
    real = mod.Flow.from_client_config

    def espiao(config, **kw):
        vistos.append(kw)
        flow = real(config, **kw)
        flow.fetch_token = lambda **_: None  # sem rede
        return flow

    with patch.object(mod.Flow, "from_client_config", side_effect=espiao):
        ctx = await servico.handle_callback("codigo", state, usuario_id=5, tenant_id=2)

    assert vistos[-1]["code_verifier"] == verifier
    assert vistos[-1]["state"] == state
    assert "code_verifier" not in ctx  # o router não precisa (nem deve) ver
    assert ctx["processo_id"] == 9
    assert await redis_client.get(chave) is None  # uso único


@pytest.mark.asyncio
async def test_si32_state_de_outro_usuario_e_recusado_antes_da_troca(redis_client: Redis):
    from app.services import google_oauth_flow as mod

    servico = mod.GoogleOAuthFlow(redis_client)
    await servico.generate_oauth_url(user_id=5, tenant_id=2, minuta_id=0, processo_id=9)
    (chave,) = await redis_client.keys("oauth_state:*")
    state = chave.decode().split(":", 1)[1] if isinstance(chave, bytes) else chave.split(":", 1)[1]

    with patch.object(mod.Flow, "from_client_config") as flow:
        with pytest.raises(mod.OutroUsuarioError):
            await servico.handle_callback("codigo", state, usuario_id=6, tenant_id=2)
        with pytest.raises(ValueError, match="Sessão expirou"):
            # o state foi descartado: nem o dono consegue reaproveitar
            await servico.handle_callback("codigo", state, usuario_id=5, tenant_id=2)
    flow.assert_not_called()  # nenhuma troca de código com o Google


@pytest.mark.asyncio
async def test_si32_sem_client_id_nao_esta_configurado(redis_client: Redis, monkeypatch):
    from app.services import google_oauth_flow as mod

    servico = mod.GoogleOAuthFlow(redis_client)
    monkeypatch.setattr(servico, "client_id", "")
    assert servico.configurado is False
    with pytest.raises(ValueError, match="não está configurado"):
        await servico.generate_oauth_url(user_id=1, tenant_id=1, minuta_id=0, processo_id=1)


def test_si32_client_secret_nao_vai_para_arquivo_temporario():
    """O secret era gravado num .json em /tmp a cada requisição e nunca
    apagado. O Flow nasce em memória (from_client_config)."""
    import inspect

    from app.services import google_oauth_flow as mod

    fonte = inspect.getsource(mod)
    assert "tempfile" not in fonte and "from_client_secrets_file" not in fonte


@pytest.mark.asyncio
async def test_si32_valor_de_exemplo_ou_sem_chave_de_cifra_conta_como_desligado(
    redis_client: Redis, monkeypatch
):
    from app.services import google_oauth_flow as mod

    servico = mod.GoogleOAuthFlow(redis_client)
    assert servico.configurado is True  # ambiente de teste: tudo preenchido

    monkeypatch.setattr(servico, "client_id", "YOUR_CLIENT_ID.apps.googleusercontent.com")
    assert servico.configurado is False  # .env.example copiado sem trocar

    servico2 = mod.GoogleOAuthFlow(redis_client)
    monkeypatch.setattr(servico2, "_tem_chave_cifra", False)
    assert servico2.configurado is False  # autorizaria e não conseguiria gravar
