"""Tests for Tool, AgentTool, and ToolCall SQLAlchemy ORM models."""

import uuid

from backend.app.modules.tools.models import AgentTool, Tool, ToolCall


def test_tool_model_instantiation() -> None:
    """Verify Tool model fields, organization ownership, and JSON schema configs."""
    org_id = uuid.uuid4()
    tool = Tool(
        organization_id=org_id,
        name="check_order_status",
        type="http",
        config={"url": "https://api.example.com/orders", "method": "POST"},
        json_schema={
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
        outcome_label="order_checked",
    )
    assert tool.organization_id == org_id
    assert tool.name == "check_order_status"
    assert tool.type == "http"
    assert tool.config["url"] == "https://api.example.com/orders"
    assert "order_id" in tool.json_schema["properties"]
    assert tool.outcome_label == "order_checked"
    assert isinstance(tool.id, uuid.UUID)


def test_agent_tool_association_model() -> None:
    """Verify AgentTool composite foreign key mapping."""
    version_id = uuid.uuid4()
    tool_id = uuid.uuid4()
    assoc = AgentTool(agent_version_id=version_id, tool_id=tool_id)
    assert assoc.agent_version_id == version_id
    assert assoc.tool_id == tool_id


def test_tool_call_audit_model() -> None:
    """Verify ToolCall audit logging fields and latency metrics."""
    session_id = uuid.uuid4()
    tool_id = uuid.uuid4()
    audit = ToolCall(
        session_id=session_id,
        tool_id=tool_id,
        tool_name="check_order_status",
        arguments={"order_id": "ORD-999"},
        result={"status": "shipped", "tracking": "TRK-123"},
        status="success",
        latency_ms=145,
    )
    assert audit.session_id == session_id
    assert audit.tool_id == tool_id
    assert audit.tool_name == "check_order_status"
    assert audit.arguments["order_id"] == "ORD-999"
    assert audit.result is not None
    assert audit.result["status"] == "shipped"
    assert audit.status == "success"
    assert audit.latency_ms == 145
    assert isinstance(audit.id, uuid.UUID)
