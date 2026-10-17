"""Unit tests for security utilities and cryptographic helpers."""

from datetime import timedelta

import pytest

from backend.app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    compare_digest,
    create_access_token,
    decode_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_compare_digest() -> None:
    """Verify constant-time comparison helper behavior."""
    token = "cadence-internal-service-token-123"
    assert compare_digest(token, token) is True
    assert compare_digest(token, "different-token") is False
    assert compare_digest(token, token[:-1]) is False
    assert compare_digest(b"raw-bytes-key", b"raw-bytes-key") is True
    assert compare_digest(b"raw-bytes-key", b"different-bytes") is False


def test_password_hashing_and_verification() -> None:
    """Verify password hashing produces salted hashes and verifies accurately."""
    password = "CorrectHorseBatteryStaple123!"
    hashed = hash_password(password)

    # Hash must not contain plaintext password
    assert password not in hashed
    assert len(hashed) > 20

    # Verification checks
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(password, "malformed$hash$value") is False


def test_jwt_access_token_creation_and_decoding() -> None:
    """Verify JWT access token issuance, signature, and claims preservation."""
    claims = {
        "sub": "usr_01H1234567890",
        "organization_id": "org_01H9876543210",
        "role": "owner",
    }
    token = create_access_token(data=claims)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    decoded = decode_access_token(token)
    assert decoded["sub"] == claims["sub"]
    assert decoded["organization_id"] == claims["organization_id"]
    assert decoded["role"] == claims["role"]
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_custom_secret_key() -> None:
    """Verify JWT encoding and decoding with custom secret keys."""
    custom_secret = "custom-test-secret-key-with-sufficient-length-32"
    claims = {"sub": "usr_custom"}
    token = create_access_token(data=claims, secret_key=custom_secret)

    # Succeeds with matching secret
    decoded = decode_access_token(token, secret_key=custom_secret)
    assert decoded["sub"] == "usr_custom"

    # Fails with mismatched secret
    with pytest.raises(TokenInvalidError):
        decode_access_token(token, secret_key="wrong-secret-key-for-decoding-32")


def test_jwt_expired_token() -> None:
    """Verify expired JWTs raise TokenExpiredError."""
    claims = {"sub": "usr_expired"}
    # Token expired 10 seconds ago
    expired_token = create_access_token(
        data=claims,
        expires_delta=timedelta(seconds=-10),
    )

    with pytest.raises(TokenExpiredError):
        decode_access_token(expired_token)


def test_jwt_malformed_token() -> None:
    """Verify malformed tokens raise TokenInvalidError."""
    with pytest.raises(TokenInvalidError):
        decode_access_token("not-a-valid-jwt-token")

    with pytest.raises(TokenInvalidError):
        decode_access_token("header.payload")


def test_jwt_tampered_token() -> None:
    """Verify tampered payload or signature raises TokenInvalidError."""
    token = create_access_token(data={"sub": "usr_clean"})
    parts = token.split(".")
    # Mutate the payload
    tampered_token = f"{parts[0]}.eyJzdWIiOiJ1c3JfaGFja2VkIn0.{parts[2]}"

    with pytest.raises(TokenInvalidError):
        decode_access_token(tampered_token)


def test_secure_token_generation_and_hashing() -> None:
    """Verify random token generation and deterministic SHA-256 token hashing."""
    token1 = generate_secure_token(32)
    token2 = generate_secure_token(32)

    assert isinstance(token1, str)
    assert len(token1) >= 32
    assert token1 != token2

    # Deterministic hashing
    hash1 = hash_token(token1)
    hash2 = hash_token(token1)
    assert hash1 == hash2
    assert hash1 != hash_token(token2)
    assert len(hash1) == 64  # SHA-256 hex digest length
