"""Empirical adversarial challenge suite for Milestone M3 (Providers, Worker Gateway & Sessions)."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.livekit import generate_livekit_token
from backend.app.core.security import create_access_token
from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService
from backend.app.modules.internal.router import get_internal_service
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.providers.service import ProviderService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.router import get_session_service
from backend.app.modules.sessions.service import SessionService
from worker.agent.entrypoint import RuntimeConfig
from worker.agent.pipeline import VoicePipeline
from worker.providers.cartesia import CartesiaTTSProvider
from worker.providers.deepgram import DeepgramSTTProvider
from worker.providers.factory import ProviderFactory
from worker.providers.openai import OpenAILLMProvider


@pytest.fixture
async def challenge_client() -> AsyncGenerator[AsyncClient, None]:
    """Test client with linked in-memory repositories and services."""
    agent_repo = AgentRepository()
    agent_svc = AgentService(repository=agent_repo, provider_service=ProviderService())
    sess_repo = SessionRepository()
    sess_svc = SessionService(repository=sess_repo, agent_service=agent_svc)
    gw_svc = InternalGatewayService(session_service=sess_svc, agent_service=agent_svc)

    app.dependency_overrides[get_agent_service] = lambda: agent_svc
    app.dependency_overrides[get_session_service] = lambda: sess_svc
    app.dependency_overrides[get_internal_service] = lambda: gw_svc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_agent_service, None)
    app.dependency_overrides.pop(get_session_service, None)
    app.dependency_overrides.pop(get_internal_service, None)


@pytest.mark.asyncio
async def test_challenge_token_security_variations(challenge_client: AsyncClient) -> None:
    """Challenge constant-time internal token verification under various invalid header formats."""
    # 1. No header
    res1 = await challenge_client.get("/internal/sessions/s1/runtime-config")
    assert res1.status_code == 401

    # 2. Empty header
    res2 = await challenge_client.get(
        "/internal/sessions/s1/runtime-config",
        headers={"X-Internal-Service-Token": ""},
    )
    assert res2.status_code == 401

    # 3. Trailing space or partial token
    res3 = await challenge_client.get(
        "/internal/sessions/s1/runtime-config",
        headers={"X-Internal-Service-Token": f"{settings.INTERNAL_SERVICE_TOKEN} "},
    )
    assert res3.status_code == 401

    # 4. Finalize with bad token
    res4 = await challenge_client.post(
        "/internal/sessions/s1/finalize",
        headers={"X-Internal-Service-Token": "invalid-token"},
        json={"duration_s": 10},
    )
    assert res4.status_code == 401

    # 5. Egress finalize with bad token
    res5 = await challenge_client.post(
        "/internal/egress/finalize",
        headers={"X-Internal-Service-Token": "invalid-token"},
        json={"egress_id": "eg-1", "session_id": "s1", "recording_key": "k.mp4", "status": "ok"},
    )
    assert res5.status_code == 401


@pytest.mark.asyncio
async def test_challenge_nonexistent_session_runtime_config(
    challenge_client: AsyncClient,
) -> None:
    """Challenge internal runtime config retrieval with a non-existent session ID."""
    headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    res = await challenge_client.get(
        "/internal/sessions/sess-nonexistent-12345/runtime-config",
        headers=headers,
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_challenge_dispatch_nonexistent_agent(challenge_client: AsyncClient) -> None:
    """Challenge POST /sessions/web with non-existent or wrong-tenant agent ID."""
    token = create_access_token(
        data={"sub": "usr-1", "organization_id": "org-chal", "role": "owner"}
    )
    headers = {"Authorization": f"Bearer {token}"}

    res = await challenge_client.post(
        "/sessions/web",
        headers=headers,
        json={"agent_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "AGENT_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_challenge_cross_tenant_session_isolation(challenge_client: AsyncClient) -> None:
    """Challenge cross-tenant data leakage on session retrieval and listing."""
    # Org A creates an agent and dispatches a session
    token_a = create_access_token(
        data={"sub": "usr-a", "organization_id": "org-aaa", "role": "owner"}
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    agent_res = await challenge_client.post(
        "/agents",
        headers=headers_a,
        json={"name": "Org A Agent", "system_prompt": "Prompt A"},
    )
    agent_id = agent_res.json()["id"]

    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=headers_a,
        json={"agent_id": agent_id},
    )
    session_id = sess_res.json()["session_id"]

    # Org B attempts to get session
    token_b = create_access_token(
        data={"sub": "usr-b", "organization_id": "org-bbb", "role": "owner"}
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    get_b_res = await challenge_client.get(f"/sessions/{session_id}", headers=headers_b)
    assert get_b_res.status_code == 404

    # Org B lists sessions: should NOT see Org A's session
    list_b_res = await challenge_client.get("/sessions", headers=headers_b)
    assert list_b_res.status_code == 200
    items = list_b_res.json()["items"]
    assert not any(item["id"] == session_id for item in items)


@pytest.mark.asyncio
async def test_challenge_agent_version_pinning_immutability(
    challenge_client: AsyncClient,
) -> None:
    """Verify updating agent after dispatch does NOT change pinned session config."""
    token = create_access_token(
        data={"sub": "usr-p", "organization_id": "org-pin", "role": "owner"}
    )
    headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    # 1. Create agent v1
    agent_res = await challenge_client.post(
        "/agents",
        headers=headers,
        json={"name": "Original Agent", "system_prompt": "Version 1 System Prompt"},
    )
    agent_id = agent_res.json()["id"]

    # 2. Dispatch session (pins v1)
    sess_res = await challenge_client.post(
        "/sessions/web",
        headers=headers,
        json={"agent_id": agent_id},
    )
    session_id = sess_res.json()["session_id"]

    # 3. Update agent to v2
    update_res = await challenge_client.patch(
        f"/agents/{agent_id}",
        headers=headers,
        json={"system_prompt": "MUTATED Version 2 System Prompt"},
    )
    assert update_res.status_code == 200

    # 4. Fetch runtime config for earlier session: MUST still have v1 system prompt!
    rtc_res = await challenge_client.get(
        f"/internal/sessions/{session_id}/runtime-config",
        headers=internal_headers,
    )
    assert rtc_res.status_code == 200
    rtc_data = rtc_res.json()
    assert rtc_data["system_prompt"] == "Version 1 System Prompt"


def test_challenge_livekit_token_structure() -> None:
    """Challenge LiveKit JWT token generation with extreme strings and verify RFC validity."""
    tok = generate_livekit_token(
        room_name="room-with-special_chars.123",
        participant_identity="caller-unicode-テスト",
        session_id="sess-xyz-987",
        ttl_seconds=7200,
    )
    assert isinstance(tok, str)
    parts = tok.split(".")
    assert len(parts) == 3


@pytest.mark.asyncio
async def test_challenge_provider_factory_custom_configs() -> None:
    """Challenge ProviderFactory with varying models and voice choices."""
    config = RuntimeConfig(
        session_id="s1",
        agent_id="a1",
        agent_version_id="v1",
        system_prompt="Prompt",
        stt_config={"provider": "deepgram", "model": "general"},
        llm_config={"provider": "openai", "model": "gpt-4o"},
        tts_config={"provider": "cartesia", "model": "sonic-multilingual", "voice": "custom-v"},
    )
    stt, llm, tts = ProviderFactory.create_providers(config)
    assert isinstance(stt, DeepgramSTTProvider)
    assert stt.model == "general"
    assert isinstance(llm, OpenAILLMProvider)
    assert llm.model == "gpt-4o"
    assert isinstance(tts, CartesiaTTSProvider)
    assert tts.model == "sonic-multilingual"
    assert tts.voice == "custom-v"


@pytest.mark.asyncio
async def test_challenge_voice_pipeline_no_greeting() -> None:
    """Challenge VoicePipeline when greeting is None."""
    config = RuntimeConfig(
        session_id="s1",
        agent_id="a1",
        agent_version_id="v1",
        system_prompt="Prompt",
        greeting=None,
    )
    stt, llm, tts = ProviderFactory.create_providers(config)
    pipeline = VoicePipeline(config=config, stt=stt, llm=llm, tts=tts)

    greeting_audio = await pipeline.get_greeting_audio()
    assert greeting_audio is None
