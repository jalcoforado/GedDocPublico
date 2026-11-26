"""Login do servidor com a conta Google (SI-32 — `routers/auth_google_login.py`,
`services/google_login.py`).

Sem rede e sem credencial: o Google é simulado por `GoogleFalso`, servido a
`google_login._cliente_http` por um `httpx.MockTransport`. O falso se comporta
como o provedor, não como o código testado: guarda o `nonce` e o
`code_challenge` recebidos na autorização, amarra o e-mail ao `code` do lado
DELE, recusa `code_verifier` que não bata com o challenge e assina o `id_token`
com uma chave RSA efêmera publicada no seu JWKS. Assim, o e-mail que decide
quem entra só pode ter vindo do `id_token` — nunca da URL.
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import text

from app.main import app
from app.services import google_login
from tests.conftest import arreio_tenant_http, provisionar_tenant_de_teste
from tests.fixtures.platform_operator_tokens import gerar_chaves

CLIENT_ID = "aprimora-google-teste.apps.googleusercontent.com"
CLIENT_SECRET = "segredo-de-teste"
REDIRECT_MINUTAS = "http://localhost:8090/api/v2/auth/google/callback"
REDIRECT_LOGIN = "http://localhost:8090/api/v2/auth/google-login/callback"


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class GoogleFalso:
    """Provedor OIDC em memória. Registra o que recebeu para as asserções."""

    def __init__(self) -> None:
        self.chaves = gerar_chaves(kid="google-teste-1")
        self.chaves_atacante = gerar_chaves(kid="google-teste-1")  # mesmo kid, outra chave
        self.pendentes: dict[str, dict] = {}
        self.chamadas_token = 0
        # Ajustes por teste
        self.assinar_com_atacante = False
        self.hs256_com_client_secret = False
        self.nonce_forjado: str | None = None
        self.aud: str = CLIENT_ID
        self.iss: str = "https://accounts.google.com"
        self.email_verified = True

    def autorizar(self, location: str, *, email: str, nome: str = "Servidora Google") -> dict:
        """O usuário escolhe a conta no Google; devolve os params da autorização."""
        u = urlparse(location)
        assert f"{u.scheme}://{u.netloc}{u.path}" == google_login.URL_AUTORIZACAO
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        code = uuid.uuid4().hex
        self.pendentes[code] = {**q, "email": email, "nome": nome}
        q["code"] = code
        return q

    def _id_token(self, p: dict, access_token: str) -> str:
        agora = int(time.time())
        claims = {
            "iss": self.iss,
            "aud": self.aud,
            "azp": self.aud,
            "sub": f"1{abs(hash(p['email'])) % 10**20}",
            "iat": agora,
            "exp": agora + 300,
            "nonce": self.nonce_forjado or p["nonce"],
            "at_hash": _b64u(hashlib.sha256(access_token.encode()).digest()[:16]),
            "email": p["email"],
            "email_verified": self.email_verified,
            "name": p["nome"],
        }
        if self.hs256_com_client_secret:
            return jwt.encode(claims, CLIENT_SECRET, algorithm="HS256",
                              headers={"kid": self.chaves.kid})
        chave = self.chaves_atacante if self.assinar_com_atacante else self.chaves
        return jwt.encode(claims, chave.private_pem, algorithm="RS256", headers={"kid": chave.kid})

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and url == google_login.URL_TOKEN:
            self.chamadas_token += 1
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if form.get("client_id") != CLIENT_ID or form.get("client_secret") != CLIENT_SECRET:
                return httpx.Response(401, json={"error": "invalid_client"})
            p = self.pendentes.pop(form.get("code", ""), None)
            if p is None or form.get("grant_type") != "authorization_code":
                return httpx.Response(400, json={"error": "invalid_grant"})
            if form.get("redirect_uri") != p["redirect_uri"]:
                return httpx.Response(400, json={"error": "redirect_uri_mismatch"})
            desafio = _b64u(hashlib.sha256(form.get("code_verifier", "").encode()).digest())
            if p.get("code_challenge_method") != "S256" or desafio != p["code_challenge"]:
                return httpx.Response(400, json={"error": "invalid_grant", "d": "pkce"})
            access = f"ya29.{uuid.uuid4().hex}"
            return httpx.Response(
                200,
                json={"access_token": access, "id_token": self._id_token(p, access),
                      "token_type": "Bearer", "expires_in": 3599},
            )
        if request.method == "GET" and url == google_login.URL_JWKS:
            return httpx.Response(200, json=self.chaves.jwks)
        return httpx.Response(404)


def _configurar(monkeypatch, *, client_id: str = CLIENT_ID, secret: str = CLIENT_SECRET):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", client_id)
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", secret)
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", REDIRECT_MINUTAS)
    monkeypatch.setenv("GOOGLE_LOGIN_REDIRECT_URI", "")
    get_settings.cache_clear()


@pytest.fixture
def google(monkeypatch):
    from app.config import get_settings

    _configurar(monkeypatch)
    falso = GoogleFalso()
    monkeypatch.setattr(
        google_login,
        "_cliente_http",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(falso.handler)),
    )
    yield falso
    get_settings.cache_clear()


@pytest.fixture
def google_desligado(monkeypatch):
    from app.config import get_settings

    _configurar(monkeypatch, client_id="", secret="")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def tenants(admin_engine):
    a = await provisionar_tenant_de_teste(admin_engine, "glogin-a-")
    b = await provisionar_tenant_de_teste(admin_engine, "glogin-b-")
    try:
        yield a, b
    finally:
        from app.database import engine as app_engine

        app.dependency_overrides.clear()
        await app_engine.dispose()


async def _servidor(engine, tenant, *, must_change=False, ativo=True, verificado=True) -> str:
    """Deixa o admin que o provisionamento criou no estado pedido; devolve o e-mail."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE utils.usuario SET must_change_password=:m, ativo=:a, "
                "email_verificado_em = CASE WHEN :v THEN NOW() ELSE NULL END "
                "WHERE tenant_id=:t"
            ),
            {"m": must_change, "a": ativo, "v": verificado, "t": tenant.id},
        )
        email = (
            await conn.execute(
                text("SELECT email FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                {"t": tenant.id},
            )
        ).scalar_one()
    return email


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _fluxo(client, falso, tenant, *, email, next_=None):
    """Login completo: /inicio → Google falso → /callback. Devolve a resposta final."""
    arreio_tenant_http(tenant.id, tenant.slug)
    params = {"next": next_} if next_ is not None else {}
    r = await client.get("/api/v2/auth/google-login/inicio", params=params)
    assert r.status_code == 302, r.text
    q = falso.autorizar(r.headers["location"], email=email)
    return await client.get(
        "/api/v2/auth/google-login/callback", params={"code": q["code"], "state": q["state"]}
    )


def _motivo(r) -> str | None:
    loc = urlparse(r.headers.get("location", ""))
    if loc.path != "/login":
        return None
    return parse_qs(loc.query).get("google", [None])[0]


# ---------------------------------------------------------------------------
# Configuração ausente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sem_configuracao_botao_some_e_rotas_voltam_ao_login(google_desligado, tenants):
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        disp = await c.get("/api/v2/auth/google-login/disponivel")
        branding = await c.get("/api/v2/branding/me")
        r1 = await c.get("/api/v2/auth/google-login/inicio")
        r2 = await c.get("/api/v2/auth/google-login/callback", params={"code": "x", "state": "y"})
    assert disp.json() == {"disponivel": False}
    assert branding.status_code == 200 and branding.json()["login_google"] is False
    assert r1.status_code == 302 and _motivo(r1) == "indisponivel"
    assert r2.status_code == 302 and _motivo(r2) == "indisponivel"
    assert "aprimora_token" not in r2.cookies


@pytest.mark.asyncio
async def test_valor_de_exemplo_do_env_conta_como_desligado(monkeypatch, tenants):
    _configurar(monkeypatch, client_id="YOUR_CLIENT_ID.apps.googleusercontent.com",
                secret="YOUR_CLIENT_SECRET")
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        disp = await c.get("/api/v2/auth/google-login/disponivel")
    assert disp.json() == {"disponivel": False}


@pytest.mark.asyncio
async def test_configurado_branding_mostra_o_botao(google, tenants):
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        branding = await c.get("/api/v2/branding/me")
    assert branding.json()["login_google"] is True


# ---------------------------------------------------------------------------
# /inicio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inicio_manda_ao_google_com_state_nonce_e_pkce(google, tenants):
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        r = await c.get("/api/v2/auth/google-login/inicio")
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith(google_login.URL_AUTORIZACAO + "?")
    q = {k: v[0] for k, v in parse_qs(urlparse(loc).query).items()}
    assert q["client_id"] == CLIENT_ID and q["response_type"] == "code"
    assert set(q["scope"].split()) == {"openid", "email", "profile"}
    # Derivado do endereço das minutas: mesmo host e porta, outro caminho.
    assert q["redirect_uri"] == REDIRECT_LOGIN
    assert len(q["state"]) >= 32 and len(q["nonce"]) >= 32 and q["state"] != q["nonce"]
    assert q["code_challenge_method"] == "S256" and q["code_challenge"]
    assert q["prompt"] == "select_account"
    set_cookie = r.headers["set-cookie"]
    assert google_login.COOKIE_ESTADO in set_cookie
    assert "HttpOnly" in set_cookie and f"Path={google_login.CAMINHO_COOKIE}" in set_cookie
    # O verifier do PKCE NÃO sai na URL — só o challenge.
    assert "code_verifier" not in loc


@pytest.mark.asyncio
async def test_redirect_uri_explicito_tem_precedencia(google, tenants, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("GOOGLE_LOGIN_REDIRECT_URI", "https://aprimora.exemplo.test/api/v2/auth/google-login/callback")
    get_settings.cache_clear()
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        r = await c.get("/api/v2/auth/google-login/inicio")
    q = {k: v[0] for k, v in parse_qs(urlparse(r.headers["location"]).query).items()}
    assert q["redirect_uri"] == "https://aprimora.exemplo.test/api/v2/auth/google-login/callback"


# ---------------------------------------------------------------------------
# Fluxo feliz
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_servidor_cadastrado_entra_com_a_sessao_do_login_por_senha(
    google, tenants, admin_engine
):
    a, _ = tenants
    email = await _servidor(admin_engine, a)
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email=email)
        assert r.status_code == 302, r.text
        assert r.headers["location"] == "/home"
        # A sessão é a do servidor (cookie `aprimora_token`), nunca a do cidadão.
        assert "aprimora_token" in r.cookies
        assert "aprimora_cidadao_token" not in r.cookies
        me = await c.get("/api/v2/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email


@pytest.mark.asyncio
async def test_next_interno_e_preservado_e_externo_recusado(google, tenants, admin_engine):
    a, _ = tenants
    email = await _servidor(admin_engine, a)
    async with _cliente() as c:
        r1 = await _fluxo(c, google, a, email=email, next_="/m/protocolo/processos?aba=1")
        r2 = await _fluxo(c, google, a, email=email, next_="//evil.example/roubo")
    assert r1.headers["location"] == "/m/protocolo/processos?aba=1"
    assert r2.headers["location"] == "/home"


@pytest.mark.asyncio
async def test_email_comparado_sem_caixa(google, tenants, admin_engine):
    a, _ = tenants
    email = await _servidor(admin_engine, a)
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email=email.upper())
    assert r.headers["location"] == "/home" and "aprimora_token" in r.cookies


@pytest.mark.asyncio
async def test_troca_obrigatoria_de_senha_tem_precedencia(google, tenants, admin_engine):
    a, _ = tenants
    email = await _servidor(admin_engine, a, must_change=True)
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email=email, next_="/m/protocolo")
    assert r.headers["location"] == "/alterar-senha-obrigatoria"


