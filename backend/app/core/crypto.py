"""Cifragem simétrica (Fernet) de dados sensíveis em repouso.

Reutilizável por qualquer campo bancário/sigiloso (credor de pagamentos) e por
tokens OAuth (PR-D da minuta). Chave em `settings.dados_sensiveis_encryption_key`
(Fernet key base64). Valores None/"" passam sem cifrar.
"""
from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet

from ..config import get_settings


class CryptoConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = get_settings().dados_sensiveis_encryption_key
    if not key:
        raise CryptoConfigError(
            "DADOS_SENSIVEIS_ENCRYPTION_KEY não configurada — impossível cifrar dados sensíveis."
        )
    return Fernet(key.encode())


def encrypt(texto: str | None) -> str | None:
    if not texto:
        return texto
    return _fernet().encrypt(texto.encode()).decode()


def decrypt(cifrado: str | None) -> str | None:
    if not cifrado:
        return cifrado
    return _fernet().decrypt(cifrado.encode()).decode()
