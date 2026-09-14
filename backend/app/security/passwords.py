"""argon2id password hashing."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2id, library defaults (t=3, m=64MiB, p=4)


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    """Constant-ish time: an unknown user still burns a hash verification."""
    if not hashed:
        _hasher.verify(_DUMMY, "not-the-password")  # same cost as a real check
        return False
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _hasher.check_needs_rehash(hashed)


_DUMMY = _hasher.hash("dummy-password-for-timing")
