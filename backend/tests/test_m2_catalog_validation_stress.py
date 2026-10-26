"""Empirical stress test suite for Milestone M2: Provider Catalog Validation & Boundaries.

Specification tests for Challenger 2:
1. Verify invalid STT models return 400 with INVALID_PROVIDER_CONFIG.
2. Verify invalid STT providers return 400 with INVALID_PROVIDER_CONFIG.
3. Verify invalid LLM models return 400 with INVALID_PROVIDER_CONFIG.
4. Verify invalid LLM providers return 400 with INVALID_PROVIDER_CONFIG.
5. Verify invalid TTS models return 400 with INVALID_PROVIDER_CONFIG.
6. Verify invalid TTS providers return 400 with INVALID_PROVIDER_CONFIG.
7. Verify invalid TTS voices return 400 with INVALID_PROVIDER_CONFIG.
8. Verify provider/model mismatches return 400 with INVALID_PROVIDER_CONFIG.
9. Verify default configs are properly applied when omitted.
10. Verify boundary parameters (silence_timeout_s, max_duration_s) reject non-positive values.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService
from backend.app.modules.providers.service import ProviderService


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Test async client with in-memory AgentService override."""
    shared_service = AgentService(repository=AgentRepository(), provider_service=ProviderService())
    app.dependency_overrides[get_agent_service] = lambda: shared_service
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_agent_service, None)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Admin token auth headers."""
    token = create_access_token(
        data={"sub": "usr-stress", "organization_id": "org-stress", "role": "owner"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_invalid_stt_model_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Invalid STT model must return 400 with INVALID_PROVIDER_CONFIG."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Bad STT Model Agent",
            "system_prompt": "Prompt",
            "stt_config": {"provider": "deepgram", "model": "invalid-whisper-99"},
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_invalid_stt_provider_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Invalid STT provider name must return 400 with INVALID_PROVIDER_CONFIG."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Bad STT Provider Agent",
            "system_prompt": "Prompt",
            "stt_config": {"provider": "bogus_stt_vendor", "model": "nova-2"},
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_invalid_llm_model_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Invalid LLM model must return 400 with INVALID_PROVIDER_CONFIG."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Bad LLM Model Agent",
            "system_prompt": "Prompt",
            "llm_config": {"provider": "openai", "model": "gpt-99-turbo"},
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_invalid_llm_provider_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Invalid LLM provider name must return 400 with INVALID_PROVIDER_CONFIG."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Bad LLM Provider Agent",
            "system_prompt": "Prompt",
            "llm_config": {"provider": "bogus_llm_vendor", "model": "gpt-4o"},
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_invalid_tts_model_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Invalid TTS model must return 400 with INVALID_PROVIDER_CONFIG."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Bad TTS Model Agent",
            "system_prompt": "Prompt",
            "tts_config": {"provider": "cartesia", "model": "invalid-tts-model"},
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_invalid_tts_provider_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Invalid TTS provider name must return 400 with INVALID_PROVIDER_CONFIG."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Bad TTS Provider Agent",
            "system_prompt": "Prompt",
            "tts_config": {"provider": "bogus_tts_vendor", "model": "sonic-english"},
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_invalid_tts_voice_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Invalid TTS voice for provider must return 400 with INVALID_PROVIDER_CONFIG."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Bad TTS Voice Agent",
            "system_prompt": "Prompt",
            "tts_config": {
                "provider": "cartesia",
                "model": "sonic-english",
                "voice": "non_existent_voice_999",
            },
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_provider_model_mismatch_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Provider-model mismatch (e.g. Anthropic with OpenAI gpt-4o) must return 400."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Mismatched Provider Agent",
            "system_prompt": "Prompt",
            "llm_config": {"provider": "anthropic", "model": "gpt-4o"},
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_defaults_applied_when_omitted(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Defaults must be applied for STT, LLM, TTS and timeout parameters."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Defaults Agent",
            "system_prompt": "Standard prompt",
        },
    )
    assert res.status_code == 201
    agent = res.json()
    ver = agent["current_version"]
    assert ver["stt_config"] == {"provider": "deepgram", "model": "nova-2"}
    assert ver["llm_config"] == {"provider": "openai", "model": "gpt-4o-mini"}
    assert ver["tts_config"] == {
        "provider": "cartesia",
        "model": "sonic-english",
        "voice": "default-voice",
    }
    assert ver["silence_timeout_s"] == 15
    assert ver["max_duration_s"] == 600


@pytest.mark.asyncio
async def test_negative_boundary_parameters_rejected(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Negative silence_timeout_s or max_duration_s must be rejected with 400 or 422."""
    res = await client.post(
        "/agents",
        headers=auth_headers,
        json={
            "name": "Negative Bounds Agent",
            "system_prompt": "Prompt",
            "silence_timeout_s": -5,
            "max_duration_s": -100,
        },
    )
    assert res.status_code in (400, 422)
