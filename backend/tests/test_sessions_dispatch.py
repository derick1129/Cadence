from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.livekit import generate_livekit_token
from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService
from backend.app.modules.providers.service import ProviderService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.router import get_session_service
from backend.app.modules.sessions.service import SessionService


def test_generate_livekit_token() -> None:
    """Verify LiveKit access token generation creates a valid signed JWT string."""
    token = generate_livekit_token(
        room_name="cadence-room-test",
        participant_identity="user-browser-123",
        session_id="sess-test-456",
    )
    assert isinstance(token, str)
    assert len(token.split(".")) == 3


@pytest.fixture
async def session_test_client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client with shared in-memory repositories."""
    agent_repo = AgentRepository()
    agent_svc = AgentService(repository=agent_repo, provider_service=ProviderService())
    sess_repo = SessionRepository()
    sess_svc = SessionService(repository=sess_repo, agent_service=agent_svc)

    app.dependency_overrides[get_agent_service] = lambda: agent_svc
    app.dependency_overrides[get_session_service] = lambda: sess_svc

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.pop(get_agent_service, None)
    app.dependency_overrides.pop(get_session_service, None)


@pytest.mark.asyncio
async def test_start_web_session_api(session_test_client: AsyncClient) -> None:
    """Verify POST /sessions/web creates a session and returns LiveKit WebRTC credentials."""
    org_id = "org-session-dispatch-test"
    token = create_access_token(data={"sub": "usr-1", "organization_id": org_id, "role": "owner"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create an agent
    agent_res = await session_test_client.post(
        "/agents",
        headers=headers,
        json={
            "name": "Live Receptionist",
            "system_prompt": "You are a test receptionist.",
        },
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    # 2. Dispatch web session
    dispatch_res = await session_test_client.post(
        "/sessions/web",
        headers=headers,
        json={"agent_id": agent_id},
    )
    assert dispatch_res.status_code == 201
    payload = dispatch_res.json()
    assert payload["session_id"] != ""
    assert payload["room_name"].startswith("cadence-room-")
    assert payload["livekit_token"] != ""
    assert payload["livekit_url"] != ""
    assert payload["agent_id"] == agent_id

    # 3. Retrieve session details
    session_id = payload["session_id"]
    get_res = await session_test_client.get(f"/sessions/{session_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == session_id
    assert get_res.json()["organization_id"] == org_id


@pytest.mark.asyncio
async def test_web_session_tenant_isolation(session_test_client: AsyncClient) -> None:
    """Verify Org B cannot access Org A's session."""
    token_a = create_access_token(
        data={"sub": "usr-a", "organization_id": "org-alpha", "role": "owner"}
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    token_b = create_access_token(
        data={"sub": "usr-b", "organization_id": "org-beta", "role": "owner"}
    )
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Org A creates agent and session
    agent_res = await session_test_client.post(
        "/agents",
        headers=headers_a,
        json={"name": "Alpha Agent", "system_prompt": "Alpha prompt"},
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    sess_res = await session_test_client.post(
        "/sessions/web",
        headers=headers_a,
        json={"agent_id": agent_id},
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["session_id"]

    # Org B attempts to access Org A's session -> 404
    cross_res = await session_test_client.get(f"/sessions/{session_id}", headers=headers_b)
    assert cross_res.status_code == 404
