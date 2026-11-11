"""Password hashing (bcrypt) and JWT helpers."""

import base64
import hashlib
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from app.core.config import settings


def _prehash(password: str) -> bytes:
    """SHA-256 + base64 keeps any password within bcrypt's 72-byte input limit."""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))
    except ValueError:
        return False


@lru_cache(maxsize=1)
def dummy_hash() -> str:
    """Used to spend equal time when a login email is unknown."""
    return hash_password("not-a-real-password")


def create_access_token(*, user_id: UUID, session_id: UUID, expires_at: datetime) -> str:
    claims = {
        "sub": str(user_id),
        "jti": str(session_id),
        "iat": datetime.now(UTC),
        "exp": expires_at,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Return the claims, or None if the token is invalid or expired."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
