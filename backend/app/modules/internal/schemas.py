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


class TranscriptSegmentInput(BaseModel):
    """Dialogue turn input from worker finalization."""

    seq: int = Field(ge=0, description="Sequential turn index")
    speaker: str = Field(description="'caller' or 'agent'")
    text: str = Field(description="Transcribed turn text")
    started_at_ms: int = Field(default=0, description="Turn start offset in milliseconds")


class SessionMetricsInput(BaseModel):
    """Aggregate metrics reported by worker on call conclusion."""

    avg_latency_ms: int | None = Field(
        default=None, description="Average voice pipeline turn latency"
    )
    p95_latency_ms: int | None = Field(default=None, description="95th percentile turn latency")
    interruption_count: int = Field(default=0, description="Caller barge-in interruptions")
    llm_tokens_used: int = Field(default=0, description="Total tokens consumed across LLM turns")
    stt_seconds_billed: float = Field(default=0.0, description="Billed STT audio duration")
    tts_characters_billed: int = Field(default=0, description="Billed TTS character count")


class FinalizeSessionRequest(BaseModel):
    """Payload sent by the worker when a session disconnects or completes."""

    status: str = Field(default="completed", description="Final session status")
    outcome: str | None = Field(default="completed", description="High-level call outcome")
    outcome_label: str | None = Field(default=None, description="Granular outcome categorization")
    duration_s: int = Field(default=0, ge=0, description="Call duration in seconds")
    transcript_segments: list[TranscriptSegmentInput] = Field(default_factory=list)
    metrics: SessionMetricsInput | None = None
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
