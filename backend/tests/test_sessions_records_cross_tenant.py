"""Tests for session reconciliation and cross-tenant records access prevention."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import create_access_token
from backend.app.core.settings import settings
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService
from backend.app.modules.internal.router import get_internal_service
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.providers.service import ProviderService
from backend.app.modules.sessions.models import Session
from backend.app.modules.sessions.reconciliation import reconcile_orphaned_sessions
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.router import get_session_service
from backend.app.modules.sessions.service import SessionService


@pytest.fixture
async def records_client() -> AsyncGenerator[AsyncClient, None]:
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
async def test_reconcile_orphaned_sessions() -> None:
    """Verify reconciliation job closes stale initiated/active sessions as failed/abandoned."""
    repo = SessionRepository()
    org_id = str(uuid.uuid4())
    sess = await repo.create_session(
        organization_id=org_id,
        agent_id=str(uuid.uuid4()),
        agent_version_id=str(uuid.uuid4()),
        channel="web",
        room_name=f"stale-{uuid.uuid4().hex[:6]}",
    )

    closed_count = await reconcile_orphaned_sessions(repository=repo, stale_threshold_seconds=0)
    assert closed_count >= 1

    updated = await repo.get_by_id_internal(sess["id"])
    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["outcome"] == "abandoned"


@pytest.mark.asyncio
async def test_reconcile_orphaned_sessions_db_mode() -> None:
    """Verify reconciliation job updates stale sessions via AsyncSession."""
    mock_session = AsyncMock(spec=AsyncSession)
    fake_sess = Session(
        organization_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        agent_version_id=uuid.uuid4(),
        room_name="test-room",
        status="active",
    )
    fake_sess.id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fake_sess]
    mock_session.execute.return_value = mock_result

    count = await reconcile_orphaned_sessions(session=mock_session, stale_threshold_seconds=0)
    assert count == 1
    assert fake_sess.status == "failed"
    assert fake_sess.outcome == "abandoned"
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_reconcile_orphaned_sessions_null_started_at() -> None:
    """Verify reconciliation closes stale initiated sessions when started_at is NULL."""
    repo = SessionRepository()
    sess = await repo.create_session(
        organization_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        agent_version_id=str(uuid.uuid4()),
        channel="web",
        room_name=f"null-started-{uuid.uuid4().hex[:6]}",
    )
    repo._mock_sessions[sess["id"]]["started_at"] = None
    repo._mock_sessions[sess["id"]]["created_at"] = datetime.now(UTC) - timedelta(seconds=700)
    repo._mock_sessions[sess["id"]]["status"] = "initiated"

    closed = await reconcile_orphaned_sessions(repository=repo, stale_threshold_seconds=600)
    assert closed == 1

    updated = await repo.get_by_id_internal(sess["id"])
    assert updated is not None
    assert updated["status"] == "failed"
    assert updated["outcome"] == "abandoned"
    assert updated["duration_s"] >= 690


@pytest.mark.asyncio
async def test_cross_tenant_records_isolation(records_client: AsyncClient) -> None:
    """Verify Org B cannot fetch Org A's transcripts, metrics, or recording URLs."""
    token_a = create_access_token(
        data={"sub": "usr-a", "organization_id": "org-alpha", "role": "owner"}
    )
    token_b = create_access_token(
        data={"sub": "usr-b", "organization_id": "org-beta", "role": "owner"}
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}

    # Org A creates agent and session
    agent_res = await records_client.post(
        "/agents", headers=headers_a, json={"name": "A", "system_prompt": "A"}
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    sess_res = await records_client.post(
        "/sessions/web", headers=headers_a, json={"agent_id": agent_id}
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # Finalize with transcripts and metrics
    fin_res = await records_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={
            "duration_s": 20,
            "transcript_segments": [{"seq": 1, "speaker": "caller", "text": "Secret info"}],
            "metrics": {"avg_latency_ms": 200},
        },
    )
    assert fin_res.status_code == 200

    # Attach recording key
    egress_res = await records_client.post(
        "/internal/egress/finalize",
        headers=internal_headers,
        json={"session_id": session_id, "recording_key": f"recordings/{session_id}.mp4"},
    )
    assert egress_res.status_code == 200

    # Org B attempts to read transcript -> 404
    res_b_trans = await records_client.get(f"/sessions/{session_id}/transcript", headers=headers_b)
    assert res_b_trans.status_code == 404

    # Org B attempts to read metrics -> 404
    res_b_metrics = await records_client.get(f"/sessions/{session_id}/metrics", headers=headers_b)
    assert res_b_metrics.status_code == 404

    # Org B attempts to get recording URL -> 404
    res_b_rec = await records_client.get(f"/sessions/{session_id}/recording-url", headers=headers_b)
    assert res_b_rec.status_code == 404

    # Org B attempts to get session detail -> 404
    res_b_sess = await records_client.get(f"/sessions/{session_id}", headers=headers_b)
    assert res_b_sess.status_code == 404
