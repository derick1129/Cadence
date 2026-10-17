"""Tests for Organization HTTP router endpoints."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core.errors import AppError, app_error_handler
from backend.app.core.security import create_access_token
from backend.app.modules.organizations.router import (
    get_organization_service,
)
from backend.app.modules.organizations.router import (
    router as org_router,
)
from backend.app.modules.organizations.service import OrganizationService


@pytest.fixture
def org_app() -> FastAPI:
    """FastAPI test app for organizations module."""
    app = FastAPI(title="Org Test App")
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.include_router(org_router)
    shared_service = OrganizationService()
    app.dependency_overrides[get_organization_service] = lambda: shared_service
    return app


@pytest.mark.asyncio
async def test_organization_router_endpoints(org_app: FastAPI) -> None:
    """Verify organization HTTP endpoints."""
    async with AsyncClient(transport=ASGITransport(app=org_app), base_url="http://test") as client:
        # Unauthenticated request is rejected
        unauth_res = await client.post("/organizations", json={"name": "No Auth Org"})
        assert unauth_res.status_code == 401

        # Create organization with auth token
        user_id = str(uuid.uuid4())
        tok = create_access_token(
            {"sub": user_id, "organization_id": str(uuid.uuid4()), "role": "owner"}
        )
        res = await client.post(
            "/organizations", json={"name": "HTTP Org"}, headers={"Authorization": f"Bearer {tok}"}
        )
        assert res.status_code == 201
        org_id = res.json()["id"]

        token = create_access_token({"sub": user_id, "organization_id": org_id, "role": "owner"})
        headers = {"Authorization": f"Bearer {token}"}

        # Get organization
        res = await client.get(f"/organizations/{org_id}", headers=headers)
        assert res.status_code == 200 and res.json()["id"] == org_id

        # Invite member
        res = await client.post(
            f"/organizations/{org_id}/members",
            headers=headers,
            json={"email": "colleague@example.com", "role": "member"},
        )
        assert res.status_code == 201 and res.json()["email"] == "colleague@example.com"

        # List members
        res = await client.get(f"/organizations/{org_id}/members", headers=headers)
        assert res.status_code == 200
        assert any(m["email"] == "colleague@example.com" for m in res.json())
        assert any(m["role"] == "owner" and m["user_id"] == user_id for m in res.json())

        # Get non-existent organization with token matching that id (should 404, not 403)
        bad_tok = create_access_token(
            {"sub": "usr", "organization_id": "non-existent-id", "role": "owner"}
        )
        res = await client.get(
            "/organizations/non-existent-id", headers={"Authorization": f"Bearer {bad_tok}"}
        )
        assert res.status_code == 404
