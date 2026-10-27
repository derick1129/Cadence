"""Tests for Telephony, Sessions, and Internal modules."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.core.settings import settings
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.schemas import AgentCreate
from backend.app.modules.agents.service import AgentService
from backend.app.modules.internal import router as internal_router
from backend.app.modules.internal.router import get_internal_service
from backend.app.modules.internal.schemas import (
    EgressFinalizeRequest,
    FinalizeSessionRequest,
    SipIntakeRequest,
    ToolInvokeRequest,
)
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.sessions import router as sessions_router
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.schemas import WebSessionStartRequest
from backend.app.modules.sessions.service import SessionService
from backend.app.modules.telephony import router as telephony_router
from backend.app.modules.telephony.schemas import PhoneNumberAssign
from backend.app.modules.telephony.service import TelephonyService
from backend.app.modules.tools.repository import ToolRepository


@pytest.fixture
def test_app() -> FastAPI:
    """FastAPI app instance containing telephony, sessions, and internal routers."""
    app = FastAPI(title="Part C Test App")
    app.include_router(telephony_router)
    app.include_router(sessions_router)
    app.include_router(internal_router)
    return app


@pytest.mark.asyncio
async def test_telephony_service_and_endpoints(test_app: FastAPI) -> None:
    """Verify TelephonyService and its HTTP endpoints."""
    service = TelephonyService()
    numbers = await service.list_phone_numbers(organization_id="org-test-1")
    assert len(numbers) >= 1
    assert numbers[0].e164 == "+15551234567"

    assigned = await service.assign_agent(
        organization_id="org-test-1",
        phone_number_id="pn-mock-1",
        data=PhoneNumberAssign(agent_id="agent-custom-9"),
    )
    assert assigned is not None
    assert assigned.agent_id == "agent-custom-9"

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        res = await client.get("/telephony/numbers?organization_id=org-test-1")
        assert res.status_code == 200
        assert len(res.json()) >= 1

        res = await client.post(
            "/telephony/numbers/pn-mock-1/assign?organization_id=org-test-1",
            json={"agent_id": "agent-new"},
        )
        assert res.status_code == 200
        assert res.json()["agent_id"] == "agent-new"


@pytest.mark.asyncio
async def test_sessions_service_and_endpoints(test_app: FastAPI) -> None:
    """Verify SessionService and its HTTP endpoints."""
    from backend.app.core.security import create_access_token
    from backend.app.modules.agents.schemas import AgentCreate
    from backend.app.modules.sessions.router import get_session_service

    service = SessionService()
    test_app.dependency_overrides[get_session_service] = lambda: service

    # 1. Create agent for org-test-1
    agent = await service.agent_service.create_agent(
        organization_id="org-test-1",
        data=AgentCreate(name="Mock Agent", system_prompt="Test"),
    )
    agent_id = agent.id

    start_res = await service.start_web_session(
        organization_id="org-test-1",
        request=WebSessionStartRequest(agent_id=agent_id),
    )
    assert start_res.session_id.startswith("sess-")
    assert "cadence-room-" in start_res.room_name
    assert start_res.livekit_token != ""

    list_res = await service.list_sessions(organization_id="org-test-1")
    assert list_res.total >= 1

    token = create_access_token(
        data={"sub": "usr-c", "organization_id": "org-test-1", "role": "owner"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        res = await client.post(
            "/sessions/web",
            headers=headers,
            json={"agent_id": agent_id},
        )
        assert res.status_code == 201
        data = res.json()
        assert "session_id" in data
        assert "room_name" in data

        res = await client.get("/sessions", headers=headers)
        assert res.status_code == 200
        assert res.json()["total"] >= 1


@pytest.mark.asyncio
async def test_internal_service_and_endpoints(test_app: FastAPI) -> None:
    """Verify InternalGatewayService and internal worker endpoints with provisioned session."""
    tool_repo = ToolRepository()
    agent_repo = AgentRepository()
    session_repo = SessionRepository()
    agent_service = AgentService(repository=agent_repo, tool_repository=tool_repo)
    session_service = SessionService(repository=session_repo, agent_service=agent_service)
    service = InternalGatewayService(
        session_service=session_service,
        agent_service=agent_service,
        tool_repository=tool_repo,
    )
    test_app.dependency_overrides[get_internal_service] = lambda: service

    try:
        org_id = "org-test-1"
        t1 = await tool_repo.create_tool(
            organization_id=org_id,
            name="get_balance",
            tool_type="transfer",
            config={"phone_number": "+15551234567"},
            json_schema={"type": "object", "properties": {"acc": {"type": "integer"}}},
        )
        t2 = await tool_repo.create_tool(
            organization_id=org_id,
            name="lookup",
            tool_type="transfer",
            config={"phone_number": "+15551234567"},
            json_schema={"type": "object"},
        )
        agent = await agent_service.create_agent(
            organization_id=org_id,
            data=AgentCreate(
                name="Mock Agent",
                system_prompt="Cadence Support Agent",
                tts_config={
                    "provider": "cartesia",
                    "model": "sonic-english",
                    "voice": "default-voice",
                },
                tool_ids=[t1["id"], t2["id"]],
            ),
        )
        assert agent.current_version is not None
        sess = await session_repo.create_session(
            organization_id=org_id,
            agent_id=agent.id,
            agent_version_id=agent.current_version.id,
            channel="web",
            room_name="cadence-room-mock-1",
        )
        session_id = sess["id"]

        cfg = await service.get_runtime_config(session_id=session_id)
        assert cfg.session_id == session_id
        assert cfg.system_prompt != ""
        assert "cartesia" in cfg.tts_config["provider"]

        sip_res = await service.handle_sip_intake(SipIntakeRequest(called_number="+15551234567"))
        assert sip_res.status == "accepted"

        tool_res = await service.invoke_tool(
            session_id=session_id,
            request=ToolInvokeRequest(tool_name="get_balance", arguments={"acc": 123}),
        )
        assert tool_res.status == "success"

        fin_res = await service.finalize_session(
            session_id=session_id,
            request=FinalizeSessionRequest(duration_s=120),
        )
        assert fin_res.status == "ok"

        egress_res = await service.finalize_egress(
            EgressFinalizeRequest(recording_key=f"recordings/{session_id}.mp4")
        )
        assert egress_res.status == "ok"

        # Test HTTP routing
        headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            res = await client.get(
                f"/internal/sessions/{session_id}/runtime-config", headers=headers
            )
            assert res.status_code == 200
            assert res.json()["session_id"] == session_id

            res = await client.post(
                "/internal/sessions/intake",
                headers=headers,
                json={"called_number": "+15551234567"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "accepted"

            res = await client.post(
                f"/internal/sessions/{session_id}/tools/invoke",
                headers=headers,
                json={"tool_name": "lookup", "arguments": {}},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "success"

            res = await client.post(
                f"/internal/sessions/{session_id}/finalize",
                headers=headers,
                json={"duration_s": 50},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "ok"

            res = await client.post(
                "/internal/egress/finalize",
                headers=headers,
                json={"recording_key": "recordings/test.mp4"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "ok"
    finally:
        test_app.dependency_overrides.pop(get_internal_service, None)


@pytest.mark.asyncio
async def test_internal_unauthorized_token(test_app: FastAPI) -> None:
    """Verify internal endpoints reject invalid token headers."""
    bad_headers = {"X-Internal-Service-Token": "wrong-invalid-token"}
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        res = await client.get("/internal/sessions/sess-1/runtime-config", headers=bad_headers)
        assert res.status_code == 401
