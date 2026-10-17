"""Authentication router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.deps import TokenClaims, get_token_claims
from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from backend.app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    session: AsyncSession = Depends(get_db),
) -> AuthService:
    """Dependency provider returning a database-backed AuthService instance."""
    return AuthService(session=session)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def signup(
    request: SignupRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Register a new user account and default organization."""
    return await service.signup(request)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Authenticate and obtain JWT credentials."""
    return await service.login(request)


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    request: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Refresh an access token using a valid refresh token."""
    return await service.refresh_token(request)


@router.get("/me", response_model=UserResponse)
async def get_me(
    claims: TokenClaims = Depends(get_token_claims),
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Retrieve profile of the currently authenticated user."""
    user = await service.get_user_by_id(claims.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
