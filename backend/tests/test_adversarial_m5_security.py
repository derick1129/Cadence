"""Empirical adversarial security and penetration tests for Milestone M5 (Tools).

Stress-tests:
1. RBAC enforcement and authentication bypass attacks (member/viewer roles, missing headers,
   unauthenticated X-Organization-Id bypass probes, malformed auth headers).
2. Cross-tenant IDOR attacks (cross-tenant tool read, delete, update, and session audit logs).
3. Agent tool binding attacks (attaching foreign tenant tools to an agent).
4. Internal gateway token fuzzing (unicode/non-ASCII, timing attack resilience, invalid session IDs,
   unattached tool invocations, and JSON schema validation bypass).
"""

import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import compare_digest, create_access_token
from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.schemas import AgentCreate, AgentUpdate
from backend.app.modules.agents.service import AgentService
from backend.app.modules.internal.schemas import ToolInvokeRequest
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.router import get_session_service
from backend.app.modules.sessions.service import SessionService
from backend.app.modules.tools.repository import ToolRepository


def _make_auth_header(
    org_id: str, role: str = "admin", user_id: str | None = None
) -> dict[str, str]:
    """Helper to generate JWT bearer header."""
    token = create_access_token(
        data={
            "sub": user_id or str(uuid.uuid4()),
            "organization_id": org_id,
            "role": role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. RBAC Enforcement & Authentication Bypass Attacks
# =====================================================================


def test_rbac_member_and_viewer_tokens_rejected_on_tools_mutations() -> None:
    """Verify that member and viewer tokens are forbidden from POST and DELETE /tools."""
    client = TestClient(app)
    org_id = str(uuid.uuid4())
    admin_headers = _make_auth_header(org_id, role="admin")
    member_headers = _make_auth_header(org_id, role="member")
    viewer_headers = _make_auth_header(org_id, role="viewer")

    # 1. Admin creates a tool
    create_payload = {
        "name": "lookup_user",
        "type": "http",
        "config": {"url": "https://api.example.com/users"},
        "json_schema": {"type": "object"},
    }
    admin_resp = client.post("/tools", json=create_payload, headers=admin_headers)
    assert admin_resp.status_code == 201
    tool_id = admin_resp.json()["id"]

    # 2. Member attempts POST /tools -> MUST return 403 Forbidden
    member_post_resp = client.post(
        "/tools",
        json={"name": "member_tool", "type": "http", "config": {}},
        headers=member_headers,
    )
    assert member_post_resp.status_code == 403, (
        f"Expected 403 for member POST, got {member_post_resp.status_code}"
    )

    # 3. Viewer attempts POST /tools -> MUST return 403 Forbidden
    viewer_post_resp = client.post(
        "/tools",
        json={"name": "viewer_tool", "type": "http", "config": {}},
        headers=viewer_headers,
    )
    assert viewer_post_resp.status_code == 403, (
        f"Expected 403 for viewer POST, got {viewer_post_resp.status_code}"
    )

    # 4. Member attempts DELETE /tools/{tool_id} -> MUST return 403 Forbidden
    member_del_resp = client.delete(f"/tools/{tool_id}", headers=member_headers)
    assert member_del_resp.status_code == 403, (
        f"Expected 403 for member DELETE, got {member_del_resp.status_code}"
    )

    # 5. Viewer attempts DELETE /tools/{tool_id} -> MUST return 403 Forbidden
    viewer_del_resp = client.delete(f"/tools/{tool_id}", headers=viewer_headers)
    assert viewer_del_resp.status_code == 403, (
        f"Expected 403 for viewer DELETE, got {viewer_del_resp.status_code}"
    )


def test_unauthenticated_requests_without_headers_rejected() -> None:
    """Verify that completely unauthenticated requests to /tools are rejected with 401."""
    client = TestClient(app)
    tool_id = str(uuid.uuid4())

    # POST /tools
    resp_post = client.post("/tools", json={"name": "evil_tool", "type": "http", "config": {}})
    assert resp_post.status_code == 401

    # GET /tools
    resp_get = client.get("/tools")
    assert resp_get.status_code == 401

    # GET /tools/{id}
    resp_get_id = client.get(f"/tools/{tool_id}")
    assert resp_get_id.status_code == 401

    # DELETE /tools/{id}
    resp_del = client.delete(f"/tools/{tool_id}")
    assert resp_del.status_code == 401


def test_malformed_auth_headers_rejected() -> None:
    """Verify malformed and invalid Authorization headers are rejected with 401 or 403."""
    client = TestClient(app)
    org_id = str(uuid.uuid4())

    malformed_headers = [
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer not-a-valid-jwt-token"},
        {"Authorization": "Bearer abc.def.ghi"},
        {"Authorization": "Basic YWRtaW46cGFzc3dvcmQ="},
        {"Authorization": "Token 1234567890"},
        {"Authorization": "Bearer"},
    ]

    for headers in malformed_headers:
        resp = client.post(
            "/tools",
            json={"name": "hack_tool", "type": "http", "config": {}},
            headers=headers,
        )
        assert resp.status_code == 401, (
            f"Expected 401 for header {headers}, got {resp.status_code}: {resp.text}"
        )

    # Token with tenant mismatch between Bearer claims and X-Organization-Id header -> 403
    token_headers = _make_auth_header(org_id, role="admin")
    mismatch_headers = {
        **token_headers,
        "X-Organization-Id": str(uuid.uuid4()),  # different org
    }
    mismatch_resp = client.post(
        "/tools",
        json={"name": "mismatch_tool", "type": "http", "config": {}},
        headers=mismatch_headers,
    )
    assert mismatch_resp.status_code == 403, (
        f"Expected 403 TENANT_MISMATCH, got {mismatch_resp.status_code}"
    )


def test_vulnerability_probe_unauthenticated_x_organization_id_bypass() -> None:
    """Adversarial probe: Test if providing X-Organization-Id without Authorization bypasses auth.

    In backend/app/modules/tools/router.py, require_tool_mutation_auth and get_tool_tenant_id
    contain:
        if x_organization_id:
            return x_organization_id
    This test executes unauthenticated attacks using only the header to prove whether
    POST, GET, and DELETE endpoints accept the unverified header.
    """
    client = TestClient(app)
    victim_org_id = str(uuid.uuid4())
    victim_admin_headers = _make_auth_header(victim_org_id, role="admin")

    # 1. Setup legitimate tool under victim organization
    resp_init = client.post(
        "/tools",
        json={
            "name": "victim_sensitive_tool",
            "type": "http",
            "config": {
                "url": "https://api.internal.victim.com",
                "headers": {"Authorization": "Bearer secret-token"},
            },
            "json_schema": {},
        },
        headers=victim_admin_headers,
    )
    assert resp_init.status_code == 201
    victim_tool_id = resp_init.json()["id"]

    # 2. Attack: Attacker sends NO Authorization header, only X-Organization-Id to GET /tools
    spoofed_headers = {"X-Organization-Id": victim_org_id}
    resp_get = client.get("/tools", headers=spoofed_headers)

    # 3. Attack: Attacker sends NO Authorization header, only X-Organization-Id to POST /tools
    create_payload = {
        "name": "unauthorized_backdoor_tool",
        "type": "http",
        "config": {"url": "https://attacker.example/exfil"},
        "json_schema": {"type": "object"},
    }
    resp_post = client.post("/tools", json=create_payload, headers=spoofed_headers)

    # 4. Attack: Attacker sends NO Authorization header, only X-Organization-Id to DELETE
    resp_del = client.delete(f"/tools/{victim_tool_id}", headers=spoofed_headers)

    # SECURE behavior: All 3 MUST return 401 Unauthorized (must require valid JWT).
    # If any returns 200/201/204, it PROVES the presence of authentication bypass vulnerabilities!
    vuln_post = resp_post.status_code == 201
    vuln_get = resp_get.status_code == 200
    vuln_del = resp_del.status_code == 204

    assert not (vuln_post or vuln_get or vuln_del), (
        f"CRITICAL VULNERABILITY FOUND: Unauthenticated requests with X-Organization-Id "
        f"bypassed authentication! POST={resp_post.status_code}, GET={resp_get.status_code}, "
        f"DELETE={resp_del.status_code}."
    )


# =====================================================================
# 2. Cross-Tenant IDOR Attacks
# =====================================================================


def test_cross_tenant_idor_lookup_update_delete_isolation() -> None:
    """Verify Tenant B cannot read, update, or delete tools belonging to Tenant A."""
    client = TestClient(app)
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    headers_a = _make_auth_header(tenant_a, role="admin")
    headers_b = _make_auth_header(tenant_b, role="admin")

    # 1. Tenant A creates Tool A
    resp_create = client.post(
        "/tools",
        json={
            "name": "tenant_a_secret_tool",
            "type": "http",
            "config": {"url": "https://internal.a.example/webhook"},
            "json_schema": {},
        },
        headers=headers_a,
    )
    assert resp_create.status_code == 201
    tool_a_id = resp_create.json()["id"]

    # 2. Tenant B attempts IDOR read (GET /tools/{tool_a_id}) -> MUST return 404
    resp_idor_get = client.get(f"/tools/{tool_a_id}", headers=headers_b)
    assert resp_idor_get.status_code == 404, (
        f"Expected 404 for IDOR read, got {resp_idor_get.status_code}"
    )

    # 3. Tenant B attempts IDOR delete (DELETE /tools/{tool_a_id}) -> MUST return 404
    resp_idor_del = client.delete(f"/tools/{tool_a_id}", headers=headers_b)
    assert resp_idor_del.status_code == 404, (
        f"Expected 404 for IDOR delete, got {resp_idor_del.status_code}"
    )

    # 4. Verify Tool A was not deleted and remains accessible to Tenant A
    resp_verify_a = client.get(f"/tools/{tool_a_id}", headers=headers_a)
    assert resp_verify_a.status_code == 200
    assert resp_verify_a.json()["name"] == "tenant_a_secret_tool"

    # 5. Tenant B attempts PATCH /tools/{tool_a_id} -> MUST return 404 or 405 (no modification)
    resp_idor_patch = client.patch(
        f"/tools/{tool_a_id}",
        json={"name": "hijacked_tool"},
        headers=headers_b,
    )
    assert resp_idor_patch.status_code in (404, 405), (
        f"Expected 404 or 405 for IDOR patch, got {resp_idor_patch.status_code}"
    )


@pytest.mark.asyncio
async def test_cross_tenant_session_tool_calls_audit_trail_isolation() -> None:
    """Verify Tenant B cannot view Tenant A's session tool-calls audit trail."""
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
        # Create Session for Tenant A
        sess_a = await session_repo.create_session(
            organization_id=tenant_a,
            agent_id=str(uuid.uuid4()),
            agent_version_id=str(uuid.uuid4()),
            room_name=f"room-a-{uuid.uuid4()}",
            channel="web",
        )
        session_a_id = sess_a["id"]

        # Record sensitive tool execution audit in Tenant A's session
        await tool_repo.record_tool_call(
            session_id=session_a_id,
            tool_name="transfer_funds",
            arguments={"account": "AC-999", "amount": 100000},
            result={"status": "approved", "tx_id": "TX-SECRET-123"},
            status="success",
            latency_ms=110,
        )

        # 1. Tenant B calls GET /sessions/{session_a_id}/tool-calls -> MUST return 404
        resp_b = client.get(f"/sessions/{session_a_id}/tool-calls", headers=headers_b)
        assert resp_b.status_code == 404, (
            f"Expected 404 for cross-tenant audit inspection, got {resp_b.status_code}"
        )

        # 2. Tenant B attempts header spoofing: Token is Tenant B, but X-Organization-Id is Tenant A
        spoofed_headers = {
            **headers_b,
            "X-Organization-Id": tenant_a,
        }
        resp_spoofed = client.get(f"/sessions/{session_a_id}/tool-calls", headers=spoofed_headers)
        assert resp_spoofed.status_code == 403, (
            f"Expected 403 TENANT_MISMATCH, got {resp_spoofed.status_code}"
        )

        # 3. Tenant A can read its own audit trail
        resp_a = client.get(f"/sessions/{session_a_id}/tool-calls", headers=headers_a)
        assert resp_a.status_code == 200
        logs = resp_a.json()
        assert len(logs) == 1
        assert logs[0]["tool_name"] == "transfer_funds"
    finally:
        app.dependency_overrides.pop(get_session_service, None)


# =====================================================================
# 3. Agent Tool Binding Attacks
# =====================================================================


@pytest.mark.asyncio
async def test_agent_tool_binding_cross_tenant_rejected() -> None:
    """Verify that Tenant B cannot bind tools owned by Tenant A to an agent."""
    tool_repo = ToolRepository()
    agent_repo = AgentRepository()
    agent_service = AgentService(repository=agent_repo, tool_repository=tool_repo)

    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    # 1. Tenant A creates Tool A
    tool_a = await tool_repo.create_tool(
        organization_id=tenant_a,
        name="tenant_a_tool",
        tool_type="http",
        config={"url": "https://api.a.example"},
        json_schema={},
    )
    tool_a_id = tool_a["id"]

    # 2. Tenant B attempts to create an Agent attaching Tool A
    from backend.app.core.errors import AppError

    with pytest.raises(AppError) as exc_info:
        await agent_service.create_agent(
            organization_id=tenant_b,
            data=AgentCreate(
                name="Tenant B Agent",
                system_prompt="Help users",
                tool_ids=[tool_a_id],  # Tool A belongs to Tenant A!
            ),
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "TOOL_NOT_FOUND"

    # 3. Tenant B creates a legitimate agent without tools
    agent_b = await agent_service.create_agent(
        organization_id=tenant_b,
        data=AgentCreate(
            name="Tenant B Agent Clean",
            system_prompt="Help users",
            tool_ids=[],
        ),
    )
    agent_b_id = agent_b.id

    # 4. Tenant B attempts to update Agent B attaching Tool A
    with pytest.raises(AppError) as exc_update_info:
        await agent_service.update_agent(
            organization_id=tenant_b,
            agent_id=agent_b_id,
            data=AgentUpdate(tool_ids=[tool_a_id]),
        )
    assert exc_update_info.value.status_code == 404
    assert exc_update_info.value.code == "TOOL_NOT_FOUND"

    # 5. Verify that no tools are attached to Agent B's version
    version_id = agent_b.current_version.id  # type: ignore[union-attr]
    attached_tools = await tool_repo.get_tools_for_version(version_id)
    assert len(attached_tools) == 0


@pytest.mark.asyncio
async def test_agent_tool_binding_nonexistent_tool_rejected() -> None:
    """Verify binding non-existent tool UUIDs is rejected with 404 TOOL_NOT_FOUND."""
    tool_repo = ToolRepository()
    agent_repo = AgentRepository()
    agent_service = AgentService(repository=agent_repo, tool_repository=tool_repo)

    org_id = str(uuid.uuid4())
    fake_tool_id = str(uuid.uuid4())

    from backend.app.core.errors import AppError

    with pytest.raises(AppError) as exc_info:
        await agent_service.create_agent(
            organization_id=org_id,
            data=AgentCreate(
                name="Fake Tool Agent",
                system_prompt="Prompt",
                tool_ids=[fake_tool_id],
            ),
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "TOOL_NOT_FOUND"


# =====================================================================
# 4. Internal Gateway Token Fuzzing & Boundary Attacks
# =====================================================================


@pytest.mark.asyncio
async def test_internal_gateway_token_fuzzing_unicode_and_malformed() -> None:
    """Fuzz X-Internal-Service-Token with unicode, non-ASCII, null bytes, and extreme lengths."""
    from fastapi import HTTPException

    from backend.app.modules.internal.router import verify_internal_token

    client = TestClient(app)
    target_endpoint = "/internal/sessions/sess-test-123/tools/invoke"
    payload = {"tool_name": "check_weather", "arguments": {}}

    # 1. ASCII-safe malformed and extreme tokens via HTTP client
    ascii_fuzz_tokens = [
        "",  # empty
        "   ",  # whitespace
        "invalid_ascii_token",
        "wrong-secret-token",
        "A" * 10000,  # buffer overflow / length stress
    ]

    for token in ascii_fuzz_tokens:
        resp = client.post(
            target_endpoint,
            json=payload,
            headers={"X-Internal-Service-Token": token},
        )
        assert resp.status_code == 401, (
            f"Fuzz token failed: expected 401, got {resp.status_code} for token: {repr(token)}"
        )

    # 2. Unicode and non-ASCII tokens tested against verify_internal_token dependency directly
    unicode_fuzz_tokens = [
        "🔑service-token",  # emoji
        "token\x00with\x00nulls",  # null bytes
        "привет_мир_токен",  # cyrillic
        "测试internal_token",  # CJK
        "\u200b\u200c\u200d",  # zero-width chars
        "\uffff\ufffe",  # high unicode
    ]

    for token in unicode_fuzz_tokens:
        with pytest.raises(HTTPException) as exc_info:
            await verify_internal_token(x_internal_service_token=token)
        assert exc_info.value.status_code == 401, (
            f"Expected 401 for unicode token {repr(token)}, got {exc_info.value.status_code}"
        )


def test_internal_gateway_token_timing_attack_resilience() -> None:
    """Empirically test timing resilience of compare_digest on token verification.

    Tests that token comparison runs in constant time regardless of prefix match depth.
    """
    secret = settings.INTERNAL_SERVICE_TOKEN
    assert len(secret) > 0, "INTERNAL_SERVICE_TOKEN must be configured"

    # Construct tokens with varying degrees of prefix matching
    mismatch_0 = "X" * len(secret)
    half_len = len(secret) // 2
    mismatch_half = secret[:half_len] + "X" * (len(secret) - half_len)
    almost_match = secret[:-1] + ("X" if secret[-1] != "X" else "Y")
    wrong_length = secret + "extra_padding"

    iterations = 50000

    def time_comparison(candidate: str) -> float:
        t0 = time.perf_counter()
        for _ in range(iterations):
            compare_digest(candidate, secret)
        return time.perf_counter() - t0

    dur_0 = time_comparison(mismatch_0)
    dur_half = time_comparison(mismatch_half)
    dur_almost = time_comparison(almost_match)
    time_comparison(wrong_length)

    # Calculate timing variance across candidate strings of same length
    times = [dur_0, dur_half, dur_almost]
    max_time = max(times)
    min_time = min(times)
    diff_ratio = (max_time - min_time) / min_time

    # In constant-time comparison, timing difference across same-length candidates
    # should be small (typically within noise threshold < 15%)
    assert diff_ratio < 0.25, (
        f"Suspicious timing variance in compare_digest: min={min_time:.4f}s, "
        f"max={max_time:.4f}s (diff ratio={diff_ratio:.2%})"
    )


def test_internal_gateway_invalid_session_ids_handling() -> None:
    """Test handling of path traversal, invalid characters, and non-existent session IDs."""
    client = TestClient(app)
    auth_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    payload = {"tool_name": "fetch_data", "arguments": {}}

    invalid_session_ids = [
        "sess-non-existent-9999",
        "12345",
        "random-uuid-string",
        "../admin",
        "../../etc/passwd",
    ]

    for sess_id in invalid_session_ids:
        resp = client.post(
            f"/internal/sessions/{sess_id}/tools/invoke",
            json=payload,
            headers=auth_headers,
        )
        # Should not crash with 500 Internal Server Error
        assert resp.status_code in (200, 404), (
            f"Expected clean error (200/404), got {resp.status_code} for session {sess_id}"
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data["status"] == "failed"
            assert "not found" in data["error"].lower()


def test_vulnerability_probe_hardcoded_mock_session_bypass() -> None:
    """Adversarial probe: Test if hardcoded session ID 'sess-mock-1' bypasses session validation.

    In backend/app/modules/internal/service.py:
        if session_id == "sess-mock-1":
            return ToolInvokeResponse(
                tool_name=request.tool_name,
                result={"status": "completed", ...},
                status="success",
            )
    This test probes whether this development artifact bypasses session and tool attachment checks.
    """
    client = TestClient(app)
    auth_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    # Invoke with an arbitrary imaginary tool on sess-mock-1 without creating the session
    resp = client.post(
        "/internal/sessions/sess-mock-1/tools/invoke",
        json={"tool_name": "unauthorized_exploit_tool", "arguments": {}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # If status is "success", it proves the hardcoded mock backdoor is active in internal gateway!
    has_hardcoded_bypass = data["status"] == "success" and data["result"] is not None
    assert not has_hardcoded_bypass, (
        "HARDCODED BACKDOOR/MOCK ARTIFACT FOUND: 'sess-mock-1' returned success "
        f"for unattached tool without session existing! Response: {data}"
    )


@pytest.mark.asyncio
async def test_internal_gateway_unattached_tool_invocation_blocked() -> None:
    """Verify that a worker cannot invoke a tool not attached to the pinned agent version."""
    tool_repo = ToolRepository()
    agent_repo = AgentRepository()
    session_repo = SessionRepository()
    session_service = SessionService(repository=session_repo)
    agent_service = AgentService(repository=agent_repo, tool_repository=tool_repo)
    internal_service = InternalGatewayService(
        session_service=session_service,
        agent_service=agent_service,
        tool_repository=tool_repo,
    )

    org_id = str(uuid.uuid4())

    # Create legitimate tool and bind to agent
    tool = await tool_repo.create_tool(
        organization_id=org_id,
        name="allowed_tool",
        tool_type="http",
        config={"url": "https://api.allowed.example"},
        json_schema={},
    )
    agent = await agent_service.create_agent(
        organization_id=org_id,
        data=AgentCreate(name="Agent", system_prompt="Prompt", tool_ids=[tool["id"]]),
    )
    sess = await session_repo.create_session(
        organization_id=org_id,
        agent_id=agent.id,
        agent_version_id=agent.current_version.id,  # type: ignore[union-attr]
        room_name=f"room-{uuid.uuid4()}",
        channel="web",
    )

    # Attempt to invoke unattached tool
    resp = await internal_service.invoke_tool(
        session_id=sess["id"],
        request=ToolInvokeRequest(tool_name="unattached_secret_tool", arguments={}),
    )
    assert resp.status == "failed"
    assert "not attached" in str(resp.error)


@pytest.mark.asyncio
async def test_vulnerability_probe_missing_json_schema_validation() -> None:
    """Adversarial probe: Test if internal gateway validates arguments against tool JSON schema.

    Requirement from ORIGINAL_REQUEST.md & M5 Plan:
        'POST /internal/sessions/{id}/tools/invoke validating arguments against tool JSON schema'
        'HTTP webhook and SIP transfer tools validate arguments against schema'
    If the tool defines required fields (e.g. order_id string) and caller passes invalid
    arguments (e.g. empty dict or wrong type), the gateway should fail validation before dispatch.
    """
    tool_repo = ToolRepository()
    agent_repo = AgentRepository()
    session_repo = SessionRepository()
    session_service = SessionService(repository=session_repo)
    agent_service = AgentService(repository=agent_repo, tool_repository=tool_repo)
    internal_service = InternalGatewayService(
        session_service=session_service,
        agent_service=agent_service,
        tool_repository=tool_repo,
    )

    org_id = str(uuid.uuid4())

    # Create tool with strict JSON schema: requires string 'order_id'
    tool = await tool_repo.create_tool(
        organization_id=org_id,
        name="strict_order_lookup",
        tool_type="http",
        config={"url": "http://93.184.216.34/orders", "method": "POST"},
        json_schema={
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
            "additionalProperties": False,
        },
    )
    agent = await agent_service.create_agent(
        organization_id=org_id,
        data=AgentCreate(name="Strict Agent", system_prompt="Prompt", tool_ids=[tool["id"]]),
    )
    sess = await session_repo.create_session(
        organization_id=org_id,
        agent_id=agent.id,
        agent_version_id=agent.current_version.id,  # type: ignore[union-attr]
        room_name=f"room-{uuid.uuid4()}",
        channel="web",
    )

    # Attack: Pass empty arguments missing the required 'order_id' property
    invalid_args: dict[str, Any] = {}

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = httpx.Response(
            status_code=200,
            json={"status": "ok"},
            request=httpx.Request("POST", "http://93.184.216.34/orders"),
        )
        await internal_service.invoke_tool(
            session_id=sess["id"],
            request=ToolInvokeRequest(tool_name="strict_order_lookup", arguments=invalid_args),
        )

        # If mock_req was called, the gateway skipped JSON schema validation and dispatched HTTP!
        dispatched_without_validation = mock_req.called
        assert not dispatched_without_validation, (
            "DEFECT FOUND: Internal gateway dispatched outbound tool call with invalid arguments "
            "without validating against tool's json_schema! (HTTP request was dispatched with {})"
        )
