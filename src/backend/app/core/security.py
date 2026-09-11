"""Cryptographic Security Utilities: Argon2id Password Hashing & JWT Token Management."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import argon2
import jwt

from app.core.config import settings
from app.core.errors import UnauthorizedException

# Initialize Argon2id password hasher with high work factor
_ph = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=8,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id algorithm.

    Args:
        password: Plaintext user password string.

    Returns:
        str: Encoded Argon2id hash string.
    """
    return _ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash string.

    Args:
        plain_password: Candidate plaintext password string.
        hashed_password: Stored Argon2id password hash.

    Returns:
        bool: True if password matches hash, False otherwise.
    """
    try:
        return _ph.verify(hashed_password, plain_password)
    except Exception:
        return False


def create_access_token(
    subject: str | UUID,
    tenant_id: str | UUID,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Encode a signed JWT access token containing identity & authorization claims.

    Claims encoded:
      - sub: User ID
      - tenant_id: Tenant ID
      - role: User RBAC Role
      - iat: Issued At UTC timestamp
      - nbf: Not Before UTC timestamp
      - exp: Expiration UTC timestamp

    Args:
        subject: Target User ID string or UUID.
        tenant_id: Associated Tenant ID string or UUID.
        role: User role string.
        expires_delta: Optional custom validity duration override.

    Returns:
        str: Encoded & signed JWT token string.
    """
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "tenant_id": str(tenant_id),
        "role": str(role),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT access token.

    Args:
        token: Incoming JWT Bearer token string.

    Raises:
        UnauthorizedException: If token signature is invalid, tampered, or expired.

    Returns:
        dict[str, Any]: Decoded claim dictionary.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException("Authentication token has expired. Please log in again.") from e
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException("Authentication token signature or claims are invalid.") from e
