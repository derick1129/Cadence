"""Tests for Agent and AgentVersion SQLAlchemy ORM models."""

import uuid

from backend.app.modules.agents.models import Agent, AgentVersion


def test_agent_model_instantiation() -> None:
    """Verify Agent model fields, primary key, and organization foreign key."""
    org_id = uuid.uuid4()
    agent = Agent(name="Customer Support", organization_id=org_id)
    assert agent.name == "Customer Support"
    assert agent.organization_id == org_id
    assert agent.current_version_id is None
    assert isinstance(agent.id, uuid.UUID)


def test_agent_version_model_instantiation() -> None:
    """Verify AgentVersion model fields, immutability defaults, and configurations."""
    agent_id = uuid.uuid4()
    version = AgentVersion(
        agent_id=agent_id,
        version_no=1,
        system_prompt="You are a helpful phone receptionist.",
        greeting="Hello, thanks for calling!",
        stt_config={"provider": "deepgram", "model": "nova-2"},
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        tts_config={"provider": "cartesia", "voice_id": "sonic-english"},
        silence_timeout_s=15,
        max_duration_s=600,
    )
    assert version.agent_id == agent_id
    assert version.version_no == 1
    assert version.system_prompt == "You are a helpful phone receptionist."
    assert version.greeting == "Hello, thanks for calling!"
    assert version.stt_config["provider"] == "deepgram"
    assert version.llm_config["model"] == "gpt-4o-mini"
    assert version.tts_config["voice_id"] == "sonic-english"
    assert version.silence_timeout_s == 15
    assert version.max_duration_s == 600
    assert isinstance(version.id, uuid.UUID)
