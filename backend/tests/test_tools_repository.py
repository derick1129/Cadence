"""Tests for ToolRepository database operations, version attachment, and audit logging."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.tools.models import Tool
from backend.app.modules.tools.repository import ToolRepository


@pytest.mark.asyncio
async def test_tools_repository_crud_mock_mode() -> None:
    """Verify tool CRUD, agent version binding, and session tool call audit logs in mock mode."""
    repo = ToolRepository()
    org_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    session_id = f"sess-{uuid.uuid4()}"

    # 1. Create Tool
    tool = await repo.create_tool(
        organization_id=org_id,
        name="lookup_inventory",
        tool_type="http",
        config={"url": "https://api.inventory.example/lookup"},
        json_schema={"type": "object", "properties": {"sku": {"type": "string"}}},
        outcome_label="inventory_checked",
    )
    assert tool["id"] is not None
    assert tool["name"] == "lookup_inventory"
    assert tool["organization_id"] == org_id

    # 2. Retrieve Tool by ID and Name
    by_id = await repo.get_tool_by_id(org_id, tool["id"])
    assert by_id is not None
    assert by_id["id"] == tool["id"]

    by_name = await repo.get_tool_by_name(org_id, "lookup_inventory")
    assert by_name is not None
    assert by_name["id"] == tool["id"]

    # 3. Cross-Tenant Isolation
    other_org = str(uuid.uuid4())
    assert await repo.get_tool_by_id(other_org, tool["id"]) is None
    assert await repo.get_tool_by_name(other_org, "lookup_inventory") is None
    assert len(await repo.list_tools(other_org)) == 0

    # 4. Attach Tool to Agent Version
    await repo.attach_tools_to_version(version_id=version_id, tool_ids=[tool["id"]])
    attached = await repo.get_tools_for_version(version_id)
    assert len(attached) == 1
    assert attached[0]["name"] == "lookup_inventory"

    # 5. Record Tool Call Audit Log (supporting sess- prefix)
    audit_rec = await repo.record_tool_call(
        session_id=session_id,
        tool_id=tool["id"],
        tool_name="lookup_inventory",
        arguments={"sku": "SKU-ABC"},
        result={"in_stock": True, "count": 12},
        status="success",
        latency_ms=120,
    )
    assert audit_rec["status"] == "success"
    assert audit_rec["latency_ms"] == 120

    # 6. List Session Tool Calls
    calls = await repo.list_tool_calls_for_session(session_id)
    assert len(calls) == 1
    assert calls[0]["arguments"]["sku"] == "SKU-ABC"

    # 7. Delete Tool
    assert await repo.delete_tool(org_id, tool["id"]) is True
    assert await repo.get_tool_by_id(org_id, tool["id"]) is None


@pytest.mark.asyncio
async def test_tools_repository_db_session_mode() -> None:
    """Verify repository methods interact with AsyncSession properly."""
    mock_session = AsyncMock(spec=AsyncSession)
    repo = ToolRepository(session=mock_session)

    org_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    session_id = f"sess-{uuid.uuid4()}"

    # 1. Create Tool
    tool_dict = await repo.create_tool(
        organization_id=org_id,
        name="db_webhook",
        tool_type="http",
        config={"url": "https://api.db.example"},
        json_schema={},
    )
    assert tool_dict["name"] == "db_webhook"
    assert mock_session.add.called
    assert mock_session.flush.called

    # 2. Get Tool By ID
    fake_tool = Tool(
        organization_id=uuid.UUID(org_id),
        name="db_webhook",
        type="http",
        config={"url": "https://api.db.example"},
        json_schema={},
    )
    fake_tool.id = uuid.UUID(tool_id)
    fake_tool.created_at = datetime.now(UTC)
    fake_tool.updated_at = datetime.now(UTC)

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = fake_tool
    mock_session.execute.return_value = mock_res

    fetched = await repo.get_tool_by_id(org_id, tool_id)
    assert fetched is not None
    assert fetched["id"] == tool_id

    # 3. Attach Tools to Version
    mock_session.reset_mock()
    await repo.attach_tools_to_version(version_id=version_id, tool_ids=[tool_id])
    assert mock_session.add.called
    assert mock_session.flush.called

    # 4. Record Tool Call (Verifying safe parsing of sess- prefix)
    mock_session.reset_mock()
    call_rec = await repo.record_tool_call(
        session_id=session_id,
        tool_id=tool_id,
        tool_name="db_webhook",
        arguments={"test": 1},
        result={"ok": True},
        status="success",
        latency_ms=90,
    )
    assert call_rec["status"] == "success"
    assert mock_session.add.called
    assert mock_session.flush.called

    # 5. Invalid UUIDs gracefully handled
    assert await repo.get_tool_by_id("invalid-uuid", tool_id) is None
    assert await repo.list_tools("invalid-uuid") == []
    assert await repo.get_tools_for_version("invalid-uuid") == []
    assert await repo.list_tool_calls_for_session("invalid-uuid") == []
