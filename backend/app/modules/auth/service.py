"""Authentication service."""

from backend.app.modules.auth.repository import AuthRepository
from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)


class AuthService:
    """Business logic for authentication, tokens, and registration."""

    def __init__(self, repository: AuthRepository | None = None) -> None:
        self.repository = repository or AuthRepository()

    async def signup(self, data: SignupRequest) -> TokenResponse:
        """Register a new user and generate initial tokens."""
        await self.repository.create_user(
            email=str(data.email),
            password_hash="mock-hash",
        )
        return TokenResponse(
            access_token="mock-access-token",
            token_type="bearer",
            refresh_token="mock-refresh-token",
        )

    async def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue tokens."""
        await self.repository.get_user_by_email(email=str(data.email))
        return TokenResponse(
            access_token="mock-access-token",
            token_type="bearer",
            refresh_token="mock-refresh-token",
        )

    async def refresh_token(self, data: RefreshTokenRequest) -> TokenResponse:
        """Issue a new access token from a valid refresh token."""
        return TokenResponse(
            access_token="mock-refreshed-token",
            token_type="bearer",
            refresh_token=data.refresh_token,
        )

    async def get_user_by_id(self, user_id: str) -> UserResponse | None:
        """Retrieve user details by ID."""
        user = await self.repository.get_user_by_id(user_id)
        if not user:
            return None
        return UserResponse(
            id=user["id"],
            email=user["email"],
            is_active=user.get("is_active", True),
        )
