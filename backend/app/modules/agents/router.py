"""Agent HTTP router."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.db import get_db
from backend.app.core.deps import (
    TokenClaims,
    get_current_tenant_id,
    require_roles,
)
from backend.app.core.errors import AppError
from backend.app.modules.agents.repository import AgentRepository
from backend.app.modules.agents.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    AgentVersionResponse,
)
from backend.app.modules.agents.service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    """Dependency provider returning an AgentService wired to the current DB session."""
    return AgentService(repository=AgentRepository(session=db))


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    org_id: str = Depends(get_current_tenant_id),
    service: AgentService = Depends(get_agent_service),
) -> list[AgentResponse]:
    """List all voice agents for the current organization."""
    return await service.list_agents(organization_id=org_id)


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreate,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    org_id: str = Depends(get_current_tenant_id),
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    """Create a new voice agent with initial version (owner and admin only)."""
    return await service.create_agent(
        organization_id=org_id,
        data=request,
        user_id=claims.user_id,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    """Get an agent by ID scoped to the authenticated organization."""
    agent = await service.get_agent(organization_id=org_id, agent_id=agent_id)
    if not agent:
        raise AppError(
            code="AGENT_NOT_FOUND",
            message="Agent not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    request: AgentUpdate,
    claims: TokenClaims = Depends(require_roles({"owner", "admin"})),
    org_id: str = Depends(get_current_tenant_id),
    service: AgentService = Depends(get_agent_service),
) -> AgentResponse:
    """Update agent metadata or bump to a new immutable version (owner and admin only)."""
    agent = await service.update_agent(
        organization_id=org_id,
        agent_id=agent_id,
        data=request,
        user_id=claims.user_id,
    )
    if not agent:
        raise AppError(
            code="AGENT_NOT_FOUND",
            message="Agent not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return agent


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
async def list_agent_versions(
    agent_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: AgentService = Depends(get_agent_service),
) -> list[AgentVersionResponse]:
    """List all version revisions for an agent."""
    agent = await service.get_agent(organization_id=org_id, agent_id=agent_id)
    if not agent:
        raise AppError(
            code="AGENT_NOT_FOUND",
            message="Agent not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return await service.list_versions(organization_id=org_id, agent_id=agent_id)


@router.get("/{agent_id}/versions/{version_id}", response_model=AgentVersionResponse)
async def get_agent_version(
    agent_id: str,
    version_id: str,
    org_id: str = Depends(get_current_tenant_id),
    service: AgentService = Depends(get_agent_service),
) -> AgentVersionResponse:
    """Retrieve a specific version of an agent."""
    version = await service.get_version(
        organization_id=org_id, agent_id=agent_id, version_id=version_id
    )
    if not version:
        raise AppError(
            code="AGENT_VERSION_NOT_FOUND",
            message="Agent version not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return version
