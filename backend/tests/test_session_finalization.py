"""Tests for session finalization and call duration recording."""

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
async def finalization_client() -> AsyncGenerator[AsyncClient, None]:
    """Test async client with wired in-memory services."""
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
async def test_session_finalization_lifecycle(finalization_client: AsyncClient) -> None:
    """Verify session transitions from initiated to completed on worker finalization."""
    org_id = "org-finalization-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Agent and dispatch session
    agent_res = await finalization_client.post(
        "/agents",
        headers=user_headers,
        json={"name": "Support Bot", "system_prompt": "Support"},
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    sess_res = await finalization_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # 2. Worker calls finalize on call end
    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    fin_res = await finalization_client.post(
        f"/internal/sessions/{session_id}/finalize",
        headers=internal_headers,
        json={"duration_s": 42},
    )
    assert fin_res.status_code == 200
    assert fin_res.json()["status"] == "ok"

    # 3. User checks call history
    get_res = await finalization_client.get(f"/sessions/{session_id}", headers=user_headers)
    assert get_res.status_code == 200
    sess_data = get_res.json()
    assert sess_data["status"] == "completed"
    assert sess_data["duration_s"] == 42
