"""Sessions HTTP router."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.deps import get_current_tenant_id
from backend.app.core.errors import AppError
from backend.app.modules.agents import AgentRepository, AgentService
from backend.app.modules.sessions.repository import SessionRepository
from backend.app.modules.sessions.schemas import (
    RecordingUrlResponse,
    SessionListResponse,
    SessionMetricResponse,
    SessionResponse,
    TranscriptSegmentResponse,
    WebSessionStartRequest,
    WebSessionStartResponse,
)
from backend.app.modules.sessions.service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_service(db: AsyncSession = Depends(get_db)) -> SessionService:
    """Dependency provider returning SessionService wired with current DB session."""
    agent_service = AgentService(repository=AgentRepository(session=db))
    return SessionService(repository=SessionRepository(session=db), agent_service=agent_service)


@router.post("/web", response_model=WebSessionStartResponse, status_code=status.HTTP_201_CREATED)
async def start_web_session(
    request: WebSessionStartRequest,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> WebSessionStartResponse:
    """Initialize a browser WebRTC voice session and return LiveKit credentials."""
    return await service.start_web_session(organization_id=org_id, request=request)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    """List session call history scoped to the authenticated organization."""
    return await service.list_sessions(organization_id=org_id, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Fetch session details ensuring tenant isolation."""
    session = await service.get_session(organization_id=org_id, session_id=session_id)
    if not session:
        raise AppError(code="SESSION_NOT_FOUND", message="Session not found", status_code=404)
    return session


@router.get("/{session_id}/transcript", response_model=list[TranscriptSegmentResponse])
async def get_session_transcript(
    session_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> list[TranscriptSegmentResponse]:
    """Retrieve ordered transcript segments for a call."""
    return await service.get_transcript(organization_id=org_id, session_id=session_id)


@router.get("/{session_id}/metrics", response_model=SessionMetricResponse | None)
async def get_session_metrics(
    session_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> SessionMetricResponse | None:
    """Retrieve turn latency and token usage metrics for a call."""
    return await service.get_metrics(organization_id=org_id, session_id=session_id)


@router.get("/{session_id}/recording-url", response_model=RecordingUrlResponse)
async def get_recording_url(
    session_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: SessionService = Depends(get_session_service),
) -> RecordingUrlResponse:
    """Get a short-lived presigned URL to stream or download call audio recording."""
    return await service.get_recording_url(organization_id=org_id, session_id=session_id)
