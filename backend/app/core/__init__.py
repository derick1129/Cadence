"""Core application configuration, errors, and shared utilities."""

from backend.app.core.base import Base, TimestampMixin
from backend.app.core.db import get_db
from backend.app.core.deps import (
    TokenClaims,
    get_current_tenant_id,
    get_current_user_id,
    get_token_claims,
    require_roles,
)
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
    "TokenClaims",
    "TokenExpiredError",
    "TokenInvalidError",
    "app_error_handler",
    "compare_digest",
    "create_access_token",
    "decode_access_token",
    "generate_secure_token",
    "get_current_tenant_id",
    "get_current_user_id",
    "get_db",
    "get_token_claims",
    "hash_password",
    "hash_token",
    "require_roles",
    "settings",
    "verify_password",
]
