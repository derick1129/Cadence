"""Tests for the tools module including creation, execution, and cross-tenant access."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core.errors import AppError, app_error_handler
from backend.app.core.security import create_access_token
from backend.app.modules.tools import (
    ToolCreate,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolService,
    ToolUpdate,
    router,
)
from backend.app.modules.tools.router import get_tool_service


def make_auth_headers(
    org_id: str,
    role: str = "owner",
    user_id: str | None = None,
) -> dict[str, str]:
    """Generate JWT authorization header for tests."""
    token = create_access_token(
        data={
            "sub": user_id or str(uuid.uuid4()),
            "organization_id": org_id,
            "role": role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def tool_service() -> ToolService:
    """Fixture providing isolated ToolService."""
    return ToolService()


@pytest.fixture
def tool_app(tool_service: ToolService) -> FastAPI:
    """FastAPI test app containing tools router with overridden service and error handler."""
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.include_router(router)
    app.dependency_overrides[get_tool_service] = lambda: tool_service
    return app


@pytest.fixture
def owner_headers() -> dict[str, str]:
    """Fixture providing valid JWT Authorization header with owner role."""
    return make_auth_headers("org-http-tools", role="owner")


@pytest.fixture
def other_owner_headers() -> dict[str, str]:
    """Fixture providing valid JWT Authorization header for a distinct organization."""
    return make_auth_headers("org-different", role="owner")


@pytest.fixture
def member_headers() -> dict[str, str]:
    """Fixture providing valid JWT Authorization header with member role."""
    return make_auth_headers("org-http-tools", role="member")


@pytest.mark.asyncio
async def test_tool_lifecycle_and_invocation(tool_service: ToolService) -> None:
    """Test tool creation, retrieval, and invocation."""
    org_id = "org-tool-test"
    create_payload = ToolCreate(
        name="lookup_order",
        type="http",
        config={"url": "https://api.example.com/orders", "method": "POST"},
        json_schema={
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
        outcome_label="order_checked",
    )

    tool = await tool_service.create_tool(org_id, create_payload)
    assert tool.id is not None
    assert tool.name == "lookup_order"
    assert tool.type == "http"

    # Fetch by ID
    fetched = await tool_service.get_tool(org_id, tool.id)
    assert fetched is not None
    assert fetched.name == "lookup_order"

    # Invoke tool
    invoke_req = ToolInvokeRequest(
        tool_name="lookup_order",
        arguments={"order_id": "ORD-12345"},
    )
    result = await tool_service.invoke_tool(org_id, invoke_req, session_id="test-session-1")
    assert isinstance(result, ToolInvokeResponse)
    assert result.status == "success"
    assert result.tool_name == "lookup_order"
    assert result.result["arguments"]["order_id"] == "ORD-12345"


@pytest.mark.asyncio
async def test_tool_service_partial_update(tool_service: ToolService) -> None:
    """Test service-level partial tool update."""
    org_id = "org-tool-test"
    tool = await tool_service.create_tool(
        org_id,
        ToolCreate(
            name="initial_tool",
            type="http",
            config={"url": "https://v1.example.com"},
            outcome_label="initial",
        ),
    )

    # Partial update: name and outcome_label
    updated = await tool_service.update_tool(
        org_id,
        tool.id,
        ToolUpdate(name="renamed_tool", outcome_label="completed"),
    )
    assert updated is not None
    assert updated.name == "renamed_tool"
    assert updated.outcome_label == "completed"
    assert updated.config == {"url": "https://v1.example.com"}

    # Update non-existent returns None
    none_result = await tool_service.update_tool(
        org_id,
        "non-existent-id",
        ToolUpdate(name="ghost"),
    )
    assert none_result is None


@pytest.mark.asyncio
async def test_tool_cross_tenant_isolation(tool_service: ToolService) -> None:
    """Verify tenant isolation: Organization B cannot read Organization A's tools."""
    org_a = "org-tools-alpha"
    org_b = "org-tools-beta"

    tool = await tool_service.create_tool(
        org_a,
        ToolCreate(
            name="internal_webhook",
            type="http",
            config={"url": "https://internal.example.com"},
        ),
    )

    # Org B cannot get Org A's tool
    b_get = await tool_service.get_tool(org_b, tool.id)
    assert b_get is None

    # Org B's tool listing does not include Org A's tool
    b_list = await tool_service.list_tools(org_b)
    assert len(b_list) == 0

    # Org B cannot update Org A's tool
    b_update = await tool_service.update_tool(
        org_b,
        tool.id,
        ToolUpdate(name="compromised"),
    )
    assert b_update is None


