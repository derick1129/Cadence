"""Empirical Challenger 1: Cross-tenant isolation, RBAC, and boundary tests for M2."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService


@pytest.fixture
async def sec_client() -> AsyncGenerator[AsyncClient, None]:
    """Test client with isolated shared repository service."""
    repo = AgentRepository()
    service = AgentService(repository=repo)
    app.dependency_overrides[get_agent_service] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_agent_service, None)


def _token(user: str, org: str, role: str) -> dict[str, str]:
    token = create_access_token(data={"sub": user, "organization_id": org, "role": role})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_cross_tenant_reads_and_updates_rejected(sec_client: AsyncClient) -> None:
    """Ensure Org B cannot read, update, or list versions of Org A's agent."""
    org_a_hdrs = _token("user-a", "org-alpha-1", "owner")
    org_b_hdrs = _token("user-b", "org-beta-1", "owner")

    res = await sec_client.post(
        "/agents",
        headers=org_a_hdrs,
        json={"name": "Org A Confidential Agent", "system_prompt": "Top secret prompt"},
    )
    assert res.status_code == 201
    agent_id = res.json()["id"]
    version_id = res.json()["current_version_id"]

    # Org B read attempt -> 404
    b_read = await sec_client.get(f"/agents/{agent_id}", headers=org_b_hdrs)
    assert b_read.status_code == 404

    # Org B update attempt -> 404
    b_patch = await sec_client.patch(
        f"/agents/{agent_id}",
        headers=org_b_hdrs,
        json={"name": "Hijacked Name", "system_prompt": "Malicious Prompt"},
    )
    assert b_patch.status_code == 404

    # Org B version list attempt -> 404
    b_versions = await sec_client.get(f"/agents/{agent_id}/versions", headers=org_b_hdrs)
    assert b_versions.status_code == 404

    # Org B specific version read attempt -> 404
    b_ver = await sec_client.get(f"/agents/{agent_id}/versions/{version_id}", headers=org_b_hdrs)
    assert b_ver.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_version_id_confusion_rejected(sec_client: AsyncClient) -> None:
    """Ensure Org B cannot access Org A's version by passing Org B's agent ID."""
    org_a_hdrs = _token("user-a", "org-alpha-2", "owner")
    org_b_hdrs = _token("user-b", "org-beta-2", "owner")

    # Create agent for Org A
    res_a = await sec_client.post(
        "/agents",
        headers=org_a_hdrs,
        json={"name": "Org A Agent", "system_prompt": "Org A Secret Prompt"},
    )
    assert res_a.status_code == 201
    version_a_id = res_a.json()["current_version_id"]

    # Create agent for Org B
    res_b = await sec_client.post(
        "/agents",
        headers=org_b_hdrs,
        json={"name": "Org B Agent", "system_prompt": "Org B Public Prompt"},
    )
    assert res_b.status_code == 201
    agent_b_id = res_b.json()["id"]

    # Attack: Org B queries Org B's agent with Org A's version ID
    confused_res = await sec_client.get(
        f"/agents/{agent_b_id}/versions/{version_a_id}",
        headers=org_b_hdrs,
    )
    assert confused_res.status_code == 404
    assert "Org A Secret Prompt" not in confused_res.text


@pytest.mark.asyncio
async def test_rbac_privilege_escalation_denied(sec_client: AsyncClient) -> None:
    """Verify non-admin roles cannot create or update agents."""
    admin_hdrs = _token("user-adm", "org-rbac-1", "admin")
    member_hdrs = _token("user-mem", "org-rbac-1", "member")
    viewer_hdrs = _token("user-view", "org-rbac-1", "viewer")
    custom_hdrs = _token("user-cust", "org-rbac-1", "contractor")

    # Admin creates agent
    res = await sec_client.post(
        "/agents",
        headers=admin_hdrs,
        json={"name": "Admin Agent", "system_prompt": "System instructions"},
    )
    assert res.status_code == 201
    agent_id = res.json()["id"]

    # Member role mutations denied
    mem_post = await sec_client.post(
        "/agents",
        headers=member_hdrs,
        json={"name": "Member Agent", "system_prompt": "Hello"},
    )
    assert mem_post.status_code == 403
    mem_patch = await sec_client.patch(
        f"/agents/{agent_id}",
        headers=member_hdrs,
        json={"name": "Member Agent"},
    )
    assert mem_patch.status_code == 403

    # Viewer role mutations denied
    view_post = await sec_client.post(
        "/agents",
        headers=viewer_hdrs,
        json={"name": "Viewer Agent", "system_prompt": "Hello"},
    )
    assert view_post.status_code == 403

    # Unknown role mutations denied
    cust_post = await sec_client.post(
        "/agents",
        headers=custom_hdrs,
        json={"name": "Contractor Agent", "system_prompt": "Hello"},
    )
    assert cust_post.status_code == 403

    # Members CAN read agents and versions
    mem_get = await sec_client.get(f"/agents/{agent_id}", headers=member_hdrs)
    assert mem_get.status_code == 200
    mem_list = await sec_client.get("/agents", headers=member_hdrs)
    assert mem_list.status_code == 200
    mem_vers = await sec_client.get(f"/agents/{agent_id}/versions", headers=member_hdrs)
    assert mem_vers.status_code == 200


