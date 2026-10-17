"""Sessions service."""

import uuid

from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.schemas import (
    SessionListResponse,
    SessionResponse,
    WebSessionStartRequest,
    WebSessionStartResponse,
)


class SessionService:
    """Business logic for session creation, lifecycle management, and test-call dispatch."""

    def __init__(self, repository: SessionRepository | None = None) -> None:
        self.repository = repository or SessionRepository()

    async def start_web_session(
        self, organization_id: str, request: WebSessionStartRequest
    ) -> WebSessionStartResponse:
        """Create session and dispatch LiveKit room for browser test call."""
        room_name = f"cadence-room-{uuid.uuid4().hex[:8]}"
        pinned_version_id = "ver-mock-1"
        created = await self.repository.create_session(
            organization_id=organization_id,
            agent_id=request.agent_id,
            agent_version_id=pinned_version_id,
            channel="web",
            room_name=room_name,
        )
        return WebSessionStartResponse(
            session_id=created["id"],
            room_name=room_name,
            livekit_token="mock-livekit-jwt-token",
            livekit_url="http://localhost:7880",
            agent_id=request.agent_id,
        )

    async def list_sessions(
        self, organization_id: str, limit: int = 50, offset: int = 0
    ) -> SessionListResponse:
        """List sessions filtered by tenant organization."""
        items, total = await self.repository.list_by_org(
            organization_id=organization_id, limit=limit, offset=offset
        )
        return SessionListResponse(
            items=[SessionResponse.model_validate(item) for item in items],
            total=total,
        )

    async def get_session(self, organization_id: str, session_id: str) -> SessionResponse | None:
        """Fetch session details ensuring organization isolation."""
        session = await self.repository.get_by_id(organization_id, session_id)
        if not session:
            return None
        return SessionResponse.model_validate(session)
