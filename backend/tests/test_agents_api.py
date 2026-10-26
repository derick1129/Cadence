"""Tests for Agent HTTP router with authentication and RBAC."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Test async client with in-memory AgentService override."""
    shared_service = AgentService()
    app.dependency_overrides[get_agent_service] = lambda: shared_service
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_agent_service, None)


@pytest.mark.asyncio
async def test_agent_routes_authenticated(client: AsyncClient) -> None:
    """Verify creating and listing agents requires valid bearer tokens and enforces tenancy."""
    token = create_access_token(
        data={"sub": "usr-agent-test", "organization_id": "org-agent-test", "role": "admin"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Agent
    create_res = await client.post(
        "/agents",
        headers=headers,
        json={
            "name": "Front Desk AI",
            "system_prompt": "You are a front desk AI assistant.",
            "greeting": "Welcome! How can I assist you?",
        },
    )
    assert create_res.status_code == 201
    agent_data = create_res.json()
    assert agent_data["name"] == "Front Desk AI"
    assert agent_data["organization_id"] == "org-agent-test"
    assert agent_data["current_version"] is not None
    assert agent_data["current_version"]["version_no"] == 1

    # 2. List Agents
    list_res = await client.get("/agents", headers=headers)
    assert list_res.status_code == 200
    agents = list_res.json()
    assert len(agents) >= 1
    assert any(a["id"] == agent_data["id"] for a in agents)


@pytest.mark.asyncio
async def test_agent_routes_unauthorized(client: AsyncClient) -> None:
    """Verify unauthenticated requests are rejected with 401."""
    res = await client.get("/agents")
    assert res.status_code == 401
