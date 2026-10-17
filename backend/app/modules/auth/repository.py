"""Authentication repository."""

from datetime import datetime
from typing import Any


class AuthRepository:
    """Repository handling persistence for users and authentication tokens."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch user record by email address."""
        return None

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Fetch user record by ID."""
        return None

    async def create_user(self, email: str, password_hash: str) -> dict[str, Any]:
        """Create a new user record."""
        return {
            "id": "mock-user-id",
            "email": email,
            "password_hash": password_hash,
            "is_active": True,
        }

    async def store_refresh_token(
        self, user_id: str, token_hash: str, expires_at: datetime
    ) -> None:
        """Store a hashed refresh token."""
        return None

    async def revoke_refresh_token(self, token_hash: str) -> None:
        """Revoke a refresh token by its hash."""
        return None
