"""Sessions module schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionResponse(BaseModel):
    """Session details including channel, status, and telemetry metadata."""

    id: str
    organization_id: str
    agent_id: str
    agent_version_id: str
    channel: str = "web"
    status: str = "initiated"
    outcome: str | None = None
    outcome_label: str | None = None
    room_name: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_s: int = 0
    recording_key: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(BaseModel):
    """Paginated list of sessions."""

    items: list[SessionResponse]
    total: int


class WebSessionStartRequest(BaseModel):
    """Request payload to initiate a web browser test session."""

    agent_id: str


class WebSessionStartResponse(BaseModel):
    """Response containing LiveKit room and connection token for web calls."""

    session_id: str
    room_name: str
    livekit_token: str
    livekit_url: str
    agent_id: str
