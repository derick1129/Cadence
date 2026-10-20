"""Tests for AgentService configuration defaults, catalog validation, and versioning."""

import pytest

from backend.app.core.errors import AppError
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.schemas import AgentCreate, AgentUpdate
from backend.app.modules.agents.service import AgentService
from backend.app.modules.providers.service import ProviderService


@pytest.mark.asyncio
async def test_agent_defaults_and_validation() -> None:
    """Verify default provider settings are populated and invalid providers raise AppError."""
    service = AgentService(repository=AgentRepository(), provider_service=ProviderService())
    org_id = "org-test-service"

    # 1. Create with empty configs uses defaults
    agent = await service.create_agent(
        organization_id=org_id,
        data=AgentCreate(
            name="Default Agent",
            system_prompt="Standard support agent.",
        ),
    )
    assert agent.current_version is not None
    assert agent.current_version.stt_config["model"] == "nova-2"
    assert agent.current_version.llm_config["model"] == "gpt-4o-mini"
    assert agent.current_version.tts_config["model"] == "sonic-english"

    # 2. Invalid model raises AppError
    with pytest.raises(AppError) as exc_info:
        await service.create_agent(
            organization_id=org_id,
            data=AgentCreate(
                name="Invalid Agent",
                system_prompt="Support",
                stt_config={"provider": "unknown_stt", "model": "bad-model"},
            ),
        )
    assert exc_info.value.code == "INVALID_PROVIDER_CONFIG"


@pytest.mark.asyncio
async def test_agent_version_bumping_on_update() -> None:
    """Verify updating prompt bumps version and retains previous version."""
    service = AgentService(repository=AgentRepository(), provider_service=ProviderService())
    org_id = "org-test-service-2"

    agent = await service.create_agent(
        organization_id=org_id,
        data=AgentCreate(
            name="Version Agent",
            system_prompt="Prompt v1",
        ),
    )
    assert agent.current_version is not None
    assert agent.current_version.version_no == 1
    v1_id = agent.current_version.id

    # Update only name -> no version bump
    updated_name_agent = await service.update_agent(
        organization_id=org_id,
        agent_id=agent.id,
        data=AgentUpdate(name="Renamed Agent"),
    )
    assert updated_name_agent is not None
    assert updated_name_agent.name == "Renamed Agent"
    assert updated_name_agent.current_version is not None
    assert updated_name_agent.current_version.version_no == 1
    assert updated_name_agent.current_version.id == v1_id

    # Update system_prompt -> bumps to version 2
    updated_prompt_agent = await service.update_agent(
        organization_id=org_id,
        agent_id=agent.id,
        data=AgentUpdate(system_prompt="Prompt v2"),
    )
    assert updated_prompt_agent is not None
    assert updated_prompt_agent.current_version is not None
    assert updated_prompt_agent.current_version.version_no == 2
    assert updated_prompt_agent.current_version.system_prompt == "Prompt v2"
    assert updated_prompt_agent.current_version.id != v1_id

    # List versions shows both v1 and v2
    versions = await service.list_versions(organization_id=org_id, agent_id=agent.id)
    assert len(versions) == 2
    assert versions[0].version_no == 1
    assert versions[0].system_prompt == "Prompt v1"
    assert versions[1].version_no == 2
    assert versions[1].system_prompt == "Prompt v2"