# ---------------------------------------------------------------------------
# Quem NÃO entra
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_conta_google_sem_cadastro_nao_entra_e_nada_e_criado(
    google, tenants, admin_engine, caplog
):
    a, _ = tenants
    await _servidor(admin_engine, a)
    caplog.set_level("INFO", logger="app.routers.auth_google_login")
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email="desconhecido@gmail.test")
    assert _motivo(r) == "sem_conta" and "aprimora_token" not in r.cookies
    # O log diz QUAL conta o Google devolveu (o suporte precisa), mascarada.
    [reg] = [x for x in caplog.records if x.getMessage() == "google_login_sem_usuario"]
    assert reg.email_google.startswith("de") and reg.email_google.endswith("@gmail.test")
    assert "desconhecido@" not in reg.email_google
    async with admin_engine.begin() as conn:
        n = (
            await conn.execute(
                text("SELECT count(*) FROM utils.usuario WHERE lower(email)=:e"),
                {"e": "desconhecido@gmail.test"},
            )
        ).scalar_one()
    assert n == 0


@pytest.mark.asyncio
async def test_servidor_de_outra_prefeitura_nao_entra(google, tenants, admin_engine):
    a, b = tenants
    await _servidor(admin_engine, a)
    email_b = await _servidor(admin_engine, b)
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email=email_b)
    assert _motivo(r) == "sem_conta" and "aprimora_token" not in r.cookies


