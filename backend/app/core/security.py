"""Security helper functions for authentication, token generation, and hashing."""

import base64
import hashlib
import hmac
import importlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.core.settings import settings


# Optional third-party provider bindings (with standard library fallbacks)
def _resolve_optional_module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except Exception:
        return None


_passlib_context = _resolve_optional_module("passlib.context")
_pwd_context: Any = (
    _passlib_context.CryptContext(schemes=["bcrypt"], deprecated="auto")
    if _passlib_context is not None
    else None
)

_bcrypt_mod: Any = _resolve_optional_module("bcrypt")
_jwt_mod: Any = _resolve_optional_module("jwt")


ALGORITHM: str = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15


class SecurityError(ValueError):
    """Base exception for cryptographic and security verification failures."""


class TokenExpiredError(SecurityError):
    """Raised when an access token has expired."""


class TokenInvalidError(SecurityError):
    """Raised when a token signature, format, or payload is invalid."""


def compare_digest(val_a: str | bytes, val_b: str | bytes) -> bool:
    """Compare two strings or byte sequences in constant time to prevent timing attacks.

    Used for validating internal service tokens (X-Internal-Service-Token)
    and webhook signatures.
    """
    a_bytes = val_a.encode("utf-8") if isinstance(val_a, str) else val_a
    b_bytes = val_b.encode("utf-8") if isinstance(val_b, str) else val_b
    return hmac.compare_digest(a_bytes, b_bytes)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt, passlib, or secure PBKDF2-HMAC-SHA256."""
    if _pwd_context is not None:
        try:
            return str(_pwd_context.hash(password))
        except Exception:
            pass

    if _bcrypt_mod is not None:
        try:
            salt = _bcrypt_mod.gensalt()
            hashed_bytes = _bcrypt_mod.hashpw(password.encode("utf-8"), salt)
            return str(hashed_bytes.decode("utf-8"))
        except Exception:
            pass

    # Built-in PBKDF2-HMAC-SHA256 fallback (standard library)
    salt_hex = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_hex.encode("utf-8"),
        100_000,
    )
    return f"pbkdf2_sha256$100000${salt_hex}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hashed password."""
    if not plain_password or not hashed_password:
        return False

    try:
        # Check for PBKDF2 fallback format
        if hashed_password.startswith("pbkdf2_sha256$"):
            parts = hashed_password.split("$")
            if len(parts) != 4:
                return False
            iterations = int(parts[1])
            salt_hex = parts[2]
            expected_hex = parts[3]
            computed = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt_hex.encode("utf-8"),
                iterations,
            ).hex()
            return compare_digest(computed, expected_hex)

        # Check for bcrypt formats ($2a$, $2b$, $2y$)
        if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            if _pwd_context is not None:
                try:
                    return bool(_pwd_context.verify(plain_password, hashed_password))
                except Exception:
                    pass
            if _bcrypt_mod is not None:
                try:
                    return bool(
                        _bcrypt_mod.checkpw(
                            plain_password.encode("utf-8"),
                            hashed_password.encode("utf-8"),
                        )
                    )
                except Exception:
                    pass
            return False

        # Generic passlib verification fallback
        if _pwd_context is not None:
            try:
                return bool(_pwd_context.verify(plain_password, hashed_password))
            except Exception:
                return False

        return False
    except Exception:
        return False


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure random URL-safe token.

    Suitable for refresh tokens, session identifiers, and CSRF tokens.
    """
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Compute deterministic SHA-256 hex digest of an opaque token for DB storage.

    Refresh tokens and API keys are stored as hashes to prevent plain-text exposure.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64url_encode(data: bytes) -> str:
    """Encode bytes using base64url encoding without trailing padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(encoded: str) -> bytes:
    """Decode unpadded base64url string to bytes."""
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode("ascii"))


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
    secret_key: str | None = None,
) -> str:
    """Create a signed JWT access token containing tenant and user claims.

    Args:
        data: Claims to embed into the token (e.g. sub, organization_id, role).
        expires_delta: Optional custom duration before expiry. Defaults to 15 minutes.
        secret_key: Signing key. Defaults to settings.SECRET_KEY.

    Returns:
        Encoded and signed JWT string.
    """
    key = secret_key or settings.SECRET_KEY
    to_encode = data.copy()
    now = datetime.now(UTC)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update(
        {
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
        }
    )

    if _jwt_mod is not None:
        try:
            return str(_jwt_mod.encode(to_encode, key, algorithm=ALGORITHM))
        except Exception:
            pass

    # RFC 7519 compliant HS256 JWT encoding
    header_json = json.dumps({"alg": ALGORITHM, "typ": "JWT"}, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_json = json.dumps(to_encode, separators=(",", ":")).encode("utf-8")
    header_b64 = _b64url_encode(header_json)
    payload_b64 = _b64url_encode(payload_json)
    signing_input = f"{header_b64}.{payload_b64}"
    sig = hmac.new(key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{signing_input}.{sig_b64}"


def decode_access_token(
    token: str,
    secret_key: str | None = None,
) -> dict[str, Any]:
    """Decode and validate a signed JWT access token.

    Args:
        token: Encoded JWT string.
        secret_key: Secret key used to verify the signature. Defaults to settings.SECRET_KEY.

    Returns:
        Decoded payload dictionary with verified claims.

    Raises:
        TokenExpiredError: If the token expiration time is in the past.
        TokenInvalidError: If the token format, signature, or payload is invalid.
    """
    key = secret_key or settings.SECRET_KEY

    if _jwt_mod is not None:
        try:
            jwt_payload: Any = _jwt_mod.decode(token, key, algorithms=[ALGORITHM])
            if isinstance(jwt_payload, dict):
                return dict(jwt_payload)
        except getattr(_jwt_mod, "ExpiredSignatureError", Exception) as exc:
            raise TokenExpiredError("Access token has expired") from exc
        except Exception as exc:
            raise TokenInvalidError(f"Invalid access token: {exc}") from exc

    # RFC 7519 compliant HS256 validation
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenInvalidError("Malformed JWT access token: expected 3 dot-separated parts")

    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(
        key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()

    try:
        received_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise TokenInvalidError("Invalid signature encoding") from exc

    if not compare_digest(expected_sig, received_sig):
        raise TokenInvalidError("Invalid token signature")

    try:
        header_raw = _b64url_decode(header_b64)
        header_parsed: Any = json.loads(header_raw.decode("utf-8"))
        if not isinstance(header_parsed, dict):
            raise TokenInvalidError("Malformed JWT header: expected dictionary")
        if header_parsed.get("alg") != ALGORITHM:
            raise TokenInvalidError(f"Unsupported token algorithm: {header_parsed.get('alg')}")
    except Exception as exc:
        if isinstance(exc, TokenInvalidError):
            raise
        raise TokenInvalidError("Malformed JWT header") from exc

    try:
        payload_raw = _b64url_decode(payload_b64)
        payload_parsed: Any = json.loads(payload_raw.decode("utf-8"))
        if not isinstance(payload_parsed, dict):
            raise TokenInvalidError("Token payload must be a JSON object")
    except Exception as exc:
        if isinstance(exc, TokenInvalidError):
            raise
        raise TokenInvalidError("Malformed JWT payload") from exc

    payload: dict[str, Any] = dict(payload_parsed)
    if "exp" in payload:
        exp_timestamp = payload["exp"]
        if not isinstance(exp_timestamp, (int, float)):
            raise TokenInvalidError("Invalid 'exp' claim in token payload")
        current_timestamp = datetime.now(UTC).timestamp()
        if current_timestamp > exp_timestamp:
            raise TokenExpiredError("Access token has expired")

    return payload
