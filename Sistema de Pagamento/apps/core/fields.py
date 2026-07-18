import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet():
    """Derives a stable Fernet key from FIELD_ENCRYPTION_KEY (RF66)."""
    digest = hashlib.sha256(settings.FIELD_ENCRYPTION_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


class EncryptedTextField(models.TextField):
    """
    Stores text encrypted at rest (Fernet/AES) — used for dados bancários de
    fornecedores (RF66). Encryption/decryption happens transparently on
    save/load; values are never stored or exposed in plaintext in the DB.
    """

    description = "Texto criptografado em repouso"

    def get_prep_value(self, value):
        if value is None or value == '':
            return value
        token = _get_fernet().encrypt(str(value).encode()).decode()
        return token

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, ValueError):
            # Data written before encryption was enabled, or key mismatch.
            return value

    def to_python(self, value):
        return value