@pytest.mark.asyncio
async def test_servidor_inativo_nao_entra(google, tenants, admin_engine):
    a, _ = tenants
    email = await _servidor(admin_engine, a, ativo=False)
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email=email)
    assert _motivo(r) == "sem_conta" and "aprimora_token" not in r.cookies


@pytest.mark.asyncio
async def test_convite_nao_aceito_nao_entra(google, tenants, admin_engine):
    a, _ = tenants
    email = await _servidor(admin_engine, a, verificado=False)
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email=email)
    assert _motivo(r) == "nao_ativada" and "aprimora_token" not in r.cookies


@pytest.mark.asyncio
async def test_email_google_nao_verificado_nao_entra(google, tenants, admin_engine):
    a, _ = tenants
    email = await _servidor(admin_engine, a)
    google.email_verified = False
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email=email)
    assert _motivo(r) == "email_nao_verificado" and "aprimora_token" not in r.cookies


@pytest.mark.asyncio
async def test_recusa_no_google_volta_como_cancelado(google, tenants, admin_engine):
    a, _ = tenants
    await _servidor(admin_engine, a)
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        r = await c.get("/api/v2/auth/google-login/inicio")
        q = {k: v[0] for k, v in parse_qs(urlparse(r.headers["location"]).query).items()}
        r2 = await c.get(
            "/api/v2/auth/google-login/callback",
            params={"error": "access_denied", "state": q["state"]},
        )
    assert _motivo(r2) == "cancelado"
    assert google.chamadas_token == 0


