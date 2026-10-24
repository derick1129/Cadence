"""Tests for /internal/sip/inbound SIP dispatch gateway endpoint."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.telephony.repository import TelephonyRepository


@pytest.mark.asyncio
async def test_internal_sip_inbound_flow() -> None:
    """Verify inbound SIP dispatch creates a phone session and returns LiveKit credentials."""
    telephony_repo = TelephonyRepository()
    agent_repo = AgentRepository()
    org_id = uuid.uuid4()

    # Create agent with version
    agent = await agent_repo.create_agent(str(org_id), name="Phone Support Agent")
    agent_id = uuid.UUID(agent["id"])
    version = await agent_repo.create_version(
        agent_id=str(agent_id),
        version_no=1,
        system_prompt="You are a phone receptionist.",
        greeting="Hello, thanks for calling.",
        stt_config={"provider": "deepgram", "model": "nova-2"},
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        tts_config={"provider": "cartesia", "voice": "sonic-english"},
    )
    version_id = uuid.UUID(version["id"])
    await agent_repo.set_current_version(str(org_id), str(agent_id), str(version_id))

    # Register phone number mapped to agent
    e164 = f"+1555{uuid.uuid4().int % 10000000:07d}"
    await telephony_repo.create_phone_number(
        organization_id=org_id,
        e164=e164,
        carrier="twilio",
        agent_id=agent_id,
        trunk_ref="trunk-inbound-test",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Reject without valid internal token
        res_unauth = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": "bad-token"},
            json={
                "caller_e164": "+15550009999",
                "called_e164": e164,
                "sip_call_id": "call-sip-xyz-123",
            },
        )
        assert res_unauth.status_code == 401

        # 2. Dispatch successfully with valid token
        res = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": "+15550009999",
                "called_e164": e164,
                "sip_call_id": "call-sip-xyz-123",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "room_name" in data
        assert "livekit_token" in data
        assert "session_id" in data
        assert data["channel"] == "phone"
        assert data["agent_id"] == str(agent_id)

        # 3. Reject unknown number with 404
        res_unknown = await client.post(
            "/internal/sip/inbound",
            headers={"X-Internal-Service-Token": settings.internal_service_token},
            json={
                "caller_e164": "+15550009999",
                "called_e164": "+15550000000",
                "sip_call_id": "call-sip-xyz-404",
            },
        )
        assert res_unknown.status_code == 404
