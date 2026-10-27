"""Tool module schemas for tool definitions and runtime execution."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolCreate(BaseModel):
    """Payload to create a new webhook or transfer tool."""

    name: str
    type: str  # "http" or "transfer"
    config: dict[str, Any] = Field(default_factory=dict)
    json_schema: dict[str, Any] = Field(default_factory=dict)
    outcome_label: str | None = None


class ToolUpdate(BaseModel):
    """Payload to update an existing webhook or transfer tool."""

    name: str | None = None
    type: str | None = None
    config: dict[str, Any] | None = None
    json_schema: dict[str, Any] | None = None
    outcome_label: str | None = None


class ToolResponse(BaseModel):
    """Tool definition response."""

    id: str
    organization_id: str
    name: str
    type: str
    config: dict[str, Any]
    json_schema: dict[str, Any]
    outcome_label: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolInvokeRequest(BaseModel):
    """Worker or internal request payload to execute a tool call."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    """Execution result of a tool call."""

    tool_name: str
    result: Any = None
    status: str = "success"  # "success", "failed", "timeout"
    latency_ms: int = 0
    error: str | None = None

    model_config = ConfigDict(from_attributes=True)
