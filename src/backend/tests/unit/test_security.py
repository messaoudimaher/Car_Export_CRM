"""Unit tests for Cryptographic Security Utilities (ADR 0005 & SECURITY.md compliance)."""

import uuid
from datetime import timedelta

import pytest

from app.core.errors import UnauthorizedException
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_argon2id_password_hashing_and_verification() -> None:
    """Verify password hashing generates valid Argon2id hash and verifies correctly."""
    plain_password = "SuperSecretPassword123!"  # noqa: S105
    hashed = hash_password(plain_password)

    assert hashed != plain_password
    assert hashed.startswith("$argon2id$")
    assert verify_password(plain_password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_jwt_access_token_creation_and_decoding() -> None:
    """Verify JWT access token creation encodes expected claims and decodes cleanly."""
    user_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    role = "SalesAgent"

    token = create_access_token(subject=user_id, tenant_id=tenant_id, role=role)
    payload = decode_access_token(token)

    assert payload["sub"] == user_id
    assert payload["tenant_id"] == tenant_id
    assert payload["role"] == role
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_access_token_expiration_rejection() -> None:
    """Verify expired JWT token raises UnauthorizedException."""
    token = create_access_token(
        subject="user_expired",
        tenant_id="tenant_expired",
        role="SalesAgent",
        expires_delta=timedelta(seconds=-10),
    )

    with pytest.raises(UnauthorizedException, match="Authentication token has expired"):
        decode_access_token(token)


def test_jwt_access_token_tampered_signature_rejection() -> None:
    """Verify tampered JWT token signature raises UnauthorizedException."""
    valid_token = create_access_token(
        subject="user_valid",
        tenant_id="tenant_valid",
        role="SalesAgent",
    )
    tampered_token = valid_token[:-5] + "XXXXX"

    with pytest.raises(UnauthorizedException, match="signature or claims are invalid"):
        decode_access_token(tampered_token)
