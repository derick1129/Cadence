"""Internal worker and webhook communication schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuntimeConfigResponse(BaseModel):
    """Configuration payload returned to the worker to initialize an agent session."""

    session_id: str
    agent_id: str
    agent_version_id: str
    system_prompt: str
    greeting: str | None = None
    stt_config: dict[str, Any] = Field(default_factory=dict)
    llm_config: dict[str, Any] = Field(default_factory=dict)
    tts_config: dict[str, Any] = Field(default_factory=dict)
    silence_timeout_s: int = 15
    max_duration_s: int = 600
    tools: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FinalizeSessionRequest(BaseModel):
    """Payload sent by the worker when a session disconnects or completes."""

    status: str = "completed"
    outcome: str | None = "completed"
    outcome_label: str | None = None
    duration_s: int = 0
    transcript_segments: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] | None = None
    interruption_count: int = 0


class SipIntakeRequest(BaseModel):
    """Payload sent by telephony gateway or LiveKit SIP upon receiving inbound call."""

    called_number: str
    caller_number: str | None = None
    sip_call_id: str | None = None
    room_name: str | None = None


class SipIntakeResponse(BaseModel):
    """Response returned to SIP bridge authorizing call and assigning LiveKit room."""

    session_id: str
    room_name: str
    status: str = "accepted"
    agent_id: str | None = None


class ToolInvokeRequest(BaseModel):
    """Payload from worker to invoke a backend-managed tool securely."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    """Execution output returned to worker to feed back into LLM context."""

    result: Any = None
    status: str = "success"


class EgressFinalizeRequest(BaseModel):
    """Webhook notification from LiveKit Egress when recording file upload finishes."""

    recording_key: str
    session_id: str | None = None
    room_name: str | None = None
    duration_s: int | None = None
    egress_id: str | None = None


class InternalGenericResponse(BaseModel):
    """Standard success acknowledgment for internal webhook and worker calls."""

    status: str = "ok"
