"""Tests for internal worker runtime configuration endpoint."""

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
async def runtime_config_client() -> AsyncGenerator[AsyncClient, None]:
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
async def test_get_internal_runtime_config_success(runtime_config_client: AsyncClient) -> None:
    """Verify runtime configuration correctly reflects pinned session agent version."""
    org_id = "org-rtc-test"
    token = create_access_token(data={"sub": "usr-rtc", "organization_id": org_id, "role": "owner"})
    user_headers = {"Authorization": f"Bearer {token}"}

    agent_res = await runtime_config_client.post(
        "/agents",
        headers=user_headers,
        json={
            "name": "Support Agent",
            "system_prompt": "Support system prompt.",
            "greeting": "Welcome to support.",
            "silence_timeout_s": 12,
        },
    )
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    session_res = await runtime_config_client.post(
        "/sessions/web",
        headers=user_headers,
        json={"agent_id": agent_id},
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["session_id"]

    internal_headers = {"X-Internal-Service-Token": settings.INTERNAL_SERVICE_TOKEN}
    runtime_res = await runtime_config_client.get(
        f"/internal/sessions/{session_id}/runtime-config",
        headers=internal_headers,
    )
    assert runtime_res.status_code == 200
    cfg = runtime_res.json()
    assert cfg["session_id"] == session_id
    assert cfg["agent_id"] == agent_id
    assert cfg["system_prompt"] == "Support system prompt."
    assert cfg["greeting"] == "Welcome to support."
    assert cfg["silence_timeout_s"] == 12


@pytest.mark.asyncio
async def test_get_internal_runtime_config_unauthorized(
    runtime_config_client: AsyncClient,
) -> None:
    """Verify missing or invalid internal service token returns 401."""
    # Invalid token
    res_bad = await runtime_config_client.get(
        "/internal/sessions/sess-123/runtime-config",
        headers={"X-Internal-Service-Token": "wrong-token"},
    )
    assert res_bad.status_code == 401

    # Missing token header
    res_none = await runtime_config_client.get(
        "/internal/sessions/sess-123/runtime-config",
    )
    assert res_none.status_code == 401
