import pytest

from app.core import crypto
from app.config import get_settings


def test_encrypt_decrypt_roundtrip(monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("DADOS_SENSIVEIS_ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    crypto._fernet.cache_clear()
    cif = crypto.encrypt("agencia-1234")
    assert cif != "agencia-1234"
    assert crypto.decrypt(cif) == "agencia-1234"


def test_none_and_empty_passthrough():
    assert crypto.encrypt(None) is None
    assert crypto.encrypt("") == ""
    assert crypto.decrypt(None) is None
    assert crypto.decrypt("") == ""


def test_missing_key_raises(monkeypatch):
    monkeypatch.setenv("DADOS_SENSIVEIS_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    crypto._fernet.cache_clear()
    with pytest.raises(crypto.CryptoConfigError):
        crypto.encrypt("x")
