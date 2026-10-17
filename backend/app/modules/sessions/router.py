"""Sessions router."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.modules.sessions.schemas import (
    SessionListResponse,
    SessionResponse,
    WebSessionStartRequest,
    WebSessionStartResponse,
)
from backend.app.modules.sessions.service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_service() -> SessionService:
    """Dependency provider for SessionService."""
    return SessionService()


@router.post(
    "/web",
    response_model=WebSessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_web_session(
    request: WebSessionStartRequest,
    organization_id: str = "org-mock-1",
    service: SessionService = Depends(get_session_service),
) -> WebSessionStartResponse:
    """Start a new web browser test voice call session."""
    return await service.start_web_session(organization_id, request)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    organization_id: str = "org-mock-1",
    limit: int = 50,
    offset: int = 0,
    service: SessionService = Depends(get_session_service),
) -> SessionListResponse:
    """List sessions with call duration and recording references."""
    return await service.list_sessions(organization_id=organization_id, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    organization_id: str = "org-mock-1",
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Retrieve details for a specific session."""
    session = await service.get_session(organization_id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return session
