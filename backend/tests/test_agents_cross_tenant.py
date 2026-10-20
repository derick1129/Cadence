"""Comprehensive cross-tenant isolation and immutability tests for the agents module."""

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
async def test_cross_tenant_agent_isolation(client: AsyncClient) -> None:
    """Verify tenant isolation: Org B cannot read, list, update, or view Org A's agent."""
    token_a = create_access_token(
        data={"sub": "usr-a", "organization_id": "org-alpha", "role": "owner"}
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    token_b = create_access_token(
        data={"sub": "usr-b", "organization_id": "org-beta", "role": "owner"}
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Org A creates an agent
    create_res = await client.post(
        "/agents",
        headers=headers_a,
        json={
            "name": "Secret Alpha Agent",
            "system_prompt": "Confidential proprietary instructions.",
        },
    )
    assert create_res.status_code == 201
    agent_id = create_res.json()["id"]
    version_id = create_res.json()["current_version_id"]

    # 2. Org B attempts to read Org A's agent -> 404
    b_read = await client.get(f"/agents/{agent_id}", headers=headers_b)
    assert b_read.status_code == 404

    # 3. Org B attempts to update Org A's agent -> 404
    b_update = await client.patch(
        f"/agents/{agent_id}",
        headers=headers_b,
        json={"name": "Hacked Agent Name"},
    )
    assert b_update.status_code == 404

    # 4. Org B attempts to list versions -> 404
    b_versions = await client.get(f"/agents/{agent_id}/versions", headers=headers_b)
    assert b_versions.status_code == 404

    # 5. Org B attempts to get specific version -> 404
    b_ver = await client.get(f"/agents/{agent_id}/versions/{version_id}", headers=headers_b)
    assert b_ver.status_code == 404

    # 6. Org B listing agents does not contain Org A's agent
    b_list = await client.get("/agents", headers=headers_b)
    assert b_list.status_code == 200
    assert all(a["id"] != agent_id for a in b_list.json())


@pytest.mark.asyncio
async def test_member_role_cannot_modify_agent(client: AsyncClient) -> None:
    """Verify that a user with role 'member' cannot create or update agents."""
    token_admin = create_access_token(
        data={"sub": "usr-admin", "organization_id": "org-alpha", "role": "admin"}
    )
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # Create agent as admin
    create_res = await client.post(
        "/agents",
        headers=headers_admin,
        json={"name": "Base Agent", "system_prompt": "Hello"},
    )
    assert create_res.status_code == 201
    agent_id = create_res.json()["id"]

    token_member = create_access_token(
        data={"sub": "usr-member", "organization_id": "org-alpha", "role": "member"}
    )
    headers_member = {"Authorization": f"Bearer {token_member}"}

    # Member cannot create agent -> 403
    res_create = await client.post(
        "/agents",
        headers=headers_member,
        json={"name": "Member Agent", "system_prompt": "Hello"},
    )
    assert res_create.status_code == 403

    # Member cannot update agent -> 403
    res_update = await client.patch(
        f"/agents/{agent_id}",
        headers=headers_member,
        json={"name": "Member Modified Name"},
    )
    assert res_update.status_code == 403

    # Member CAN read agent -> 200
    res_read = await client.get(f"/agents/{agent_id}", headers=headers_member)
    assert res_read.status_code == 200


@pytest.mark.asyncio
async def test_agent_immutable_version_bumping(client: AsyncClient) -> None:
    """Verify that updating prompts bumps version_no and preserves previous immutable versions."""
    token = create_access_token(
        data={"sub": "usr-owner", "organization_id": "org-versioning", "role": "owner"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Create v1
    create_res = await client.post(
        "/agents",
        headers=headers,
        json={"name": "Versioned Agent", "system_prompt": "Version 1 prompt"},
    )
    assert create_res.status_code == 201
    agent_id = create_res.json()["id"]
    v1_id = create_res.json()["current_version_id"]

    # Update prompt -> bumps to v2
    update_res = await client.patch(
        f"/agents/{agent_id}",
        headers=headers,
        json={"system_prompt": "Version 2 prompt"},
    )
    assert update_res.status_code == 200
    v2_id = update_res.json()["current_version_id"]
    assert v2_id != v1_id
    assert update_res.json()["current_version"]["version_no"] == 2

    # Fetch version list: both v1 and v2 exist
    versions_res = await client.get(f"/agents/{agent_id}/versions", headers=headers)
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) == 2
    assert versions[0]["version_no"] == 1
    assert versions[0]["system_prompt"] == "Version 1 prompt"
    assert versions[0]["id"] == v1_id
    assert versions[1]["version_no"] == 2
    assert versions[1]["system_prompt"] == "Version 2 prompt"
    assert versions[1]["id"] == v2_id

    # Fetch individual versions
    v1_get = await client.get(f"/agents/{agent_id}/versions/{v1_id}", headers=headers)
    assert v1_get.status_code == 200
    assert v1_get.json()["system_prompt"] == "Version 1 prompt"

    v2_get = await client.get(f"/agents/{agent_id}/versions/{v2_id}", headers=headers)
    assert v2_get.status_code == 200
    assert v2_get.json()["system_prompt"] == "Version 2 prompt"
