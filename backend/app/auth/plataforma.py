"""Validador de token administrativo e gate da fronteira de plataforma.

SEC-01A · Autoridade: `docs/architecture/adr/ADR-016-platform-operator-identity.md`
Contrato de validação: `docs/architecture/security/platform-operator-claims-matrix.md`
— cada linha daquela matriz é um teste em `tests/test_platform_token_validator.py`.

O que este módulo substitui: `require_platform_admin` comparava
`usuario.email` contra a allowlist `PLATFORM_ADMIN_EMAILS`. Como o e-mail é
único apenas **por tenant** (`UNIQUE (tenant_id, email)`), qualquer tenant capaz
de criar um usuário com o e-mail certo produzia um administrador de plataforma
— o achado **F-01**. Aqui a decisão passa a ser: token RS256 do IdP dedicado
(`iss`/`aud` próprios) **mais** um principal ativo em
`aprimora_py.platform_principal`, identificado pelo par opaco
`(issuer, subject)`. O e-mail não participa de nada.

Três propriedades que não podem ser afrouxadas:

1. **Fail-closed em tudo.** Configuração ausente nega; JWKS fora do ar com
   cache vencido devolve `503`; erro ao ler o principal devolve `503`. Em
   nenhum caminho a ausência de informação vira permissão.
2. **HS256 é recusado pelo ALGORITMO, não pela assinatura.** O segredo HS256
   municipal é compartilhado com o PHP legado; recusar "porque a assinatura não
   bate" deixaria a fronteira dependente de um segredo que vaza fácil. O
   algoritmo é conferido no header, antes de qualquer verificação de chave.
3. **Configuração se lê POR CHAMADA.** `auth/jwt.py:23` faz
   `_settings = get_settings()` no import e congela a configuração; com isso,
   `monkeypatch.setenv` + `cache_clear()` num teste não têm efeito e o teste
   vira falso verde. Aqui todo acesso é `get_settings()` dentro da função.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database_plataforma import PlataformaSemBancoError, get_platform_db
from ..models import PlatformPrincipal

logger = logging.getLogger("plataforma")

# Tolerância de relógio da matriz §1: no máximo 60 s, para `exp`, `nbf` e `iat`.
TOLERANCIA_RELOGIO_S = 60
# Teto do cache de JWKS (ADR §2.1 e runbook §6), mesmo que o IdP mande mais.
TETO_CACHE_JWKS_S = 24 * 3600
# TTL quando o IdP não manda `Cache-Control`.
CACHE_JWKS_PADRAO_S = 600
# Piso do TTL, aplicado inclusive contra um `max-age` menor. Ver `_max_age`.
PISO_CACHE_JWKS_S = 60
# Rate limit do refresh disparado por `kid` desconhecido (runbook §6): sem ele,
# um atacante mandando `kid` aleatório transforma nossa fronteira em
# amplificador de tráfego contra o IdP.
INTERVALO_MINIMO_REFRESH_S = 30.0

# Claims que PROVAM que o token não é de plataforma (matriz §2). A presença de
# qualquer um é rejeição imediata + alerta, nunca "ignorar o campo": ignorar
# aceitaria um token municipal cujo `iss`/`aud` tivessem sido configurados por
# engano com os valores de plataforma.
CLAIMS_MUNICIPAIS = ("usuario_id", "cidadao_id", "tenant_id", "conexao", "app")


class ErroPlataforma(HTTPException):
    """Negativa da fronteira de plataforma, com o código exigido pela matriz."""

    def __init__(self, status_code: int, motivo: str) -> None:
        super().__init__(status_code=status_code, detail=motivo)
        self.motivo = motivo


def _nega(status_code: int, motivo: str, **contexto: Any) -> ErroPlataforma:
    logger.warning("plataforma_acesso_negado", extra={"motivo": motivo, **contexto})
    return ErroPlataforma(status_code, motivo)


# ---------------------------------------------------------------------------
# JWKS — cache com teto, refresh sob `kid` desconhecido e rate limit
# ---------------------------------------------------------------------------


@dataclass
class _EstadoJwks:
    chaves: dict[str, dict[str, Any]]
    expira_em: float  # em `time.monotonic()`
    ultimo_refresh: float


_jwks: dict[str, _EstadoJwks] = {}


def limpar_cache_jwks() -> None:
    """Descarta o cache. Usado por teste — e só por teste."""
    _jwks.clear()


def _max_age(cache_control: str) -> int:
    """Segundos de `max-age` no `Cache-Control`, entre o piso e o teto de 24 h.

    O **piso** não é arredondamento: `max-age=0` — que um proxy ou um IdP em
    modo de manutenção emite — faria o cache nascer vencido, e cada requisição
    voltaria a buscar o JWKS. Combinado com o rate limit, o efeito é uma
    fronteira que alterna entre uma busca boa e 30 s de `503` auto-infligido.
    Respeitar `max-age=0` literalmente é obedecer o IdP até o ponto de nos
    derrubarmos sozinhos.
    """
    for parte in cache_control.split(","):
        parte = parte.strip().lower()
        if parte.startswith("max-age="):
            try:
                bruto = int(parte.split("=", 1)[1])
            except ValueError:
                return CACHE_JWKS_PADRAO_S
            return max(PISO_CACHE_JWKS_S, min(bruto, TETO_CACHE_JWKS_S))
    return CACHE_JWKS_PADRAO_S


async def _buscar_jwks(url: str) -> tuple[dict[str, Any], int]:
    """Busca o JWKS. Ponto de injeção dos testes — eles substituem esta função,
    não a rede: teste que bate no IdP real é teste que quebra sem internet."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resposta = await client.get(url)
        resposta.raise_for_status()
        return resposta.json(), _max_age(resposta.headers.get("cache-control", ""))


