"""Tests for customer-facing transcript, metrics, and recording presigned URL endpoints."""

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
async def api_records_client() -> AsyncGenerator[AsyncClient, None]:
    agent_repo = AgentRepository()
    agent_svc = AgentService(repository=agent_repo, provider_service=ProviderService())
    sess_repo = SessionRepository()
    sess_svc = SessionService(repository=sess_repo, agent_service=agent_svc)
    gw_svc = InternalGatewayService(session_service=sess_svc, agent_service=agent_svc)

    app.dependency_overrides[get_agent_service] = lambda: agent_svc
    app.dependency_overrides[get_session_service] = lambda: sess_svc
    app.dependency_overrides[get_internal_service] = lambda: gw_svc

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_agent_service, None)
    app.dependency_overrides.pop(get_session_service, None)
    app.dependency_overrides.pop(get_internal_service, None)


@pytest.mark.asyncio
async def test_customer_records_endpoints(api_records_client: AsyncClient) -> None:
    """Verify customer can retrieve session transcripts, metrics, and presigned recording URLs."""
    org_id = "org-records-api-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    # 1. Create Agent and Session
    agent_res = await api_records_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Billing Agent", "system_prompt": "Help with bills."},
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    sess_res = await api_records_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # 2. Finalize session with transcript & recording
    fin_res = await api_records_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 30,
            "transcript_segments": [
                {
                    "seq": 1,
                    "speaker": "caller",
                    "text": "I paid my bill.",
                    "started_at_ms": 1000,
                },
                {
                    "seq": 2,
                    "speaker": "agent",
                    "text": "Thank you, payment confirmed.",
                    "started_at_ms": 3000,
                },
            ],
            "metrics": {"avg_latency_ms": 250, "p95_latency_ms": 400},
        },
    )
    assert fin_res.status_code == 200

    egress_res = await api_records_client.post(
        "/internal/egress/finalize",
        headers=internal_headers,
        json={"session_id": session_id, "recording_key": f"recordings/{session_id}.mp4"},
    )
    assert egress_res.status_code == 200

    # 3. Retrieve Transcript
    trans_res = await api_records_client.get(
        f"/sessions/{session_id}/transcript", headers=user_headers
    )
    assert trans_res.status_code == 200
    trans_data = trans_res.json()
    assert len(trans_data) == 2
    assert trans_data[0]["speaker"] == "caller"
    assert trans_data[1]["text"] == "Thank you, payment confirmed."

    # 4. Retrieve Metrics
    metrics_res = await api_records_client.get(
        f"/sessions/{session_id}/metrics", headers=user_headers
    )
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert metrics_data["avg_latency_ms"] == 250
    assert metrics_data["p95_latency_ms"] == 400

    # 5. Retrieve Recording URL
    rec_res = await api_records_client.get(
        f"/sessions/{session_id}/recording-url", headers=user_headers
    )
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert "recording_url" in rec_data
    assert f"recordings/{session_id}.mp4" in rec_data["recording_url"]
    assert rec_data["expires_in_seconds"] == 900
