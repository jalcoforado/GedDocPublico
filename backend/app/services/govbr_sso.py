"""Login do cidadão pelo gov.br (OpenID Connect, authorization code + PKCE).

Autenticação — o erro aqui não é tela quebrada, é sessão de outra pessoa. O
rascunho de onde isto saiu (WIP de 2026-09-24) tinha quatro defeitos que davam,
cada um sozinho, login como qualquer CPF ou coisa pior; ficam registrados para
que nenhum volte:

1. **Modo mock ligado por padrão.** `client_id` ausente virava `"mock"`, e no
   modo mock o CPF saía do próprio `code` da URL
   (`/callback?code=mock-code-<CPF>`). Em qualquer ambiente sem configuração —
   ou seja, todos —, bastava um link para entrar como qualquer cidadão. Não há
   mock aqui: sem configuração o fluxo responde 503, e os testes simulam o
   gov.br trocando `_cliente_http`, não o código de produção.
2. **`state` gerado e jogado fora.** Nada o guardava nem o conferia no
   callback: CSRF de login livre. Hoje ele vai num cookie assinado, preso ao
   navegador que iniciou o fluxo, junto com o `nonce` e o `code_verifier`.
3. **Identidade não verificada.** O CPF vinha do `userinfo` sem conferir o
   `id_token`. Hoje vem do `sub` do `id_token` com assinatura RS256 conferida
   no JWKS do gov.br, `iss`/`aud`/`exp`/`nonce`/`at_hash` validados.
4. **Token de servidor para cidadão.** Emitia `build_payload` (o token de
   `utils.usuario`) com o id do cidadão, no cookie `aprimora_token` — a sessão
   administrativa do servidor que tivesse o mesmo id numérico. A sessão agora é
   emitida por `auth/cidadao_sessao.py`, o mesmo caminho do login por senha.

O que este módulo NÃO faz: decidir tenant (vem do `Host`, via
`require_tenant_id`, e o estado só o confere) nem criar sessão (router).
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

logger = logging.getLogger("govbr_sso")

COOKIE_ESTADO = "aprimora_govbr_estado"
TTL_ESTADO_S = 600
DESTINO_PADRAO = "/cidadao/processos"
ESCOPOS = "openid email profile govbr_confiabilidades"
TOLERANCIA_RELOGIO_S = 60
_AUD_ESTADO = "aprimora-govbr-estado"

# Níveis de confiabilidade do gov.br por id (API de confiabilidades v3).
# Contrato a confirmar na homologação — ver `consultar_nivel`.
_NIVEIS = {"1": "bronze", "2": "prata", "3": "ouro"}


class GovBrErro(Exception):
    """Falha do fluxo. `status_code` é o HTTP que o router devolve."""

    def __init__(self, status_code: int, detalhe: str) -> None:
        super().__init__(detalhe)
        self.status_code = status_code
        self.detalhe = detalhe


def exigir_configuracao() -> None:
    if not get_settings().govbr_configurado:
        raise GovBrErro(503, "Login gov.br não está configurado neste ambiente")


# ---------------------------------------------------------------------------
# Destino pós-login — allowlist
# ---------------------------------------------------------------------------


def destino_seguro(bruto: str | None) -> str:
    """Caminho interno do portal do cidadão, ou `DESTINO_PADRAO`.

    Mesma política de `frontend/lib/destino-login.ts` (allowlist, não lista
    negra), restrita ao portal do cidadão: só `/cidadao` e abaixo. Recusa
    `//host` e `/\\host` (protocol-relative, saem do domínio), qualquer `\\`,
    caractere de controle e a própria tela de login (laço).
    """
    if not bruto or len(bruto) > 512:
        return DESTINO_PADRAO
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in bruto):
        return DESTINO_PADRAO
    if "\\" in bruto or bruto.startswith("//"):
        return DESTINO_PADRAO
    caminho = bruto.split("?", 1)[0].split("#", 1)[0]
    if caminho != "/cidadao" and not caminho.startswith("/cidadao/"):
        return DESTINO_PADRAO
    if caminho == "/cidadao/login" or caminho.startswith("/cidadao/login/"):
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
    """Chave derivada: o cookie de estado não compartilha chave com a sessão.

    Com a mesma chave, só o `aud` separaria um do outro; derivando, nem um
    token de sessão vira estado nem o contrário, qualquer que seja o `aud`.
    """
    return hmac.new(segredo_jwt.encode(), b"govbr-estado-v1", hashlib.sha256).hexdigest()


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
    """Valida o cookie e o `state` do callback. Levanta 400 em qualquer desvio.

    É o anti-CSRF: o `state` da URL tem de ser o que ESTE navegador recebeu ao
    iniciar o fluxo. Um callback forjado (o atacante mandando a vítima para
    `/callback?code=<do atacante>&state=<do atacante>`) chega sem o cookie
    correspondente e morre aqui.
    """
    if not cookie or not state_recebido:
        raise GovBrErro(400, "Sessão de login gov.br ausente ou expirada; tente de novo")
    try:
        claims = jwt.decode(
            cookie,
            _chave_estado(segredo_jwt),
            algorithms=["HS256"],
            audience=_AUD_ESTADO,
            options={"require_aud": True, "require_exp": True},
        )
    except Exception as exc:  # noqa: BLE001 — JWTError e subclasses
        raise GovBrErro(400, "Sessão de login gov.br inválida ou expirada") from exc
    if not hmac.compare_digest(str(claims.get("state", "")), state_recebido):
        raise GovBrErro(400, "Parâmetro state não confere")
    if claims.get("tenant_id") != tenant_id:
        # O cookie é do host de origem; chegar a outro tenant é callback no
        # host errado (ou manipulação). Nunca se troca o tenant pelo do estado.
        raise GovBrErro(400, "Login gov.br iniciado em outra prefeitura")
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


def _sso() -> str:
    return get_settings().govbr_sso_url.strip().rstrip("/")


def url_autorizacao(estado: EstadoLogin, *, redirect_uri: str) -> str:
    s = get_settings()
    params = {
        "response_type": "code",
        "client_id": s.govbr_client_id.strip(),
        "scope": ESCOPOS,
        "redirect_uri": redirect_uri,
        "state": estado.state,
        "nonce": estado.nonce,
        "code_challenge": _code_challenge(estado.code_verifier),
        "code_challenge_method": "S256",
    }
    return f"{_sso()}/authorize?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Callback — troca do code e verificação da identidade
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentidadeGovBr:
    cpf: str
    nome: str
    email: str | None
    nivel: str | None


def _cliente_http() -> httpx.AsyncClient:
    """Ponto de injeção dos testes: eles trocam o transporte, não o fluxo."""
    return httpx.AsyncClient(timeout=10.0)


async def _validar_id_token(
    client: httpx.AsyncClient, id_token: str, *, access_token: str, nonce: str
) -> dict[str, Any]:
    s = get_settings()
    client_id = s.govbr_client_id.strip()
    try:
        header = jwt.get_unverified_header(id_token)
    except Exception as exc:  # noqa: BLE001
        raise GovBrErro(401, "id_token malformado") from exc
    # Algoritmo fixo ANTES da chave: `none`/HS256 com a chave pública como
    # segredo são os ataques clássicos de confusão de algoritmo.
    if str(header.get("alg", "")).upper() != "RS256":
        raise GovBrErro(401, "id_token com algoritmo não aceito")
    kid = header.get("kid")

    try:
        resp = await client.get(f"{_sso()}/jwk")
        resp.raise_for_status()
        chaves = [k for k in resp.json().get("keys", []) if isinstance(k, dict)]
    except Exception as exc:  # noqa: BLE001
        raise GovBrErro(502, "gov.br indisponível (JWKS)") from exc
    if kid:
        chaves = [k for k in chaves if k.get("kid") == kid]
    if len(chaves) != 1:
        raise GovBrErro(401, "chave do id_token não encontrada no JWKS do gov.br")

    try:
        claims = jwt.decode(
            id_token,
            chaves[0],
            algorithms=["RS256"],
            audience=client_id,
            access_token=access_token,
            options={
                "leeway": TOLERANCIA_RELOGIO_S,
                # `iss` é conferido à mão abaixo (tolerando a barra final).
                "verify_iss": False,
                # python-jose 3.3.0: sem estes, claim AUSENTE passa (ver o
                # mesmo alerta em `auth/plataforma.py`).
                "require_aud": True,
                "require_exp": True,
                "require_iat": True,
                "require_sub": True,
            },
        )
    except Exception as exc:  # noqa: BLE001 — JWTError e subclasses
        raise GovBrErro(401, "id_token recusado") from exc

    if str(claims.get("iss", "")).rstrip("/") != _sso():
        raise GovBrErro(401, "id_token de outro emissor")
    azp = claims.get("azp")
    if azp is not None and azp != client_id:
        raise GovBrErro(401, "id_token emitido para outro cliente")
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise GovBrErro(401, "nonce do id_token não confere")
    return claims


async def consultar_nivel(
    client: httpx.AsyncClient, *, cpf: str, access_token: str
) -> str | None:
    """Maior nível de confiabilidade da conta, ou None. Nunca bloqueia login.

    O contrato da API de confiabilidades (caminho e forma da resposta) segue o
    roteiro público do gov.br e **precisa ser confirmado na homologação** —
    sem credencial não há como exercitá-lo contra o serviço real. Por isso
    qualquer falha aqui vira `None`, e não erro: o nível é informação, não
    identidade.
    """
    api = get_settings().govbr_api_url.strip().rstrip("/")
    if not api:
        return None
    try:
        resp = await client.get(
            f"{api}/confiabilidades/v3/contas/{cpf}/niveis",
            params={"response-type": "ids"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        ids = {str(item.get("id")) for item in resp.json() if isinstance(item, dict)}
    except Exception:  # noqa: BLE001
        logger.warning("govbr_nivel_indisponivel")
        return None
    for nivel_id in ("3", "2", "1"):
        if nivel_id in ids:
            return _NIVEIS[nivel_id]
    return None


async def identidade_do_callback(
    code: str, estado: EstadoLogin, *, redirect_uri: str
) -> IdentidadeGovBr:
    """Troca o `code` servidor-a-servidor e devolve a identidade VERIFICADA.

    O CPF sai do `sub` do `id_token` validado — nunca de parâmetro da URL, de
    cookie ou de campo que o navegador controle. `userinfo` só complementa nome
    e e-mail quando o `id_token` não os traz, e só se o `sub` dele bater.
    """
    exigir_configuracao()
    s = get_settings()
    async with _cliente_http() as client:
        try:
            resp = await client.post(
                f"{_sso()}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": estado.code_verifier,
                },
                auth=(s.govbr_client_id.strip(), s.govbr_client_secret.strip()),
            )
        except Exception as exc:  # noqa: BLE001
            raise GovBrErro(502, "gov.br indisponível (token)") from exc
        if resp.status_code != 200:
            logger.warning("govbr_token_recusado", extra={"status": resp.status_code})
            raise GovBrErro(401, "gov.br recusou o código de autorização")
        try:
            tokens = resp.json()
            access_token = str(tokens["access_token"])
            id_token = str(tokens["id_token"])
        except Exception as exc:  # noqa: BLE001
            raise GovBrErro(502, "resposta de token do gov.br sem id_token") from exc

        claims = await _validar_id_token(
            client, id_token, access_token=access_token, nonce=estado.nonce
        )
        cpf = "".join(ch for ch in str(claims["sub"]) if ch.isdigit())
        if len(cpf) != 11:
            raise GovBrErro(401, "id_token sem CPF válido")

        nome = claims.get("name")
        email = claims.get("email") if claims.get("email_verified") is True else None
        if not nome:
            try:
                ui = await client.get(
                    f"{_sso()}/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                ui.raise_for_status()
                dados = ui.json()
            except Exception:  # noqa: BLE001 — nome é complemento, não identidade
                dados = {}
            if dados:
                if str(dados.get("sub", "")) != str(claims["sub"]):
                    raise GovBrErro(401, "userinfo de outra identidade")
                nome = dados.get("name")
                if email is None and dados.get("email_verified") is True:
                    email = dados.get("email")

        nivel = await consultar_nivel(client, cpf=cpf, access_token=access_token)

    return IdentidadeGovBr(
        cpf=cpf, nome=str(nome or ""), email=str(email) if email else None, nivel=nivel
    )