@pytest.mark.asyncio
async def test_tool_router_http(
    tool_app: FastAPI,
    owner_headers: dict[str, str],
    other_owner_headers: dict[str, str],
) -> None:
    """Test HTTP endpoints for tools including auth, mutations, patch, and isolation."""
    transport = ASGITransport(app=tool_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create tool
        resp = await client.post(
            "/tools",
            headers=owner_headers,
            json={
                "name": "check_balance",
                "type": "http",
                "config": {"url": "https://api.bank.example/balance"},
                "json_schema": {"type": "object"},
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        tool_id = data["id"]
        assert data["name"] == "check_balance"

        # List tools
        list_resp = await client.get(
            "/tools",
            headers=owner_headers,
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # Patch tool
        patch_resp = await client.patch(
            f"/tools/{tool_id}",
            headers=owner_headers,
            json={"name": "check_balance_updated", "outcome_label": "balance_checked"},
        )
        assert patch_resp.status_code == 200
        patched_data = patch_resp.json()
        assert patched_data["name"] == "check_balance_updated"
        assert patched_data["outcome_label"] == "balance_checked"

        # Cross-tenant get returns 404
        cross_resp = await client.get(
            f"/tools/{tool_id}",
            headers=other_owner_headers,
        )
        assert cross_resp.status_code == 404

        # Cross-tenant patch returns 404
        cross_patch_resp = await client.patch(
            f"/tools/{tool_id}",
            headers=other_owner_headers,
            json={"name": "hijacked"},
        )
        assert cross_patch_resp.status_code == 404

        # Invoke tool endpoint
        inv_resp = await client.post(
            "/tools/invoke",
            headers=owner_headers,
            json={
                "tool_name": "check_balance_updated",
                "arguments": {"account_number": "123"},
            },
        )
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()
        assert inv_data["status"] == "success"
        assert inv_data["tool_name"] == "check_balance_updated"

        # Delete tool
        del_resp = await client.delete(
            f"/tools/{tool_id}",
            headers=owner_headers,
        )
        assert del_resp.status_code == 204

        # Verified deleted tool returns 404
        verify_del = await client.get(
            f"/tools/{tool_id}",
            headers=owner_headers,
        )
        assert verify_del.status_code == 404


@pytest.mark.asyncio
async def test_tool_router_auth_enforcement(
    tool_app: FastAPI,
    member_headers: dict[str, str],
) -> None:
    """Test that unauthenticated requests return 401 and member role returns 403."""
    transport = ASGITransport(app=tool_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated calls -> 401
        assert (await client.get("/tools")).status_code == 401
        assert (await client.post("/tools", json={"name": "x", "type": "http"})).status_code == 401
        assert (await client.patch("/tools/any-id", json={"name": "y"})).status_code == 401
        assert (await client.delete("/tools/any-id")).status_code == 401

        # Spoofed X-Organization-Id without bearer -> 401 (proves backdoor is removed)
        spoofed = {"X-Organization-Id": "victim-org"}
        assert (await client.get("/tools", headers=spoofed)).status_code == 401
        res = await client.post("/tools", json={"name": "x", "type": "http"}, headers=spoofed)
        assert res.status_code == 401
        assert (await client.delete("/tools/any-id", headers=spoofed)).status_code == 401

        # Member role on mutations -> 403
        member_post = await client.post(
            "/tools", json={"name": "x", "type": "http"}, headers=member_headers
        )
        assert member_post.status_code == 403
        member_patch = await client.patch(
            "/tools/any-id", json={"name": "y"}, headers=member_headers
        )
        assert member_patch.status_code == 403
        assert (await client.delete("/tools/any-id", headers=member_headers)).status_code == 403
