"""Security, password hashing (Argon2id), and JWT authentication utilities."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

# Argon2id password hasher configured with OWASP recommended baseline parameters
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Args:
        password: Raw user password string.

    Returns:
        str: Cryptographic Argon2id password hash.

    Raises:
        ValueError: If password length does not satisfy bounds (8-128 characters).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters.")
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.

    Args:
        plain_password: Raw password entered by user.
        hashed_password: Stored Argon2id hash string.

    Returns:
        bool: True if password matches hash, False otherwise.
    """
    if not plain_password or len(plain_password) > MAX_PASSWORD_LENGTH:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    subject: str | uuid.UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token containing subject, issued-at, and expiration claims.

    Args:
        subject: The unique user identifier (UUID or string).
        expires_delta: Optional custom token lifespan duration.

    Returns:
        str: Encoded HS256 JWT access token string.
    """
    now = datetime.now(UTC)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT access token.

    Args:
        token: Raw JWT bearer token string.

    Returns:
        dict[str, Any]: Decoded token claims dictionary containing sub, iat, exp.

    Raises:
        jwt.ExpiredSignatureError: If token expiration (exp) is in the past.
        jwt.InvalidTokenError: If signature, claims, or format are invalid.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp"]},
    )
