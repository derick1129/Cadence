"""Authentication router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.deps import TokenClaims, get_token_claims
from backend.app.modules.auth.repository import AuthRepository
from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from backend.app.modules.auth.service import AuthService
from backend.app.modules.organizations.repository import OrganizationRepository
from backend.app.modules.organizations.service import OrganizationService

router = APIRouter(prefix="/auth", tags=["auth"])

# Ensure class-level mock dictionaries exist for fallback/test persistence
if not hasattr(AuthRepository, "_mock_users"):
    AuthRepository._mock_users = {}
if not hasattr(AuthRepository, "_mock_tokens"):
    AuthRepository._mock_tokens = {}
if not hasattr(OrganizationRepository, "_mock_orgs"):
    OrganizationRepository._mock_orgs = {}
if not hasattr(OrganizationRepository, "_mock_members"):
    OrganizationRepository._mock_members = []


def get_auth_service(
    session: AsyncSession = Depends(get_db),
) -> AuthService:
    """Dependency provider returning a database-backed AuthService instance."""
    org_repo = OrganizationRepository(session=session)
    if session is None:
        org_repo._mock_orgs = getattr(OrganizationRepository, "_mock_orgs", org_repo._mock_orgs)
        org_repo._mock_members = getattr(
            OrganizationRepository, "_mock_members", org_repo._mock_members
        )
    org_service = OrganizationService(repository=org_repo)
    auth_repo = AuthRepository(session=session)
    if session is None:
        auth_repo._mock_users = getattr(AuthRepository, "_mock_users", auth_repo._mock_users)
        auth_repo._mock_tokens = getattr(AuthRepository, "_mock_tokens", auth_repo._mock_tokens)
    return AuthService(repository=auth_repo, org_service=org_service)


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