async def obter_chave_publica(kid: str, url: str) -> dict[str, Any]:
    """Resolve o `kid` no JWKS. Nunca devolve chave sem tê-la verificado no IdP.

    Erros distintos de propósito:
      - `kid` que o IdP não conhece ⇒ **401** (cenário 11): o token é inválido.
      - JWKS inalcançável e cache vencido ⇒ **503** (cenário 12): nós é que
        estamos cegos. Devolver 401 aqui mentiria sobre a causa, e devolver
        allow seria a falha que o ADR §2.6 proíbe nominalmente.
    """
    agora = time.monotonic()
    estado = _jwks.get(url)
    cache_valido = estado is not None and agora < estado.expira_em
    if estado is not None and cache_valido and kid in estado.chaves:
        return estado.chaves[kid]

    # Rate limit — SÓ no caminho de `kid` desconhecido com cache VÁLIDO, que é
    # o único que o runbook §6 descreve ("`kid` desconhecido dispara UMA
    # tentativa de refresh, com rate limit"). Aplicá-lo também com cache
    # vencido produzia 503 auto-infligido: bastava o TTL vencer para a
    # fronteira ficar 30 s recusando sem sequer tentar buscar.
    if (
        estado is not None
        and cache_valido
        and (agora - estado.ultimo_refresh) < INTERVALO_MINIMO_REFRESH_S
    ):
        raise _nega(status.HTTP_401_UNAUTHORIZED, "kid desconhecido no JWKS", kid=kid)

    # Este caminho é alcançável SEM autenticação: basta um JWT sintaticamente
    # válido com `alg: RS256` e um `kid` qualquer, porque a assinatura ainda não
    # foi verificada. Por isso a marca de tentativa é gravada ANTES da busca e
    # sobrevive à falha — se só o sucesso marcasse, o IdP fora do ar (ou o cache
    # frio) faria cada requisição disparar uma busca nova, e nós viraríamos o
    # amplificador de tráfego contra o IdP exatamente quando ele está em apuros.
    if estado is not None:
        estado.ultimo_refresh = agora
    else:
        _jwks[url] = estado = _EstadoJwks(chaves={}, expira_em=0.0, ultimo_refresh=agora)

    try:
        jwks, ttl = await _buscar_jwks(url)
    except Exception as exc:  # noqa: BLE001 — qualquer falha de rede/formato
        logger.error("plataforma_jwks_indisponivel", extra={"url": url, "erro": str(exc)})
        if cache_valido and kid in estado.chaves:
            return estado.chaves[kid]
        raise _nega(
            status.HTTP_503_SERVICE_UNAVAILABLE, "JWKS indisponível e cache expirado", kid=kid
        ) from exc

    chaves = {k["kid"]: k for k in jwks.get("keys", []) if k.get("kid")}
    _jwks[url] = _EstadoJwks(chaves=chaves, expira_em=agora + ttl, ultimo_refresh=agora)
    if kid not in chaves:
        raise _nega(status.HTTP_401_UNAUTHORIZED, "kid desconhecido no JWKS", kid=kid)
    return chaves[kid]


