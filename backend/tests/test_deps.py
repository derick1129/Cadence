"""Tests for authentication, tenant context, and RBAC FastAPI dependencies."""

from datetime import timedelta

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core.deps import (
    TokenClaims,
    get_current_tenant_id,
    get_current_user_id,
    get_token_claims,
    require_roles,
)
from backend.app.core.errors import AppError, app_error_handler
from backend.app.core.security import create_access_token


@pytest.fixture
def test_deps_app() -> FastAPI:
    """Create test FastAPI application utilizing auth dependencies."""
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    @app.get("/test/claims")
    async def claims_route(claims: TokenClaims = Depends(get_token_claims)) -> dict[str, str]:
        return {"user_id": claims.user_id, "org_id": claims.organization_id, "role": claims.role}

    @app.get("/test/user")
    async def user_route(user_id: str = Depends(get_current_user_id)) -> dict[str, str]:
        return {"user_id": user_id}

    @app.get("/test/tenant")
    async def tenant_route(org_id: str = Depends(get_current_tenant_id)) -> dict[str, str]:
        return {"organization_id": org_id}

    @app.get("/test/admin-only")
    async def admin_route(
        claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    ) -> dict[str, str]:
        return {"status": "ok", "role": claims.role}

    return app


@pytest.mark.asyncio
async def test_deps_valid_token(test_deps_app: FastAPI) -> None:
    """Verify endpoints accept valid JWT bearer tokens and extract tenant claims."""
    token = create_access_token(
        data={"sub": "usr-123", "organization_id": "org-456", "role": "admin"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=test_deps_app), base_url="http://test"
    ) as client:
        res = await client.get("/test/claims", headers=headers)
        assert res.status_code == 200
        assert res.json() == {"user_id": "usr-123", "org_id": "org-456", "role": "admin"}

        res = await client.get("/test/user", headers=headers)
        assert res.status_code == 200
        assert res.json() == {"user_id": "usr-123"}

        res = await client.get("/test/tenant", headers=headers)
        assert res.status_code == 200
        assert res.json() == {"organization_id": "org-456"}

        res = await client.get("/test/admin-only", headers=headers)
        assert res.status_code == 200
        assert res.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_deps_tenant_header_matching_and_mismatch(test_deps_app: FastAPI) -> None:
    """Verify X-Organization-Id consistency check."""
    token = create_access_token(
        data={"sub": "usr-123", "organization_id": "org-456", "role": "member"}
    )
    valid_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": "org-456"}
    mismatch_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": "org-other"}

    async with AsyncClient(
        transport=ASGITransport(app=test_deps_app), base_url="http://test"
    ) as client:
        # Matching header succeeds
        res = await client.get("/test/tenant", headers=valid_headers)
        assert res.status_code == 200
        assert res.json() == {"organization_id": "org-456"}

        # Mismatching header is rejected with 403 TENANT_MISMATCH
        res = await client.get("/test/tenant", headers=mismatch_headers)
        assert res.status_code == 403
        data = res.json()
        assert data["error"]["code"] == "TENANT_MISMATCH"


@pytest.mark.asyncio
async def test_deps_missing_and_invalid_auth_header(test_deps_app: FastAPI) -> None:
    """Verify rejection when Authorization header is absent or empty."""
    async with AsyncClient(
        transport=ASGITransport(app=test_deps_app), base_url="http://test"
    ) as client:
        # Missing header
        res = await client.get("/test/claims")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"

        # Empty bearer credentials
        res = await client.get("/test/claims", headers={"Authorization": "Bearer "})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_deps_expired_and_invalid_tokens(test_deps_app: FastAPI) -> None:
    """Verify rejection of expired, tampered, or incomplete tokens."""
    async with AsyncClient(
        transport=ASGITransport(app=test_deps_app), base_url="http://test"
    ) as client:
        # Expired token
        expired_token = create_access_token(
            data={"sub": "usr-123", "organization_id": "org-456", "role": "admin"},
            expires_delta=timedelta(seconds=-10),
        )
        res = await client.get("/test/claims", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "TOKEN_EXPIRED"

        # Tampered / malformed token
        res = await client.get(
            "/test/claims", headers={"Authorization": "Bearer invalid.jwt.payload"}
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "TOKEN_INVALID"

        # Token missing tenant claims (missing organization_id)
        incomplete_token = create_access_token(data={"sub": "usr-123"})
        res = await client.get(
            "/test/claims", headers={"Authorization": f"Bearer {incomplete_token}"}
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "TOKEN_INVALID"


@pytest.mark.asyncio
async def test_deps_role_based_access(test_deps_app: FastAPI) -> None:
    """Verify role-based access control enforcement."""
    async with AsyncClient(
        transport=ASGITransport(app=test_deps_app), base_url="http://test"
    ) as client:
        # Role member denied on admin-only route
        member_token = create_access_token(
            data={"sub": "usr-789", "organization_id": "org-456", "role": "member"}
        )
        res = await client.get(
            "/test/admin-only", headers={"Authorization": f"Bearer {member_token}"}
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "FORBIDDEN"

        # Role owner allowed on admin-only route (allowed_roles: owner, admin)
        owner_token = create_access_token(
            data={"sub": "usr-owner", "organization_id": "org-456", "role": "owner"}
        )
        res = await client.get(
            "/test/admin-only", headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert res.status_code == 200
        assert res.json()["role"] == "owner"
