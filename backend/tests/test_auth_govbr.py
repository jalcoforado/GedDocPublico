"""Login do cidadão pelo gov.br (`routers/auth_govbr.py`, `services/govbr_sso.py`).

Sem rede e sem credencial: o gov.br é simulado por `GovBrFalso`, servido a
`govbr_sso._cliente_http` por um `httpx.MockTransport`. O falso se comporta
como o provedor, não como o código testado: ele guarda o `nonce` e o
`code_challenge` recebidos no `/authorize`, amarra o CPF ao `code` do lado DELE,
recusa `code_verifier` que não bata com o challenge e assina o `id_token` com
uma chave RSA efêmera publicada no seu JWKS. Assim, o CPF que chega ao
cadastro só pode ter vindo do `id_token` — nunca da URL.

Os testes do rascunho (WIP de 2026-09-24) passavam pelo motivo errado: o
callback aceitava `state="some-state"` sem cookie nenhum e o CPF saía do
`code=mock-code-<CPF>` — o teste "verde" era a prova do defeito.
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models import UsuarioExterno
from app.services import govbr_sso
from tests.conftest import arreio_tenant_http, provisionar_tenant_de_teste
from tests.fixtures.platform_operator_tokens import gerar_chaves

SSO = "https://sso.govbr.test.local"
API = "https://api.govbr.test.local"
CLIENT_ID = "aprimora-govbr-teste"
CLIENT_SECRET = "segredo-de-teste"

CPF_A = "52998224725"
CPF_B = "11144477735"


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class GovBrFalso:
    """Provedor OIDC em memória. Registra o que recebeu para as asserções."""

    def __init__(self) -> None:
        self.chaves = gerar_chaves(kid="govbr-teste-1")
        self.chaves_atacante = gerar_chaves(kid="govbr-teste-1")  # mesmo kid, outra chave
        self.pendentes: dict[str, dict] = {}
        self.chamadas_token = 0
        # Ajustes por teste
        self.assinar_com_atacante = False
        self.hs256_com_client_secret = False
        self.nonce_forjado: str | None = None
        self.incluir_nome_no_id_token = True
        self.userinfo_sub: str | None = None
        self.niveis: list[dict] = [{"id": "1"}, {"id": "3"}]

    def autorizar(self, location: str, *, cpf: str, nome: str = "Maria Gov") -> dict:
        """O usuário se autentica no gov.br; devolve os params do /authorize."""
        u = urlparse(location)
        assert f"{u.scheme}://{u.netloc}" == SSO and u.path == "/authorize"
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        code = uuid.uuid4().hex
        self.pendentes[code] = {**q, "cpf": cpf, "nome": nome}
        q["code"] = code
        return q

    def _id_token(self, p: dict, access_token: str) -> str:
        agora = int(time.time())
        claims = {
            "iss": f"{SSO}/",
            "aud": CLIENT_ID,
            "sub": p["cpf"],
            "iat": agora,
            "exp": agora + 300,
            "nonce": self.nonce_forjado or p["nonce"],
            "at_hash": _b64u(hashlib.sha256(access_token.encode()).digest()[:16]),
            "email": f"{p['cpf']}@govbr.test",
            "email_verified": True,
        }
        if self.incluir_nome_no_id_token:
            claims["name"] = p["nome"]
        if self.hs256_com_client_secret:
            return jwt.encode(claims, CLIENT_SECRET, algorithm="HS256",
                              headers={"kid": self.chaves.kid})
        chave = self.chaves_atacante if self.assinar_com_atacante else self.chaves
        return jwt.encode(
            claims, chave.private_pem, algorithm="RS256", headers={"kid": chave.kid}
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and url == f"{SSO}/token":
            self.chamadas_token += 1
            esperado = "Basic " + base64.b64encode(
                f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
            ).decode()
            if request.headers.get("authorization") != esperado:
                return httpx.Response(401, json={"error": "invalid_client"})
            form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            p = self.pendentes.pop(form.get("code", ""), None)
            if p is None or form.get("grant_type") != "authorization_code":
                return httpx.Response(400, json={"error": "invalid_grant"})
            if form.get("redirect_uri") != p["redirect_uri"]:
                return httpx.Response(400, json={"error": "invalid_grant"})
            # PKCE S256, conferido pelo PROVEDOR como o gov.br faz.
            desafio = _b64u(hashlib.sha256(form.get("code_verifier", "").encode()).digest())
            if p.get("code_challenge_method") != "S256" or desafio != p["code_challenge"]:
                return httpx.Response(400, json={"error": "invalid_grant", "d": "pkce"})
            access = f"at-{uuid.uuid4().hex}"
            self._ultimo = {"access": access, **p}
            return httpx.Response(
                200,
                json={"access_token": access, "id_token": self._id_token(p, access),
                      "token_type": "Bearer"},
            )
        if request.method == "GET" and url == f"{SSO}/jwk":
            return httpx.Response(200, json=self.chaves.jwks)
        if request.method == "GET" and url == f"{SSO}/userinfo":
            return httpx.Response(
                200,
                json={"sub": self.userinfo_sub or self._ultimo["cpf"],
                      "name": self._ultimo["nome"]},
            )
        if request.method == "GET" and url.startswith(f"{API}/confiabilidades/v3/contas/"):
            return httpx.Response(200, json=self.niveis)
        return httpx.Response(404)


@pytest.fixture
def govbr(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("GOVBR_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOVBR_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setenv("GOVBR_SSO_URL", SSO)
    monkeypatch.setenv("GOVBR_API_URL", API)
    monkeypatch.setenv("GOVBR_REDIRECT_URI", "")
    get_settings.cache_clear()
    falso = GovBrFalso()
    monkeypatch.setattr(
        govbr_sso,
        "_cliente_http",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(falso.handler)),
    )
    yield falso
    get_settings.cache_clear()


@pytest.fixture
def govbr_desligado(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    for var in ("GOVBR_CLIENT_ID", "GOVBR_CLIENT_SECRET", "GOVBR_SSO_URL"):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def tenants(admin_engine):
    a = await provisionar_tenant_de_teste(admin_engine, "govbr-a-")
    b = await provisionar_tenant_de_teste(admin_engine, "govbr-b-")
    try:
        yield a, b
    finally:
        from app.database import engine as app_engine

        app.dependency_overrides.clear()
        await app_engine.dispose()


def _cliente() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _fluxo(client, falso, tenant, *, cpf=CPF_A, next_=None):
    """Login completo: /login → gov.br falso → /callback. Devolve a resposta final."""
    arreio_tenant_http(tenant.id, tenant.slug)
    params = {"next": next_} if next_ is not None else {}
    r = await client.get("/api/v2/auth/govbr/login", params=params)
    assert r.status_code == 302, r.text
    q = falso.autorizar(r.headers["location"], cpf=cpf)
    return await client.get(
        "/api/v2/auth/govbr/callback", params={"code": q["code"], "state": q["state"]}
    )


async def _cidadaos(engine, tenant_id: int, cpf: str) -> list[UsuarioExterno]:
    async with _sm(engine)() as s:
        return list(
            (
                await s.execute(
                    select(UsuarioExterno).where(
                        UsuarioExterno.tenant_id == tenant_id,
                        UsuarioExterno.cpf_cnpj == cpf,
                    )
                )
            ).scalars()
        )


# ---------------------------------------------------------------------------
# Configuração ausente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sem_configuracao_as_duas_rotas_respondem_503(govbr_desligado, tenants):
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        r1 = await c.get("/api/v2/auth/govbr/login")
        r2 = await c.get("/api/v2/auth/govbr/callback", params={"code": "x", "state": "y"})
    assert r1.status_code == 503 and "configurado" in r1.json()["detail"]
    assert r2.status_code == 503


# ---------------------------------------------------------------------------
# /login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_manda_ao_govbr_com_state_nonce_e_pkce(govbr, tenants):
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        r = await c.get("/api/v2/auth/govbr/login")
    assert r.status_code == 302
    q = {k: v[0] for k, v in parse_qs(urlparse(r.headers["location"]).query).items()}
    assert q["client_id"] == CLIENT_ID and q["response_type"] == "code"
    assert "openid" in q["scope"].split()
    assert q["redirect_uri"] == "http://test/api/v2/auth/govbr/callback"
    assert len(q["state"]) >= 32 and len(q["nonce"]) >= 32 and q["state"] != q["nonce"]
    assert q["code_challenge_method"] == "S256" and q["code_challenge"]
    set_cookie = r.headers["set-cookie"]
    assert govbr_sso.COOKIE_ESTADO in set_cookie
    assert "HttpOnly" in set_cookie and "Path=/api/v2/auth/govbr" in set_cookie
    # O verifier do PKCE NÃO sai na URL — só o challenge.
    assert "code_verifier" not in r.headers["location"]


# ---------------------------------------------------------------------------
# Fluxo feliz: primeiro login cria, segundo reaproveita, sessão é a do cidadão
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_primeiro_login_cria_cidadao_e_emite_sessao_de_cidadao(
    govbr, tenants, admin_engine
):
    a, _ = tenants
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a, next_="/cidadao/processos")
        assert r.status_code == 302, r.text
        assert r.headers["location"] == "/cidadao/processos"
        # A sessão é a do login por senha: cookie de cidadão, nunca o de servidor.
        assert "aprimora_cidadao_token" in r.cookies
        assert "aprimora_token" not in r.cookies
        me = await c.get("/api/v2/cidadao/me")
    assert me.status_code == 200, me.text
    assert me.json()["cpf_cnpj"] == CPF_A

    [cid] = await _cidadaos(admin_engine, a.id, CPF_A)
    assert cid.login_govbr is True
    assert cid.nivel_govbr == "ouro"  # maior id que o gov.br falso informou
    assert cid.nome == "Maria Gov"
    assert cid.email == f"{CPF_A}@govbr.test"
    assert cid.senha_bcrypt is None and cid.senha == ""
    assert cid.ativo is True


@pytest.mark.asyncio
async def test_segundo_login_reaproveita_o_cadastro(govbr, tenants, admin_engine):
    a, _ = tenants
    async with _cliente() as c:
        r1 = await _fluxo(c, govbr, a)
        r2 = await _fluxo(c, govbr, a)
    assert r1.status_code == 302 and r2.status_code == 302
    assert len(await _cidadaos(admin_engine, a.id, CPF_A)) == 1


@pytest.mark.asyncio
async def test_cadastro_por_senha_existente_e_vinculado_sem_sobrescrever(
    govbr, tenants, admin_engine
):
    a, _ = tenants
    async with _sm(admin_engine)() as s:
        s.add(UsuarioExterno(
            tenant_id=a.id, nome="Nome do Cadastro", cpf_cnpj=CPF_A,
            email="proprio@cadastro.test", senha="", senha_bcrypt=None,
            login_govbr=False, ativo=True, excluido=False, uid=uuid.uuid4(),
            data_criacao=datetime.utcnow(), app="t",
            telefone_whatsapp=False,
        ))
        await s.commit()
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a)
    assert r.status_code == 302, r.text
    [cid] = await _cidadaos(admin_engine, a.id, CPF_A)
    assert cid.login_govbr is True and cid.nivel_govbr == "ouro"
    assert cid.nome == "Nome do Cadastro" and cid.email == "proprio@cadastro.test"


@pytest.mark.asyncio
async def test_cidadao_inativo_nao_e_reativado(govbr, tenants, admin_engine):
    a, _ = tenants
    async with _sm(admin_engine)() as s:
        s.add(UsuarioExterno(
            tenant_id=a.id, nome="Inativo", cpf_cnpj=CPF_A, senha="",
            login_govbr=False, ativo=False, excluido=False, uid=uuid.uuid4(),
            data_criacao=datetime.utcnow(), app="t",
            telefone_whatsapp=False,
        ))
        await s.commit()
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a)
    assert r.status_code == 403
    assert "aprimora_cidadao_token" not in r.cookies
    [cid] = await _cidadaos(admin_engine, a.id, CPF_A)
    assert cid.ativo is False and cid.login_govbr is False


# ---------------------------------------------------------------------------
# state / CSRF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_diferente_do_cookie_e_recusado(govbr, tenants, admin_engine):
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        r = await c.get("/api/v2/auth/govbr/login")
        q = govbr.autorizar(r.headers["location"], cpf=CPF_A)
        cb = await c.get(
            "/api/v2/auth/govbr/callback", params={"code": q["code"], "state": "outro"}
        )
    assert cb.status_code == 400
    assert govbr.chamadas_token == 0  # nem chegou a trocar o code
    assert await _cidadaos(admin_engine, a.id, CPF_A) == []


@pytest.mark.asyncio
async def test_callback_sem_o_cookie_do_navegador_e_recusado(govbr, tenants, admin_engine):
    """CSRF de login: o atacante inicia o fluxo e manda o callback DELE à vítima."""
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as atacante:
        r = await atacante.get("/api/v2/auth/govbr/login")
        q = govbr.autorizar(r.headers["location"], cpf=CPF_B)
    async with _cliente() as vitima:  # navegador sem o cookie de estado
        cb = await vitima.get(
            "/api/v2/auth/govbr/callback", params={"code": q["code"], "state": q["state"]}
        )
    assert cb.status_code == 400
    assert govbr.chamadas_token == 0
    assert await _cidadaos(admin_engine, a.id, CPF_B) == []


@pytest.mark.asyncio
async def test_cookie_de_estado_forjado_e_recusado(govbr, tenants):
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    falso = govbr_sso.codificar_estado(
        govbr_sso.novo_estado(tenant_id=a.id, destino=None), "segredo-que-nao-e-o-nosso"
    )
    async with _cliente() as c:
        c.cookies.set(govbr_sso.COOKIE_ESTADO, falso, path="/api/v2/auth/govbr")
        st = jwt.get_unverified_claims(falso)["state"]
        cb = await c.get("/api/v2/auth/govbr/callback", params={"code": "x", "state": st})
    assert cb.status_code == 400
    assert govbr.chamadas_token == 0


# ---------------------------------------------------------------------------
# Identidade só da fonte verificada
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_id_token_assinado_por_outra_chave_e_recusado(govbr, tenants, admin_engine):
    a, _ = tenants
    govbr.assinar_com_atacante = True
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a)
    assert r.status_code == 401
    assert "aprimora_cidadao_token" not in r.cookies
    assert await _cidadaos(admin_engine, a.id, CPF_A) == []


@pytest.mark.asyncio
async def test_id_token_hs256_com_client_secret_e_recusado(govbr, tenants, admin_engine):
    """Quem conhece o client_secret (vazado, ou o próprio servidor de outro
    ambiente) não pode cunhar identidade: só RS256 da chave do gov.br vale."""
    a, _ = tenants
    govbr.hs256_com_client_secret = True
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a)
    assert r.status_code == 401
    assert await _cidadaos(admin_engine, a.id, CPF_A) == []


@pytest.mark.asyncio
async def test_id_token_com_nonce_de_outro_fluxo_e_recusado(govbr, tenants, admin_engine):
    a, _ = tenants
    govbr.nonce_forjado = "nonce-de-outro-fluxo"
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a)
    assert r.status_code == 401
    assert await _cidadaos(admin_engine, a.id, CPF_A) == []


@pytest.mark.asyncio
async def test_userinfo_de_outra_identidade_e_recusado(govbr, tenants, admin_engine):
    a, _ = tenants
    govbr.incluir_nome_no_id_token = False  # força a consulta ao userinfo
    govbr.userinfo_sub = CPF_B
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a)
    assert r.status_code == 401
    assert await _cidadaos(admin_engine, a.id, CPF_A) == []
    assert await _cidadaos(admin_engine, a.id, CPF_B) == []


@pytest.mark.asyncio
async def test_cpf_na_url_nao_vira_identidade(govbr, tenants, admin_engine):
    """O CPF vem do `sub` do id_token; parâmetro extra na URL é ignorado."""
    a, _ = tenants
    arreio_tenant_http(a.id, a.slug)
    async with _cliente() as c:
        r = await c.get("/api/v2/auth/govbr/login")
        q = govbr.autorizar(r.headers["location"], cpf=CPF_A)
        cb = await c.get(
            "/api/v2/auth/govbr/callback",
            params={"code": q["code"], "state": q["state"], "cpf": CPF_B, "sub": CPF_B},
        )
    assert cb.status_code == 302
    assert len(await _cidadaos(admin_engine, a.id, CPF_A)) == 1
    assert await _cidadaos(admin_engine, a.id, CPF_B) == []


@pytest.mark.asyncio
async def test_falha_na_consulta_de_nivel_nao_bloqueia_login(govbr, tenants, admin_engine):
    a, _ = tenants
    govbr.niveis = "isto não é uma lista"  # type: ignore[assignment]
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a)
    assert r.status_code == 302
    [cid] = await _cidadaos(admin_engine, a.id, CPF_A)
    assert cid.nivel_govbr is None


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_em_outro_tenant_e_recusado(govbr, tenants, admin_engine):
    a, b = tenants
    async with _cliente() as c:
        arreio_tenant_http(a.id, a.slug)
        r = await c.get("/api/v2/auth/govbr/login")
        q = govbr.autorizar(r.headers["location"], cpf=CPF_A)
        arreio_tenant_http(b.id, b.slug)  # o callback chega resolvido para B
        cb = await c.get(
            "/api/v2/auth/govbr/callback", params={"code": q["code"], "state": q["state"]}
        )
    assert cb.status_code == 400
    assert govbr.chamadas_token == 0
    assert await _cidadaos(admin_engine, a.id, CPF_A) == []
    assert await _cidadaos(admin_engine, b.id, CPF_A) == []


@pytest.mark.asyncio
async def test_mesmo_cpf_em_dois_tenants_sao_cadastros_distintos(
    govbr, tenants, admin_engine
):
    a, b = tenants
    async with _cliente() as c:
        assert (await _fluxo(c, govbr, a)).status_code == 302
        assert (await _fluxo(c, govbr, b)).status_code == 302
    [ca] = await _cidadaos(admin_engine, a.id, CPF_A)
    [cb] = await _cidadaos(admin_engine, b.id, CPF_A)
    assert ca.id != cb.id


# ---------------------------------------------------------------------------
# Redirect pós-login
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bruto",
    [
        "//evil.example",
        "//evil.example/cidadao",
        "/\\evil.example",
        "https://evil.example/cidadao",
        "javascript:alert(1)",
        "/cidadao\\..\\modulos",
        "/cidadao/../modulos",
        "/cidadao/login",
        "/modulos",
        "/cidadaox",
        "/cidadao/pro\ncessos",
        "",
        None,
    ],
)
def test_destino_malicioso_cai_no_padrao(bruto):
    assert govbr_sso.destino_seguro(bruto) == govbr_sso.DESTINO_PADRAO


@pytest.mark.parametrize("ok", ["/cidadao", "/cidadao/processos/12", "/cidadao/servicos?x=1"])
def test_destino_interno_do_portal_passa(ok):
    assert govbr_sso.destino_seguro(ok) == ok


@pytest.mark.asyncio
async def test_redirect_malicioso_no_fluxo_completo_vai_ao_padrao(govbr, tenants):
    a, _ = tenants
    async with _cliente() as c:
        r = await _fluxo(c, govbr, a, next_="//evil.example")
    assert r.status_code == 302
    assert r.headers["location"] == govbr_sso.DESTINO_PADRAO


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_municipal_pode_gravar_nivel_govbr(admin_engine):
    """A 0124 é ADD COLUMN: herda o grant de tabela. Trava a premissa — se um
    dia a tabela ganhar grant por coluna (como `aprimora_py.tenant` na 0080),
    o callback quebraria sob `aprimora_app` e este teste avisa antes."""
    async with admin_engine.connect() as conn:
        pode = (
            await conn.execute(
                text(
                    "SELECT has_column_privilege('aprimora_app', "
                    "'utils.usuario_externo', 'nivel_govbr', 'UPDATE') "
                    "AND has_column_privilege('aprimora_app', "
                    "'utils.usuario_externo', 'nivel_govbr', 'INSERT')"
                )
            )
        ).scalar_one()
    assert pode is True
