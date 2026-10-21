"""Tests for Agent-Tool binding, version immutability, and runtime-config injection."""

import uuid

import pytest

from backend.app.core.errors import AppError
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.schemas import AgentCreate, AgentUpdate
from backend.app.modules.agents.service import AgentService
from backend.app.modules.internal.service import InternalGatewayService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.tools.repository import ToolRepository


@pytest.mark.asyncio
async def test_agent_create_with_tools_and_runtime_config_injection() -> None:
    """Verify tool binding during agent creation and injection into runtime config."""
    tool_repo = ToolRepository()
    agent_repo = AgentRepository()
    session_repo = SessionRepository()
    agent_service = AgentService(repository=agent_repo, tool_repository=tool_repo)
    internal_service = InternalGatewayService(
        session_repository=session_repo,
        agent_service=agent_service,
        tool_repository=tool_repo,
    )

    org_id = str(uuid.uuid4())

    # 1. Register tools
    tool_1 = await tool_repo.create_tool(
        organization_id=org_id,
        name="check_balance",
        tool_type="http",
        config={"url": "https://api.bank.example/balance"},
        json_schema={
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    )
    tool_2 = await tool_repo.create_tool(
        organization_id=org_id,
        name="transfer_call",
        tool_type="transfer",
        config={"phone_number": "+15551234567"},
        json_schema={"type": "object", "properties": {}},
    )

    # 2. Create agent with tool_ids
    agent = await agent_service.create_agent(
        organization_id=org_id,
        data=AgentCreate(
            name="Banking Assistant",
            system_prompt="You are a banking assistant.",
            tool_ids=[tool_1["id"], tool_2["id"]],
        ),
    )
    assert agent.current_version is not None
    assert agent.current_version.version_no == 1
    v1_id = agent.current_version.id

    # Verify tools bound to version in repository
    v1_tools = await tool_repo.get_tools_for_version(v1_id)
    assert len(v1_tools) == 2
    tool_names = {t["name"] for t in v1_tools}
    assert tool_names == {"check_balance", "transfer_call"}

    # 3. Create session pinned to agent and test runtime config
    room = f"room-{uuid.uuid4()}"
    session = await session_repo.create_session(
        organization_id=org_id,
        agent_id=agent.id,
        agent_version_id=v1_id,
        room_name=room,
        channel="web",
    )
    sess_id = session["id"]

    runtime_config = await internal_service.get_runtime_config(session_id=sess_id)
    assert len(runtime_config.tools) == 2
    fn_map = {t["name"]: t for t in runtime_config.tools}
    assert "check_balance" in fn_map
    assert fn_map["check_balance"]["type"] == "function"
    assert "account_id" in fn_map["check_balance"]["parameters"]["properties"]
    assert "transfer_call" in fn_map


@pytest.mark.asyncio
async def test_agent_update_tools_triggers_version_bump_immutability() -> None:
    """Verify updating tool_ids triggers version bump while preserving prior version tools."""
    tool_repo = ToolRepository()
    agent_repo = AgentRepository()
    agent_service = AgentService(repository=agent_repo, tool_repository=tool_repo)

    org_id = str(uuid.uuid4())

    t1 = await tool_repo.create_tool(
        organization_id=org_id,
        name="tool_a",
        tool_type="http",
        config={"url": "https://a.example"},
        json_schema={},
    )
    t2 = await tool_repo.create_tool(
        organization_id=org_id,
        name="tool_b",
        tool_type="http",
        config={"url": "https://b.example"},
        json_schema={},
    )

    # Initial Agent with tool_a
    agent = await agent_service.create_agent(
        organization_id=org_id,
        data=AgentCreate(
            name="Version Test Agent",
            system_prompt="Initial prompt",
            tool_ids=[t1["id"]],
        ),
    )
    assert agent.current_version is not None
    v1_id = agent.current_version.id
    assert agent.current_version.version_no == 1

    # Update with tool_b only -> Should bump to version 2
    updated = await agent_service.update_agent(
        organization_id=org_id,
        agent_id=agent.id,
        data=AgentUpdate(tool_ids=[t2["id"]]),
    )
    assert updated is not None
    assert updated.current_version is not None
    assert updated.current_version.version_no == 2
    v2_id = updated.current_version.id

    # Verify v1 tools still intact (immutability)
    v1_tools = await tool_repo.get_tools_for_version(v1_id)
    assert len(v1_tools) == 1
    assert v1_tools[0]["name"] == "tool_a"

    # Verify v2 has new tools
    v2_tools = await tool_repo.get_tools_for_version(v2_id)
    assert len(v2_tools) == 1
    assert v2_tools[0]["name"] == "tool_b"

    # Update prompt only -> Should bump to version 3 and INHERIT tool_b
    updated_v3 = await agent_service.update_agent(
        organization_id=org_id,
        agent_id=agent.id,
        data=AgentUpdate(system_prompt="Updated prompt"),
    )
    assert updated_v3 is not None
    assert updated_v3.current_version is not None
    assert updated_v3.current_version.version_no == 3
    v3_id = updated_v3.current_version.id

    v3_tools = await tool_repo.get_tools_for_version(v3_id)
    assert len(v3_tools) == 1
    assert v3_tools[0]["name"] == "tool_b"


@pytest.mark.asyncio
async def test_agent_tool_binding_cross_tenant_rejection() -> None:
    """Verify an agent cannot be bound to tools owned by another tenant."""
    tool_repo = ToolRepository()
    agent_repo = AgentRepository()
    agent_service = AgentService(repository=agent_repo, tool_repository=tool_repo)

    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    tool_b = await tool_repo.create_tool(
        organization_id=tenant_b,
        name="secret_tool",
        tool_type="http",
        config={"url": "https://b.example/secret"},
        json_schema={},
    )

    # Tenant A attempts to bind Tenant B's tool
    with pytest.raises(AppError) as exc_info:
        await agent_service.create_agent(
            organization_id=tenant_a,
            data=AgentCreate(
                name="Attacker Agent",
                system_prompt="Attack",
                tool_ids=[tool_b["id"]],
            ),
        )
    assert exc_info.value.status_code in (400, 403, 404)
