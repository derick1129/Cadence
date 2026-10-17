"""Tests for the agents module including service, versioning, and tenant isolation."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.modules.agents import (
    AgentCreate,
    AgentService,
    AgentUpdate,
    router,
)
from backend.app.modules.agents.router import get_agent_service


@pytest.fixture
def agent_service() -> AgentService:
    """Fixture providing an isolated AgentService instance."""
    return AgentService()


@pytest.fixture
def agent_app(agent_service: AgentService) -> FastAPI:
    """FastAPI test app containing the agents router."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_agent_service] = lambda: agent_service
    return app


@pytest.mark.asyncio
async def test_agent_lifecycle_and_versioning(agent_service: AgentService) -> None:
    """Test full agent creation, initial v1 generation, and version bumping."""
    org_id = "org-test-1"
    create_payload = AgentCreate(
        name="Sales Assistant",
        system_prompt="You are a helpful sales assistant.",
        greeting="Hello, how can I help you today?",
        stt_config={"model": "nova-2"},
        llm_config={"model": "gpt-4o-mini"},
        tts_config={"voice": "default-voice"},
        silence_timeout_s=15,
        max_duration_s=600,
    )

    agent = await agent_service.create_agent(org_id, create_payload)
    assert agent.id is not None
    assert agent.name == "Sales Assistant"
    assert agent.current_version is not None
    assert agent.current_version.version_no == 1
    assert agent.current_version.system_prompt == "You are a helpful sales assistant."

    # Update only the name (no version bump)
    updated_name = await agent_service.update_agent(
        org_id, agent.id, AgentUpdate(name="Senior Sales Assistant")
    )
    assert updated_name is not None
    assert updated_name.name == "Senior Sales Assistant"
    assert updated_name.current_version is not None
    assert updated_name.current_version.version_no == 1

    # Update prompt (triggers new immutable version v2)
    updated_prompt = await agent_service.update_agent(
        org_id,
        agent.id,
        AgentUpdate(system_prompt="Updated sales script v2."),
    )
    assert updated_prompt is not None
    assert updated_prompt.current_version is not None
    assert updated_prompt.current_version.version_no == 2
    assert updated_prompt.current_version.system_prompt == "Updated sales script v2."

    # Verify versions history
    versions = await agent_service.list_versions(org_id, agent.id)
    assert len(versions) == 2
    assert versions[0].version_no == 1
    assert versions[1].version_no == 2


@pytest.mark.asyncio
async def test_agent_cross_tenant_isolation(agent_service: AgentService) -> None:
    """Verify tenant isolation: organization B cannot view or modify organization A's agent."""
    org_a = "org-tenant-alpha"
    org_b = "org-tenant-beta"

    agent = await agent_service.create_agent(
        org_a,
        AgentCreate(
            name="Confidential Agent",
            system_prompt="Secret prompt",
        ),
    )

    # Org B attempts to read Org A's agent
    b_read = await agent_service.get_agent(org_b, agent.id)
    assert b_read is None

    # Org B attempts to list agents
    b_list = await agent_service.list_agents(org_b)
    assert len(b_list) == 0

    # Org B attempts to update Org A's agent
    b_update = await agent_service.update_agent(org_b, agent.id, AgentUpdate(name="Hacked Name"))
    assert b_update is None

    # Org B attempts to view versions
    b_versions = await agent_service.list_versions(org_b, agent.id)
    assert b_versions == []


@pytest.mark.asyncio
async def test_agent_router_http(agent_app: FastAPI) -> None:
    """Test HTTP endpoints for agents including headers and error handling."""
    transport = ASGITransport(app=agent_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create agent
        resp = await client.post(
            "/agents",
            headers={"X-Organization-Id": "org-http"},
            json={
                "name": "Support Bot",
                "system_prompt": "Support prompt",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        agent_id = data["id"]
        assert data["name"] == "Support Bot"

        # List agents
        list_resp = await client.get(
            "/agents",
            headers={"X-Organization-Id": "org-http"},
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # Cross-tenant get should return 404
        cross_resp = await client.get(
            f"/agents/{agent_id}",
            headers={"X-Organization-Id": "org-other"},
        )
        assert cross_resp.status_code == 404

        # Same-tenant get
        get_resp = await client.get(
            f"/agents/{agent_id}",
            headers={"X-Organization-Id": "org-http"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == agent_id
