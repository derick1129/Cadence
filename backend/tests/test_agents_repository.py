"""Tests for AgentRepository database persistence and tenant isolation."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.agents.models import Agent, AgentVersion
from backend.app.modules.agents.repository import AgentRepository


@pytest.mark.asyncio
async def test_agent_repository_crud() -> None:
    """Verify repository creates, retrieves, and updates agents with tenant filtering."""
    repo = AgentRepository()
    org_a = str(uuid.uuid4())
    org_b = str(uuid.uuid4())

    # Create agent in Org A
    agent_a = await repo.create_agent(organization_id=org_a, name="Sales Agent")
    assert agent_a["id"] is not None
    assert agent_a["name"] == "Sales Agent"
    assert agent_a["organization_id"] == org_a

    # Fetch agent in Org A
    fetched_a = await repo.get_agent_by_id(organization_id=org_a, agent_id=agent_a["id"])
    assert fetched_a is not None
    assert fetched_a["id"] == agent_a["id"]

    # Cross-tenant read must return None
    fetched_cross = await repo.get_agent_by_id(organization_id=org_b, agent_id=agent_a["id"])
    assert fetched_cross is None

    # Update agent name
    updated_name = await repo.update_agent_name(
        organization_id=org_a, agent_id=agent_a["id"], name="Renamed Sales Agent"
    )
    assert updated_name is not None
    assert updated_name["name"] == "Renamed Sales Agent"

    # Cross-tenant update name must return None
    updated_cross = await repo.update_agent_name(
        organization_id=org_b, agent_id=agent_a["id"], name="Hacked Name"
    )
    assert updated_cross is None

    # Create version
    version_1 = await repo.create_version(
        agent_id=agent_a["id"],
        version_no=1,
        system_prompt="Prompt v1",
        greeting="Hi",
        stt_config={"provider": "deepgram"},
        llm_config={"provider": "openai"},
        tts_config={"provider": "cartesia"},
    )
    assert version_1["version_no"] == 1
    assert version_1["agent_id"] == agent_a["id"]

    # Set current version
    updated_agent = await repo.set_current_version(
        organization_id=org_a,
        agent_id=agent_a["id"],
        version_id=version_1["id"],
    )
    assert updated_agent is not None
    assert updated_agent["current_version_id"] == version_1["id"]

    # Cross-tenant set current version returns None
    updated_agent_cross = await repo.set_current_version(
        organization_id=org_b,
        agent_id=agent_a["id"],
        version_id=version_1["id"],
    )
    assert updated_agent_cross is None

    # Latest version number
    latest_no = await repo.get_latest_version_no(agent_id=agent_a["id"])
    assert latest_no == 1

    # List versions
    versions = await repo.list_versions_by_agent_id(agent_id=agent_a["id"])
    assert len(versions) == 1
    assert versions[0]["id"] == version_1["id"]

    # Get version by id
    v_fetched = await repo.get_version_by_id(version_id=version_1["id"])
    assert v_fetched is not None
    assert v_fetched["id"] == version_1["id"]


@pytest.mark.asyncio
async def test_agent_repository_db_session_mode() -> None:
    """Verify repository methods interact with AsyncSession properly."""
    mock_session = AsyncMock(spec=AsyncSession)
    repo = AgentRepository(session=mock_session)

    org_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())

    # Create agent
    agent_dict = await repo.create_agent(organization_id=org_id, name="DB Agent")
    assert agent_dict["name"] == "DB Agent"
    assert mock_session.add.called
    assert mock_session.flush.called

    # Get agent by id (mock return)
    fake_agent = Agent(name="DB Agent", organization_id=uuid.UUID(org_id))
    fake_agent.id = uuid.UUID(agent_id)
    fake_agent.current_version_id = None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_agent
    mock_session.execute.return_value = mock_result

    fetched = await repo.get_agent_by_id(organization_id=org_id, agent_id=agent_id)
    assert fetched is not None
    assert fetched["id"] == agent_id
    assert fetched["organization_id"] == org_id

    # Invalid UUIDs return None / empty list gracefully
    assert await repo.get_agent_by_id("invalid-uuid", agent_id) is None
    assert await repo.list_agents("invalid-uuid") == []
    assert await repo.get_version_by_id("invalid-uuid") is None
    assert await repo.list_versions_by_agent_id("invalid-uuid") == []
    assert await repo.get_latest_version_no("invalid-uuid") == 0

    # Create version
    version_dict = await repo.create_version(
        agent_id=agent_id,
        version_no=1,
        system_prompt="DB Prompt",
        greeting="Hello",
        stt_config={"model": "nova-2"},
        llm_config={"model": "gpt-4o-mini"},
        tts_config={"model": "sonic-english"},
    )
    assert version_dict["version_no"] == 1
    assert version_dict["agent_id"] == agent_id

    # Get version by id
    fake_version = AgentVersion(
        agent_id=uuid.UUID(agent_id),
        version_no=1,
        system_prompt="DB Prompt",
        greeting="Hello",
        stt_config={"model": "nova-2"},
        llm_config={"model": "gpt-4o-mini"},
        tts_config={"model": "sonic-english"},
    )
    fake_version.id = uuid.UUID(version_id)
    mock_ver_result = MagicMock()
    mock_ver_result.scalar_one_or_none.return_value = fake_version
    mock_session.execute.return_value = mock_ver_result

    fetched_ver = await repo.get_version_by_id(version_id=version_id)
    assert fetched_ver is not None
    assert fetched_ver["id"] == version_id
