"""Tests for Authentication repository and service."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.app.core.errors import AppError
from backend.app.core.security import decode_access_token, hash_password, hash_token
from backend.app.modules.auth.repository import AuthRepository
from backend.app.modules.auth.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    SignupRequest,
)
from backend.app.modules.auth.service import AuthService
from backend.app.modules.organizations import OrganizationService


@pytest.fixture
def auth_components() -> tuple[AuthService, AuthRepository, OrganizationService]:
    """Provide initialized AuthService, AuthRepository, and OrganizationService instances."""
    org_service = OrganizationService()
    auth_repo = AuthRepository()
    auth_service = AuthService(repository=auth_repo, org_service=org_service)
    return auth_service, auth_repo, org_service


@pytest.mark.asyncio
async def test_auth_signup_login_and_refresh() -> None:
    """Verify signup creates user/org, login verifies password, and refresh rotates token."""
    org_service = OrganizationService()
    auth_repo = AuthRepository()
    auth_service = AuthService(repository=auth_repo, org_service=org_service)

    # 1. Signup
    signup_req = SignupRequest(
        email="developer@example.com",
        password="ValidPassword123!",
        organization_name="Developer Inc",
    )
    tokens = await auth_service.signup(signup_req)
    assert tokens.access_token != ""
    assert tokens.refresh_token is not None

    # Verify access token payload
    claims = decode_access_token(tokens.access_token)
    assert claims["role"] == "owner"
    assert claims["organization_id"] != ""
    assert claims["sub"] != ""

    # 2. Duplicate signup fails (case-insensitive)
    dup_req = SignupRequest(
        email="DEVELOPER@example.com",
        password="ValidPassword123!",
        organization_name="Duplicate Org",
    )
    with pytest.raises(AppError) as exc_info:
        await auth_service.signup(dup_req)
    assert exc_info.value.code == "USER_ALREADY_EXISTS"
    assert exc_info.value.status_code == 409

    # 3. Login with correct password
    login_req = LoginRequest(
        email="developer@example.com",
        password="ValidPassword123!",
    )
    login_tokens = await auth_service.login(login_req)
    assert login_tokens.access_token != ""
    assert login_tokens.refresh_token is not None

    # 4. Login with invalid password fails
    bad_login = LoginRequest(
        email="developer@example.com",
        password="WrongPassword123!",
    )
    with pytest.raises(AppError) as bad_exc:
        await auth_service.login(bad_login)
    assert bad_exc.value.code == "INVALID_CREDENTIALS"
    assert bad_exc.value.status_code == 401

    # 5. Token refresh rotates token
    refresh_req = RefreshTokenRequest(refresh_token=login_tokens.refresh_token)
    new_tokens = await auth_service.refresh_token(refresh_req)
    assert new_tokens.access_token != ""
    assert new_tokens.refresh_token != login_tokens.refresh_token

    # 6. Reusing old refresh token fails (revoked)
    with pytest.raises(AppError) as revoked_exc:
        await auth_service.refresh_token(refresh_req)
    assert revoked_exc.value.code == "INVALID_REFRESH_TOKEN"
    assert revoked_exc.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_login_unknown_user(
    auth_components: tuple[AuthService, AuthRepository, OrganizationService],
) -> None:
    """Verify login with non-existent email returns 401 INVALID_CREDENTIALS."""
    auth_service, _, _ = auth_components
    req = LoginRequest(email="nonexistent@example.com", password="Password123!")
    with pytest.raises(AppError) as exc_info:
        await auth_service.login(req)
    assert exc_info.value.code == "INVALID_CREDENTIALS"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_login_deactivated_user(
    auth_components: tuple[AuthService, AuthRepository, OrganizationService],
) -> None:
    """Verify login for deactivated account returns 403 USER_INACTIVE."""
    auth_service, auth_repo, _ = auth_components
    await auth_service.signup(SignupRequest(email="inactive@example.com", password="Password123!"))
    user = await auth_repo.get_user_by_email("inactive@example.com")
    assert user is not None
    user["is_active"] = False

    with pytest.raises(AppError) as exc_info:
        await auth_service.login(
            LoginRequest(email="inactive@example.com", password="Password123!")
        )
    assert exc_info.value.code == "USER_INACTIVE"
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_login_no_tenant_membership(
    auth_components: tuple[AuthService, AuthRepository, OrganizationService],
) -> None:
    """Verify login for user without any tenant memberships returns 403 NO_TENANT_MEMBERSHIP."""
    auth_service, auth_repo, _ = auth_components
    await auth_repo.create_user(
        email="nomembership@example.com",
        password_hash=hash_password("Password123!"),
    )
    with pytest.raises(AppError) as exc_info:
        await auth_service.login(
            LoginRequest(email="nomembership@example.com", password="Password123!")
        )
    assert exc_info.value.code == "NO_TENANT_MEMBERSHIP"
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_refresh_token_expired(
    auth_components: tuple[AuthService, AuthRepository, OrganizationService],
) -> None:
    """Verify expired refresh token is rejected with 401 INVALID_REFRESH_TOKEN."""
    auth_service, auth_repo, _ = auth_components
    tokens = await auth_service.signup(
        SignupRequest(email="expiring@example.com", password="Password123!")
    )
    assert tokens.refresh_token is not None

    token_digest = hash_token(tokens.refresh_token)
    stored = await auth_repo.get_refresh_token(token_digest)
    assert stored is not None
    stored["expires_at"] = datetime.now(UTC) - timedelta(hours=1)

    with pytest.raises(AppError) as exc_info:
        await auth_service.refresh_token(RefreshTokenRequest(refresh_token=tokens.refresh_token))
    assert exc_info.value.code == "INVALID_REFRESH_TOKEN"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_refresh_token_invalid_hash(
    auth_components: tuple[AuthService, AuthRepository, OrganizationService],
) -> None:
    """Verify unknown or tampered refresh token is rejected with 401 INVALID_REFRESH_TOKEN."""
    auth_service, _, _ = auth_components
    with pytest.raises(AppError) as exc_info:
        await auth_service.refresh_token(
            RefreshTokenRequest(refresh_token="non-existent-refresh-token")
        )
    assert exc_info.value.code == "INVALID_REFRESH_TOKEN"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_refresh_token_deactivated_user(
    auth_components: tuple[AuthService, AuthRepository, OrganizationService],
) -> None:
    """Verify refresh token for deactivated account returns 403 USER_INACTIVE."""
    auth_service, auth_repo, _ = auth_components
    tokens = await auth_service.signup(
        SignupRequest(email="inactive-refresh@example.com", password="Password123!")
    )
    assert tokens.refresh_token is not None

    user = await auth_repo.get_user_by_email("inactive-refresh@example.com")
    assert user is not None
    user["is_active"] = False

    with pytest.raises(AppError) as exc_info:
        await auth_service.refresh_token(RefreshTokenRequest(refresh_token=tokens.refresh_token))
    assert exc_info.value.code == "USER_INACTIVE"
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_get_user_by_id(
    auth_components: tuple[AuthService, AuthRepository, OrganizationService],
) -> None:
    """Verify get_user_by_id retrieves user details or None if not found."""
    auth_service, _, _ = auth_components
    non_existent = await auth_service.get_user_by_id("non-existent-id")
    assert non_existent is None

    tokens = await auth_service.signup(
        SignupRequest(email="getuser@example.com", password="Password123!")
    )
    claims = decode_access_token(tokens.access_token)
    user_resp = await auth_service.get_user_by_id(claims["sub"])
    assert user_resp is not None
    assert user_resp.id == claims["sub"]
    assert user_resp.email == "getuser@example.com"
    assert user_resp.is_active is True
