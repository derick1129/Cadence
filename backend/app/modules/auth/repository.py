"""Authentication repository."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.auth.models import RefreshToken, User


class AuthRepository:
    """Repository handling persistence for users and authentication tokens."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self._mock_users: dict[str, dict[str, Any]] = {}
        self._mock_tokens: dict[str, dict[str, Any]] = {}

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Fetch user record by email address."""
        normalized_email = email.strip().lower()
        if self.session is not None:
            result = await self.session.execute(select(User).where(User.email == normalized_email))
            user = result.scalar_one_or_none()
            if not user:
                return None
            return {
                "id": str(user.id),
                "email": user.email,
                "password_hash": user.password_hash,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
        for u in self._mock_users.values():
            if u["email"] == normalized_email:
                return u
        return None

    async def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Fetch user record by ID."""
        if self.session is not None:
            try:
                u_uuid = uuid.UUID(user_id)
            except ValueError:
                return None
            result = await self.session.execute(select(User).where(User.id == u_uuid))
            user = result.scalar_one_or_none()
            if not user:
                return None
            return {
                "id": str(user.id),
                "email": user.email,
                "password_hash": user.password_hash,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
        return self._mock_users.get(user_id)

    async def create_user(self, email: str, password_hash: str) -> dict[str, Any]:
        """Create a new user record."""
        now = datetime.now(UTC)
        normalized_email = email.strip().lower()
        if self.session is not None:
            user = User(
                email=normalized_email,
                password_hash=password_hash,
                is_active=True,
            )
            self.session.add(user)
            await self.session.flush()
            return {
                "id": str(user.id),
                "email": user.email,
                "password_hash": user.password_hash,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
        user_id = str(uuid.uuid4())
        record = {
            "id": user_id,
            "email": normalized_email,
            "password_hash": password_hash,
            "is_active": True,
            "created_at": now,
        }
        self._mock_users[user_id] = record
        return record

    async def store_refresh_token(
        self, user_id: str, token_hash: str, expires_at: datetime
    ) -> None:
        """Store a hashed refresh token."""
        if self.session is not None:
            token = RefreshToken(
                user_id=uuid.UUID(user_id),
                token_hash=token_hash,
                expires_at=expires_at,
            )
            self.session.add(token)
            await self.session.flush()
            return
        self._mock_tokens[token_hash] = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "revoked_at": None,
        }

    async def get_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        """Look up refresh token by its SHA-256 hash."""
        if self.session is not None:
            result = await self.session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
            token = result.scalar_one_or_none()
            if not token:
                return None
            return {
                "id": str(token.id),
                "user_id": str(token.user_id),
                "token_hash": token.token_hash,
                "expires_at": token.expires_at,
                "revoked_at": token.revoked_at,
            }
        return self._mock_tokens.get(token_hash)

    async def revoke_refresh_token(self, token_hash: str) -> None:
        """Revoke a refresh token by setting revoked_at timestamp."""
        now = datetime.now(UTC)
        if self.session is not None:
            await self.session.execute(
                update(RefreshToken)
                .where(RefreshToken.token_hash == token_hash)
                .values(revoked_at=now)
            )
            await self.session.flush()
            return
        token = self._mock_tokens.get(token_hash)
        if token:
            token["revoked_at"] = now
