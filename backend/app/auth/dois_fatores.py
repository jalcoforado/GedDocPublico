"""Tokens do 2FA por e-mail: o DESAFIO (entre a senha e o código) e o
LEMBRAR (computador confiável por 30 dias).

Nenhum dos dois é sessão. Ambos são JWT HS256 com a chave HS do sistema, mas
com `aud` próprio e sem a claim `usuario_id`: `decode_token` (sessão) confere
o `aud` de sessão e recusa os dois, e mesmo que não recusasse não acharia de
quem é a sessão. Usar um deles como `aprimora_token` não entra em nada.

O LEMBRAR carrega uma impressão da senha (`fp`): trocar ou redefinir a senha
derruba todos os computadores lembrados daquela conta, sem tabela nem
revogação manual — a impressão deixa de bater.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from jose import JWTError, jwt

AUD_DESAFIO = "aprimora-2fa-desafio"
AUD_LEMBRAR = "aprimora-2fa-lembrar"
COOKIE_LEMBRAR = "aprimora_2fa_lembrar"
VALIDADE_DESAFIO = 10 * 60
VALIDADE_LEMBRAR = 30 * 24 * 3600


def _impressao(senha_bcrypt: str | None) -> str:
    return hashlib.sha256((senha_bcrypt or "").encode()).hexdigest()[:16]


def emitir_desafio(segredo: str, *, usuario_id: int, tenant_id: int, id_token: int) -> str:
    agora = int(time.time())
    return jwt.encode(
        {
            "aud": AUD_DESAFIO,
            "sub": str(usuario_id),
            "tid": tenant_id,
            "tok": id_token,
            "iat": agora,
            "exp": agora + VALIDADE_DESAFIO,
        },
        segredo,
        algorithm="HS256",
    )


def ler_desafio(segredo: str, token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, segredo, algorithms=["HS256"], audience=AUD_DESAFIO)
    except JWTError:
        return None


def emitir_lembrar(segredo: str, *, usuario_id: int, tenant_id: int, senha_bcrypt: str | None) -> str:
    agora = int(time.time())
    return jwt.encode(
        {
            "aud": AUD_LEMBRAR,
            "sub": str(usuario_id),
            "tid": tenant_id,
            "fp": _impressao(senha_bcrypt),
            "iat": agora,
            "exp": agora + VALIDADE_LEMBRAR,
        },
        segredo,
        algorithm="HS256",
    )


def lembrar_vale(
    segredo: str, token: str | None, *, usuario_id: int, tenant_id: int, senha_bcrypt: str | None
) -> bool:
    if not token:
        return False
    try:
        dados = jwt.decode(token, segredo, algorithms=["HS256"], audience=AUD_LEMBRAR)
    except JWTError:
        return False
    return (
        dados.get("sub") == str(usuario_id)
        and dados.get("tid") == tenant_id
        and dados.get("fp") == _impressao(senha_bcrypt)
    )
