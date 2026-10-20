"""Tool service implementing tool registration and invocation."""

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.tools.repository import ToolRepository
from backend.app.modules.tools.schemas import (
    ToolCreate,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolResponse,
    ToolUpdate,
)


class ToolService:
    """Service handling custom tool management, schema validation, and execution."""

    def __init__(
        self,
        repository: ToolRepository | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        if repository is not None:
            self.repository = repository
        elif session is not None:
            self.repository = ToolRepository(session=session)
        else:
            self.repository = ToolRepository()

    async def list_tools(self, organization_id: str) -> list[ToolResponse]:
        """List all tools registered for the organization."""
        tools = await self.repository.list_tools(organization_id)
        return [ToolResponse(**tool) for tool in tools]

    async def get_tool(self, organization_id: str, tool_id: str) -> ToolResponse | None:
        """Retrieve a specific tool by ID scoped to the organization."""
        tool = await self.repository.get_tool_by_id(organization_id, tool_id)
        if not tool:
            return None
        return ToolResponse(**tool)

    async def create_tool(self, organization_id: str, data: ToolCreate) -> ToolResponse:
        """Register a new tool for an organization."""
        tool = await self.repository.create_tool(
            organization_id=organization_id,
            name=data.name,
            tool_type=data.type,
            config=data.config,
            json_schema=data.json_schema,
            outcome_label=data.outcome_label,
        )
        return ToolResponse(**tool)

    async def delete_tool(self, organization_id: str, tool_id: str) -> bool:
        """Delete a tool by ID scoped to the organization."""
        return await self.repository.delete_tool(organization_id=organization_id, tool_id=tool_id)

    async def update_tool(
        self,
        organization_id: str,
        tool_id: str,
        data: ToolUpdate,
    ) -> ToolResponse | None:
        """Update an existing tool's definition partially."""
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            tool = await self.repository.get_tool_by_id(organization_id, tool_id)
            return ToolResponse(**tool) if tool else None

        updated = await self.repository.update_tool(
            organization_id=organization_id,
            tool_id=tool_id,
            updates=updates,
        )
        if not updated:
            return None
        return ToolResponse(**updated)

    async def invoke_tool(
        self,
        organization_id: str,
        request: ToolInvokeRequest,
        session_id: str | None = None,
    ) -> ToolInvokeResponse:
        """Invoke a tool by name with arguments and log the execution."""
        start_time = time.perf_counter()
        tool = await self.repository.get_tool_by_name(organization_id, request.tool_name)

        tool_id = tool["id"] if tool else None
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Simulation execution for skeleton foundation
        mock_result: dict[str, Any] = {
            "executed": True,
            "tool_name": request.tool_name,
            "arguments": request.arguments,
        }

        if session_id:
            await self.repository.record_tool_call(
                session_id=session_id,
                tool_id=tool_id,
                tool_name=request.tool_name,
                arguments=request.arguments,
                result=mock_result,
                status="success",
                latency_ms=elapsed_ms,
            )

        return ToolInvokeResponse(
            tool_name=request.tool_name,
            result=mock_result,
            status="success",
            latency_ms=elapsed_ms,
            error=None,
        )

    async def list_tool_calls_for_session(self, session_id: str) -> list[dict[str, Any]]:
        """List audit log records for tool executions during a session."""
        return await self.repository.list_tool_calls_for_session(session_id)
