"""Authentication schemas."""

from pydantic import BaseModel, ConfigDict


class SignupRequest(BaseModel):
    """Payload for user and organization registration."""

    email: str
    password: str
    organization_name: str | None = None


class LoginRequest(BaseModel):
    """Payload for user authentication."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """Response containing access and optional refresh tokens."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900
    refresh_token: str | None = None


class RefreshTokenRequest(BaseModel):
    """Payload for refreshing an expired access token."""

    refresh_token: str


class UserResponse(BaseModel):
    """Public user profile response."""

    id: str
    email: str
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)