# ---------------------------------------------------------------------------
# Ataques ao fluxo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_sem_cookie_de_estado_e_recusado_sem_trocar_o_code(
    google, tenants, admin_engine
):
    """CSRF de login: o atacante manda a vítima ao callback com o code DELE."""
    a, _ = tenants
    email = await _servidor(admin_engine, a)
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as atacante:
        r = await atacante.get("/api/v2/auth/google-login/inicio")
        q = google.autorizar(r.headers["location"], email=email)
    async with _cliente() as vitima:
        r2 = await vitima.get(
            "/api/v2/auth/google-login/callback", params={"code": q["code"], "state": q["state"]}
        )
    assert _motivo(r2) == "expirou" and "aprimora_token" not in r2.cookies
    assert google.chamadas_token == 0


@pytest.mark.asyncio
async def test_state_que_nao_confere_e_recusado(google, tenants, admin_engine):
    a, _ = tenants
    email = await _servidor(admin_engine, a)
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        r = await c.get("/api/v2/auth/google-login/inicio")
        q = google.autorizar(r.headers["location"], email=email)
        r2 = await c.get(
            "/api/v2/auth/google-login/callback", params={"code": q["code"], "state": "outro"}
        )
    assert _motivo(r2) == "falhou" and "aprimora_token" not in r2.cookies
    assert google.chamadas_token == 0


@pytest.mark.asyncio
async def test_estado_de_outra_prefeitura_e_recusado(google, tenants, admin_engine):
    a, b = tenants
    await _servidor(admin_engine, a)
    email_b = await _servidor(admin_engine, b)
    async with _cliente() as c:
        arreio_tenant_http(a.id, a.slug)
        r = await c.get("/api/v2/auth/google-login/inicio")
        q = google.autorizar(r.headers["location"], email=email_b)
        # O callback chega ao host de B com o cookie iniciado em A.
        arreio_tenant_http(b.id, b.slug)
        r2 = await c.get(
            "/api/v2/auth/google-login/callback", params={"code": q["code"], "state": q["state"]}
        )
    assert _motivo(r2) == "falhou" and "aprimora_token" not in r2.cookies


@pytest.mark.parametrize(
    "ajuste",
    ["assinar_com_atacante", "hs256_com_client_secret", "nonce_forjado", "aud", "iss"],
)
@pytest.mark.asyncio
async def test_id_token_adulterado_e_recusado(google, tenants, admin_engine, ajuste):
    a, _ = tenants
    email = await _servidor(admin_engine, a)
    if ajuste == "nonce_forjado":
        google.nonce_forjado = "nonce-de-outro-fluxo"
    elif ajuste == "aud":
        google.aud = "outro-cliente.apps.googleusercontent.com"
    elif ajuste == "iss":
        google.iss = "https://accounts.google.com.evil.test"
    else:
        setattr(google, ajuste, True)
    async with _cliente() as c:
        r = await _fluxo(c, google, a, email=email)
    assert _motivo(r) == "falhou", (ajuste, r.headers.get("location"))
    assert "aprimora_token" not in r.cookies


# ---------------------------------------------------------------------------
# Destino — allowlist (mesma política de frontend/lib/destino-login.ts)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        (None, "/home"),
        ("", "/home"),
        ("/m/frota", "/m/frota"),
        ("/m/protocolo/processos/7?tab=documentos", "/m/protocolo/processos/7?tab=documentos"),
        ("https://evil.example", "/home"),
        ("//evil.example", "/home"),
        ("/\\evil.example", "/home"),
        ("javascript:alert(1)", "/home"),
        ("/login", "/home"),
        ("/login/convite", "/home"),
        ("/alterar-senha-obrigatoria", "/home"),
        ("/api/v2/auth/me", "/home"),
        ("/cidadao/processos", "/home"),
        ("/m/../login", "/home"),
        ("/m\r\nSet-Cookie: x=1", "/home"),
    ],
)
def test_destino_seguro(bruto, esperado):
    assert google_login.destino_seguro(bruto) == esperado
