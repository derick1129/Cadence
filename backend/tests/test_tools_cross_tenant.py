"""Tests for customer tools REST API, RBAC enforcement, and cross-tenant isolation."""

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.service import AgentService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.router import get_session_service
from backend.app.modules.sessions.service import SessionService
from backend.app.modules.tools.repository import ToolRepository


def _make_auth_header(
    org_id: str, role: str = "admin", user_id: str | None = None
) -> dict[str, str]:
    token = create_access_token(
        data={
            "sub": user_id or str(uuid.uuid4()),
            "organization_id": org_id,
            "role": role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_tools_auth_and_rbac_enforcement() -> None:
    """Verify customer tools endpoints require JWT authentication and owner/admin role."""
    client = TestClient(app)
    org_id = str(uuid.uuid4())

    create_payload = {
        "name": "lookup_account",
        "type": "http",
        "config": {"url": "https://api.example.com/account"},
        "json_schema": {"type": "object"},
    }

    # 1. Unauthenticated request -> 401
    resp = client.post("/tools", json=create_payload)
    assert resp.status_code == 401

    # 2. Member role -> 403 Forbidden
    member_headers = _make_auth_header(org_id, role="member")
    resp = client.post("/tools", json=create_payload, headers=member_headers)
    assert resp.status_code == 403

    # 3. Admin role -> 201 Created
    admin_headers = _make_auth_header(org_id, role="admin")
    resp = client.post("/tools", json=create_payload, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "lookup_account"
    tool_id = data["id"]

    # 4. Member delete -> 403 Forbidden
    resp = client.delete(f"/tools/{tool_id}", headers=member_headers)
    assert resp.status_code == 403


def test_tools_cross_tenant_isolation() -> None:
    """Verify strict tenant isolation across tool listing, retrieval, and deletion."""
    client = TestClient(app)
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    headers_a = _make_auth_header(tenant_a, role="admin")
    headers_b = _make_auth_header(tenant_b, role="admin")

    # 1. Tenant A creates tool
    resp_a = client.post(
        "/tools",
        json={
            "name": "tenant_a_tool",
            "type": "http",
            "config": {"url": "https://a.example/webhook"},
            "json_schema": {},
        },
        headers=headers_a,
    )
    assert resp_a.status_code == 201
    tool_a_id = resp_a.json()["id"]

    # 2. Tenant B lists tools -> should be empty
    list_b = client.get("/tools", headers=headers_b)
    assert list_b.status_code == 200
    b_ids = [t["id"] for t in list_b.json()]
    assert tool_a_id not in b_ids

    # 3. Tenant B attempts to fetch Tenant A's tool -> 404
    get_b = client.get(f"/tools/{tool_a_id}", headers=headers_b)
    assert get_b.status_code == 404

    # 4. Tenant B attempts to delete Tenant A's tool -> 404
    del_b = client.delete(f"/tools/{tool_a_id}", headers=headers_b)
    assert del_b.status_code == 404

    # 5. Tenant A deletes their tool -> 204
    del_a = client.delete(f"/tools/{tool_a_id}", headers=headers_a)
    assert del_a.status_code == 204

    # 6. Tenant A attempts to delete again -> 404
    del_a_again = client.delete(f"/tools/{tool_a_id}", headers=headers_a)
    assert del_a_again.status_code == 404


@pytest.mark.asyncio
async def test_session_tool_calls_audit_trail_and_cross_tenant() -> None:
    """Verify GET /sessions/{id}/tool-calls returns audit trail and enforces tenant isolation."""
    client = TestClient(app)
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    headers_a = _make_auth_header(tenant_a, role="admin")
    headers_b = _make_auth_header(tenant_b, role="admin")

    agent_repo = AgentRepository()
    agent_svc = AgentService(repository=agent_repo)
    session_repo = SessionRepository()
    session_svc = SessionService(repository=session_repo, agent_service=agent_svc)
    tool_repo = ToolRepository()

    app.dependency_overrides[get_session_service] = lambda: session_svc

    try:
        sess_a = await session_repo.create_session(
            organization_id=tenant_a,
            agent_id=str(uuid.uuid4()),
            agent_version_id=str(uuid.uuid4()),
            room_name=f"room-{uuid.uuid4()}",
            channel="web",
        )
        session_a_id = sess_a["id"]

        # Record tool call for Session A
        await tool_repo.record_tool_call(
            session_id=session_a_id,
            tool_name="database_sync",
            arguments={"row_id": 42},
            result={"synced": True},
            status="success",
            latency_ms=85,
        )

        # 1. Tenant B requests Session A's tool calls -> 404 Not Found
        resp_b = client.get(f"/sessions/{session_a_id}/tool-calls", headers=headers_b)
        assert resp_b.status_code == 404

        # 2. Tenant A requests Session A's tool calls -> 200 with audit list
        resp_a = client.get(f"/sessions/{session_a_id}/tool-calls", headers=headers_a)
        assert resp_a.status_code == 200
        calls = resp_a.json()
        assert len(calls) == 1
        assert calls[0]["tool_name"] == "database_sync"
        assert calls[0]["arguments"] == {"row_id": 42}
        assert calls[0]["status"] == "success"
        assert calls[0]["latency_ms"] == 85
    finally:
        app.dependency_overrides.pop(get_session_service, None)
