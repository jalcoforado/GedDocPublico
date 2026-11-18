"""Login do servidor municipal com a conta Google (SI-32).

OpenID Connect, authorization code + PKCE — o mesmo desenho do login gov.br do
cidadão (`services/govbr_sso.py`), com as mesmas quatro proteções, porque o erro
aqui também não é tela quebrada, é sessão de outra pessoa:

1. **Sem modo de teste no código.** Sem client ID/secret o fluxo não existe
   (o botão some e as rotas mandam para `/login?google=indisponivel`). Os
   testes simulam o Google trocando `_cliente_http`, não este módulo.
2. **`state` preso ao navegador.** Vai num cookie assinado (chave derivada do
   segredo do JWT, nunca a mesma), junto com o `nonce` e o `code_verifier`. Um
   callback forjado chega sem o cookie e morre na conferência.
3. **Identidade verificada.** O e-mail sai do `id_token` com a assinatura RS256
   conferida no JWKS do Google e `iss`/`aud`/`exp`/`nonce`/`at_hash`
   validados — nunca da URL nem do `userinfo`. E só vale com
   `email_verified=true`: conta Google com e-mail não confirmado não prova que
   a pessoa é dona daquele endereço.
4. **Não cria conta.** O Google só diz QUEM é; quem PODE entrar é o cadastro
   do município. Entra o usuário ativo deste tenant com aquele e-mail, e
   ninguém mais — o servidor é cadastrado pela prefeitura, como no login por
   senha.

O que este módulo NÃO faz: decidir tenant (vem do `Host`, via
`require_tenant_id`; o estado só o confere) nem emitir sessão (router, com o
mesmo `_emitir_sessao` do login por senha).

Limitação conhecida, registrada no card: o login com Google não pede o código
por e-mail (2FA). Hoje não importa — a conta por e-mail está desligada —, mas
tem de ser revisto quando ela for ligada.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import jwt

from ..config import get_settings

logger = logging.getLogger("google_login")

COOKIE_ESTADO = "aprimora_google_login_estado"
CAMINHO_COOKIE = "/api/v2/auth/google-login"
TTL_ESTADO_S = 600
DESTINO_PADRAO = "/home"
ESCOPOS = "openid email profile"
TOLERANCIA_RELOGIO_S = 60
_AUD_ESTADO = "aprimora-google-login-estado"

URL_AUTORIZACAO = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
# O Google emite com e sem o esquema (documentado em "OpenID Connect").
EMISSORES = frozenset({"https://accounts.google.com", "accounts.google.com"})

# Prefixos que nunca são destino — mesma lista de `frontend/lib/destino-login.ts`.
_NUNCA_DESTINO = ("/login", "/alterar-senha-obrigatoria")


class GoogleLoginErro(Exception):
    """Falha do fluxo. `motivo` é o rótulo curto que a tela de login traduz
    (`?google=<motivo>`); `detalhe` fica só no log."""

    def __init__(self, motivo: str, detalhe: str) -> None:
        super().__init__(detalhe)
        self.motivo = motivo
        self.detalhe = detalhe


def exigir_configuracao() -> None:
    s = get_settings()
    if not s.google_login_configurado:
        raise GoogleLoginErro("indisponivel", "Login com Google não está configurado neste ambiente")


# ---------------------------------------------------------------------------
# Destino pós-login — allowlist
# ---------------------------------------------------------------------------


def destino_seguro(bruto: str | None) -> str:
    """Caminho interno do portal do servidor, ou `DESTINO_PADRAO`.

    Mesma política de `frontend/lib/destino-login.ts` (allowlist): só caminho
    interno, nunca `//host` ou `/\\host` (saem do domínio), nem caractere de
    controle, nem a própria tela de login (laço) ou a troca obrigatória de
    senha (decidida pelo backend, não pela URL).
    """
    if not bruto or len(bruto) > 512:
        return DESTINO_PADRAO
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in bruto):
        return DESTINO_PADRAO
    if not bruto.startswith("/") or bruto.startswith("//") or "\\" in bruto:
        return DESTINO_PADRAO
    caminho = bruto.split("?", 1)[0].split("#", 1)[0]
    if any(caminho == p or caminho.startswith(f"{p}/") for p in _NUNCA_DESTINO):
        return DESTINO_PADRAO
    if caminho.startswith("/api/") or caminho.startswith("/cidadao"):
        # API não é página; o portal do cidadão é outra sessão.
        return DESTINO_PADRAO
    if "/../" in f"{caminho}/" or "/./" in f"{caminho}/":
        return DESTINO_PADRAO
    return bruto


# ---------------------------------------------------------------------------
# Estado do fluxo (state + nonce + PKCE), num cookie assinado
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EstadoLogin:
    state: str
    nonce: str
    code_verifier: str
    tenant_id: int
    destino: str


def novo_estado(*, tenant_id: int, destino: str | None) -> EstadoLogin:
    return EstadoLogin(
        state=secrets.token_urlsafe(32),
        nonce=secrets.token_urlsafe(32),
        code_verifier=secrets.token_urlsafe(64),  # 86 caracteres (RFC 7636: 43–128)
        tenant_id=tenant_id,
        destino=destino_seguro(destino),
    )


def _chave_estado(segredo_jwt: str) -> str:
    """Chave derivada: o cookie de estado não compartilha chave com a sessão
    nem com o estado do gov.br (rótulo diferente)."""
    return hmac.new(segredo_jwt.encode(), b"google-login-estado-v1", hashlib.sha256).hexdigest()


def codificar_estado(estado: EstadoLogin, segredo_jwt: str) -> str:
    agora = int(time.time())
    return jwt.encode(
        {
            "aud": _AUD_ESTADO,
            "iat": agora,
            "exp": agora + TTL_ESTADO_S,
            "state": estado.state,
            "nonce": estado.nonce,
            "cv": estado.code_verifier,
            "tenant_id": estado.tenant_id,
            "destino": estado.destino,
        },
        _chave_estado(segredo_jwt),
        algorithm="HS256",
    )


def conferir_estado(
    cookie: str | None, *, state_recebido: str | None, tenant_id: int, segredo_jwt: str
) -> EstadoLogin:
    """Valida o cookie e o `state` do callback (anti-CSRF de login)."""
    if not cookie or not state_recebido:
        raise GoogleLoginErro("expirou", "Cookie de estado ausente ou state vazio")
    try:
        claims = jwt.decode(
            cookie,
            _chave_estado(segredo_jwt),
            algorithms=["HS256"],
            audience=_AUD_ESTADO,
            options={"require_aud": True, "require_exp": True},
        )
    except Exception as exc:  # noqa: BLE001 — JWTError e subclasses
        raise GoogleLoginErro("expirou", "Cookie de estado inválido ou expirado") from exc
    if not hmac.compare_digest(str(claims.get("state", "")), state_recebido):
        raise GoogleLoginErro("falhou", "state não confere com o cookie")
    if claims.get("tenant_id") != tenant_id:
        # Callback no host de outro município: nunca se troca o tenant pelo do estado.
        raise GoogleLoginErro("falhou", "Login iniciado em outra prefeitura")
    return EstadoLogin(
        state=claims["state"],
        nonce=claims["nonce"],
        code_verifier=claims["cv"],
        tenant_id=claims["tenant_id"],
        destino=destino_seguro(claims.get("destino")),
    )


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def url_autorizacao(estado: EstadoLogin, *, redirect_uri: str) -> str:
    s = get_settings()
    params = {
        "response_type": "code",
        "client_id": s.google_oauth_client_id.strip(),
        "scope": ESCOPOS,
        "redirect_uri": redirect_uri,
        "state": estado.state,
        "nonce": estado.nonce,
        "code_challenge": _code_challenge(estado.code_verifier),
        "code_challenge_method": "S256",
        # Sempre mostra a escolha de conta: quem usa o computador da repartição
        # depois de um colega não entra, sem perceber, com a conta dele.
        "prompt": "select_account",
    }
    return f"{URL_AUTORIZACAO}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Callback — troca do code e verificação da identidade
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentidadeGoogle:
    email: str
    nome: str
    sub: str


def _cliente_http() -> httpx.AsyncClient:
    """Ponto de injeção dos testes: eles trocam o transporte, não o fluxo."""
    return httpx.AsyncClient(timeout=10.0)


async def _validar_id_token(
    client: httpx.AsyncClient, id_token: str, *, access_token: str, nonce: str
) -> dict[str, Any]:
    client_id = get_settings().google_oauth_client_id.strip()
    try:
        header = jwt.get_unverified_header(id_token)
    except Exception as exc:  # noqa: BLE001
        raise GoogleLoginErro("falhou", "id_token malformado") from exc
    # Algoritmo fixo ANTES da chave: `none`/HS256 com a chave pública como
    # segredo são os ataques clássicos de confusão de algoritmo.
    if str(header.get("alg", "")).upper() != "RS256":
        raise GoogleLoginErro("falhou", "id_token com algoritmo não aceito")
    kid = header.get("kid")

    try:
        resp = await client.get(URL_JWKS)
        resp.raise_for_status()
        chaves = [k for k in resp.json().get("keys", []) if isinstance(k, dict)]
    except Exception as exc:  # noqa: BLE001
        raise GoogleLoginErro("falhou", "Google indisponível (JWKS)") from exc
    if kid:
        chaves = [k for k in chaves if k.get("kid") == kid]
    if len(chaves) != 1:
        raise GoogleLoginErro("falhou", "chave do id_token não encontrada no JWKS do Google")

    try:
        claims = jwt.decode(
            id_token,
            chaves[0],
            algorithms=["RS256"],
            audience=client_id,
            access_token=access_token,
            options={
                "leeway": TOLERANCIA_RELOGIO_S,
                # `iss` conferido à mão abaixo (o Google usa duas grafias).
                "verify_iss": False,
                # python-jose 3.3.0: sem estes, claim AUSENTE passa.
                "require_aud": True,
                "require_exp": True,
                "require_iat": True,
                "require_sub": True,
            },
        )
    except Exception as exc:  # noqa: BLE001 — JWTError e subclasses
        raise GoogleLoginErro("falhou", "id_token recusado") from exc

    if str(claims.get("iss", "")) not in EMISSORES:
        raise GoogleLoginErro("falhou", "id_token de outro emissor")
    azp = claims.get("azp")
    if azp is not None and azp != client_id:
        raise GoogleLoginErro("falhou", "id_token emitido para outro cliente")
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise GoogleLoginErro("falhou", "nonce do id_token não confere")
    return claims


async def identidade_do_callback(
    code: str, estado: EstadoLogin, *, redirect_uri: str
) -> IdentidadeGoogle:
    """Troca o `code` servidor-a-servidor e devolve a identidade VERIFICADA."""
    exigir_configuracao()
    s = get_settings()
    async with _cliente_http() as client:
        try:
            resp = await client.post(
                URL_TOKEN,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": estado.code_verifier,
                    "client_id": s.google_oauth_client_id.strip(),
                    "client_secret": s.google_oauth_client_secret.strip(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise GoogleLoginErro("falhou", "Google indisponível (token)") from exc
        if resp.status_code != 200:
            # O corpo do erro do Google ("redirect_uri_mismatch",
            # "invalid_client") é o que diz o que está mal configurado.
            logger.warning(
                "google_login_token_recusado",
                extra={"status": resp.status_code, "corpo": resp.text[:200]},
            )
            raise GoogleLoginErro("falhou", "Google recusou o código de autorização")
        try:
            tokens = resp.json()
            access_token = str(tokens["access_token"])
            id_token = str(tokens["id_token"])
        except Exception as exc:  # noqa: BLE001
            raise GoogleLoginErro("falhou", "resposta de token do Google sem id_token") from exc

        claims = await _validar_id_token(
            client, id_token, access_token=access_token, nonce=estado.nonce
        )

    email = str(claims.get("email") or "").strip()
    if not email or claims.get("email_verified") is not True:
        raise GoogleLoginErro("email_nao_verificado", "Conta Google sem e-mail verificado")
    return IdentidadeGoogle(
        email=email, nome=str(claims.get("name") or ""), sub=str(claims["sub"])
    )
