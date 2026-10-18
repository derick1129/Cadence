"""End-to-end tests verifying tenant isolation and role permissions.

Covers cross-tenant access, RBAC, and unauthenticated rejections across auth and organizations.
"""

from collections.abc import Generator

import pytest
from httpx import AsyncClient

from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.modules.auth.repository import AuthRepository
from backend.app.modules.auth.router import get_auth_service
from backend.app.modules.auth.service import AuthService
from backend.app.modules.organizations.repository import OrganizationRepository
from backend.app.modules.organizations.router import get_organization_service
from backend.app.modules.organizations.service import OrganizationService


@pytest.fixture(autouse=True)
def mock_isolated_services() -> Generator[None, None, None]:
    """Provide isolated in-memory repositories and services for each test."""
    org_repo = OrganizationRepository(session=None)
    org_service = OrganizationService(repository=org_repo)
    auth_repo = AuthRepository(session=None)
    auth_service = AuthService(repository=auth_repo, org_service=org_service)

    app.dependency_overrides[get_organization_service] = lambda: org_service
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    yield
    app.dependency_overrides.pop(get_organization_service, None)
    app.dependency_overrides.pop(get_auth_service, None)


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(async_client: AsyncClient) -> None:
    """Verify that requests without Authorization header to protected endpoints return 401."""
    org_id = "org-unauth-test"

    res_org = await async_client.get(f"/organizations/{org_id}")
    assert res_org.status_code == 401

    res_members = await async_client.get(f"/organizations/{org_id}/members")
    assert res_members.status_code == 401

    res_me = await async_client.get("/organizations/me")
    assert res_me.status_code == 401

    res_curr_members = await async_client.get("/organizations/members")
    assert res_curr_members.status_code == 401


@pytest.mark.asyncio
async def test_cross_tenant_organization_isolation(async_client: AsyncClient) -> None:
    """Verify that Organization A members cannot read or modify Organization B data."""
    # User A in Org Alpha (Owner)
    token_alpha = create_access_token(
        data={"sub": "usr-alpha", "organization_id": "org-alpha-123", "role": "owner"}
    )
    headers_alpha = {"Authorization": f"Bearer {token_alpha}"}

    # User B in Org Beta (Member)
    token_beta = create_access_token(
        data={"sub": "usr-beta", "organization_id": "org-beta-456", "role": "member"}
    )
    headers_beta = {"Authorization": f"Bearer {token_beta}"}

    # User A accesses own org -> 200 or 404 (if not seeded, but not forbidden)
    res_a = await async_client.get("/organizations/org-alpha-123", headers=headers_alpha)
    assert res_a.status_code in (200, 404)

    # User B attempts to access Org A -> Forbidden 403
    res_b_cross = await async_client.get(
        "/organizations/org-alpha-123",
        headers={"Authorization": f"Bearer {token_beta}", "X-Organization-Id": "org-alpha-123"},
    )
    assert res_b_cross.status_code == 403

    # User B attempts to list members of Org A -> Forbidden 403
    res_b_members = await async_client.get(
        "/organizations/org-alpha-123/members",
        headers=headers_beta,
    )
    assert res_b_members.status_code == 403

    # User B attempts to invite someone into Org A -> Forbidden 403
    invite_res = await async_client.post(
        "/organizations/org-alpha-123/members",
        headers=headers_beta,
        json={"email": "attacker@example.com", "role": "admin"},
    )
    assert invite_res.status_code == 403

    # User B attempts to delete someone from Org A -> Forbidden 403
    delete_res = await async_client.delete(
        "/organizations/org-alpha-123/members/usr-alpha",
        headers=headers_beta,
    )
    assert delete_res.status_code == 403


@pytest.mark.asyncio
async def test_auth_signup_and_protected_access(async_client: AsyncClient) -> None:
    """Verify full HTTP signup, token acquisition, and protected tenant access under /api/v1."""
    email = "integration_test@example.com"
    signup_res = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "PasswordStrong123!",
            "organization_name": "Integration Inc",
        },
    )
    assert signup_res.status_code == 200
    tokens = signup_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    auth_header = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Profile lookup
    me_res = await async_client.get("/api/v1/auth/me", headers=auth_header)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email

    # Tenant org lookup
    org_res = await async_client.get("/api/v1/organizations/me", headers=auth_header)
    assert org_res.status_code == 200
    assert org_res.json()["name"] == "Integration Inc"

    # Member list via /api/v1/organizations/members
    members_res = await async_client.get("/api/v1/organizations/members", headers=auth_header)
    assert members_res.status_code == 200
    assert len(members_res.json()) >= 1

    # Member list via root /organizations/current/members alias
    curr_members_res = await async_client.get(
        "/organizations/current/members",
        headers=auth_header,
    )
    assert curr_members_res.status_code == 200
    assert len(curr_members_res.json()) >= 1


@pytest.mark.asyncio
async def test_member_management_rbac_and_isolation(async_client: AsyncClient) -> None:
    """Verify owner/admin can invite and remove members, while member role cannot."""
    # 1. Signup owner of Org A
    owner_res = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "corp_owner@example.com",
            "password": "PasswordStrong123!",
            "organization_name": "Corp A",
        },
    )
    owner_token = owner_res.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Owner invites a new member
    invite_res = await async_client.post(
        "/api/v1/organizations/members",
        headers=owner_headers,
        json={"email": "employee@example.com", "role": "member"},
    )
    assert invite_res.status_code == 201
    invited_data = invite_res.json()
    invited_user_id = invited_data["user_id"]

    # 3. Create a member-only token for Org A
    member_token = create_access_token(
        data={
            "sub": invited_user_id,
            "organization_id": invited_data["organization_id"],
            "role": "member",
        }
    )
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # 4. Member attempts to invite someone -> Forbidden 403
    unauth_invite = await async_client.post(
        "/api/v1/organizations/members",
        headers=member_headers,
        json={"email": "hacker@example.com", "role": "admin"},
    )
    assert unauth_invite.status_code == 403

    # 5. Member attempts to delete another member -> Forbidden 403
    unauth_delete = await async_client.delete(
        f"/api/v1/organizations/members/{invited_user_id}",
        headers=member_headers,
    )
    assert unauth_delete.status_code == 403

    # 6. Owner deletes the member -> 200 OK
    delete_res = await async_client.delete(
        f"/api/v1/organizations/members/{invited_user_id}",
        headers=owner_headers,
    )
    assert delete_res.status_code == 200

    # 7. Attempting to delete non-existent member -> 404
    delete_again = await async_client.delete(
        f"/api/v1/organizations/members/{invited_user_id}",
        headers=owner_headers,
    )
    assert delete_again.status_code == 404


@pytest.mark.asyncio
async def test_token_rotation_and_revocation(async_client: AsyncClient) -> None:
    """Verify refresh token rotation and rejection of replayed/revoked tokens."""
    signup_res = await async_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "rotation_test@example.com",
            "password": "PasswordStrong123!",
            "organization_name": "Rotation Inc",
        },
    )
    tokens = signup_res.json()
    first_refresh = tokens["refresh_token"]

    # Refresh token rotation
    refresh_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert new_tokens["refresh_token"] != first_refresh

    # Replay of revoked token fails
    replay_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert replay_res.status_code in (401, 403)
