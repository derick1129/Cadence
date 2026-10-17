"""Authentication router."""

from fastapi import APIRouter, Depends

from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
)
from backend.app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(
    request: SignupRequest,
    service: AuthService = Depends(AuthService),
) -> TokenResponse:
    """Register a new user account."""
    return await service.signup(request)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(AuthService),
) -> TokenResponse:
    """Authenticate and obtain JWT credentials."""
    return await service.login(request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    service: AuthService = Depends(AuthService),
) -> TokenResponse:
    """Refresh an access token using a refresh token."""
    return await service.refresh_token(request)
