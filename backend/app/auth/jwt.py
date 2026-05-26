"""JWT encode/decode.

Coexistência HS256 ↔ RS256 (Fase 9.3):
  - `encode_token` usa `settings.jwt_algorithm` (default HS256 — interop PHP).
  - `decode_token` ACEITA AMBOS: tenta HS256 com o segredo; se falhar, tenta
    RS256 com a chave pública. Assim podemos trocar a emissão pra RS256 sem
    invalidar tokens HS256 emitidos antes ou pelo PHP.

Chaves RSA carregadas do disco apenas se necessárias (lazy + cache).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings

_settings = get_settings()
_cached_hs_secret: str | None = None
_cached_private_key: str | None = None
_cached_public_key: str | None = None


async def get_jwt_secret(db: AsyncSession) -> str:
    """Segredo HS256. Mantido para validação de tokens HS256 (PHP + legacy).

    Strategy:
      - "db"   : reads utils.sistema_constante (default; matches PHP exactly)
      - "env"  : uses JWT_SECRET_STATIC env var (for tests / CI / pre-bootstrap)
    """
    global _cached_hs_secret
    if _cached_hs_secret:
        return _cached_hs_secret

    if _settings.jwt_secret_source == "env":
        if not _settings.jwt_secret_static:
            raise RuntimeError("JWT_SECRET_STATIC not set with JWT_SECRET_SOURCE=env")
        _cached_hs_secret = _settings.jwt_secret_static
        return _cached_hs_secret

    result = await db.execute(
        text(
            "SELECT valor_padrao FROM utils.sistema_constante "
            "WHERE constante = 'KEY_LOGIN_GLOBAL_JWT' LIMIT 1"
        )
    )
    row = result.first()
    if row is None or not row[0]:
        raise RuntimeError(
            "KEY_LOGIN_GLOBAL_JWT not found in utils.sistema_constante"
        )
    _cached_hs_secret = row[0]
    return _cached_hs_secret


def _get_private_key() -> str:
    global _cached_private_key
    if _cached_private_key:
        return _cached_private_key
    p = Path(_settings.jwt_private_key_path)
    if not p.exists():
        raise RuntimeError(
            f"JWT_ALGORITHM=RS256 mas chave privada não encontrada em {p}. "
            "Gerar conforme keys/README.md."
        )
    _cached_private_key = p.read_text()
    return _cached_private_key


def _get_public_key() -> str | None:
    """Lê chave pública se existir; retorna None se ausente (sem RS256 configurado)."""
    global _cached_public_key
    if _cached_public_key:
        return _cached_public_key
    p = Path(_settings.jwt_public_key_path)
    if not p.exists():
        return None
    _cached_public_key = p.read_text()
    return _cached_public_key


def build_payload(
    usuario_id: int, usuario_email: str, tenant_id: int | None = None
) -> dict[str, Any]:
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": _settings.jwt_iss,
        "aud": _settings.jwt_aud,
        "iat": now,
        "exp": now + _settings.jwt_ttl_seconds,
        "usuario_id": usuario_id,
        "usuario_email": usuario_email,
        "conexao": _settings.cidade_conn,
        "app": _settings.app_name,
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return payload


def build_cidadao_payload(
    cidadao_id: int, cpf_cnpj: str, tenant_id: int | None = None
) -> dict[str, Any]:
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": _settings.jwt_iss,
        "aud": _settings.jwt_aud,
        "iat": now,
        "exp": now + _settings.jwt_ttl_seconds,
        "cidadao_id": cidadao_id,
        "cpf_cnpj": cpf_cnpj,
        "conexao": _settings.cidade_conn,
        "app": _settings.app_name,
        "tipo": "cidadao",
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return payload


def encode_token(payload: dict[str, Any], hs_secret: str) -> str:
    """Emite token usando o algoritmo configurado.

    HS256: usa `hs_secret` (mesmo do PHP, lido do banco).
    RS256: usa a chave privada do disco; `hs_secret` é ignorado.
    """
    algo = _settings.jwt_algorithm.upper()
    if algo == "RS256":
        return jwt.encode(payload, _get_private_key(), algorithm="RS256")
    return jwt.encode(payload, hs_secret, algorithm="HS256")


def decode_token(token: str, hs_secret: str) -> dict[str, Any] | None:
    """Valida o token tentando HS256 primeiro, depois RS256.

    Tenta os dois pois durante a transição podem existir tokens válidos com
    qualquer um dos algoritmos (emitidos antes/depois do switch, ou pelo PHP).
    """
    # 1ª tentativa: HS256 (cobre tokens do PHP e Python pre-cutover)
    try:
        return jwt.decode(
            token,
            hs_secret,
            algorithms=["HS256"],
            audience=_settings.jwt_aud,
            issuer=_settings.jwt_iss,
        )
    except JWTError:
        pass

    # 2ª tentativa: RS256 (tokens Python emitidos após cutover)
    pub = _get_public_key()
    if pub is None:
        return None
    try:
        return jwt.decode(
            token,
            pub,
            algorithms=["RS256"],
            audience=_settings.jwt_aud,
            issuer=_settings.jwt_iss,
        )
    except JWTError:
        return None
