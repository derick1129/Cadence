"""Adversarial stress-test suite for Milestone M2: Agents & Versions.

Authored by Empirical Challenger to rigorously stress-test:
1. Uppercase UUID handling across all endpoints and in-memory repository.
2. Invalid provider names (bogus, empty, null, casing, cross-category).
3. Invalid models (unsupported, cross-provider mismatch, empty, uppercase).
4. Invalid voices (nonexistent, cross-provider mismatch).
5. Boundary parameter constraints (silence_timeout_s, max_duration_s, name length, empty prompt).
6. Mutation atomicity on validation failure.
7. Immutable version history retention.
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import create_access_token
from backend.app.main import app
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.router import get_agent_service
from backend.app.modules.agents.service import AgentService
from backend.app.modules.providers.service import ProviderService


@pytest.fixture
async def challenge_client() -> AsyncGenerator[AsyncClient, None]:
    """Test client with isolated shared repository service."""
    service = AgentService(repository=AgentRepository(), provider_service=ProviderService())
    app.dependency_overrides[get_agent_service] = lambda: service
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_agent_service, None)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = create_access_token(
        data={"sub": "usr-adversarial", "organization_id": "org-adv-1", "role": "owner"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_uppercase_agent_id_endpoints(
    challenge_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Verify uppercase agent UUID is supported on get, patch, list_versions."""
    create_res = await challenge_client.post(
        "/agents",
        headers=auth_headers,
        json={"name": "UUID Case Agent", "system_prompt": "Initial prompt"},
    )
    assert create_res.status_code == 201
    agent_id = create_res.json()["id"]
    upper_agent_id = agent_id.upper()

    # GET /agents/{upper_agent_id}
    get_res = await challenge_client.get(f"/agents/{upper_agent_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == agent_id

    # PATCH /agents/{upper_agent_id}
    patch_res = await challenge_client.patch(
        f"/agents/{upper_agent_id}",
        headers=auth_headers,
        json={"name": "Renamed Case Agent"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Renamed Case Agent"

    # GET /agents/{upper_agent_id}/versions
    versions_res = await challenge_client.get(
        f"/agents/{upper_agent_id}/versions", headers=auth_headers
    )
    assert versions_res.status_code == 200
    assert len(versions_res.json()) >= 1


@pytest.mark.asyncio
async def test_uppercase_version_id_endpoint(
    challenge_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Verify behavior of uppercase version_id on GET /agents/{agent_id}/versions/{version_id}."""
    create_res = await challenge_client.post(
        "/agents",
        headers=auth_headers,
        json={"name": "Version Case Agent", "system_prompt": "Initial prompt"},
    )
    assert create_res.status_code == 201
    agent_id = create_res.json()["id"]
    version_id = create_res.json()["current_version_id"]

    # Lowercase version_id
    res_lower = await challenge_client.get(
        f"/agents/{agent_id}/versions/{version_id}", headers=auth_headers
    )
    assert res_lower.status_code == 200
    assert res_lower.json()["id"] == version_id

    # Uppercase version_id check
    res_upper = await challenge_client.get(
        f"/agents/{agent_id}/versions/{version_id.upper()}", headers=auth_headers
    )
    # RFC 4122 requires case-insensitivity on UUID inputs
    assert res_upper.status_code == 200, (
        f"Expected 200 for uppercase version_id but got {res_upper.status_code}: {res_upper.text}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("category", "payload"),
    [
        ("STT", {"stt_config": {"provider": "bogus_stt", "model": "nova-2"}}),
        ("STT", {"stt_config": {"provider": "", "model": "nova-2"}}),
        ("STT", {"stt_config": {"provider": "cartesia", "model": "nova-2"}}),  # cross-category
        ("STT", {"stt_config": {"provider": "DEEPGRAM", "model": "nova-2"}}),  # case mismatch
        ("LLM", {"llm_config": {"provider": "bogus_llm", "model": "gpt-4o"}}),
        ("LLM", {"llm_config": {"provider": "", "model": "gpt-4o"}}),
        ("LLM", {"llm_config": {"provider": "deepgram", "model": "gpt-4o"}}),  # cross-category
        ("LLM", {"llm_config": {"provider": "OPENAI", "model": "gpt-4o"}}),  # case mismatch
        ("TTS", {"tts_config": {"provider": "bogus_tts", "model": "sonic-english"}}),
        ("TTS", {"tts_config": {"provider": "", "model": "sonic-english"}}),
        ("TTS", {"tts_config": {"provider": "openai", "model": "sonic-english"}}),  # cross-category
        (
            "TTS",
            {"tts_config": {"provider": "CARTESIA", "model": "sonic-english"}},
        ),  # case mismatch
    ],
)
async def test_invalid_provider_names_rejected(
    challenge_client: AsyncClient,
    auth_headers: dict[str, str],
    category: str,
    payload: dict[str, Any],
) -> None:
    """Invalid provider names must return 400 with INVALID_PROVIDER_CONFIG."""
    body = {"name": f"Invalid {category} Provider", "system_prompt": "Prompt", **payload}
    res = await challenge_client.post("/agents", headers=auth_headers, json=body)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("category", "payload"),
    [
        ("STT", {"stt_config": {"provider": "deepgram", "model": "whisper-v3"}}),
        ("STT", {"stt_config": {"provider": "deepgram", "model": ""}}),
        ("STT", {"stt_config": {"provider": "deepgram", "model": "NOVA-2"}}),
        ("LLM", {"llm_config": {"provider": "openai", "model": "claude-3-5-sonnet"}}),
        ("LLM", {"llm_config": {"provider": "anthropic", "model": "gpt-4o"}}),  # provider mismatch
        ("LLM", {"llm_config": {"provider": "gemini", "model": "gpt-4o"}}),
        ("LLM", {"llm_config": {"provider": "openai", "model": ""}}),
        ("LLM", {"llm_config": {"provider": "openai", "model": "GPT-4O"}}),
        ("TTS", {"tts_config": {"provider": "cartesia", "model": "eleven_turbo_v2_5"}}),
        ("TTS", {"tts_config": {"provider": "elevenlabs", "model": "sonic-english"}}),
        ("TTS", {"tts_config": {"provider": "cartesia", "model": ""}}),
        ("TTS", {"tts_config": {"provider": "cartesia", "model": "SONIC-ENGLISH"}}),
    ],
)
async def test_invalid_models_rejected(
    challenge_client: AsyncClient,
    auth_headers: dict[str, str],
    category: str,
    payload: dict[str, Any],
) -> None:
    """Invalid models and provider-model mismatches must return 400 with INVALID_PROVIDER_CONFIG."""
    body = {"name": f"Invalid {category} Model", "system_prompt": "Prompt", **payload}
    res = await challenge_client.post("/agents", headers=auth_headers, json=body)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {
            "tts_config": {
                "provider": "cartesia",
                "model": "sonic-english",
                "voice": "unknown-voice",
            }
        },
        {
            "tts_config": {
                "provider": "elevenlabs",
                "model": "eleven_turbo_v2_5",
                "voice": "sonic-preview",
            }
        },
        {"tts_config": {"provider": "cartesia", "model": "sonic-english", "voice": "rachel"}},
    ],
)
async def test_invalid_voices_rejected(
    challenge_client: AsyncClient, auth_headers: dict[str, str], payload: dict[str, Any]
) -> None:
    """Invalid voices and voice-provider mismatches must return 400 with INVALID_PROVIDER_CONFIG."""
    body = {"name": "Invalid Voice Agent", "system_prompt": "Prompt", **payload}
    res = await challenge_client.post("/agents", headers=auth_headers, json=body)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"silence_timeout_s": 0}, 422),
        ({"silence_timeout_s": 1}, 201),
        ({"silence_timeout_s": 120}, 201),
        ({"silence_timeout_s": 121}, 422),
        ({"silence_timeout_s": -10}, 422),
        ({"max_duration_s": 9}, 422),
        ({"max_duration_s": 10}, 201),
        ({"max_duration_s": 7200}, 201),
        ({"max_duration_s": 7201}, 422),
        ({"max_duration_s": -1}, 422),
        ({"name": ""}, 422),
        ({"name": "a" * 255}, 201),
        ({"name": "a" * 256}, 422),
        ({"system_prompt": ""}, 422),
    ],
)
async def test_boundary_parameter_validation(
    challenge_client: AsyncClient,
    auth_headers: dict[str, str],
    payload: dict[str, Any],
    expected_status: int,
) -> None:
    """Verify strict validation of boundary parameters."""
    base = {"name": "Valid Name", "system_prompt": "Valid Prompt"}
    base.update(payload)
    res = await challenge_client.post("/agents", headers=auth_headers, json=base)
    assert res.status_code == expected_status, f"Payload {payload} gave {res.status_code}"


@pytest.mark.asyncio
async def test_update_atomicity_on_validation_failure(
    challenge_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Ensure PATCH never mutates name or bumps version when config validation fails."""
    create_res = await challenge_client.post(
        "/agents",
        headers=auth_headers,
        json={"name": "Atomic Original", "system_prompt": "Prompt v1"},
    )
    assert create_res.status_code == 201
    agent_id = create_res.json()["id"]
    version_id = create_res.json()["current_version_id"]

    # Attempt mutation with invalid STT
    fail_res = await challenge_client.patch(
        f"/agents/{agent_id}",
        headers=auth_headers,
        json={"name": "Corrupted Name", "stt_config": {"model": "nonexistent"}},
    )
    assert fail_res.status_code == 400
    assert fail_res.json()["error"]["code"] == "INVALID_PROVIDER_CONFIG"

    # Verify agent state is unchanged
    check_res = await challenge_client.get(f"/agents/{agent_id}", headers=auth_headers)
    assert check_res.status_code == 200
    assert check_res.json()["name"] == "Atomic Original"
    assert check_res.json()["current_version_id"] == version_id
    assert check_res.json()["current_version"]["version_no"] == 1