# ---------------------------------------------------------------------------
# Validação do token — matriz de claims §1 e §2
# ---------------------------------------------------------------------------


async def validar_token_plataforma(token: str) -> dict[str, Any]:
    """Valida o token administrativo e devolve os claims. Levanta em qualquer
    desvio — não existe retorno "válido com ressalva"."""
    s = get_settings()  # POR CHAMADA. Ver docstring do módulo.

    # Cenários 23 e 24: configuração faltante NEGA. `hd` é o único que a matriz
    # marca como 403 (é política de domínio); os demais são 401 (não há como
    # sequer decidir de que realm o token é).
    if not s.platform_oidc_hosted_domain.strip():
        raise _nega(
            status.HTTP_403_FORBIDDEN,
            "PLATFORM_OIDC_HOSTED_DOMAIN não configurada — fronteira de plataforma negando",
        )
    if not s.platform_oidc_audience.strip():
        raise _nega(status.HTTP_401_UNAUTHORIZED, "PLATFORM_OIDC_AUDIENCE não configurada")
    if not s.platform_oidc_issuer.strip() or not s.platform_oidc_jwks_url.strip():
        raise _nega(
            status.HTTP_401_UNAUTHORIZED,
            "PLATFORM_OIDC_ISSUER/PLATFORM_OIDC_JWKS_URL não configurados",
        )

    # 1. Algoritmo, ANTES de qualquer chave. HS256/none/simétricos são
    #    recusados aqui — não por a assinatura não bater (cenários 7 e 8).
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:  # noqa: BLE001
        raise _nega(status.HTTP_401_UNAUTHORIZED, "token malformado") from exc
    alg = str(header.get("alg", "")).upper()
    if alg != "RS256":
        raise _nega(
            status.HTTP_401_UNAUTHORIZED,
            f"algoritmo {alg or '(ausente)'} proibido nesta fronteira; só RS256",
        )
    kid = header.get("kid")
    if not kid:
        raise _nega(status.HTTP_401_UNAUTHORIZED, "token sem kid")

    chave = await obter_chave_publica(kid, s.platform_oidc_jwks_url.strip())

    # 2. Assinatura, `iss`, `aud`, `exp` e `nbf` — com a tolerância da matriz.
    try:
        claims = jwt.decode(
            token,
            chave,
            algorithms=["RS256"],
            audience=s.platform_oidc_audience.strip(),
            issuer=s.platform_oidc_issuer.strip(),
            options={
                "leeway": TOLERANCIA_RELOGIO_S,
                "verify_at_hash": False,
                # `iat` é validado à mão logo abaixo: o python-jose só confere o
                # formato, e o cenário 10 exige recusar token emitido no futuro.
                "verify_iat": False,
                # NÃO REMOVER. Na python-jose 3.3.0 estes dois têm default
                # `False`, e `_validate_aud`/`_validate_exp` começam com
                # `if "aud"/"exp" not in claims: return` — ou seja, **claim
                # ausente passa**. Sem eles, um token SEM `exp` nunca expira
                # (e a revogação do principal deixa de ser defesa em
                # profundidade para virar defesa única) e um token SEM `aud`
                # atravessa homologação e produção indistintamente, já que a
                # audience é o único discriminante de ambiente. A matriz §1
                # marca os dois como obrigatórios com deny 401.
                "require_aud": True,
                "require_exp": True,
            },
        )
    except Exception as exc:  # noqa: BLE001 — JWTError e subclasses
        raise _nega(status.HTTP_401_UNAUTHORIZED, f"token recusado: {exc}") from exc

    agora = int(time.time())

    # 3. `iat` obrigatório e não no futuro além da tolerância (cenário 10).
    iat = claims.get("iat")
    if iat is None:
        raise _nega(status.HTTP_401_UNAUTHORIZED, "token sem iat")
    try:
        iat = int(iat)
    except (TypeError, ValueError) as exc:
        raise _nega(status.HTTP_401_UNAUTHORIZED, "iat inválido") from exc
    if iat > agora + TOLERANCIA_RELOGIO_S:
        raise _nega(status.HTTP_401_UNAUTHORIZED, "token emitido no futuro")

    # 4. Claims que provam que o token NÃO é de plataforma (matriz §2).
    #    Alerta em nível de erro: ou é ataque, ou é configuração que fundiu os
    #    realms. As duas merecem investigação.
    intrusos = [c for c in CLAIMS_MUNICIPAIS if c in claims]
    if claims.get("tipo") == "cidadao":
        intrusos.append("tipo=cidadao")
    if intrusos:
        logger.error(
            "plataforma_confusao_de_token",
            extra={"claims_municipais": intrusos, "iss": claims.get("iss")},
        )
        raise _nega(
            status.HTTP_401_UNAUTHORIZED,
            f"token traz claims municipais ({', '.join(intrusos)}) — confusão de realm",
        )

    # 5. `azp`, quando presente, tem de ser a própria audience.
    azp = claims.get("azp")
    if azp is not None and azp != s.platform_oidc_audience.strip():
        raise _nega(status.HTTP_401_UNAUTHORIZED, "azp diferente da audience")

    # 6. `sub` — chave natural do principal junto com `iss`.
    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise _nega(status.HTTP_401_UNAUTHORIZED, "token sem sub")

    # 7. `hd` — política de domínio corporativo (D-2). 403: o token é
    #    autêntico, a identidade é que não pertence ao domínio aceito.
    if claims.get("hd") != s.platform_oidc_hosted_domain.strip():
        raise _nega(status.HTTP_403_FORBIDDEN, "hd fora do domínio corporativo configurado")

    # 8. `email_verified` — obrigatório e verdadeiro (cenário 14). O e-mail em
    #    si continua sendo só rótulo; o que se exige aqui é que o IdP tenha
    #    confirmado a caixa, não que ela autorize algo.
    if claims.get("email_verified") is not True:
        raise _nega(status.HTTP_403_FORBIDDEN, "email_verified ausente ou falso")

    return claims


