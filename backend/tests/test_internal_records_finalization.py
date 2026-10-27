"""Tests for internal worker finalization with full transcript and metrics recording."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

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


@pytest.fixture
async def finalization_records_client() -> AsyncGenerator[
    tuple[AsyncClient, SessionRepository], None
]:
    agent_repo = AgentRepository()
    agent_svc = AgentService(repository=agent_repo, provider_service=ProviderService())
    sess_repo = SessionRepository()
    sess_svc = SessionService(repository=sess_repo, agent_service=agent_svc)
    gw_svc = InternalGatewayService(session_service=sess_svc, agent_service=agent_svc)

    app.dependency_overrides[get_agent_service] = lambda: agent_svc
    app.dependency_overrides[get_session_service] = lambda: sess_svc
    app.dependency_overrides[get_internal_service] = lambda: gw_svc

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, sess_repo

    app.dependency_overrides.pop(get_agent_service, None)
    app.dependency_overrides.pop(get_session_service, None)
    app.dependency_overrides.pop(get_internal_service, None)


@pytest.mark.asyncio
async def test_internal_finalization_with_transcripts_and_metrics(
    finalization_records_client: tuple[AsyncClient, SessionRepository],
) -> None:
    """Verify worker can finalize session with transcripts, metrics, and egress recording."""
    client, sess_repo = finalization_records_client
    org_id = "org-records-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Agent and Web Session
    agent_res = await client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Support Agent", "system_prompt": "Help users."},
    )
    agent_id = agent_res.json()["id"]

    sess_res = await client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    session_id = sess_res.json()["session_id"]
    room_name = sess_res.json()["room_name"]

    # 2. Worker calls /finalize with transcripts and metrics
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    finalize_payload = {
        "duration_s": 55,
        "status": "completed",
        "outcome": "completed",
        "outcome_label": "resolved",
        "transcript_segments": [
            {
                "seq": 1,
                "speaker": "caller",
                "text": "What are your business hours?",
                "started_at_ms": 1000,
            },
            {
                "seq": 2,
                "speaker": "agent",
                "text": "We are open from 9am to 5pm daily.",
                "started_at_ms": 2500,
            },
        ],
        "metrics": {
            "avg_latency_ms": 310,
            "p95_latency_ms": 580,
            "interruption_count": 0,
            "llm_tokens_used": 120,
            "stt_seconds_billed": 6.5,
            "tts_characters_billed": 38,
        },
    }
    fin_res = await client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json=finalize_payload,
    )
    assert fin_res.status_code == 200

    # 3. LiveKit Egress calls /egress/finalize
    egress_res = await client.post(
        "/internal/egress/finalize",
        headers=internal_headers,
        json={
            "room_name": room_name,
            "recording_key": f"recordings/{session_id}.mp4",
        },
    )
    assert egress_res.status_code == 200

    # 4. Verify persisted state
    saved_sess = await sess_repo.get_by_id_internal(session_id)
    assert saved_sess is not None
    assert saved_sess["status"] == "completed"
    assert saved_sess["outcome"] == "completed"
    assert saved_sess["outcome_label"] == "resolved"
    assert saved_sess["duration_s"] == 55
    assert saved_sess["recording_key"] == f"recordings/{session_id}.mp4"

    transcripts = await sess_repo.get_transcript(session_id)
    assert len(transcripts) == 2
    assert transcripts[0]["text"] == "What are your business hours?"
    assert transcripts[1]["speaker"] == "agent"

    metrics = await sess_repo.get_metrics(session_id)
    assert metrics is not None
    assert metrics["avg_latency_ms"] == 310
    assert metrics["p95_latency_ms"] == 580
