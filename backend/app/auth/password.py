"""Verificação e hashing de senhas — coexistência MD5 (legacy) ↔ bcrypt.

Estratégia transparente (Fase 9.2):
  - `verify_password(plain, bcrypt_hash, md5_hash)`:
      * Tenta bcrypt primeiro (campo `senha_bcrypt`).
      * Cai pra MD5 (campo `senha`) se bcrypt for None ou inválido.
      * Retorna `(ok, needs_rehash)` — `needs_rehash=True` quando autenticou
        via MD5 e ainda não tem bcrypt; o chamador deve popular `senha_bcrypt`.
  - `hash_password(plain) -> str`: sempre bcrypt.
  - `hash_md5(plain)` / `verify_md5(...)`: mantidos para o cadastro de cidadão
    continuar gravando MD5 em `senha` (compat PHP) enquanto também grava bcrypt.
"""
from __future__ import annotations

import hashlib

import bcrypt


def hash_md5(plain: str) -> str:
    return hashlib.md5(plain.encode("utf-8")).hexdigest()


def verify_md5(plain: str, stored_hash: str) -> bool:
    return hash_md5(plain) == stored_hash


def hash_password(plain: str) -> str:
    """Sempre bcrypt. Usar para popular `senha_bcrypt`."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_bcrypt(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_password(
    plain: str, *, bcrypt_hash: str | None, md5_hash: str | None
) -> tuple[bool, bool]:
    """Retorna (ok, needs_rehash).

    needs_rehash=True quando a senha bateu em MD5 mas não havia bcrypt — o
    chamador deve calcular `hash_password(plain)` e gravar em `senha_bcrypt`.
    """
    if bcrypt_hash and _verify_bcrypt(plain, bcrypt_hash):
        return True, False
    if md5_hash and verify_md5(plain, md5_hash):
        return True, True
    return False, False
