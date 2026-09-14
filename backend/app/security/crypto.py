"""Field-level encryption for the [enc] columns (DATA_MODEL 1.2, 5 "Encryption boundary").

passengers.known_traveler_number / redress_number, account_holders.tax_id,
travel_documents.number, crew_members.license_number are stored as ciphertext
``bytea`` with a plaintext ``*_last4`` beside them for display. The API accepts
plaintext on write, stores ciphertext + last4, and never returns the plaintext.

Today: one Fernet key from APP_FIELD_ENCRYPTION_KEY. Per-tenant envelope
encryption (a DEK per tenant wrapped by a KMS) is the intended end state; the
call sites do not change when that lands.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

# Column -> its last4 column. Everything the API must never echo back.
ENCRYPTED_FIELDS: dict[str, str] = {
    "known_traveler_number": "ktn_last4",
    "redress_number": "",  # no last4 column in the schema; redacted entirely
    "tax_id": "tax_id_last4",
    "number": "number_last4",
    "license_number": "license_last4",
}
SENSITIVE_FIELDS = set(ENCRYPTED_FIELDS) | {"password_hash", "token_hash", "password"}


def _fernet() -> Fernet:
    return Fernet(get_settings().fernet_key)


def encrypt(plain: str) -> bytes:
    return _fernet().encrypt(plain.encode())


def decrypt(cipher: bytes) -> str:
    try:
        return _fernet().decrypt(bytes(cipher)).decode()
    except InvalidToken as e:
        raise ValueError("ciphertext cannot be decrypted with the configured key") from e


def last4(plain: str) -> str:
    return plain[-4:]


def redact(data: dict | None) -> dict | None:
    """Strip sensitive keys from a before/after snapshot before it reaches the audit trail."""
    if data is None:
        return None
    return {k: ("[redacted]" if k in SENSITIVE_FIELDS else v) for k, v in data.items()}
