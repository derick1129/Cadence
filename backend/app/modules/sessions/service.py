"""Sessions service."""

import uuid
from typing import Any

from backend.app.core.errors import AppError
from backend.app.core.livekit import generate_livekit_token
from backend.app.core.settings import settings
from backend.app.modules.agents import AgentService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.schemas import (
    SessionListResponse,
    SessionResponse,
    WebSessionStartRequest,
    WebSessionStartResponse,
)


class SessionService:
    """Business logic for session creation, lifecycle management, and test-call dispatch."""

    def __init__(
        self,
        repository: SessionRepository | None = None,
        agent_service: AgentService | None = None,
    ) -> None:
        self.repository = repository or SessionRepository()
        self.agent_service = agent_service or AgentService()

    async def start_web_session(
        self, organization_id: str, request: WebSessionStartRequest
    ) -> WebSessionStartResponse:
        """Create session, pin agent version, and dispatch LiveKit room for browser test call."""
        agent = await self.agent_service.get_agent(organization_id, request.agent_id)
        if not agent or not agent.current_version_id:
            raise AppError(
                code="AGENT_NOT_CONFIGURED",
                message="Agent does not exist or has no active version configured",
                status_code=404,
            )

        session_uuid = str(uuid.uuid4())
        room_name = f"cadence-room-{session_uuid[:8]}"
        created = await self.repository.create_session(
            organization_id=organization_id,
            agent_id=agent.id,
            agent_version_id=agent.current_version_id,
            channel="web",
            room_name=room_name,
        )

        livekit_token = generate_livekit_token(
            room_name=room_name,
            participant_identity=f"caller-{session_uuid[:6]}",
            session_id=created["id"],
        )

        return WebSessionStartResponse(
            session_id=created["id"],
            room_name=room_name,
            livekit_token=livekit_token,
            livekit_url=settings.LIVEKIT_URL,
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

    async def get_session_internal(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session by ID for internal worker gateway."""
        return await self.repository.get_by_id_internal(session_id)

    async def update_status_internal(
        self,
        session_id: str,
        status: str,
        outcome: str | None = None,
        duration_s: int | None = None,
    ) -> dict[str, Any] | None:
        """Update session status and duration for internal worker finalization."""
        return await self.repository.update_status(
            session_id=session_id,
            status=status,
            outcome=outcome,
            duration_s=duration_s,
        )
