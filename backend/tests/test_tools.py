"""Tests for the tools module including creation, execution, and cross-tenant access."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.modules.tools import (
    ToolCreate,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolService,
    router,
)
from backend.app.modules.tools.router import get_tool_service


@pytest.fixture
def tool_service() -> ToolService:
    """Fixture providing isolated ToolService."""
    return ToolService()


@pytest.fixture
def tool_app(tool_service: ToolService) -> FastAPI:
    """FastAPI test app containing tools router with overridden service."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_tool_service] = lambda: tool_service
    return app


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


@pytest.mark.asyncio
async def test_tool_router_http(tool_app: FastAPI) -> None:
    """Test HTTP endpoints for tools including cross-tenant access enforcement."""
    transport = ASGITransport(app=tool_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create tool
        resp = await client.post(
            "/tools",
            headers={"X-Organization-Id": "org-http-tools"},
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

        # List tools
        list_resp = await client.get(
            "/tools",
            headers={"X-Organization-Id": "org-http-tools"},
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # Cross-tenant get returns 404
        cross_resp = await client.get(
            f"/tools/{tool_id}",
            headers={"X-Organization-Id": "org-different"},
        )
        assert cross_resp.status_code == 404

        # Invoke tool endpoint
        inv_resp = await client.post(
            "/tools/invoke",
            headers={"X-Organization-Id": "org-http-tools"},
            json={
                "tool_name": "check_balance",
                "arguments": {"account_number": "123"},
            },
        )
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()
        assert inv_data["status"] == "success"
        assert inv_data["tool_name"] == "check_balance"