# ---------------------------------------------------------------------------
# Principal — autorização (matriz §3)
# ---------------------------------------------------------------------------


async def carregar_principal(
    db: AsyncSession, issuer: str, subject: str
) -> PlatformPrincipal | None:
    """Lê o principal pela chave natural. Consulta a CADA requisição, sem cache
    de sessão — é isso que faz a revogação valer em minutos e não em 8 horas
    (ADR §2.4)."""
    stmt = select(PlatformPrincipal).where(
        PlatformPrincipal.issuer == issuer,
        PlatformPrincipal.subject == subject,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _token_do_request(request: Request) -> str:
    """Só o header `Authorization: Bearer`.

    **Nunca** o cookie municipal `aprimora_token`: ele é a credencial do outro
    realm, e aceitá-lo aqui recriaria o compartilhamento de sessão que o
    ADR §2.2/§1.5 manda separar. O cookie de operador é trabalho de `SEC-01B`.
    """
    cabecalho = request.headers.get("Authorization", "")
    if not cabecalho.lower().startswith("bearer "):
        raise _nega(status.HTTP_401_UNAUTHORIZED, "token administrativo ausente")
    token = cabecalho.split(" ", 1)[1].strip()
    if not token:
        raise _nega(status.HTTP_401_UNAUTHORIZED, "token administrativo ausente")
    return token


async def require_platform_admin(
    request: Request,
    db: AsyncSession | None = Depends(get_platform_db),
) -> PlatformPrincipal:
    """Gate das rotas de plataforma. Devolve o principal, não um `Usuario`.

    Nenhuma credencial municipal participa: não há `get_current_user`, não há
    consulta a `utils.usuario`, não há allowlist de e-mail. Um super-usuário de
    prefeitura — de qualquer prefeitura, com qualquer e-mail — não passa daqui.
    """
    claims = await validar_token_plataforma(_token_do_request(request))

    # Só agora: sem conexão dedicada não há como consultar o principal, e a
    # matriz §3 manda 500 (erro de configuração). Depois da validação do token
    # de propósito — ver a docstring de `get_platform_db`.
    if db is None:
        raise PlataformaSemBancoError()

    issuer = str(claims["iss"])
    subject = str(claims["sub"])

    try:
        principal = await carregar_principal(db, issuer, subject)
    except SQLAlchemyError as exc:
        # Matriz §3: "Erro ao ler o principal (banco indisponível) ⇒ deny 503".
        logger.error("plataforma_principal_ilegivel", extra={"erro": str(exc)})
        raise ErroPlataforma(
            status.HTTP_503_SERVICE_UNAVAILABLE, "principal de plataforma ilegível"
        ) from exc

    agora = datetime.utcnow()
    if principal is None or not principal.vigente_em(agora):
        motivo = (
            "principal inexistente" if principal is None else "principal inativo ou fora de vigência"
        )
        # A trilha da tentativa negada é o que o runbook §2 manda usar para
        # colher `(iss, sub)` no bootstrap do primeiro operador — sem ela, o
        # procedimento documentado não tem de onde tirar o par.
        from ..services.plataforma_auditoria import registrar_tentativa_negada

        await registrar_tentativa_negada(
            db,
            issuer=issuer,
            subject=subject,
            motivo=motivo,
            principal_id=principal.id if principal is not None else None,
            correlation_id=getattr(request.state, "request_id", None),
        )
        logger.warning(
            "plataforma_principal_negado",
            extra={"motivo": motivo, "iss": issuer, "sub": subject},
        )
        raise ErroPlataforma(status.HTTP_403_FORBIDDEN, motivo)

    request.state.platform_principal_id = principal.id
    return principal


def exigir_tenant_alvo(tenant_id: int | None) -> int:
    """Matriz §3: operação cross-tenant recebe o tenant **da operação**, nunca
    do middleware/host. Ausente ⇒ 400.

    Existe como função e não como `if` solto para que a regra tenha um nome, um
    teste e um lugar único onde mudar.
    """
    if tenant_id is None:
        raise ErroPlataforma(
            status.HTTP_400_BAD_REQUEST,
            "operação de plataforma exige tenant alvo explícito",
        )
    return int(tenant_id)


def verificar_configuracao_na_inicializacao() -> None:
    """Cenário 23/24: configuração ausente **registra erro na inicialização**.

    Não levanta: derrubar o app municipal inteiro porque o console de operador
    está desconfigurado trocaria um console indisponível por um sistema
    indisponível. A negação acontece em cada requisição de plataforma; aqui só
    garantimos que ninguém descubra isso por acidente.
    """
    s = get_settings()
    if s.environment.strip().lower().startswith("test"):
        return
    if s.plataforma_configurada:
        return
    ausentes = [
        nome
        for nome, valor in (
            ("PLATFORM_OIDC_ISSUER", s.platform_oidc_issuer),
            ("PLATFORM_OIDC_AUDIENCE", s.platform_oidc_audience),
            ("PLATFORM_OIDC_JWKS_URL", s.platform_oidc_jwks_url),
            ("PLATFORM_OIDC_HOSTED_DOMAIN", s.platform_oidc_hosted_domain),
        )
        if not valor.strip()
    ]
    logger.error(
        "plataforma_configuracao_ausente",
        extra={
            "ausentes": ausentes,
            "efeito": "toda rota de plataforma nega; ver runbook platform-operator-bootstrap §1",
        },
    )
