"""Core application configuration, errors, and shared utilities."""

from backend.app.core.base import Base, TimestampMixin
from backend.app.core.errors import AppError, app_error_handler
from backend.app.core.security import (
    SecurityError,
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
from backend.app.core.settings import Settings, settings

__all__ = [
    "AppError",
    "Base",
    "SecurityError",
    "Settings",
    "TimestampMixin",
    "TokenExpiredError",
    "TokenInvalidError",
    "app_error_handler",
    "compare_digest",
    "create_access_token",
    "decode_access_token",
    "generate_secure_token",
    "hash_password",
    "hash_token",
    "settings",
    "verify_password",
]
