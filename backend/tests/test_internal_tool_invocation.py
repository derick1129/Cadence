"""Tests for worker internal tool invocation gateway, audit logging, and outcome sync."""

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.schemas import AgentCreate
from backend.app.modules.agents.service import AgentService
from backend.app.modules.internal.schemas import ToolInvokeRequest
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.service import SessionService
from backend.app.modules.tools.repository import ToolRepository


@pytest.mark.asyncio
async def test_invoke_http_tool_success_and_audit_recording() -> None:
    """Verify executing an attached HTTP tool runs outbound call and records audit log."""
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

    # 1. Create tool
    tool = await tool_repo.create_tool(
        organization_id=org_id,
        name="fetch_user_profile",
        tool_type="http",
        config={"url": "http://93.184.216.34/profile", "method": "POST"},
        json_schema={"type": "object", "properties": {"user_id": {"type": "string"}}},
        outcome_label="profile_fetched",
    )

    # 2. Create agent with tool
    agent = await agent_service.create_agent(
        organization_id=org_id,
        data=AgentCreate(
            name="Profile Assistant",
            system_prompt="Fetch profiles",
            tool_ids=[tool["id"]],
        ),
    )
    v1_id = agent.current_version.id  # type: ignore[union-attr]

    # 3. Create session
    sess = await session_repo.create_session(
        organization_id=org_id,
        agent_id=agent.id,
        agent_version_id=v1_id,
        room_name=f"room-{uuid.uuid4()}",
        channel="web",
    )
    session_id = sess["id"]

    # 4. Invoke tool with mocked HTTP transport
    mock_response = httpx.Response(
        status_code=200,
        json={"name": "Alice", "tier": "gold"},
        request=httpx.Request("POST", "http://93.184.216.34/profile"),
    )

    with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        resp = await internal_service.invoke_tool(
            session_id=session_id,
            request=ToolInvokeRequest(
                tool_name="fetch_user_profile",
                arguments={"user_id": "usr-123"},
            ),
        )

        assert resp.status == "success"
        assert resp.tool_name == "fetch_user_profile"
        assert resp.result == {"name": "Alice", "tier": "gold"}
        assert resp.error is None
        assert resp.latency_ms >= 0

    # 5. Verify audit log recorded in ToolRepository
    calls = await tool_repo.list_tool_calls_for_session(session_id)
    assert len(calls) == 1
    assert calls[0]["tool_name"] == "fetch_user_profile"
    assert calls[0]["arguments"] == {"user_id": "usr-123"}
    assert calls[0]["status"] == "success"

    # 6. Verify session outcome_label was updated
    updated_sess = await session_service.get_session_internal(session_id)
    assert updated_sess is not None
    assert updated_sess.get("outcome_label") == "profile_fetched"


@pytest.mark.asyncio
async def test_invoke_transfer_tool_and_unattached_tool_failure() -> None:
    """Verify telephony transfer tool execution and error handling for unattached tools."""
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

    # Create transfer tool and bind to agent
    tool = await tool_repo.create_tool(
        organization_id=org_id,
        name="transfer_to_support",
        tool_type="transfer",
        config={"phone_number": "+15559876543"},
        json_schema={},
    )
    agent = await agent_service.create_agent(
        organization_id=org_id,
        data=AgentCreate(
            name="Transfer Agent",
            system_prompt="Transfer calls",
            tool_ids=[tool["id"]],
        ),
    )
    sess = await session_repo.create_session(
        organization_id=org_id,
        agent_id=agent.id,
        agent_version_id=agent.current_version.id,  # type: ignore[union-attr]
        room_name=f"room-{uuid.uuid4()}",
        channel="web",
    )

    # 1. Invoke transfer tool
    resp = await internal_service.invoke_tool(
        session_id=sess["id"],
        request=ToolInvokeRequest(tool_name="transfer_to_support", arguments={}),
    )
    assert resp.status == "success"
    assert resp.result["action"] == "transfer"
    assert resp.result["target"] == "+15559876543"

    # 2. Invoke unattached tool -> fails
    unattached_resp = await internal_service.invoke_tool(
        session_id=sess["id"],
        request=ToolInvokeRequest(tool_name="non_existent_tool", arguments={}),
    )
    assert unattached_resp.status == "failed"
    assert "not attached" in str(unattached_resp.error)

    # 3. Invoke on non-existent session -> fails
    bad_sess_resp = await internal_service.invoke_tool(
        session_id="sess-does-not-exist",
        request=ToolInvokeRequest(tool_name="transfer_to_support", arguments={}),
    )
    assert bad_sess_resp.status == "failed"
    assert "not found" in str(bad_sess_resp.error)


def test_internal_tool_invoke_endpoint_auth() -> None:
    """Verify POST /internal/sessions/{id}/tools/invoke enforces service token auth."""
    client = TestClient(app)

    # Missing token -> 401
    resp = client.post(
        "/internal/sessions/sess-123/tools/invoke",
        json={"tool_name": "test", "arguments": {}},
    )
    assert resp.status_code == 401

    # Invalid token -> 401
    resp = client.post(
        "/internal/sessions/sess-123/tools/invoke",
        json={"tool_name": "test", "arguments": {}},
        headers={"X-Internal-Service-Token": "wrong-token"},
    )
    assert resp.status_code == 401

    # Valid token -> 200 (processed)
    resp = client.post(
        "/internal/sessions/sess-123/tools/invoke",
        json={"tool_name": "test", "arguments": {}},
        headers={"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN},
    )
    assert resp.status_code == 200
