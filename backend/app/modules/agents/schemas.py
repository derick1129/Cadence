"""Agent schemas for configuration and immutable versioning."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    """Payload to create a new agent with an initial version."""

    name: str = Field(..., min_length=1, max_length=255)
    system_prompt: str = Field(..., min_length=1)
    greeting: str | None = None
    stt_config: dict[str, Any] = Field(default_factory=dict)
    llm_config: dict[str, Any] = Field(default_factory=dict)
    tts_config: dict[str, Any] = Field(default_factory=dict)
    silence_timeout_s: int = Field(default=15, ge=1, le=120)
    max_duration_s: int = Field(default=600, ge=10, le=7200)


class AgentUpdate(BaseModel):
    """Payload to update an agent's metadata or create a new pinned version."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    system_prompt: str | None = Field(default=None, min_length=1)
    greeting: str | None = None
    stt_config: dict[str, Any] | None = None
    llm_config: dict[str, Any] | None = None
    tts_config: dict[str, Any] | None = None
    silence_timeout_s: int | None = Field(default=None, ge=1, le=120)
    max_duration_s: int | None = Field(default=None, ge=10, le=7200)


class AgentVersionResponse(BaseModel):
    """Immutable version configuration of an agent."""

    id: str
    agent_id: str
    version_no: int
    system_prompt: str
    greeting: str | None = None
    stt_config: dict[str, Any]
    llm_config: dict[str, Any]
    tts_config: dict[str, Any]
    silence_timeout_s: int
    max_duration_s: int
    created_by: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentResponse(BaseModel):
    """Agent entity response including its current pinned version."""

    id: str
    organization_id: str
    name: str
    current_version_id: str | None = None
    current_version: AgentVersionResponse | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
