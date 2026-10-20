"""Tool repository handling persistence for tools, version attachments, and audit logs."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.tools.models import AgentTool, Tool, ToolCall


def _parse_uuid(val: Any) -> uuid.UUID | None:
    """Safely parse a string or UUID to uuid.UUID, stripping prefixes if present."""
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        clean = str(val).strip()
        for prefix in ("tool-", "sess-", "org-", "ver-"):
            if clean.startswith(prefix):
                clean = clean.removeprefix(prefix)
                break
        return uuid.UUID(clean)
    except (ValueError, TypeError, AttributeError):
        return None


class ToolRepository:
    """Repository handling persistence for custom tools and execution audit logs."""

    _mock_tools: dict[str, dict[str, Any]] = {}
    _mock_agent_tools: list[dict[str, str]] = []
    _mock_tool_calls: list[dict[str, Any]] = []

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self._tools = self._mock_tools
        self._agent_tools = self._mock_agent_tools
        self._tool_calls = self._mock_tool_calls

    async def list_tools(self, organization_id: str) -> list[dict[str, Any]]:
        """List all tools belonging to an organization."""
        if self.session is not None:
            org_uuid = _parse_uuid(organization_id)
            if org_uuid is None:
                return []
            result = await self.session.execute(
                select(Tool).where(Tool.organization_id == org_uuid).order_by(desc(Tool.created_at))
            )
            records = result.scalars().all()
            return [
                {
                    "id": str(r.id),
                    "organization_id": str(r.organization_id),
                    "name": r.name,
                    "type": r.type,
                    "config": r.config,
                    "json_schema": r.json_schema,
                    "outcome_label": r.outcome_label,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in records
            ]

        clean_org = organization_id.removeprefix("org-")
        return [
            tool
            for tool in self._tools.values()
            if tool.get("organization_id") == organization_id
            or tool.get("organization_id", "").removeprefix("org-") == clean_org
        ]

    async def get_tool_by_id(self, organization_id: str, tool_id: str) -> dict[str, Any] | None:
        """Retrieve a tool by ID strictly scoped to an organization."""
        if self.session is not None:
            org_uuid = _parse_uuid(organization_id)
            tool_uuid = _parse_uuid(tool_id)
            if org_uuid is None or tool_uuid is None:
                return None
            result = await self.session.execute(
                select(Tool).where(Tool.id == tool_uuid, Tool.organization_id == org_uuid)
            )
            r = result.scalar_one_or_none()
            if not r:
                return None
            return {
                "id": str(r.id),
                "organization_id": str(r.organization_id),
                "name": r.name,
                "type": r.type,
                "config": r.config,
                "json_schema": r.json_schema,
                "outcome_label": r.outcome_label,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }

        tool = self._tools.get(tool_id)
        if not tool:
            clean_tool = tool_id.removeprefix("tool-")
            for t in self._tools.values():
                if t.get("id") == tool_id or t.get("id", "").removeprefix("tool-") == clean_tool:
                    tool = t
                    break
        if not tool:
            return None
        tool_org = tool.get("organization_id", "")
        if tool_org != organization_id and tool_org.removeprefix(
            "org-"
        ) != organization_id.removeprefix("org-"):
            return None
        return tool

    async def get_tool_by_name(self, organization_id: str, name: str) -> dict[str, Any] | None:
        """Find a tool by name within an organization."""
        if self.session is not None:
            org_uuid = _parse_uuid(organization_id)
            if org_uuid is None:
                return None
            result = await self.session.execute(
                select(Tool).where(Tool.name == name, Tool.organization_id == org_uuid)
            )
            r = result.scalar_one_or_none()
            if not r:
                return None
            return {
                "id": str(r.id),
                "organization_id": str(r.organization_id),
                "name": r.name,
                "type": r.type,
                "config": r.config,
                "json_schema": r.json_schema,
                "outcome_label": r.outcome_label,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }

        clean_org = organization_id.removeprefix("org-")
        for tool in self._tools.values():
            t_org = tool.get("organization_id", "")
            if (t_org == organization_id or t_org.removeprefix("org-") == clean_org) and tool.get(
                "name"
            ) == name:
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
        if self.session is not None:
            org_uuid = _parse_uuid(organization_id)
            if org_uuid is None:
                org_uuid = uuid.uuid4()
            tool = Tool(
                organization_id=org_uuid,
                name=name,
                type=tool_type,
                config=config,
                json_schema=json_schema,
                outcome_label=outcome_label,
            )
            self.session.add(tool)
            await self.session.flush()
            return {
                "id": str(tool.id),
                "organization_id": str(tool.organization_id),
                "name": tool.name,
                "type": tool.type,
                "config": tool.config,
                "json_schema": tool.json_schema,
                "outcome_label": tool.outcome_label,
                "created_at": tool.created_at,
                "updated_at": tool.updated_at,
            }

        tool_id = str(uuid.uuid4())
        tool_dict = {
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
        self._tools[tool_id] = tool_dict
        return tool_dict

    async def delete_tool(self, organization_id: str, tool_id: str) -> bool:
        """Delete a tool by ID strictly scoped to organization."""
        if self.session is not None:
            org_uuid = _parse_uuid(organization_id)
            tool_uuid = _parse_uuid(tool_id)
            if org_uuid is None or tool_uuid is None:
                return False
            result = await self.session.execute(
                delete(Tool).where(Tool.id == tool_uuid, Tool.organization_id == org_uuid)
            )
            await self.session.flush()
            rowcount = getattr(result, "rowcount", 0)
            return bool(rowcount and rowcount > 0)

        target_key = None
        clean_org = organization_id.removeprefix("org-")
        clean_tool = tool_id.removeprefix("tool-")
        for k, t in self._tools.items():
            if k == tool_id or k.removeprefix("tool-") == clean_tool:
                t_org = t.get("organization_id", "")
                if t_org == organization_id or t_org.removeprefix("org-") == clean_org:
                    target_key = k
                    break
        if target_key:
            del self._tools[target_key]
            return True
        return False

    async def attach_tools_to_version(self, version_id: str, tool_ids: list[str]) -> None:
        """Bind tools to an immutable agent version."""
        if self.session is not None:
            ver_uuid = _parse_uuid(version_id)
            if ver_uuid is None:
                ver_uuid = uuid.uuid4()
            for tid in tool_ids:
                t_uuid = _parse_uuid(tid)
                if t_uuid is not None:
                    assoc = AgentTool(agent_version_id=ver_uuid, tool_id=t_uuid)
                    self.session.add(assoc)
            await self.session.flush()
            return

        for tid in tool_ids:
            record = {"agent_version_id": version_id, "tool_id": tid}
            if record not in self._agent_tools:
                self._agent_tools.append(record)

    async def get_tools_for_version(self, version_id: str) -> list[dict[str, Any]]:
        """Retrieve all tools bound to an agent version."""
        if self.session is not None:
            ver_uuid = _parse_uuid(version_id)
            if ver_uuid is None:
                return []
            result = await self.session.execute(
                select(Tool)
                .join(AgentTool, AgentTool.tool_id == Tool.id)
                .where(AgentTool.agent_version_id == ver_uuid)
            )
            records = result.scalars().all()
            return [
                {
                    "id": str(r.id),
                    "organization_id": str(r.organization_id),
                    "name": r.name,
                    "type": r.type,
                    "config": r.config,
                    "json_schema": r.json_schema,
                    "outcome_label": r.outcome_label,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in records
            ]

        clean_ver = version_id.removeprefix("ver-")
        matching_ids = {
            a["tool_id"]
            for a in self._agent_tools
            if a["agent_version_id"] == version_id
            or a["agent_version_id"].removeprefix("ver-") == clean_ver
        }
        clean_matching_ids = {mid.removeprefix("tool-") for mid in matching_ids}
        return [
            t
            for t in self._tools.values()
            if t["id"] in matching_ids or t["id"].removeprefix("tool-") in clean_matching_ids
        ]

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
        if self.session is not None:
            sess_uuid = _parse_uuid(session_id)
            if sess_uuid is None:
                sess_uuid = uuid.uuid4()
            tool_uuid = _parse_uuid(tool_id) if tool_id else None

            call_record = ToolCall(
                session_id=sess_uuid,
                tool_id=tool_uuid,
                tool_name=tool_name,
                arguments=arguments,
                result=result if isinstance(result, dict) else {"output": result},
                status=status,
                latency_ms=latency_ms,
            )
            self.session.add(call_record)
            await self.session.flush()
            return {
                "id": str(call_record.id),
                "session_id": str(call_record.session_id),
                "tool_id": str(call_record.tool_id) if call_record.tool_id else None,
                "tool_name": call_record.tool_name,
                "arguments": call_record.arguments,
                "result": call_record.result,
                "status": call_record.status,
                "latency_ms": call_record.latency_ms,
                "created_at": call_record.created_at,
                "updated_at": call_record.updated_at,
            }

        call_id = str(uuid.uuid4())
        record = {
            "id": call_id,
            "session_id": session_id,
            "tool_id": tool_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result if isinstance(result, dict) else {"output": result},
            "status": status,
            "latency_ms": latency_ms,
            "created_at": now,
            "updated_at": now,
        }
        self._tool_calls.append(record)
        return record

    async def list_tool_calls_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve audit log of tools executed during a session."""
        if self.session is not None:
            sess_uuid = _parse_uuid(session_id)
            if sess_uuid is None:
                return []
            result = await self.session.execute(
                select(ToolCall)
                .where(ToolCall.session_id == sess_uuid)
                .order_by(ToolCall.created_at.asc())
            )
            records = result.scalars().all()
            return [
                {
                    "id": str(r.id),
                    "session_id": str(r.session_id),
                    "tool_id": str(r.tool_id) if r.tool_id else None,
                    "tool_name": r.tool_name,
                    "arguments": r.arguments,
                    "result": r.result,
                    "status": r.status,
                    "latency_ms": r.latency_ms,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in records
            ]

        clean_sess = session_id.removeprefix("sess-")
        return [
            c
            for c in self._tool_calls
            if c["session_id"] == session_id or c["session_id"].removeprefix("sess-") == clean_sess
        ]