@pytest.mark.asyncio
async def test_role_casing_and_empty_role_rejection(sec_client: AsyncClient) -> None:
    """Verify role casing variations (e.g. 'ADMIN', 'Owner') do not bypass RBAC."""
    upper_admin_hdrs = _token("user-ua", "org-casing-1", "ADMIN")
    mixed_owner_hdrs = _token("user-mo", "org-casing-1", "Owner")
    empty_role_hdrs = _token("user-er", "org-casing-1", "")

    # Role 'ADMIN' must be rejected (only lowercase 'admin', 'owner' allowed)
    res1 = await sec_client.post(
        "/agents",
        headers=upper_admin_hdrs,
        json={"name": "Agent 1", "system_prompt": "Prompt"},
    )
    assert res1.status_code == 403

    # Role 'Owner' must be rejected
    res2 = await sec_client.post(
        "/agents",
        headers=mixed_owner_hdrs,
        json={"name": "Agent 2", "system_prompt": "Prompt"},
    )
    assert res2.status_code == 403

    # Empty role must be rejected
    res3 = await sec_client.post(
        "/agents",
        headers=empty_role_hdrs,
        json={"name": "Agent 3", "system_prompt": "Prompt"},
    )
    assert res3.status_code == 403


@pytest.mark.asyncio
async def test_tenant_header_mismatch_validation(sec_client: AsyncClient) -> None:
    """Verify X-Organization-Id header mismatch enforcement."""
    token = create_access_token(
        data={"sub": "usr-1", "organization_id": "org-actual", "role": "owner"}
    )
    # Correct matching header works
    valid_hdrs = {"Authorization": f"Bearer {token}", "X-Organization-Id": "org-actual"}
    res_valid = await sec_client.get("/agents", headers=valid_hdrs)
    assert res_valid.status_code == 200

    # Mismatched header on GET /agents returns 403 TENANT_MISMATCH
    mismatch_hdrs = {"Authorization": f"Bearer {token}", "X-Organization-Id": "org-spoofed"}
    res_mismatch = await sec_client.get("/agents", headers=mismatch_hdrs)
    assert res_mismatch.status_code == 403
    assert res_mismatch.json()["error"]["code"] == "TENANT_MISMATCH"

    # Mismatched header on GET /agents/{id} returns 403 TENANT_MISMATCH
    fake_id = str(uuid.uuid4())
    res_mismatch_id = await sec_client.get(f"/agents/{fake_id}", headers=mismatch_hdrs)
    assert res_mismatch_id.status_code == 403
    assert res_mismatch_id.json()["error"]["code"] == "TENANT_MISMATCH"


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(sec_client: AsyncClient) -> None:
    """Ensure missing, malformed, or empty authorization headers return 401."""
    # No Authorization header
    res_no_auth = await sec_client.get("/agents")
    assert res_no_auth.status_code == 401

    # Empty bearer
    res_empty_bearer = await sec_client.get("/agents", headers={"Authorization": "Bearer "})
    assert res_empty_bearer.status_code == 401

    # Invalid token string
    res_invalid_tok = await sec_client.get(
        "/agents", headers={"Authorization": "Bearer not-a-valid-jwt"}
    )
    assert res_invalid_tok.status_code == 401


@pytest.mark.asyncio
async def test_malformed_and_injection_uuid_handling(sec_client: AsyncClient) -> None:
    """Verify non-UUID IDs and injection strings return 404 without crashing (500)."""
    headers = _token("user-sql", "org-sql-1", "owner")

    malformed_ids = [
        "not-a-uuid",
        "' OR '1'='1",
        "../../etc/passwd",
        "<script>alert(1)</script>",
        "00000000-0000-0000-0000-000000000000x",
    ]

    for bad_id in malformed_ids:
        # GET /agents/{bad_id}
        res_get = await sec_client.get(f"/agents/{bad_id}", headers=headers)
        assert res_get.status_code in {404, 422}

        # PATCH /agents/{bad_id}
        res_patch = await sec_client.patch(
            f"/agents/{bad_id}",
            headers=headers,
            json={"name": "Test"},
        )
        assert res_patch.status_code in {404, 422}

        # GET /agents/{bad_id}/versions
        res_vers = await sec_client.get(f"/agents/{bad_id}/versions", headers=headers)
        assert res_vers.status_code in {404, 422}

        # GET /agents/{bad_id}/versions/{bad_id}
        res_ver = await sec_client.get(
            f"/agents/{bad_id}/versions/{bad_id}",
            headers=headers,
        )
        assert res_ver.status_code in {404, 422}
