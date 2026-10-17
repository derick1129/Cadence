"""Tool repository handling persistence for tools and audit logs."""

import uuid
from datetime import UTC, datetime
from typing import Any


class ToolRepository:
    """Repository handling persistence for custom tools and execution audit logs."""

    def __init__(self, session: Any | None = None) -> None:
        self.session = session
        self._tools: dict[str, dict[str, Any]] = {}
        self._tool_calls: list[dict[str, Any]] = []

    async def list_tools(self, organization_id: str) -> list[dict[str, Any]]:
        """List all tools belonging to an organization."""
        return [
            tool for tool in self._tools.values() if tool.get("organization_id") == organization_id
        ]

    async def get_tool_by_id(self, organization_id: str, tool_id: str) -> dict[str, Any] | None:
        """Retrieve a tool by ID strictly scoped to an organization."""
        tool = self._tools.get(tool_id)
        if not tool or tool.get("organization_id") != organization_id:
            return None
        return tool

    async def get_tool_by_name(self, organization_id: str, name: str) -> dict[str, Any] | None:
        """Find a tool by name within an organization."""
        for tool in self._tools.values():
            if tool.get("organization_id") == organization_id and tool.get("name") == name:
                return tool
        return None

    async def create_tool(
        self,
        organization_id: str,
        name: str,
        tool_type: str,
        config: dict[str, Any],
        json_schema: dict[str, Any],
        outcome_label: str | None = None,
    ) -> dict[str, Any]:
        """Create a new tool record for the tenant."""
        now = datetime.now(UTC)
        tool_id = str(uuid.uuid4())
        tool = {
            "id": tool_id,
            "organization_id": organization_id,
            "name": name,
            "type": tool_type,
            "config": config,
            "json_schema": json_schema,
            "outcome_label": outcome_label,
            "created_at": now,
            "updated_at": now,
        }
        self._tools[tool_id] = tool
        return tool

    async def record_tool_call(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any,
        status: str,
        latency_ms: int,
        tool_id: str | None = None,
    ) -> dict[str, Any]:
        """Record an executed tool invocation in audit log."""
        now = datetime.now(UTC)
        record = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "tool_id": tool_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "status": status,
            "latency_ms": latency_ms,
            "created_at": now,
        }
        self._tool_calls.append(record)
        return record
