"""Empirical stress test suite for Milestone M2: Agents & Versions.

Tests:
1. Version immutability across repeated updates (byte-for-byte check).
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService
from backend.app.modules.providers.service import ProviderService


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Test async client with in-memory AgentService override."""
    shared_service = AgentService(repository=AgentRepository(), provider_service=ProviderService())
    app.dependency_overrides[get_agent_service] = lambda: shared_service
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_agent_service, None)


@pytest.mark.asyncio
async def test_empirical_version_immutability(client: AsyncClient) -> None:
    """Stress test: Perform repeated updates and ensure historical versions are 100% immutable."""
    token = create_access_token(
        data={"sub": "usr-immutability", "organization_id": "org-immutability", "role": "owner"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create initial agent (v1)
    create_payload = {
        "name": "Immutability Agent",
        "system_prompt": "Prompt v1: Initial instruction.",
        "greeting": "Greeting v1: Hello caller.",
        "stt_config": {"provider": "deepgram", "model": "nova-2"},
        "llm_config": {"provider": "openai", "model": "gpt-4o-mini"},
        "tts_config": {
            "provider": "cartesia",
            "model": "sonic-english",
            "voice": "sonic-preview",
        },
        "silence_timeout_s": 12,
        "max_duration_s": 300,
    }
    res1 = await client.post("/agents", headers=headers, json=create_payload)
    assert res1.status_code == 201, res1.text
    v1_snapshot = res1.json()["current_version"]
    agent_id = res1.json()["id"]
    v1_id = v1_snapshot["id"]

    # 2. Update 1: Change prompt and max_duration -> bumps to v2
    update1_payload = {
        "system_prompt": "Prompt v2: Revised instruction.",
        "max_duration_s": 450,
    }
    res2 = await client.patch(f"/agents/{agent_id}", headers=headers, json=update1_payload)
    assert res2.status_code == 200
    v2_snapshot = res2.json()["current_version"]
    v2_id = v2_snapshot["id"]
    assert v2_id != v1_id
    assert v2_snapshot["version_no"] == 2

    # Verify v1 is still 100% identical
    v1_check1 = await client.get(f"/agents/{agent_id}/versions/{v1_id}", headers=headers)
    assert v1_check1.status_code == 200
    assert v1_check1.json() == v1_snapshot

    # 3. Update 2: Name update only -> must NOT bump version
    update2_payload = {"name": "Renamed Immutability Agent"}
    res3 = await client.patch(f"/agents/{agent_id}", headers=headers, json=update2_payload)
    assert res3.status_code == 200
    assert res3.json()["name"] == "Renamed Immutability Agent"
    assert res3.json()["current_version_id"] == v2_id
    assert res3.json()["current_version"]["version_no"] == 2

    # Verify v1 and v2 are still 100% identical
    v1_check2 = await client.get(f"/agents/{agent_id}/versions/{v1_id}", headers=headers)
    v2_check2 = await client.get(f"/agents/{agent_id}/versions/{v2_id}", headers=headers)
    assert v1_check2.json() == v1_snapshot
    assert v2_check2.json() == v2_snapshot

    # 4. Update 3: Change LLM config model to gpt-4o -> bumps to v3
    update3_payload = {
        "llm_config": {"provider": "openai", "model": "gpt-4o"},
    }
    res4 = await client.patch(f"/agents/{agent_id}", headers=headers, json=update3_payload)
    assert res4.status_code == 200
    v3_snapshot = res4.json()["current_version"]
    v3_id = v3_snapshot["id"]
    assert v3_id != v2_id
    assert v3_snapshot["version_no"] == 3

    # 5. Update 4: Change silence_timeout_s -> bumps to v4
    update4_payload = {"silence_timeout_s": 20}
    res5 = await client.patch(f"/agents/{agent_id}", headers=headers, json=update4_payload)
    assert res5.status_code == 200
    v4_snapshot = res5.json()["current_version"]
    v4_id = v4_snapshot["id"]
    assert v4_id != v3_id
    assert v4_snapshot["version_no"] == 4

    # 6. Final verification: Check all 4 versions from /versions endpoint and individual endpoints
    list_versions_res = await client.get(f"/agents/{agent_id}/versions", headers=headers)
    assert list_versions_res.status_code == 200
    all_versions = list_versions_res.json()
    assert len(all_versions) == 4
    assert [v["version_no"] for v in all_versions] == [1, 2, 3, 4]

    assert all_versions[0] == v1_snapshot
    assert all_versions[1] == v2_snapshot
    assert all_versions[2] == v3_snapshot
    assert all_versions[3] == v4_snapshot

    # Verify each individual version endpoint returns exact bytes
    for expected_snap in [v1_snapshot, v2_snapshot, v3_snapshot, v4_snapshot]:
        v_res = await client.get(
            f"/agents/{agent_id}/versions/{expected_snap['id']}", headers=headers
        )
        assert v_res.json() == expected_snap
